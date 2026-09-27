//! contact —— 联系方式模块(对齐 Python module_contact)
//!
//! Python 侧 app.mount("/contact") 下没有任何路由, 仅暴露邮件发送服务
//! (EmailService 供 module_authorization 注册验证码等流程调用);
//! Rust 侧等价提供 email 服务函数, 无 HTTP 端点、无权限声明。

// 邮件内容/请求响应数据对象层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;
// 邮件发送业务逻辑层(对齐 Python service/)
pub mod services;
