from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request
import jwt
from pydantic import BaseModel
from enum import StrEnum


class TokenType(StrEnum):
    access = "access"
    refresh = "refresh"


class TokenConfig(BaseModel):
    """
    Token工具的配置类
    """

    secret: str
    algorithm: str = "HS256"
    expire_minutes: int = 30
    refresh_expire_days: int = 7


class TokenUtil:
    """
    尽量减少直接通过 API 请求发送用户密码的情况。一旦用户成功登录并获得访问令牌，
    后续请求可以使用这个令牌来进行身份验证，而不是每次都发送密码。
    前后端传输不考虑加密，https更好，数据库可以考虑。
    """

    def __init__(self, config: TokenConfig):
        """
        初始化 TokenUtil 实例。
        :param config: Token配置对象
        """
        self.SECRET_KEY = config.secret
        self.ALGORITHM = config.algorithm
        self.ACCESS_TOKEN_EXPIRE_MINUTES = config.expire_minutes
        self.REFRESH_TOKEN_EXPIRE_DAYS = config.refresh_expire_days
        # 加密 密码加密 Header和Payload部分分别进行Base64Url编码成消息字符串。
        # 使用指定的算法(例如HMAC SHA256)和密钥对消息字符串进行签名

    def data2token(self, data: dict) -> str:
        """
        创建一个带有过期时间的 JWT。
        :param data: 需要编码到 JWT 中的数据。
        :return: 编码后的 JWT 字符串。
        """
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        data.update({"exp": expire})
        # 加密
        encoded_jwt = jwt.encode(data, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    def token_request2data(self, request: Request):
        """
        解码 JWT 并返回数据。
        :param request: HTTP 请求对象。
        :return: 解码后的数据。
        :raises HTTPException: 如果无法验证凭据或 JWT 已过期。
        """
        # 从请求头中获取 Bearer 令牌
        authorization_header = request.headers.get("Authorization")
        if authorization_header is None:
            raise HTTPException(
                status_code=401,
                detail="Missing Authorization Header",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # 假设 Token 格式为 "Bearer <token>"
        token_type, _, token = authorization_header.partition(" ")
        if token_type != "Bearer":
            raise HTTPException(status_code=401, detail="无效的Token")
        try:
            # 解码 JWT  保证不被篡改
            data_decoded = jwt.decode(
                token, self.SECRET_KEY, algorithms=[self.ALGORITHM]
            )
            return data_decoded
        except jwt.exceptions.InvalidTokenError:
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.exceptions.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def update_token(self, old_request: Request):
        """
        更新 JWT 令牌。
        :param old_request: 包含旧 JWT 令牌的请求对象。
        :return: 新的 JWT 令牌。
        :raises HTTPException: 如果旧的 JWT 令牌无效或已过期。
        """
        try:
            # 验证旧的 JWT 令牌
            old_data = self.token_request2data(old_request)
            # 生成新的 JWT 令牌
            new_token = self.data2token(old_data)
            return new_token
        except HTTPException as e:
            raise e

    def create_token(self, user_id, token_type=TokenType.access, additional_data=None):
        """
        创建令牌
        :param user_id: 用户ID
        :param token_type: 令牌类型("access"或"refresh")
        :param additional_data: 额外数据字典
        :return: 令牌字符串
        """
        to_encode = {
            "sub": user_id,
            # iat 是一个重要的安全和管理字段，建议保留
            "iat": datetime.now(timezone.utc),
        }
        if token_type == TokenType.access:
            to_encode.update(
                {
                    "exp": datetime.now(timezone.utc)
                    + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
                }
            )
        else:
            to_encode.update(
                {
                    "exp": datetime.now(timezone.utc)
                    + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
                }
            )
        if additional_data:
            to_encode.update(additional_data)

        return jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)

    def verify_token(self, token: str):
        """
        验证令牌
        :param token: 要验证的令牌
        :return: 令牌中的载荷数据
        :raises: jwt.JWTError 如果令牌无效或过期
        """
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise jwt.JWTError("Token has expired")
        except jwt.InvalidTokenError:
            raise jwt.JWTError("Invalid token")

    def get_token_expiry(self, token_type=TokenType.access):
        """
        获取令牌过期时间
        :param token_type: 令牌类型("access"或"refresh")
        :return: 过期时间和过期秒数
        """
        now = datetime.now(timezone.utc)
        if token_type == TokenType.access:
            expires_at = now + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
            expires_in = self.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        else:
            # refresh token
            expires_at = now + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
            expires_in = self.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

        return expires_at, expires_in


# 示例用法
if __name__ == "__main__":
    import time

    # 加密算法
    algorithm = "HS256"
    # 加密密钥
    secret = "1111111"
    # 加密过期时间minutes
    expire = 30

    # 使用BaseModel配置类创建TokenUtil实例
    config = TokenConfig(secret=secret, algorithm=algorithm, expire_minutes=expire)
    token_util: TokenUtil = TokenUtil(config)

    # 创建 JWT
    data = {"sub": "test123"}
    encoded_jwt = token_util.data2token(data)
    print(f"Generated encoded_jwt: {encoded_jwt}")

    # 解码 JWT
    from fastapi import Request
    from starlette.requests import Request as StarletteRequest

    class MockRequest(StarletteRequest):
        headers = {"Authorization": f"Bearer {encoded_jwt}"}

    mock_request = MockRequest(scope={"type": "http"})
    try:
        decoded_data = token_util.token_request2data(mock_request)
        print(f"Decoded Data: {decoded_data}")
    except HTTPException as e:
        print(f"Error: {e.detail}")

    # 更新 JWT
    try:
        time.sleep(1)  # 等待一段时间以使令牌更新依赖时间戳不一致
        encoded_jwt_new = token_util.update_token(mock_request)
        print(f"Updated Token: {encoded_jwt_new}")

        print(f"token是否一致: {encoded_jwt == encoded_jwt_new}")
    except HTTPException as e:
        print(f"Error: {e.detail}")

    # 多对消息字符串和签名组可以提供更多数据点，但推导出SECRET_KEY仍然是极其困难的 较为安全
