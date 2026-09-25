"""邮箱配置冒烟测试: EmailSettings(动态配置) 字段与 EmailConfig 映射一致性(纯内存, 不触库)"""
from module_contact.do.email import EmailConfig
from common.config.dynamic.schemas import EmailSettings


def test_email_settings_maps_to_email_config():
    """EmailSettings 所有字段都能映射进 EmailConfig(防止动态配置字段漂移)"""
    cfg = EmailSettings()
    config = EmailConfig(
        smtp_server=cfg.smtp_server,
        smtp_port=cfg.smtp_port,
        sender_email=cfg.sender_email,
        sender_password=cfg.sender_password,
        sender_name=cfg.sender_name,
        use_for_register=cfg.use_for_register,
    )
    assert config.smtp_server == cfg.smtp_server
    assert config.smtp_port == cfg.smtp_port
    assert config.sender_email == cfg.sender_email
    assert config.sender_password.get_secret_value() == cfg.sender_password
    assert config.sender_name == cfg.sender_name
    assert config.use_for_register == cfg.use_for_register
