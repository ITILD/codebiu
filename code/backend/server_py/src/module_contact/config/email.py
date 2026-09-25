"""邮箱配置(动态): import 期零副作用, 消费点经 get_email_config() 按调用时读取"""
from common.config.dynamic import get_settings
from common.config.dynamic.schemas import EmailSettings
from module_contact.do.email import EmailConfig


async def get_email_config() -> EmailConfig:
    """构建 EmailConfig(按当前动态配置; 每次调用构建, 配置中心变更即时生效)"""
    cfg = await get_settings(EmailSettings)
    return EmailConfig(
        smtp_server=cfg.smtp_server,
        smtp_port=cfg.smtp_port,
        sender_email=cfg.sender_email,
        sender_password=cfg.sender_password,
        sender_name=cfg.sender_name,
        use_for_register=cfg.use_for_register,
    )
