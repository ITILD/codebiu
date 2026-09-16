"""注册流程配置: 邮箱验证开关与验证码缓存策略"""
from module_contact.config.email import email_config

# 是否开启注册邮箱验证码(email.use_for_register; 未配置邮箱服务时恒为 False)
EMAIL_VERIFY_ENABLED: bool = bool(email_config and email_config.use_for_register)

# 验证码位数
REGISTER_CODE_LENGTH = 6
# 验证码有效期(秒)
REGISTER_CODE_TTL_SECONDS = 300
# 同一邮箱验证码发送间隔(秒), 防止频繁发送
REGISTER_CODE_COOLDOWN_SECONDS = 60

# 验证码缓存键(值: 验证码字符串)
REGISTER_CODE_KEY = "auth:register:code:{email}"
# 发送冷却缓存键(值: 固定标记)
REGISTER_CODE_COOLDOWN_KEY = "auth:register:code:cooldown:{email}"