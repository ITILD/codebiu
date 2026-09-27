//! `SeaORM` Entity — project_document_chunk(知识库文档分块表)
//!
//! 对齐 Python module_rag/do/project_document_chunk.py 的 ProjectDocumentChunk
//! (VectorModel/Milvus 集合)。Rust 服务暂未接入向量库引擎, 解析管线把分块
//! 文本落关系表(向量字段 embedding/sparse 省略), 供后续接入时迁移。

use sea_orm::entity::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, DeriveEntityModel, Eq, Serialize, Deserialize)]
#[sea_orm(table_name = "project_document_chunk")]
pub struct Model {
    /// 分块唯一ID(uuid4 hex)
    #[sea_orm(primary_key, auto_increment = false)]
    pub id: String,
    /// 排序, 默认0
    pub sort: i32,
    /// 所属文档ID
    pub document_id: String,
    /// 所属项目ID
    pub project_id: String,
    /// 文本内容(用于 BM25 分析的文本)
    pub content: String,
    /// 来源
    #[sea_orm(default_value = "")]
    pub source: String,
    /// 包含的内容类型(JSON 数组, 如 ["text"])
    #[sea_orm(column_type = "JsonBinary", default_value = "[\"text\"]")]
    pub content_types: Json,
    /// 位置信息(JSON 对象, 对齐 Python Position)
    #[sea_orm(column_type = "JsonBinary", default_value = "{}")]
    pub position: Json,
    /// 聚合的非标元数据(可空)
    #[sea_orm(column_type = "JsonBinary")]
    pub metadata: Option<Json>,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {}

impl ActiveModelBehavior for ActiveModel {}
