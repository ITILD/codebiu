//! 邮件内容数据对象(对齐 Python module_contact/do/email.py + config/email.py 模板部分)
//!
//! 存放邮件主题/正文模板等数据对象与纯构建函数; 发送逻辑在 services/email.rs。

/// 注册验证码邮件主题(对齐 REGISTER_CODE_SUBJECT)
pub const REGISTER_CODE_SUBJECT: &str = "注册邮箱验证码";

/// 注册验证码邮件正文模板(HTML, 对齐 REGISTER_CODE_TEMPLATE)
pub const REGISTER_CODE_TEMPLATE: &str = r#"<div style="font-family: sans-serif; font-size: 14px; color: #333;">
  <p>您正在注册账号, 本次验证码为:</p>
  <p style="font-size: 24px; font-weight: bold; letter-spacing: 4px;">{code}</p>
  <p>验证码 {expire_minutes} 分钟内有效, 请勿泄露给他人。</p>
</div>
"#;

/// 构建注册验证码邮件正文(纯函数, 便于测试)
pub fn build_register_code_content(code: &str, expire_minutes: i64) -> String {
    REGISTER_CODE_TEMPLATE
        .replace("{code}", code)
        .replace("{expire_minutes}", &expire_minutes.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_code_content_fills_placeholders() {
        let content = build_register_code_content("123456", 5);
        assert!(content.contains("123456"));
        assert!(content.contains("5 分钟内有效"));
        assert!(!content.contains("{code}"));
        assert!(!content.contains("{expire_minutes}"));
    }
}
