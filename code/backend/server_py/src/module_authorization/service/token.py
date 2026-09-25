from module_authorization.do.token import TokenType
from datetime import datetime, timedelta, timezone
import jwt
from common.utils.security.token_util import TokenUtil, TokenConfig
from module_authorization.dao.token import TokenDao
from module_authorization.do.token import TokenCreate, TokenResponseBase
from module_authorization.do.token import TokenCreateRequest
import logging

logger = logging.getLogger(__name__)


class TokenService:
    """令牌服务"""

    def __init__(self, token_dao: TokenDao):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.token_dao = token_dao or TokenDao()

    async def _token_util(self) -> TokenUtil:
        """按当前动态配置构建 TokenUtil(轻量对象, 每次构建; 配置中心变更即时生效)"""
        from common.config.dynamic import get_settings
        from common.config.dynamic.schemas import TokenSettings

        cfg = await get_settings(TokenSettings)
        return TokenUtil(
            TokenConfig(
                secret=cfg.secret_key,
                algorithm=cfg.algorithm,
                expire_minutes=cfg.expire_minutes,
                refresh_expire_days=cfg.refresh_expire_days,
            )
        )

    async def create_token(self, request: TokenCreateRequest) -> TokenResponseBase:
        """
        创建访问令牌和刷新令牌
        :param request: 令牌创建请求对象，包含user_id、username和additional_data
        :return: Token对象
        """
        token_id = None
        # 按当前动态配置构建工具(本次请求内复用同一实例)
        token_util = await self._token_util()
        # 使用TokenUtil创建访问令牌
        token = token_util.create_token(
            user_id=request.user_id,
            token_type=request.token_type,
            additional_data=request.additional_data,
        )
        # 获取过期时间
        expires_at, expires_in = token_util.get_token_expiry(request.token_type)

        # 只保存刷新令牌信息，访问令牌不保存
        if request.token_type == TokenType.refresh:
            token_info = TokenCreate(
                user_id=request.user_id,
                token=token,  # 这里存储的是刷新令牌
                token_type=request.token_type,
                expires_in=expires_in,
                expires_at=expires_at,
            )
            token_info = await self.token_dao.save_token(token_info)
            token_id = token_info.id
        # 返回访问令牌和过期时间
        token_response = TokenResponseBase(
            token=token, expires_in=expires_in, token_id=token_id
        )
        return token_response

    async def verify_token(
        self, token: str, token_type: TokenType = TokenType.access
    ) -> dict:
        """
        验证 JWT 令牌并检查其状态。
        :param token: 待验证的令牌字符串
        :param token_type: 令牌类型，必须为 access 或 refresh
        :return: 令牌载荷(用户ID等信息)
        :raises jwt.InvalidTokenError: 令牌无效、过期或已被撤销
        """
        try:
            payload = (await self._token_util()).verify_token(token)
            user_id = payload.get("sub")
            if not user_id:
                raise jwt.InvalidTokenError("Invalid token payload: missing 'sub'")

            # 刷新令牌必须检查数据库状态(是否被撤销)
            if token_type == TokenType.refresh:
                token_info = await self.token_dao.get_token_by_user_id(user_id)
                if not token_info or token_info.is_revoked:
                    raise jwt.InvalidTokenError("Token has been revoked")

            return payload

        except jwt.ExpiredSignatureError:
            # 过期刷新令牌自动撤销，仅抛出错误，由上层决定是否清理
            raise jwt.InvalidTokenError("Token has expired")

        except (jwt.InvalidTokenError, jwt.PyJWTError):
            raise jwt.InvalidTokenError("Invalid token")

    async def token_refresh(self, token_refresh):
        """
        使用刷新令牌获取新的访问令牌
        :param token_refresh: 刷新令牌
        :return: 新的Token对象
        """
        try:
            # 验证刷新令牌
            payload = await self.verify_token(
                token_refresh, token_type=TokenType.refresh
            )

            # 从载荷中获取用户信息
            user_id = payload.get("sub")

            # 创建TokenCreateRequest对象
            request = TokenCreateRequest(user_id=user_id)

            # 创建新的令牌对
            return await self.create_token(request)
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid refresh token: {str(e)}")

    async def revoke_token(self, token, token_id):
        """
        撤销刷新令牌
        :param token: 要撤销的刷新令牌(仅用于校验有效性,防止凭空吊销)
        :param token_id: 令牌存储记录ID(优先使用; JWT 载荷不含 token_id)
        :return: 撤销是否成功
        """
        # 校验刷新令牌有效性(无效/过期直接抛错)
        payload = await self.verify_token(token, token_type=TokenType.refresh)
        target_id = token_id or payload.get("token_id")
        if not target_id:
            raise ValueError("Invalid token: missing token_id")
        return await self.token_dao.revoke_token_by_token_id(target_id)

    async def revoke_all_tokens_by_user(self, user_id):
        """
        撤销用户的所有令牌
        :param user_id: 用户ID
        """
        await self.token_dao.delete_tokens_by_user_id(user_id)

    async def get_token_by_user_id(self, user_id):
        """
        通过用户ID获取令牌信息
        :param user_id: 用户ID
        :return: 刷新令牌信息
        """
        return await self.token_dao.get_token_by_user_id(user_id)
