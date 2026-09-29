//! MinerU 引擎解析器(对齐 Python utils/file_parase/mineru/parser.py):
//! 调用远程/本地 MinerU 服务, content_list.json → Chunk。
//!
//! MinerU 结果 zip 内含 `{文件名}/content_list.json`(结构化内容列表)、
//! `{文件名}/full.md`、`{文件名}/images/*`。按 content_list 逐条映射:
//!
//! - text     → Text; 有 text_level 时 → Title(带 heading_level)
//! - table    → Table(table_body html 转紧凑 markdown); 大表拆 TableHeader+TableContent
//! - image    → Image(图片落盘后输出文件链接) + ImageContent(caption;
//!              Rust 侧未接入 VLM OCR, caption 缺省时跳过该块)
//! - equation → Text(LaTeX 原文)
//! - page_idx(0-based) → position.page(1-based, 与 docling 引擎对齐)

use std::collections::HashMap;
use std::io::Cursor;
use std::io::Read;
use std::path::PathBuf;

use common::config::get as get_config;
use common::utils::error::AppError;
use serde_json::{json, Map, Value};

use crate::do_::chunk::{Chunk, ContentType, Position};
use crate::utils::file_parse::mineru::client::{build_client, MineruClient};

/// 大表格阈值(字符数): 与 docling/mineru(Python) 引擎一致, 超过拆表头+表内容
const TABLE_LARGE_THRESHOLD: usize = 2000;

/// 解析单个文件(MinerU 引擎): 调服务取结果 zip, 解包后逐条转 Chunk
pub async fn extract(filename: &str, bytes: &[u8]) -> Result<Vec<Chunk>, AppError> {
    let cfg = &get_config().mineru;
    let client: MineruClient = build_client(cfg)?;
    let zip_bytes = client.parse(filename, bytes).await?;
    let stem = file_stem(filename);
    let (items, images) = unpack(&zip_bytes, &stem)?;
    let mut chunks = Vec::with_capacity(items.len());
    for item in &items {
        chunks.extend(item_to_chunks(item, &images));
    }
    Ok(chunks)
}

// ==================== 结果解包 ====================

/// 解包结果 zip: 返回 (content_list 条目列表, img_path → 本地落盘路径映射)
fn unpack(zip_bytes: &[u8], stem: &str) -> Result<(Vec<Value>, HashMap<String, String>), AppError> {
    let zip_open_err = |e: zip::result::ZipError| {
        AppError::business(format!("MinerU 结果 zip 读取失败: {e}"))
    };
    let zip_read_err = |e: std::io::Error| AppError::business(format!("MinerU 结果 zip 读取失败: {e}"));
    let mut items: Vec<Value> = Vec::new();
    let mut full_md = String::new();
    let mut images: HashMap<String, String> = HashMap::new();
    let media_dir = temp_dir().join(stem);

    let mut zip = zip::ZipArchive::new(Cursor::new(zip_bytes))
        .map_err(|e| AppError::business(format!("MinerU 结果 zip 解析失败: {e}")))?;
    for i in 0..zip.len() {
        let mut file = zip.by_index(i).map_err(zip_open_err)?;
        let name = file.name().to_string();
        let base = name.rsplit('/').next().unwrap_or("").to_string();
        let mut buf = Vec::new();
        file.read_to_end(&mut buf).map_err(zip_read_err)?;
        if base == "content_list.json" {
            if let Ok(list) = serde_json::from_slice::<Vec<Value>>(&buf) {
                items = list;
            }
        } else if base == "full.md" && full_md.is_empty() {
            full_md = String::from_utf8_lossy(&buf).into_owned();
        } else if let Some(file_in_images) = name.split("/images/").nth(1) {
            // 图片落盘 temp 目录; 双键映射: 完整相对键(images/xxx.jpg) 与 文件名兜底
            if !base.is_empty() {
                let target = media_dir.join(&base);
                if std::fs::create_dir_all(&media_dir).is_ok()
                    && std::fs::write(&target, &buf).is_ok()
                {
                    let path = target.display().to_string();
                    images.insert(format!("images/{file_in_images}"), path.clone());
                    images.insert(base, path);
                }
            }
        }
    }

    if items.is_empty() && !full_md.is_empty() {
        // 回退: 无结构化列表时按行粗分 full.md
        tracing::warn!("MinerU 结果缺少 content_list.json, 回退 full.md 按行分块");
        items = full_md
            .lines()
            .filter(|l| !l.trim().is_empty())
            .map(|l| json!({"type": "text", "text": l}))
            .collect();
    }
    if items.is_empty() {
        return Err(AppError::business("MinerU 结果中无 content_list.json 与 full.md"));
    }
    Ok((items, images))
}

// ==================== 条目 → Chunk ====================

/// 将单个 content_list 条目映射为 Chunk 列表
fn item_to_chunks(item: &Value, images: &HashMap<String, String>) -> Vec<Chunk> {
    let typ = item.get("type").and_then(Value::as_str).unwrap_or("");
    let page = page_no(item);
    match typ {
        "text" => text_chunks(item, page),
        "equation" => {
            let Some(text) = clean_text(item.get("text")) else {
                return vec![];
            };
            vec![Chunk {
                content: Some(text),
                content_type: ContentType::Text,
                position: pos(page),
                metadata: Some(unmergeable(None)),
            }]
        }
        "table" => table_chunks(item, page),
        "image" => image_chunks(item, page, images),
        // 未知类型: 有文本则按普通文本输出, 保证内容不丢
        _ => {
            let Some(text) = clean_text(item.get("text")) else {
                return vec![];
            };
            vec![Chunk {
                content: Some(text),
                content_type: ContentType::Text,
                position: pos(page),
                metadata: None,
            }]
        }
    }
}

/// 文本条目: 有 text_level(标题级别) → Title, 否则 Text
fn text_chunks(item: &Value, page: i64) -> Vec<Chunk> {
    let Some(text) = clean_text(item.get("text")) else {
        return vec![];
    };
    let level = item.get("text_level").and_then(Value::as_i64).filter(|l| *l > 0);
    match level {
        Some(l) => vec![Chunk {
            content: Some(text),
            content_type: ContentType::Title,
            position: Position {
                page: Some(page),
                heading_level: Some(l),
                ..Default::default()
            },
            metadata: None,
        }],
        None => vec![Chunk {
            content: Some(text),
            content_type: ContentType::Text,
            position: pos(page),
            metadata: None,
        }],
    }
}

/// 表格条目: table_body(html) 转紧凑 markdown; 超阈值拆表头+表内容
fn table_chunks(item: &Value, page: i64) -> Vec<Chunk> {
    let caption = join_texts(item.get("table_caption"));
    let html = item.get("table_body").and_then(Value::as_str).unwrap_or("");
    let rows = html_table_to_rows(html);
    if rows.is_empty() {
        // 无结构化表格体: caption 兜底输出
        if caption.is_empty() {
            return vec![];
        }
        return vec![Chunk {
            content: Some(caption),
            content_type: ContentType::Table,
            position: pos(page),
            metadata: Some(unmergeable(None)),
        }];
    }

    let prefix = if caption.is_empty() { String::new() } else { format!("{caption}\n\n") };
    let text_len: usize = rows.iter().map(|r| r.iter().map(|c| c.len()).sum::<usize>()).sum();
    let header_md = rows_to_md_table(std::slice::from_ref(&rows[0]), true);

    if text_len <= TABLE_LARGE_THRESHOLD || rows.len() == 1 {
        let body_md = rows_to_md_table(&rows[1..], false);
        let md = if body_md.is_empty() {
            format!("{prefix}{header_md}")
        } else {
            format!("{prefix}{header_md}\n{body_md}")
        };
        return vec![Chunk {
            content: Some(md),
            content_type: ContentType::Table,
            position: pos(page),
            metadata: Some(unmergeable(None)),
        }];
    }
    // 大表格: 拆 TableHeader + TableContent(与 docling 引擎一致)
    let body_md = rows_to_md_table(&rows[1..], false);
    vec![
        Chunk {
            content: Some(format!("{prefix}{header_md}")),
            content_type: ContentType::TableHeader,
            position: pos(page),
            metadata: Some(unmergeable(None)),
        },
        Chunk {
            content: Some(body_md),
            content_type: ContentType::TableContent,
            position: pos(page),
            metadata: Some(unmergeable(None)),
        },
    ]
}

/// 图片条目: Image(文件链接) + ImageContent(caption; Rust 未接入 VLM OCR)
fn image_chunks(item: &Value, page: i64, images: &HashMap<String, String>) -> Vec<Chunk> {
    let img_path = item.get("img_path").and_then(Value::as_str).unwrap_or("");
    let local = images
        .get(img_path)
        .or_else(|| PathBuf::from(img_path).file_name().and_then(|n| n.to_str()).and_then(|n| images.get(n)));
    let caption = join_texts(item.get("img_caption"));

    let mut result = Vec::new();
    // 基础元数据(图片落盘成功时含 image_path)
    let base_meta: Option<Map<String, Value>> = local.map(|path| {
        let mut m = Map::new();
        m.insert("image_path".to_string(), json!(path));
        m
    });
    if let Some(path) = local {
        result.push(Chunk {
            content: Some(format!("![]({path})")),
            content_type: ContentType::Image,
            position: pos(page),
            metadata: Some(unmergeable(base_meta.clone())),
        });
    }
    // IMAGE_CONTENT: caption 优先(Python 侧 caption 缺省时回退 VLM OCR, Rust 未接入)
    if !caption.is_empty() {
        result.push(Chunk {
            content: Some(caption),
            content_type: ContentType::ImageContent,
            position: pos(page),
            metadata: Some(unmergeable(base_meta)),
        });
    }
    result
}

// ==================== 工具函数 ====================

/// page_idx(0-based) → 页码(1-based, 与 docling prov.page_no 对齐)
fn page_no(item: &Value) -> i64 {
    item.get("page_idx").and_then(Value::as_i64).map(|p| p + 1).unwrap_or(1)
}

/// 页码位置快捷构造
fn pos(page: i64) -> Position {
    Position { page: Some(page), ..Default::default() }
}

/// 不参与行内合并的元数据(image_path 可选附加)
fn unmergeable(extra: Option<Map<String, Value>>) -> Map<String, Value> {
    let mut meta = extra.unwrap_or_default();
    meta.insert("mergeable".to_string(), json!("false"));
    meta
}

/// 清洗文本: 去首尾空白, 空值返回 None
fn clean_text(value: Option<&Value>) -> Option<String> {
    let text = value.and_then(Value::as_str)?.trim();
    (!text.is_empty()).then(|| text.to_string())
}

/// caption 等字段兼容 str / list[str] 两种形态, 拼接为多行文本
fn join_texts(value: Option<&Value>) -> String {
    match value {
        Some(Value::String(s)) => s.trim().to_string(),
        Some(Value::Array(list)) => list
            .iter()
            .filter_map(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .collect::<Vec<_>>()
            .join("\n"),
        _ => String::new(),
    }
}

/// 文件名去后缀(对齐 Python Path.stem)
fn file_stem(filename: &str) -> String {
    let name = filename.rsplit(['/', '\\']).next().unwrap_or(filename);
    match name.rfind('.') {
        Some(i) if i > 0 => name[..i].to_string(),
        _ => name.to_string(),
    }
}

/// 文件内媒体输出目录: {dir.base}/{dir.base_child.temp}(对齐 Python DIR_TEMP)
fn temp_dir() -> PathBuf {
    let dir = &get_config().dir;
    PathBuf::from(&dir.base).join(&dir.base_child.temp)
}

/// 解析 table_body html 为二维文本网格: colspan 展开保持列对齐, 行宽补齐
///
/// 轻量实现(不引入 html 引擎): 只识别 tr/td/th/br 结构标签,
/// 内层标签文本保留(等价 bs4 get_text(strip=True)), 常见实体解码。
fn html_table_to_rows(html: &str) -> Vec<Vec<String>> {
    let chars: Vec<char> = html.chars().collect();
    let mut rows: Vec<Vec<String>> = Vec::new();
    let mut row: Option<Vec<String>> = None;
    let mut cell: Option<String> = None;
    let mut colspan = 1usize;
    let mut i = 0usize;

    while i < chars.len() {
        if chars[i] == '<' {
            // 找标签闭合 '>'
            let Some(rel) = chars[i + 1..].iter().position(|c| *c == '>') else { break };
            let tag: String = chars[i + 1..i + 1 + rel].iter().collect();
            i += rel + 2;
            let close = tag.starts_with('/');
            let body = if close { &tag[1..] } else { tag.as_str() };
            let (name, attrs) = match body.find(char::is_whitespace) {
                Some(p) => (body[..p].to_ascii_lowercase(), &body[p..]),
                None => (body.trim().to_ascii_lowercase(), ""),
            };
            // 自闭合(XHTML `<td/>`): 按开始+立即结束处理
            let self_close = name.ends_with('/');
            let name = name.trim_end_matches('/').to_string();
            match name.as_str() {
                "tr" => {
                    if let Some(r) = row.take() {
                        if !r.is_empty() {
                            rows.push(r);
                        }
                    }
                    if !close && !self_close {
                        row = Some(Vec::new());
                    }
                    cell = None;
                }
                "td" | "th" => {
                    if !close {
                        // 未闭合的旧单元格先结算(容错)
                        if let Some(c) = cell.take() {
                            flush_cell(row.as_mut(), c, colspan);
                        }
                        colspan = parse_colspan(attrs).max(1);
                        cell = Some(String::new());
                    } else {
                        if let Some(c) = cell.take() {
                            flush_cell(row.as_mut(), c, colspan);
                        }
                        colspan = 1;
                    }
                }
                "br" => {
                    if let Some(c) = cell.as_mut() {
                        c.push(' ');
                    }
                }
                // 其余标签(thead/tbody/span/...)直接跳过, 文本照常收集
                _ => {}
            }
        } else if let Some(c) = cell.as_mut() {
            c.push(chars[i]);
            i += 1;
        } else {
            i += 1;
        }
    }
    // 收尾: 未闭合的行/单元格
    if let Some(c) = cell.take() {
        flush_cell(row.as_mut(), c, colspan);
    }
    if let Some(r) = row.take() {
        if !r.is_empty() {
            rows.push(r);
        }
    }
    if rows.is_empty() {
        return rows;
    }
    // 行宽补齐到最大列数(markdown 表格要求列对齐)
    let width = rows.iter().map(Vec::len).max().unwrap_or(0);
    rows.into_iter().map(|mut r| {
        r.resize(width, String::new());
        r.into_iter().map(|c| normalize_ws(&decode_entities(&c))).collect()
    }).collect()
}

/// 结算单元格: 压入行并按 colspan 补空位(保持列对齐)
fn flush_cell(row: Option<&mut Vec<String>>, cell: String, colspan: usize) {
    if let Some(r) = row {
        r.push(normalize_ws(&decode_entities(&cell)));
        for _ in 1..colspan {
            r.push(String::new());
        }
    }
}

/// 从标签属性提取 colspan 值(形如 ` colspan="2"`)
fn parse_colspan(attrs: &str) -> usize {
    let lower = attrs.to_ascii_lowercase();
    let Some(p) = lower.find("colspan") else { return 1 };
    let rest = attrs[p + "colspan".len()..].trim_start();
    let rest = rest.strip_prefix('=').unwrap_or(rest).trim();
    let digits: String = rest
        .trim_start_matches(['"', '\''])
        .chars()
        .take_while(|c| c.is_ascii_digit())
        .collect();
    digits.parse().unwrap_or(1)
}

/// 解码常见 HTML 实体(&amp; 最后处理避免双解码)
fn decode_entities(s: &str) -> String {
    if !s.contains('&') {
        return s.to_string();
    }
    let mut out = s
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&#39;", "'")
        .replace("&nbsp;", " ");
    out = out.replace("&amp;", "&");
    out
}

/// 折叠连续空白为单空格并去首尾(对齐 bs4 get_text(" ", strip=True))
fn normalize_ws(s: &str) -> String {
    s.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// 渲染紧凑 markdown 表格(与 docling 引擎一致的分隔符与转义风格)
fn rows_to_md_table(rows: &[Vec<String>], with_separator: bool) -> String {
    if rows.is_empty() {
        return String::new();
    }
    let mut lines: Vec<String> = Vec::with_capacity(rows.len() + 1);
    for (i, row) in rows.iter().enumerate() {
        let cells: Vec<String> = row.iter().map(|c| c.replace('|', "\\|")).collect();
        lines.push(format!("| {} |", cells.join(" | ")));
        if i == 0 && with_separator {
            lines.push(format!("|{}|", vec!["---"; row.len()].join("|")));
        }
    }
    lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn html表格解析_colspan展开_实体解码_行宽补齐() {
        let rows = html_table_to_rows(
            "<table><thead><tr><th>名称</th><th colspan=\"2\">数量</th></tr></thead>\
             <tbody><tr><td>苹果 &amp; 梨</td><td>3</td></tr></tbody></table>",
        );
        assert_eq!(
            rows,
            vec![
                vec!["名称".to_string(), "数量".to_string(), String::new()],
                vec!["苹果 & 梨".to_string(), "3".to_string(), String::new()],
            ]
        );
    }

    #[test]
    fn 文本条目_标题级别与页码映射() {
        let item = json!({"type": "text", "text": "第一章 概述", "text_level": 1, "page_idx": 0});
        let chunks = item_to_chunks(&item, &HashMap::new());
        assert_eq!(chunks.len(), 1);
        assert!(matches!(chunks[0].content_type, ContentType::Title));
        assert_eq!(chunks[0].position.page, Some(1));
        assert_eq!(chunks[0].position.heading_level, Some(1));

        let plain = json!({"type": "text", "text": "正文内容", "page_idx": 2});
        let chunks = item_to_chunks(&plain, &HashMap::new());
        assert_eq!(chunks.len(), 1);
        assert!(matches!(chunks[0].content_type, ContentType::Text));
        assert_eq!(chunks[0].position.page, Some(3));
    }

    #[test]
    fn 小表格_caption前置紧凑markdown() {
        let item = json!({
            "type": "table",
            "table_body": "<table><tr><td>名称</td><td>数量</td></tr><tr><td>苹果</td><td>3</td></tr></table>",
            "table_caption": ["表1 水果"],
            "page_idx": 1,
        });
        let chunks = item_to_chunks(&item, &HashMap::new());
        assert_eq!(chunks.len(), 1);
        assert!(matches!(chunks[0].content_type, ContentType::Table));
        assert_eq!(
            chunks[0].content.as_deref().unwrap(),
            "表1 水果\n\n| 名称 | 数量 |\n|---|---|\n| 苹果 | 3 |"
        );
    }

    #[test]
    fn 大表格拆分_表头与内容两个块() {
        let head = "x".repeat(60);
        let body: Vec<String> = (0..40).map(|i| format!("row{i}-{}", "y".repeat(60))).collect();
        let trs: String = body.iter().map(|b| format!("<tr><td>{b}</td></tr>")).collect();
        let item = json!({
            "type": "table",
            "table_body": format!("<table><tr><td>{head}</td></tr>{trs}</table>"),
            "page_idx": 3,
        });
        let chunks = item_to_chunks(&item, &HashMap::new());
        assert_eq!(chunks.len(), 2);
        assert!(matches!(chunks[0].content_type, ContentType::TableHeader));
        assert!(matches!(chunks[1].content_type, ContentType::TableContent));
        assert_eq!(chunks[0].position.page, Some(4));
    }

    #[test]
    fn 图片条目_链接与caption两个块() {
        let mut images = HashMap::new();
        images.insert("images/abc.jpg".to_string(), "temp_source/temp/demo/abc.jpg".to_string());
        images.insert("abc.jpg".to_string(), "temp_source/temp/demo/abc.jpg".to_string());
        let item = json!({
            "type": "image",
            "img_path": "images/abc.jpg",
            "img_caption": ["图1 示意图"],
            "page_idx": 2,
        });
        let chunks = item_to_chunks(&item, &images);
        assert_eq!(chunks.len(), 2);
        assert!(matches!(chunks[0].content_type, ContentType::Image));
        assert_eq!(chunks[0].content.as_deref().unwrap(), "![](temp_source/temp/demo/abc.jpg)");
        assert!(matches!(chunks[1].content_type, ContentType::ImageContent));
        assert_eq!(
            chunks[0].metadata.as_ref().unwrap().get("image_path").and_then(Value::as_str),
            Some("temp_source/temp/demo/abc.jpg")
        );
    }
}
