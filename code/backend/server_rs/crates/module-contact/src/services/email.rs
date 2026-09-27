//! 邮件发送服务(对齐 Python module_contact/service/email.py + utils/contact/email.py)
//!
//! - 配置来源: 动态配置中心 "email" 组(common::config::dynamic::EmailSettings),
//!   每次发送按当前配置读取, 配置变更即时生效(等价 get_email_config)。
//! - 传输层: lettre SMTP 隐式 TLS(等价 aiosmtplib use_tls=True), 失败仅记日志并返回 false。
//! - 未配置授权码 → 400 业务错误(对齐 Python ValueError 全局处理器)。
//! - 邮件主题/正文模板等数据对象见 do/email.rs。

use std::time::Duration;

use common::runtime::AppState;
use common::config::dynamic::EmailSettings;
use common::utils::error::AppError;
use lettre::message::{header::ContentType, Mailbox};
use lettre::transport::smtp::authentication::Credentials;
use lettre::{AsyncSmtpTransport, AsyncTransport, Tokio1Executor};

use crate::do_::email::{build_register_code_content, REGISTER_CODE_SUBJECT};

/// 默认 SMTP 超时(秒, 对齐 Python send 默认参数 timeout=10)
const DEFAULT_TIMEOUT_SECS: i64 = 10;

/// 读取当前动态邮箱配置(每次调用构建, 配置中心变更即时生效)
pub async fn get_email_config(state: &AppState) -> Result<EmailSettings, AppError> {
    Ok(state.settings.get::<EmailSettings>("email").await?)
}

/// 异步发送邮件(对齐 EmailService.send + Email.asend)
///
/// :param receiver_email: 收件人邮箱
/// :param subject: 邮件主题
/// :param content: 邮件内容
/// :param receiver_name: 收件人名称(为空时用邮箱代替)
/// :param content_type: 内容类型(plain/html)
/// :param timeout_secs: SMTP超时时间(秒)
/// :return: 是否发送成功(SMTP 失败仅记录日志, 不抛错)
pub async fn send(
    state: &AppState,
    receiver_email: &str,
    subject: &str,
    content: &str,
    receiver_name: &str,
    content_type: &str,
    timeout_secs: i64,
) -> Result<bool, AppError> {
    let config = get_email_config(state).await?;
    if config.sender_password.is_empty() {
        // 对齐 Python: 未配置授权码抛 ValueError → 全局处理器返回 400
        return Err(AppError::business("未配置邮箱服务, 无法发送邮件"));
    }
    // 收件人名称为空时用邮箱代替
    let receiver_name = if receiver_name.is_empty() {
        receiver_email
    } else {
        receiver_name
    };
    match send_smtp(
        &config,
        receiver_email,
        receiver_name,
        subject,
        content,
        content_type,
        timeout_secs,
    )
    .await
    {
        Ok(()) => Ok(true),
        Err(e) => {
            tracing::error!("异步邮件发送失败: {e}");
            Ok(false)
        }
    }
}

/// SMTP 隐式 TLS 发送(等价 aiosmtplib use_tls=True)
async fn send_smtp(
    config: &EmailSettings,
    receiver_email: &str,
    receiver_name: &str,
    subject: &str,
    content: &str,
    content_type: &str,
    timeout_secs: i64,
) -> Result<(), AppError> {
    // Mailbox.email 为 lettre Address(实现 FromStr, 直接解析完整邮箱串)
    let from = Mailbox {
        name: Some(config.sender_name.clone()),
        email: config
            .sender_email
            .parse()
            .map_err(|e| AppError::business(format!("发件人邮箱无效: {e}")))?,
    };
    let to = Mailbox {
        name: Some(receiver_name.to_string()),
        email: receiver_email
            .parse()
            .map_err(|e| AppError::business(format!("收件人邮箱无效: {e}")))?,
    };
    let header = if content_type.eq_ignore_ascii_case("html") {
        ContentType::TEXT_HTML
    } else {
        ContentType::TEXT_PLAIN
    };
    let message = lettre::Message::builder()
        .from(from)
        .to(to)
        .subject(subject)
        .header(header)
        .body(content.to_string())
        .map_err(|e| AppError::Internal(format!("邮件构建失败: {e}")))?;
    // relay 返回 Builder(已设置隐式 TLS Wrapper, 等价 aiosmtplib use_tls=True),
    // 覆盖端口/凭据/超时后调用 build() 得到 Transport
    let mailer = AsyncSmtpTransport::<Tokio1Executor>::relay(&config.smtp_server)
        .map_err(|e| AppError::Internal(format!("SMTP 配置错误: {e}")))?
        .port(u16::try_from(config.smtp_port).unwrap_or(465))
        .credentials(Credentials::new(
            config.sender_email.clone(),
            config.sender_password.clone(),
        ))
        .timeout(Some(Duration::from_secs(timeout_secs.max(1) as u64)))
        .build();
    mailer
        .send(message)
        .await
        .map_err(|e| AppError::Internal(format!("SMTP 发送失败: {e}")))?;
    Ok(())
}

/// 发送注册邮箱验证码邮件(对齐 EmailService.send_register_code)
///
/// :param receiver_email: 收件人邮箱
/// :param code: 验证码
/// :param expire_minutes: 验证码有效期(分钟)
/// :return: 是否发送成功
pub async fn send_register_code(
    state: &AppState,
    receiver_email: &str,
    code: &str,
    expire_minutes: i64,
) -> Result<bool, AppError> {
    let content = build_register_code_content(code, expire_minutes);
    send(
        state,
        receiver_email,
        REGISTER_CODE_SUBJECT,
        &content,
        "",
        "html",
        DEFAULT_TIMEOUT_SECS,
    )
    .await
}
