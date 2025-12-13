from pydantic import BaseModel, Field, SecretStr

# --------------------------
# 1. 定义 Pydantic 配置模型
# --------------------------
class EmailConfig(BaseModel):
    smtp_server: str = Field(default="smtp.qq.com", description="SMTP服务器地址")
    smtp_port: int = Field(default=465, description="SMTP端口(SSL)")
    sender_email: str = Field(..., description="发件人邮箱")
    sender_password: SecretStr = Field(..., description="SMTP授权码(敏感字段)")
    sender_name: str = Field(default="系统通知", description="发件人显示名称")

    class Config:
        json_encoders = {
            SecretStr: lambda v: v.get_secret_value() if v else None
        }
