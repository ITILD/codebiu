from module_contact.service.email import EmailService

# 全局单例(邮件发送无状态, 复用同一实例)

_email_service = EmailService()


def get_email_service() -> EmailService:
    """获取邮件服务单例"""
    return _email_service