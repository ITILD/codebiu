from module_authorization.do.token import TokenType
from datetime import datetime, timedelta, timezone
import jwt
from common.utils.security.token_util import TokenUtil, TokenConfig
from module_authorization.dao.token import TokenDao
from module_authorization.do.token import TokenCreate, TokenResponseBase
from module_authorization.config.token import token_config
from module_authorization.do.token import TokenCreateRequest
import logging

logger = logging.getLogger(__name__)


class TokenService:
    """令牌服务"""

    def __init__(self, token_dao: TokenDao):
        self.token_dao = token_dao
        # 初始化TokenUtil工具类(使用BaseModel配置类)
        self.token_util = TokenUtil(token_config)

    async def create_token(self, request: TokenCreateRequest) -> TokenResponseBase:
        """
        创建访问令牌和刷新令牌
        :param request: 令牌创建请求对象，包含user_id、username和additional_data
        :return: Token对象
        """
        token_id = None
        # 使用TokenUtil创建访问令牌
        token = self.token_util.create_token(
            user_id=request.user_id,
            token_type=request.token_type,
            additional_data=request.additional_data,
        )
        # 获取过期时间
        expires_at, expires_in = self.token_util.get_token_expiry(request.token_type)

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
        :raises jwt.JWTError: 令牌无效、过期或已被撤销
        """
        try:
            payload = self.token_util.verify_token(token)
            user_id = payload.get("sub")
            if not user_id:
                raise jwt.JWTError("Invalid token payload: missing 'sub'")

            # 刷新令牌必须检查数据库状态(是否被撤销)
            if token_type == TokenType.refresh:
                token_info = await self.token_dao.get_token_by_user_id(user_id)
                if not token_info or token_info.is_revoked:
                    raise jwt.JWTError("Token has been revoked")

            return payload

        except jwt.ExpiredSignatureError:
            # 过期刷新令牌自动撤销，仅抛出错误，由上层决定是否清理
            raise jwt.JWTError("Token has expired")

        except (jwt.InvalidTokenError, jwt.PyJWTError):
            raise jwt.JWTError("Invalid token")

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
        except jwt.JWTError as e:
            raise ValueError(f"Invalid refresh token: {str(e)}")

    async def revoke_token(self, token, token_id):
        """
        撤销令牌
        :param token: 要撤销的令牌
        :return: 撤销是否成功
        """
        # 验证并获取信息
        payload = await self.verify_token(token, token_type=TokenType.refresh)
        token_id = payload.get("token_id")
        if not token_id:
            raise ValueError("Invalid token payload: missing 'token_id'")
        return await self.token_dao.revoke_token_by_token_id(token_id)

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
