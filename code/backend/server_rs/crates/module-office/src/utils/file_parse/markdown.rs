//! Markdown/文本解析器(对齐 Python docling MarkdownParser, 支持 .md/.markdown/.csv/.txt)
//!
//! Rust 服务未引入 docling: 文本类文件按原文单块输出(file2markdown 的 join 结果
//! 与原文一致); CSV 的表格转 Markdown 特性未实现, 输出原文。

use common::utils::error::AppError;

use crate::do_::chunk::Chunk;
use crate::utils::file_parse::decode_bytes;

/// 解析 Markdown/文本文件为单块 Chunk(内容为文件原文)
pub fn extract(bytes: &[u8]) -> Result<Vec<Chunk>, AppError> {
    let text = decode_bytes(bytes);
    Ok(vec![Chunk::text(text)])
}
