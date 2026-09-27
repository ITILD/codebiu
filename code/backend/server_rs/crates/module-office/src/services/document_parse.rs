//! 文件解析服务(对齐 Python service/document_parse.py)
//!
//! file2chunk: 按文件类型路由解析器 → 带元数据的分块列表;
//! file2markdown: 分块内容按换行合并。

use axum::body::Bytes;

use common::utils::error::AppError;

use crate::do_::chunk::Chunk;
use crate::utils::file_parse::{FileType, suffix_lower};

/// 将文件解析为带元数据(文件原位置, 文件类型大小等)的分块列表
///
/// 路由口径对齐 Python DocumentParseService.file2chunk:
/// - 文档类型 → 工厂按后缀路由解析器;
/// - 图片/音频/视频 → 暂未接入解析器, 返回空列表(Python 侧 pass);
/// - 其他类型 → 报错(对齐 Python ValueError → 500)。
pub async fn file2chunk(filename: &str, bytes: Bytes) -> Result<Vec<Chunk>, AppError> {
    let ext = suffix_lower(filename);
    if FileType::is_document(&ext) {
        // 文档文件: 通过工厂按后缀路由到对应解析器
        crate::utils::file_parse::create_and_extract(filename, &bytes).await
    } else if FileType::is_image(&ext) || FileType::is_audio(&ext) || FileType::is_video(&ext) {
        // 图片/音频/视频: 待接入解析器(对齐 Python 分支 pass)
        Ok(vec![])
    } else {
        // 对齐 Python ValueError(未捕获异常 → 500)
        Err(AppError::internal(format!("不支持的文件类型: {ext}")))
    }
}

/// 将文件解析为 Markdown 格式(分块内容按换行合并, 对齐 file2markdown)
pub async fn file2markdown(filename: &str, bytes: Bytes) -> Result<String, AppError> {
    let chunks = file2chunk(filename, bytes).await?;
    Ok(chunks
        .into_iter()
        .filter_map(|c| c.content)
        .collect::<Vec<_>>()
        .join("\n"))
}
