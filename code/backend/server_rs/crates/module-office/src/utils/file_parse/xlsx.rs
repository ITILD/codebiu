//! Excel 表格解析器(calamine 引擎, 支持 .xlsx)
//!
//! 对齐 Python XlsxParser(docling 引擎)的分块口径:
//! - sheet 页 → 二级标题 chunk("## sheet名", heading_level=1, table_sheet 类型)
//! - 表格数据 → markdown 表格 chunk(≤1000 字整表; 超长拆表头+分块内容)

use std::io::Cursor;

use calamine::{open_workbook_auto_from_rs, Data, Reader};

use common::utils::error::AppError;

use crate::do_::chunk::{Chunk, ContentType, Position};

/// 单块内容长度上限(超过则拆分为表头+内容块)
const MAX_TABLE_CHARS: usize = 1000;
/// 大表内容块的行数步长(每块最多 40 行)
const BIG_TABLE_ROWS: usize = 40;

/// 解析 xlsx 字节流为分块列表
pub fn extract(bytes: &[u8]) -> Result<Vec<Chunk>, AppError> {
    let cursor = Cursor::new(bytes.to_vec());
    let mut workbook =
        open_workbook_auto_from_rs(cursor).map_err(|e| AppError::business(format!("xlsx 打开失败: {e}")))?;
    let sheet_names = workbook.sheet_names().to_vec();
    let mut chunks = Vec::new();
    for name in sheet_names {
        // 读取工作表数据范围(空表跳过, 对齐 Python "有内容时输出标题 chunk")
        let range = match workbook.worksheet_range(&name) {
            Ok(r) if !r.is_empty() => r,
            _ => continue,
        };
        // sheet 标题块(一级章节)
        chunks.push(Chunk {
            content: Some(format!("## {name}")),
            content_type: ContentType::TableSheet,
            position: Position {
                heading_level: Some(1),
                ..Default::default()
            },
            metadata: None,
        });
        // 表格行 → 字符串矩阵
        let rows: Vec<Vec<String>> = range
            .rows()
            .map(|row| row.iter().map(cell_to_string).collect())
            .collect();
        chunks.extend(table_chunks(&rows));
    }
    if chunks.is_empty() {
        return Err(AppError::business("xlsx 无可解析内容(工作表为空)"));
    }
    Ok(chunks)
}

/// 单元格值 → 显示字符串(对齐 Excel 显示口径: 数字去尾零, 空串保持空)
fn cell_to_string(cell: &Data) -> String {
    match cell {
        Data::Empty => String::new(),
        Data::Float(f) => {
            // 整数浮点显示为整数(3.0 → 3)
            if f.fract() == 0.0 && f.abs() < 1e15 {
                format!("{}", *f as i64)
            } else {
                f.to_string()
            }
        }
        Data::Int(i) => i.to_string(),
        Data::String(s) => s.clone(),
        Data::Bool(b) => b.to_string(),
        Data::DateTime(dt) => dt.to_string(),
        Data::DateTimeIso(s) => s.clone(),
        Data::DurationIso(s) => s.clone(),
        Data::Error(e) => format!("{e:?}"),
    }
}

/// 表格行集 → 分块(整表 markdown; 超长拆表头+内容块)
fn table_chunks(rows: &[Vec<String>]) -> Vec<Chunk> {
    let width = rows.iter().map(|r| r.len()).max().unwrap_or(0);
    if width == 0 {
        return Vec::new();
    }
    let table_md = rows_to_markdown(rows);
    if table_md.chars().count() <= MAX_TABLE_CHARS {
        // 小表: 整表一个 chunk
        return vec![Chunk {
            content: Some(table_md),
            content_type: ContentType::Table,
            position: Position::default(),
            metadata: None,
        }];
    }
    // 大表: 表头块 + 按行组内容块(表头行在每个内容块前重复, 保证块内可独立理解)
    let header = rows.first().cloned().unwrap_or_default();
    let mut chunks = vec![Chunk {
        content: Some(rows_to_markdown(std::slice::from_ref(&header))),
        content_type: ContentType::TableHeader,
        position: Position::default(),
        metadata: None,
    }];
    let body = if rows.len() > 1 { &rows[1..] } else { &[][..] };
    for group in body.chunks(BIG_TABLE_ROWS) {
        let mut block = vec![header.clone()];
        block.extend(group.iter().cloned());
        chunks.push(Chunk {
            content: Some(rows_to_markdown(&block)),
            content_type: ContentType::TableContent,
            position: Position::default(),
            metadata: None,
        });
    }
    chunks
}

/// 行集 → markdown 表格(管道转义, 空单元格占位空串)
fn rows_to_markdown(rows: &[Vec<String>]) -> String {
    let width = rows.iter().map(|r| r.len()).max().unwrap_or(0);
    if width == 0 {
        return String::new();
    }
    let mut out = String::new();
    for (i, row) in rows.iter().enumerate() {
        let cells: Vec<String> = (0..width)
            .map(|c| {
                row.get(c)
                    .map(|v| v.replace('|', "\\|"))
                    .unwrap_or_default()
            })
            .collect();
        out.push_str("| ");
        out.push_str(&cells.join(" | "));
        out.push_str(" |\n");
        // 首行后插入分隔行
        if i == 0 {
            out.push_str("|");
            for _ in 0..width {
                out.push_str(" --- |");
            }
            out.push('\n');
        }
    }
    out
}
