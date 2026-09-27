//! 密码哈希(对齐 Python pwdlib[argon2])
//!
//! 兼容要点:
//! - Python pwdlib 产出 PHC 格式串: `$argon2id$v=19$m=19456,t=2,p=1$<salt>$<hash>`
//! - 验证时以哈希串内嵌的参数为准(argon2::PasswordVerifier 自动读取), 新旧互通
//! - 新增哈希使用 argon2 默认参数(OWASP 推荐 m=19456,t=2,p=1, 与 pwdlib 默认一致)
//! - 防御性支持历史 `$2b$` bcrypt 哈希(可选特性, 默认仅 argon2)

use argon2::password_hash::{rand_core::OsRng, PasswordHash, PasswordHasher, PasswordVerifier, SaltString};
use argon2::Argon2;

/// 哈希明文密码 → PHC 格式串(argon2id, 默认参数)
pub fn hash_password(plain: &str) -> Result<String, String> {
    let salt = SaltString::generate(&mut OsRng);
    Argon2::default()
        .hash_password(plain.as_bytes(), &salt)
        .map(|h| h.to_string())
        .map_err(|e| format!("密码哈希失败: {e}"))
}

/// 校验明文密码与 PHC 哈希串是否匹配
///
/// - argon2 哈希: 按 PHC 串内嵌参数验证(与 pwdlib 互通)
/// - bcrypt `$2b$` 前缀: 本版本不启用, 返回 false(历史数据迁移期由 Python 侧处理)
pub fn verify_password(plain: &str, hash: &str) -> bool {
    if hash.starts_with("$argon2") {
        let parsed = match PasswordHash::new(hash) {
            Ok(parsed) => parsed,
            Err(_) => return false,
        };
        Argon2::default()
            .verify_password(plain.as_bytes(), &parsed)
            .is_ok()
    } else {
        // 未知哈希格式(含 bcrypt): 不匹配
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 哈希后可验证通过() {
        let hash = hash_password("admin123").unwrap();
        assert!(hash.starts_with("$argon2id$"));
        assert!(verify_password("admin123", &hash));
        assert!(!verify_password("wrong", &hash));
    }

    #[test]
    fn 与pwdlib默认参数格式互通() {
        // pwdlib[argon2] 默认输出形如: $argon2id$v=19$m=19456,t=2,p=1$<b64salt>$<b64hash>
        // 构造一个同参数但哈希值随机的串验证解析路径(真实互通由契约测试覆盖)
        let hash = hash_password("x").unwrap();
        let parts: Vec<&str> = hash.split('$').collect();
        // parts: ["", "argon2id", "v=19", "m=19456,t=2,p=1", salt, hash]
        assert_eq!(parts[1], "argon2id");
        assert!(parts[3].contains("m=19456"));
        assert!(parts[3].contains("t=2"));
        assert!(parts[3].contains("p=1"));
    }

    #[test]
    fn 哈希串损坏时验证返回false() {
        assert!(!verify_password("x", "not-a-hash"));
        assert!(!verify_password("x", "$argon2id$broken"));
    }
}
