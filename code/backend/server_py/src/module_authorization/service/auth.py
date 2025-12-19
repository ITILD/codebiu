from common.utils.security.token_util import TokenType
from module_authorization.service.user import UserService
from module_authorization.service.token import TokenService
from module_authorization.do.user import UserCreate, UserResponse, User
from module_authorization.do.token import (
    TokenCreateRequest,
    TokenResponseFull,
)
from module_authorization.do.auth import AuthResponse, AuthLogoutRequest

# db_cache redis客户端 用于存储已吊销的 access_token 的黑名单
from common.config.db import db_cache 
from module_authorization.config.token import token_config

import logging

logger = logging.getLogger(__name__)


class AuthService:
    """认证服务"""

    def __init__(self, user_service: UserService, token_service: TokenService):
        """
        初始化认证服务
        :param user_service: 用户服务对象
        :param token_service: 令牌服务对象
        """
        self.user_service = user_service
        self.token_service = token_service

    async def register(self, user_create: UserCreate) -> AuthResponse:
        """
        用户注册
        :param user_create: 用户创建数据
        :return: 注册成功的用户信息
        :raises: ValueError 如果用户名已存在
        """
        user = await self.user_service.add(user_create)
        if not user:
            raise ValueError("用户创建失败")
        # 创建令牌响应
        return await self._create_token_response_full(user)

    async def login(self, username: str, password: str) -> AuthResponse:
        """
        用户登录
        :param username: 用户名
        :param password: 密码
        :return: 令牌响应
        :raises: ValueError 如果用户名或密码错误
        """
        # 验证用户凭据
        user = await self.user_service.authenticate(username, password)
        if not user:
            raise ValueError("用户名或密码错误")

        # 检查用户是否激活
        if not user.is_active:
            raise ValueError("用户账户已被禁用")

        # 创建令牌请求
        return await self._create_token_response_full(user)

    async def _create_token_response_full(self, user: User) -> AuthResponse:
        """
        创建令牌响应
        :param user: 用户对象
        :return: 令牌响应
        """
        token_access = await self.token_service.create_token(
            TokenCreateRequest(
                user_id=user.id,
                token_type=TokenType.access,
            )
        )
        token_refresh = await self.token_service.create_token(
            TokenCreateRequest(
                user_id=user.id,
                token_type=TokenType.refresh,
            )
        )
        return AuthResponse(
            tokens=TokenResponseFull(
                access=token_access,
                refresh=token_refresh,
            ),
            user=UserResponse.model_validate(user),
        )

    async def logout(self, logout_request: AuthLogoutRequest) -> bool:
        """
        用户登出
        :param logout_request: 登出请求
        :return: 登出是否成功
        """
        try:
            # 验证访问令牌有效性 无效会抛错
            await self.verify_token(logout_request.token_access)
            # logger.info(f"用户 {user_id} 登出成功")
        except Exception:
            logger.info(f"访问令牌无效: {logout_request.token_access}")
            # 防止重复登出
            raise ValueError("访问令牌无效")
        try:
            # 对于安全性要求较高的系统，采用黑名单/废止列表来使 access_token 立即失效
            await db_cache .set(
                logout_request.token_access,
                "revoked",
                ex=token_config.expire_minutes * 60,
            )
            # 撤销刷新令牌
            await self.token_service.revoke_token(
                logout_request.token_refresh,
                logout_request.token_refresh_id,
            )
        except Exception:
            # 刷新令牌无效，继续执行登出逻辑
            logger.info(f"刷新令牌无效: {logout_request.token_access}")
        return True

    async def verify_token(self, token_access: str) -> dict:
        """
        验证访问令牌
        :param token_access: 访问令牌
        :return: 令牌载荷数据
        :raises: ValueError 如果令牌无效
        """
        try:
            # 黑名单 检查令牌是否已被吊销
            revoked = await db_cache .get(token_access)
            # 查看所有async_redis内的键值对
            logger.info(f"db_cache  内的键值对: {await db_cache .keys()}")
            if revoked == b"revoked":
                raise ValueError("令牌已被吊销")
            return await self.token_service.verify_token(token_access)
        except Exception as e:
            raise ValueError(f"令牌验证失败: {str(e)}")

    async def revoke_all_user_tokens(self, user_id: str) -> bool:
        """
        撤销用户的所有令牌
        :param user_id: 用户ID
        :return: 操作是否成功
        """
        try:
            await self.token_service.revoke_all_tokens_by_user(user_id)
            return True
        except Exception:
            return False

    async def get_current_user_id(self, token: str) -> str:
        """
        获取当前用户ID
        :param token: 访问令牌
        :return: 当前用户ID
        :raises: ValueError 如果令牌无效
        """
        try:
            # 验证令牌有效性
            payload = await self.verify_token(token)
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError("令牌中缺少用户ID")
            return user_id
        except Exception as e:
            raise ValueError(f"获取当前用户ID失败: {str(e)}")

    async def get_current_user(self, token: str) -> User:
        """
        获取当前用户
        :param token: 访问令牌
        :return: 当前用户
        :raises: ValueError 如果令牌无效
        """
        try:
            user_id = await self.get_current_user_id(token)
            return await self.user_service.get(user_id)
        except Exception as e:
            raise ValueError(f"获取当前用户失败: {str(e)}")

    async def token_refresh(self, token_refresh: str) -> TokenResponseFull:
        """
        刷新访问令牌
        :param token_refresh: 刷新令牌
        :return: 新的令牌响应
        :raises: ValueError 如果刷新令牌无效
        """
        # 验证刷新令牌有效性
        payload = await self.token_service.verify_token(token_refresh, TokenType.refresh)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("刷新令牌中缺少用户ID")
        # 验证刷新令牌 获取用户信息
        user = await self.user_service.get(user_id)

        # 检查用户是否激活
        if not user.is_active:
            raise ValueError("用户账户已被禁用")

        # 创建新的令牌请求
        token_request = TokenCreateRequest(
            user_id=user.id,
            token_type=TokenType.access,
        )
        # 生成新令牌
        new_token = await self.token_service.create_token(token_request)
        return new_token
