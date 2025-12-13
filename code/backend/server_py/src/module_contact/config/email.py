from module_contact.do.email import EmailConfig
# 从配置文件中读取email配置
from common.config.index import conf
import logging
logger = logging.getLogger(__name__)

email_config: EmailConfig = None
if conf.email:
    # 初始化配置
    email_config = EmailConfig(
        smtp_server=conf.email.smtp_server,
        smtp_port=conf.email.smtp_port,
        sender_email=conf.email.sender_email,
        sender_password=conf.email.sender_password,
        sender_name=conf.email.sender_name,
    )

