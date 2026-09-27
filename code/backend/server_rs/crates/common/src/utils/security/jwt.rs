//! JWT 令牌工具(对齐 Python common/utils/security/token_util.py)
//!
//! 兼容要点:
//! - HS256 签名, claims 为 {sub, iat, exp}(PyJWT 默认将 iat/exp 序列化为整秒时间戳)
//! - 验证只校验签名与 exp, 不强制要求 sub/iat(与 PyJWT 默认行为一致, 老 token 兼容)
//! - access 过期分钟数 / refresh 过期天数由动态配置中心注入

use chrono::{Duration, Utc};
use jsonwebtoken::{decode, encode, Algorithm, DecodingKey, EncodingKey, Header, Validation};
use serde::{Deserialize, Serialize};
use serde_json::Value;

/// 令牌类型(与 Python TokenType StrEnum 对齐)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TokenType {
    Access,
    Refresh,
}

/// JWT 配置(来源: 动态配置中心 token 组)
#[derive(Debug, Clone)]
pub struct TokenConfig {
    pub secret: String,
    pub algorithm: String,
    pub expire_minutes: i64,
    pub refresh_expire_days: i64,
}

/// JWT 载荷(开放为 Value 以兼容 additional_data 透传)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    /// 用户ID
    pub sub: String,
    /// 签发时间(整秒时间戳, 与 PyJWT 一致)
    pub iat: i64,
    /// 过期时间(整秒时间戳)
    pub exp: i64,
    /// 附加数据(预留, 与 Python additional_data 对齐)
    #[serde(flatten)]
    pub extra: Value,
}

/// 创建令牌(返回编码后的 JWT 字符串)
///
/// - access: exp = now + expire_minutes 分钟
/// - refresh: exp = now + refresh_expire_days 天
/// - extra: 附加数据并入载荷(对齐 Python additional_data, 传 Null 表示无)
/// - 失败(如算法名不识别)返回 Err 文案
pub fn create_token(
    user_id: &str,
    token_type: TokenType,
    config: &TokenConfig,
    extra: Value,
) -> Result<String, String> {
    let now = Utc::now();
    let exp = match token_type {
        TokenType::Access => now + Duration::minutes(config.expire_minutes),
        TokenType::Refresh => now + Duration::days(config.refresh_expire_days),
    };
    let claims = Claims {
        sub: user_id.to_string(),
        iat: now.timestamp(),
        exp: exp.timestamp(),
        extra,
    };
    let header = build_header(&config.algorithm)?;
    encode(&header, &claims, &EncodingKey::from_secret(config.secret.as_bytes()))
        .map_err(|e| format!("令牌编码失败: {e}"))
}

/// 验证令牌(签名 + exp; 返回完整载荷)
pub fn verify_token(token: &str, config: &TokenConfig) -> Result<Claims, String> {
    let algorithm = parse_algorithm(&config.algorithm)?;
    let mut validation = Validation::new(algorithm);
    // 与 PyJWT 默认一致: 只要求 exp 可验证, 不强制 sub/iat 存在
    validation.required_spec_claims.clear();
    validation.validate_exp = true;
    decode::<Claims>(
        token,
        &DecodingKey::from_secret(config.secret.as_bytes()),
        &validation,
    )
    .map(|data| data.claims)
    .map_err(|e| match e.kind() {
        jsonwebtoken::errors::ErrorKind::ExpiredSignature => "Token has expired".to_string(),
        _ => "Invalid token".to_string(),
    })
}

/// 计算令牌过期信息: (expires_at, expires_in 秒)
pub fn token_expiry(token_type: TokenType, config: &TokenConfig) -> (chrono::DateTime<Utc>, i64) {
    match token_type {
        TokenType::Access => {
            let expires_at = Utc::now() + Duration::minutes(config.expire_minutes);
            (expires_at, config.expire_minutes * 60)
        }
        TokenType::Refresh => {
            let expires_at = Utc::now() + Duration::days(config.refresh_expire_days);
            (expires_at, config.refresh_expire_days * 24 * 60 * 60)
        }
    }
}

/// 算法名 → jsonwebtoken 算法枚举(仅支持与 Python 侧一致的 HS 系列)
fn parse_algorithm(name: &str) -> Result<Algorithm, String> {
    match name {
        "HS256" => Ok(Algorithm::HS256),
        "HS384" => Ok(Algorithm::HS384),
        "HS512" => Ok(Algorithm::HS512),
        other => Err(format!("不支持的签名算法: {other}")),
    }
}

fn build_header(algorithm: &str) -> Result<Header, String> {
    Ok(Header::new(parse_algorithm(algorithm)?))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn config() -> TokenConfig {
        TokenConfig {
            secret: "test123456789123456789123456789123456789".to_string(),
            algorithm: "HS256".to_string(),
            expire_minutes: 30,
            refresh_expire_days: 7,
        }
    }

    #[test]
    fn 创建并验证访问令牌() {
        let cfg = config();
        let token = create_token("user123", TokenType::Access, &cfg, Value::Null).unwrap();
        let claims = verify_token(&token, &cfg).unwrap();
        assert_eq!(claims.sub, "user123");
        // exp - iat ≈ 30 分钟
        assert_eq!(claims.exp - claims.iat, 30 * 60);
    }

    #[test]
    fn 刷新令牌过期时间为天() {
        let cfg = config();
        let token = create_token("u1", TokenType::Refresh, &cfg, Value::Null).unwrap();
        let claims = verify_token(&token, &cfg).unwrap();
        assert_eq!(claims.exp - claims.iat, 7 * 24 * 60 * 60);
    }

    #[test]
    fn 篡改令牌验证失败() {
        let cfg = config();
        let mut token = create_token("u1", TokenType::Access, &cfg, Value::Null).unwrap();
        token.push('x');
        let err = verify_token(&token, &cfg).unwrap_err();
        assert_eq!(err, "Invalid token");
    }

    #[test]
    fn 附加数据并入载荷() {
        let cfg = config();
        let extra = serde_json::json!({ "k": "v" });
        let token = create_token("u1", TokenType::Access, &cfg, extra).unwrap();
        let claims = verify_token(&token, &cfg).unwrap();
        assert_eq!(claims.extra["k"], "v");
    }

    #[test]
    #[allow(non_snake_case)]
    fn 与PythonPyJWT产物互通() {
        // PyJWT HS256 默认 header {"alg":"HS256","typ":"JWT"}, 验证本实现 header 与之一致
        // (Python 编码令牌的互通验证由契约测试覆盖)
        let cfg = config();
        let token = create_token("abc", TokenType::Access, &cfg, Value::Null).unwrap();
        let parts: Vec<&str> = token.split('.').collect();
        assert_eq!(parts.len(), 3);
        let header_bytes = b64url_decode(parts[0]);
        let header: serde_json::Value = serde_json::from_slice(&header_bytes).unwrap();
        assert_eq!(header["alg"], "HS256");
        assert_eq!(header["typ"], "JWT");
    }

    /// JWT base64url 解码(无填充, 与 RFC 7515 一致)
    fn b64url_decode(input: &str) -> Vec<u8> {
        use base64::Engine;
        base64::engine::general_purpose::URL_SAFE_NO_PAD
            .decode(input)
            .expect("base64 解码")
    }
}
