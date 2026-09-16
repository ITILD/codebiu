// 性别枚举
export enum GenderEnum {
  BOY = 'boy',
  GIRL = 'girl',
  UNKNOWN = 'unknown'
}

// 名字风格枚举
export enum NameStyleEnum {
  TRADITIONAL = 'traditional', // 传统
  MODERN = 'modern', // 现代
  LITERARY = 'literary', // 文艺
  SIMPLE = 'simple', // 简约
  UNIQUE = 'unique' // 独特
}

// 宝宝基本信息
export interface NameInfoBase {
  birth_date: string // 出生日期，考虑农历描述
  birth_time: string // 出生时间，考虑时辰描述
  gender: GenderEnum // 性别
  surname: string // 姓
}

// 宝宝额外信息
export interface NameInfoEX {
  name_length?: number // 名字长度
  other?: string // 补充信息，如首选发音、禁止字符、特殊字符、数字、风格、含义等
}

// 用于推测姓名信息的完整模型
export interface NameInfoPredictFull extends NameInfoBase, NameInfoEX {
}

// 推测姓名信息的完整请求模型
export interface NameInfoPredictFullRequest extends NameInfoPredictFull {
  model_id: string // 模型 ID
}

// 五行和星座偏好
export interface NameInfoPreference {
  wuxing_preference: string[] // 五行偏好，结合 name_length 按顺序每个字的属性，可以多个
  constellation_preference: string[] // 星座偏好
}

// 完整的宝宝信息（包含偏好）
export interface NameInfoFull extends NameInfoBase, NameInfoEX, NameInfoPreference {
}

// 推测结果基础
export interface NameInfoResultBase {
  name: string // 宝宝完整名字
}

// 名字解释
export interface NameInfoResultExplanation {
  explanation_wuxing: string // 名字的五行解释
  explanation_constellation: string // 名字的星座解释
  explanation_meaning: string // 名字的寓意解释
}

export interface NameInfoResponse {
  explanation_wuxing: string // 名字的五行解释
  explanation_constellation: string // 名字的星座解释
  explanation_meaning_list:string// 名字的寓意解释列表
}

// 推测结果和解释
export interface NameInfoResult extends NameInfoResultBase, NameInfoResultExplanation {
}

// 推测结果列表
export interface NameInfoResultList {
  results: NameInfoResult[] // 推测结果列表
}

// ==================== 参考体系(民俗/神话) ====================

/** 参考体系标识(与后端 ReferenceEnum 一一对应) */
export type ReferenceKey =
  | 'wuxing' // 五行八字
  | 'sancai' // 三才五格
  | 'constellation' // 星座
  | 'zodiac' // 生肖
  | 'tarot' // 塔罗牌
  | 'christian' // 基督
  | 'buddhism' // 佛教
  | 'taoism' // 道教

/** 参考体系目录项(供多选卡片渲染) */
export interface FolkReferenceItem {
  key: ReferenceKey
  label: string // 名称, 如 五行八字
  icon: string // 展示图标(emoji)
  desc: string // 一句话说明
  strict: boolean // 是否有经典程序化计算(false 为文化风格类)
}

/** 单柱干支信息 */
export interface FourPillarInfo {
  label: string // 柱名(年柱/月柱/日柱/时柱)
  ganzhi: string // 干支, 如 丙午
  wuxing: string // 干支五行, 如 火火
}

/** 五行八字推算结果 */
export interface WuxingInfo {
  pillars: FourPillarInfo[]
  counts: Record<string, number> // 五行个数 {金木水火土}
  canggan: { pillar: string; branch: string; hidden: string }[] // 地支藏干明细
  day_master: string // 日主五行
  strength: string // 日主强弱(身强/身弱)
  favorable: string[] // 喜用五行(按优先级)
  summary: string // 一句话总结
}

/** 星座推算结果 */
export interface ConstellationInfo {
  name: string
  date_range: string
  element: string // 四大元素(火土风水)
  traits: string
  summary: string
}

/** 生肖推算结果 */
export interface ZodiacInfo {
  name: string
  year_ganzhi: string // 年柱干支(立春分界)
  favorable_chars: string // 传统宜用字根提示
  summary: string
}

/** 塔罗牌推算结果 */
export interface TarotInfo {
  number: number // 生命灵数
  card: string // 生命塔罗牌名
  meaning: string // 牌意
  summary: string
}

/** 姓氏三才五格基准(推测阶段仅姓氏可算天格基准) */
export interface SancaiBaseInfo {
  surname_strokes: Record<string, number> // 姓氏各字康熙笔画
  estimated_chars: string[] // 笔画为估计值的字
  tian_ge: number
  note: string
}

/** 佛教本命佛推算结果(按生肖取守护佛) */
export interface BuddhismInfo {
  zodiac: string // 生肖(立春分界)
  buddha: string // 本命佛名
  meaning: string // 本命佛寓意
  hint_chars: string // 佛家意趣宜用字
  summary: string
}

/** 道教本命太岁推算结果(按年柱干支取值年太岁) */
export interface TaoismInfo {
  year_ganzhi: string // 年柱干支(立春分界)
  taishi: string // 本命太岁星君
  meaning: string // 太岁文化寓意
  hint_chars: string // 道家意趣宜用字
  summary: string
}

/** 基督圣经意象推算结果(按出生季节取主题经文) */
export interface ChristianInfo {
  season: string // 出生季节(春夏秋冬)
  theme: string // 圣经主题意象
  verse: string // 对应经文(含出处)
  hint_chars: string // 祝福意趣宜用字
  summary: string
}

/** 参考体系推算请求 */
export interface ReferenceCalculateRequest extends NameInfoBase {
  references: ReferenceKey[] // 要推算的参考体系(strict 项才参与计算)
}

/** 参考体系推算结果(按选择返回对应子对象, 未选为 null) */
export interface ReferenceCalculateResult {
  wuxing: WuxingInfo | null
  constellation: ConstellationInfo | null
  zodiac: ZodiacInfo | null
  tarot: TarotInfo | null
  sancai: SancaiBaseInfo | null
  buddhism: BuddhismInfo | null // 佛教本命佛结果
  taoism: TaoismInfo | null // 道教本命太岁结果
  christian: ChristianInfo | null // 基督圣经意象结果
}

/** 单个名字的三才五格评分 */
export interface SancaiScore {
  strokes: number[] // 每个字康熙笔画(姓+名)
  estimated_chars: string[] // 笔画为估计值的字
  tian_ge: number
  ren_ge: number
  di_ge: number
  wai_ge: number
  zong_ge: number
  sancai: string // 三才配置, 如 木火土
  grid_lucks: Record<string, string> // 各格吉凶
  score: number // 评分 0-100
}

/** 生成后经程序评定的名字 */
export interface EvaluatedName {
  name: string // 宝宝完整名字(含姓)
  meaning: string // 名字寓意
  sancai: SancaiScore | null // 三才五格评定(选择三才参考时)
  score: number // 综合评分 0-100
}

/** 起名生成请求(流式) */
export interface BabyNameGenerateRequest extends NameInfoPredictFullRequest {
  references: ReferenceKey[] // 参考的民俗/神话体系(多选)
  count: number // 本次生成数量(默认 20)
  exclude_names: string[] // 需避开的历史名字("生成更多"防重复)
}
