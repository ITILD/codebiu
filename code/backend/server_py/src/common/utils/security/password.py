from pwdlib import PasswordHash

# 全局创建一次，安全且高效
_password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
    """对密码进行哈希"""
    return _password_hash.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    return _password_hash.verify(password, hashed)