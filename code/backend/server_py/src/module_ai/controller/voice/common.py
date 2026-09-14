"""语音控制器辅助工具"""
import logging

from module_ai.do.voice import VoiceEngine, normalize_engine

logger = logging.getLogger(__name__)


def resolve_engine(raw: str | None) -> VoiceEngine | None:
    """解析 engine 参数并归一化为新方案(online/local)

    - 空/None 返回 None, 由模型配置自动选择
    - 旧值兼容: dashscope->online, sherpa/qwen->local
    - 无效值回落 LOCAL(本地方案零外部依赖, 最稳)
    """
    engine = normalize_engine(raw)
    if engine is None and raw and raw.strip():
        return VoiceEngine.LOCAL
    return engine


async def ws_user_id(token: str | None) -> str | None:
    """WS 连接 query 参数 token -> 用户ID(可选登录; 缺失/无效按匿名处理走全局配置)"""
    if not token:
        return None
    try:
        # 延迟导入避免模块加载期耦合
        from module_authorization.dao.token import TokenDao
        from module_authorization.dao.user import UserDao
        from module_authorization.service.auth import AuthService
        from module_authorization.service.token import TokenService
        from module_authorization.service.user import UserService

        auth = AuthService(UserService(UserDao()), TokenService(TokenDao()))
        return await auth.get_current_user_id(token)
    except Exception as e:
        logger.warning(f"WS 连接令牌解析失败, 按匿名处理: {e}")
        return None
