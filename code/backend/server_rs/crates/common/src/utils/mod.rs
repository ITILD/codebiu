//! utils —— 公共工具子包(对齐 Python src/common/utils)
//!
//! - error.rs       统一错误体系(对应 utils/fastapiEX/exceptions.py)
//! - extract.rs     请求提取器 AppJson/AppQuery(对应 fastapiEX, 422 pydantic 契约)
//! - pagination.rs  分页参数/响应(对应 utils/db/schema/pagination.py)
//! - middleware.rs  CORS/GZip/耗时日志中间件
//! - security/      JWT 签发校验(对应 token_util.py)+ argon2 密码哈希(对应 password.py)
//! - tables.rs      表级运维注册中心(各模块实体建表注册 + create_all/drop_all)
//! - db_vector.rs   Milvus 向量库客户端(REST v2, 对应 pymilvus AsyncMilvusClient 使用面)

pub mod db_vector;
pub mod error;
pub mod extract;
pub mod middleware;
pub mod pagination;
pub mod security;
pub mod tables;
