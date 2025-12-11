import asyncio
import smtplib
import aiosmtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from module_contact.do.email import EmailConfig
class Email():
    # --------------------------
    # 异步邮件发送函数
    # --------------------------
    async def asend(
        config: EmailConfig,
        receiver_email: str,
        receiver_name: str,
        subject: str,
        content: str,
        content_type: str = "plain",
        timeout: int = 10,
    ) -> bool:
        """
        异步发送邮件
        :param config: EmailConfig 配置对象
        :param receiver_email: 收件人邮箱
        :param receiver_name: 收件人名称
        :param subject: 邮件主题
        :param content: 邮件内容
        :param content_type: 内容类型(plain/html)
        :param timeout: SMTP超时时间(秒)
        :return: 是否发送成功
        """
        msg = MIMEText(content, content_type, "utf-8")
        msg["From"] = formataddr((config.sender_name, config.sender_email))
        msg["To"] = formataddr((receiver_name, receiver_email))
        msg["Subject"] = subject

        try:
            # 异步SMTP连接
            await aiosmtplib.send(
                msg,
                hostname=config.smtp_server,
                port=config.smtp_port,
                username=config.sender_email,
                password=config.sender_password.get_secret_value(),
                use_tls=True,
                timeout=timeout,
            )
            return True
        except Exception as e:
            print(f"异步邮件发送失败: {e}")
            return False

    # --------------------------
    # 同步邮件发送函数(保留原有实现)
    # --------------------------
    def send(
        config: EmailConfig,
        receiver_email: str,
        receiver_name: str,
        subject: str,
        content: str,
        content_type: str = "plain",
    ) -> bool:
        """同步发送邮件(原有代码不变)"""
        msg = MIMEText(content, content_type, "utf-8")
        msg["From"] = formataddr((config.sender_name, config.sender_email))
        msg["To"] = formataddr((receiver_name, receiver_email))
        msg["Subject"] = subject

        try:
            with smtplib.SMTP_SSL(config.smtp_server, config.smtp_port) as server:
                server.login(
                    config.sender_email,
                    config.sender_password.get_secret_value()
                )
                server.sendmail(config.sender_email, [receiver_email], msg.as_string())
            return True
        except Exception as e:
            print(f"同步邮件发送失败: {e}")
            return False
