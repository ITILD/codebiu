# self
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)
from module_life.do.baby_name import (
    BabyName,
    BabyNameCreate,
    BabyNameUpdate,
    BabyNameBatchDelete,
)
from module_life.utils.baby_name.do.baby_name import (
    NameInfoBase,
    NameInfoFull,
    NameInfoResultList,
    NameInfoResult,
    NameInfoPreference,
    NameInfoResultExplanation,
    NameInfoResultBase,
    NameInfoEX,
    NameInfoPredictFull,
    ReferenceCalculateRequest,
    ReferenceCalculateResult,
    WuxingInfo,
    ConstellationInfo,
    ZodiacInfo,
    TarotInfo,
    SancaiBaseInfo,
    FourPillarInfo,
    BabyNameGenerateRequest,
    BuddhismInfo,
    TaoismInfo,
    ChristianInfo,
)
from module_life.dao.baby_name import BabyNameDao
from module_ai.service.llm import LLMService
from module_ai.utils.llm.chat.think import with_think_mode
from common.utils.fastapiEX.exceptions import BusinessError
# lib
from module_life.utils.baby_name.almanac import (
    GAN,
    GAN_WUXING_MAP,
    ZHI,
    ZHI_WUXING_MAP,
    ZODIAC_HINTS,
    year_pillar,
    get_four_pillars,
)
from module_life.utils.baby_name.constellation import get_constellation
from module_life.utils.baby_name.folklore import FOLK_REFERENCES, ReferenceEnum, get_reference_catalog
from module_life.utils.baby_name.sancai import evaluate_name
from module_life.utils.baby_name.strokes import stroke_of
from module_life.utils.baby_name.tarot import get_tarot
from module_life.utils.baby_name.wuxing import analyze_wuxing
from module_life.utils.baby_name.baby_name import baby_name_generator
from module_life.utils.baby_name.religion import (
    get_benming_buddha,
    get_christian_theme,
    get_taishi,
)
import datetime as dt

class BabyNameService:
    """宝宝名字服务"""

    def __init__(self, baby_name_dao: BabyNameDao, llm_service: LLMService):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.baby_name_dao = baby_name_dao or BabyNameDao()
        self.llm_service = llm_service or LLMService()

    # ==================== 参考体系推算(经典严格算法, 纯程序计算) ====================

    async def calculate_reference(self, request: ReferenceCalculateRequest) -> ReferenceCalculateResult:
        """按选中的参考体系做严格程序推算(五行/星座/生肖/塔罗/姓氏五格基准)

        :param request: 宝宝天生信息 + 参考体系列表
        :return: 各参考体系推算结果(未选为 None)
        """
        result = ReferenceCalculateResult()
        refs = set(request.references)
        if ReferenceEnum.WUXING in refs:
            w = analyze_wuxing(request.birth_date, request.birth_time)
            pillars = get_four_pillars(request.birth_date, request.birth_time)
            result.wuxing = WuxingInfo(
                pillars=[
                    FourPillarInfo(
                        label=label,
                        ganzhi=name,
                        wuxing=GAN_WUXING_MAP[name[0]] + ZHI_WUXING_MAP[name[1]],
                    )
                    for label, name in zip(w["pillar_labels"], w["pillar_names"])
                ],
                counts=w["counts"],
                canggan=w["canggan"],
                day_master=w["day_master"],
                strength=w["strength"],
                favorable=w["favorable"],
                summary=w["summary"],
            )
        if ReferenceEnum.CONSTELLATION in refs:
            c = get_constellation(request.birth_date)
            result.constellation = ConstellationInfo(
                name=c.name,
                date_range=c.date_range,
                element=c.element,
                traits=c.traits,
                summary=c.summary(),
            )
        if ReferenceEnum.ZODIAC in refs:
            zodiac = get_zodiac_name(request.birth_date)
            y_gan, y_zhi = year_pillar(dt.date.fromisoformat(request.birth_date))
            result.zodiac = ZodiacInfo(
                name=zodiac,
                year_ganzhi=GAN[y_gan] + ZHI[y_zhi],
                favorable_chars=ZODIAC_HINTS.get(zodiac, ""),
                summary=f"生肖{zodiac}。{ZODIAC_HINTS.get(zodiac, '')}",
            )
        if ReferenceEnum.TAROT in refs:
            t = get_tarot(request.birth_date)
            result.tarot = TarotInfo(
                number=t["number"], card=t["card"], meaning=t["meaning"], summary=t["summary"]
            )
        if ReferenceEnum.SANCAI in refs:
            strokes: dict[str, int] = {}
            estimated: list[str] = []
            for ch in request.surname:
                n, exact = stroke_of(ch)
                strokes[ch] = n
                if not exact:
                    estimated.append(ch)
            tian = sum(strokes.values()) + (1 if len(request.surname) == 1 else 0)
            result.sancai = SancaiBaseInfo(
                surname_strokes=strokes,
                estimated_chars=estimated,
                tian_ge=tian,
                note="天格由姓氏决定; 完整五格需待名字生成后逐个评定",
            )
        if ReferenceEnum.BUDDHISM in refs:
            b = get_benming_buddha(request.birth_date)
            result.buddhism = BuddhismInfo(**b)
        if ReferenceEnum.TAOISM in refs:
            t = get_taishi(request.birth_date)
            result.taoism = TaoismInfo(**t)
        if ReferenceEnum.CHRISTIAN in refs:
            c = get_christian_theme(request.birth_date)
            result.christian = ChristianInfo(**c)
        return result

    async def get_reference_catalog(self) -> list[dict]:
        """参考体系目录(供前端多选卡片)"""
        return get_reference_catalog()

    # ==================== AI 起名(流式) ====================

    async def generate_names_stream(self, request: BabyNameGenerateRequest, model_id: str = ""):
        """按参考体系配置流式起名(严格计算节点 + LLM 生成 + 程序评定)

        :param request: 宝宝信息+参考配置+数量+排除名单
        :param model_id: LLM 模型ID(留空自动使用默认公共 chat 模型)
        :return: SSE 事件流
        """
        model = await self.llm_service.get_llm(model_id) if model_id else None
        if model is None:
            # 未指定模型(或配置不可用): 兜底默认公共 chat 模型, 用户无需手选即可起名
            from module_ai.dao.model_config import ModelConfigDao

            default_config = await ModelConfigDao().get_default_by_type("chat", active_only=True)
            if not default_config:
                raise BusinessError("未找到可用的默认 chat 模型, 请先在模型配置中添加并设为默认")
            model = await self.llm_service.get_llm(default_config.id)
        if model is None:
            raise BusinessError("起名模型不可用, 请检查模型配置是否停用")
        # 按请求的思考模式调整模型(始终思考模型关闭被拒时由请求层自动回退开启)
        model = with_think_mode(model, request.think_mode)
        return baby_name_generator.generate_stream(request, model)

    async def predict_baby_info_base_by_ai(
        self, name_info_predict_full: NameInfoPredictFull, model_id: str
    ) -> NameInfoResultList:
        """根据宝宝全部基础信息推测宝宝名字(兼容旧端点, 默认参考五行+星座)

        :param name_info_predict_full: 姓名信息基础数据
        :return: SSE 事件流
        """
        model = await self.llm_service.get_llm(model_id)
        return baby_name_generator.generate_stream(name_info_predict_full, model)

    async def predict_name_info_preference_by_ai(
        self, name_info_base: NameInfoBase
    ) -> NameInfoPreference:
        """根据宝宝天生信息推测偏好(严格程序计算: 五行喜用+星座)

        :param name_info_base: 宝宝天生信息
        :return: 偏好信息
        """
        w = analyze_wuxing(name_info_base.birth_date, name_info_base.birth_time)
        c = get_constellation(name_info_base.birth_date)
        return NameInfoPreference(
            wuxing_preference=w["favorable"],
            constellation_preference=[c.name],
        )

    async def predict_name_by_ai(
        self, name_info_base: NameInfoBase
    ) -> NameInfoResultList:
        """
        根据宝宝全部基础信息推测宝宝名字
        :param name_info_base: 姓名信息基础数据
        :return: 推测结果列表
        """
        # 保留桩实现: 非流式端点, 完整起名请走 /generate 流式接口
        return NameInfoResultList(results=[])

    async def evaluate_name_explanation(
        self, surname: str, given: str
    ) -> dict:
        """程序评定单个名字的三才五格(供反推寓意端点扩展使用)"""
        return {"sancai": evaluate_name(surname, given)}

    async def predict_name_explanation_by_ai(
        self, name_info_result_base: NameInfoResultBase
    ) -> NameInfoResultExplanation:
        """
        根据姓名信息推测宝宝名字的偏好信息和寓意
        :param name_info_result_base: 姓名基础信息
        :return: 推测的解释
        """
        # 保留桩实现: 结构化解释暂未开放
        return NameInfoResultExplanation()

    async def add(self, baby_name: BabyNameCreate) -> str:
        """
        添加新的宝宝名字
        :param baby_name: 宝宝名字创建数据
        :return: 创建的名字ID
        """
        return await self.baby_name_dao.add(baby_name)

    async def delete(self, id: str):
        """
        删除宝宝名字
        :param id: 名字ID
        """
        await self.baby_name_dao.delete(id)

    async def batch_delete(self, batch_delete: BabyNameBatchDelete) -> int:
        """
        批量删除宝宝名字
        :param batch_delete: 批量删除请求
        :return: 删除的记录数
        """
        return await self.baby_name_dao.batch_delete(batch_delete)

    async def update(self, name_id: str, baby_name: BabyNameUpdate):
        """
        更新宝宝名字信息
        :param name_id: 名字ID
        :param baby_name: 更新数据
        """
        await self.baby_name_dao.update(name_id, baby_name)

    async def get(self, id: str) -> BabyName | None:
        """
        获取单个宝宝名字
        :param id: 名字ID
        :return: 宝宝名字信息或None
        """
        return await self.baby_name_dao.get(id)

    async def list_paged(self, pagination: PaginationParams):
        """
        获取宝宝名字列表
        :param pagination: 分页参数
        :return: 分页响应数据
        """
        items = await self.baby_name_dao.list_paged(pagination)
        total = await self.baby_name_dao.count()
        return PaginationResponse.create(items, total, pagination)

    async def get_scroll(self, params: InfiniteScrollParams):
        """
        滚动加载宝宝名字列表
        :param params: 滚动参数
        :return: 滚动响应数据
        """
        items: list[BabyName] = await self.baby_name_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)


def get_zodiac_name(birth_date: str) -> str:
    """生肖名(立春分界)"""
    from module_life.utils.baby_name.almanac import get_zodiac

    return get_zodiac(birth_date)
