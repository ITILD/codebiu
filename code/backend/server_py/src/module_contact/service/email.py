"""邮件服务: 对外统一暴露邮件发送能力, 供其他模块(如注册验证)调用"""
import logging

from module_contact.config.email import email_config
from module_contact.do.email import EmailConfig
from module_contact.utils.contact.email import Email

logger = logging.getLogger(__name__)

# 注册验证码邮件主题
REGISTER_CODE_SUBJECT = "注册邮箱验证码"

# 注册验证码邮件正文模板(HTML)
REGISTER_CODE_TEMPLATE = """
<div style="font-family: sans-serif; font-size: 14px; color: #333;">
  <p>您正在注册账号, 本次验证码为:</p>
  <p style="font-size: 24px; font-weight: bold; letter-spacing: 4px;">{code}</p>
  <p>验证码 {expire_minutes} 分钟内有效, 请勿泄露给他人。</p>
</div>
"""


class EmailService:
    """邮件服务: 基于 module_contact 的邮件配置发送外部邮件"""

    def __init__(self, config: EmailConfig | None = None, sender: Email | None = None):
        """
        依赖注入构造器
        :param config: 邮件配置(默认取模块全局配置)
        :param sender: 邮件发送实现
        """
        self.config = config if config is not None else email_config
        self.sender = sender or Email()

    async def send(
        self,
        receiver_email: str,
        subject: str,
        content: str,
        receiver_name: str = "",
        content_type: str = "plain",
        timeout: int = 10,
    ) -> bool:
        """
        异步发送邮件
        :param receiver_email: 收件人邮箱
        :param subject: 邮件主题
        :param content: 邮件内容
        :param receiver_name: 收件人名称(为空时用邮箱代替)
        :param content_type: 内容类型(plain/html)
        :param timeout: SMTP超时时间(秒)
        :return: 是否发送成功
        :raises ValueError: 未配置邮箱服务
        """
        if not self.config:
            raise ValueError("未配置邮箱服务, 无法发送邮件")
        return await self.sender.asend(
            self.config,
            receiver_email,
            receiver_name or receiver_email,
            subject,
            content,
            content_type=content_type,
            timeout=timeout,
        )

    async def send_register_code(
        self, receiver_email: str, code: str, expire_minutes: int
    ) -> bool:
        """
        发送注册邮箱验证码邮件
        :param receiver_email: 收件人邮箱
        :param code: 验证码
        :param expire_minutes: 验证码有效期(分钟)
        :return: 是否发送成功
        :raises ValueError: 未配置邮箱服务
        """
        content = REGISTER_CODE_TEMPLATE.format(
            code=code, expire_minutes=expire_minutes
        )
        return await self.send(
            receiver_email,
            REGISTER_CODE_SUBJECT,
            content,
            content_type="html",
        )