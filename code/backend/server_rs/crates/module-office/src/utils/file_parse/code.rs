//! Python/Java 源代码语义解析(对齐 Python utils/file_parase/code/parser.py)
//!
//! 解析器尽量按可检索的语义单元输出 Chunk:
//! - Java: 包/导入等模块级代码、类型上下文、方法/构造器(大括号深度算法与 Python 版 1:1);
//! - Python: Rust 无 AST 解析器, 采用行级启发式(缩进 + def/class 关键字 + 装饰器回溯 +
//!   三引号字符串跟踪), 输出模块级代码、函数、类上下文、类方法;
//! - 解析不出语义单元时保留全文并标记 fallback, 交给后续 CodeChunker 安全切分。

use serde_json::{json, Map};

use common::utils::error::AppError;

use crate::do_::chunk::Chunk;
use crate::utils::file_parse::decode_bytes;

/// 语义代码单元(对齐 Python _CodeUnit)
struct CodeUnit {
    /// 起始行(1-based)
    start_line: usize,
    /// 结束行(1-based, 含)
    end_line: usize,
    content: String,
    symbol_type: String,
    symbol_name: String,
    qualified_name: String,
    parse_mode: &'static str,
}

/// 行类型判定(顶层 def/class 识别)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum DefKind {
    Function,
    Class,
}

/// Java 控制流关键字(方法名排除表, 对齐 Python control_words)
const JAVA_CONTROL_WORDS: [&str; 8] =
    ["if", "for", "while", "switch", "catch", "synchronized", "try", "do"];

/// 解析代码文件为语义 Chunk 列表(对齐 CodeParser.extract)
///
/// :param ext: 小写后缀(".py"/".java", 工厂已校验)
/// :param bytes: 文件内容
/// :param filename: 上传原始文件名(写入 metadata.source)
pub fn extract(ext: &str, bytes: &[u8], filename: &str) -> Result<Vec<Chunk>, AppError> {
    let source = decode_bytes(bytes);
    let language = match ext {
        ".py" => "python",
        ".java" => "java",
        // 工厂已做后缀校验, 保留防御式检查(对齐 Python)
        other => return Err(AppError::business(format!("不支持的代码类型: {other}"))),
    };

    let units = match language {
        "python" => parse_python(&source),
        _ => parse_java(&source),
    };

    Ok(units
        .into_iter()
        .filter(|u| !u.content.trim().is_empty())
        .map(|u| {
            let mut meta = Map::new();
            meta.insert("source".into(), json!(filename));
            meta.insert("language".into(), json!(language));
            meta.insert("symbol_type".into(), json!(u.symbol_type));
            meta.insert("symbol_name".into(), json!(u.symbol_name));
            meta.insert("qualified_name".into(), json!(u.qualified_name));
            meta.insert("parse_mode".into(), json!(u.parse_mode));
            Chunk::code(u.content, u.start_line as i64, u.end_line as i64, meta)
        })
        .collect())
}

// ==================== 通用工具 ====================

/// 标识符首字符([A-Za-z_$])
fn is_ident_start(b: u8) -> bool {
    b.is_ascii_alphabetic() || b == b'_' || b == b'$'
}

/// 标识符字符([A-Za-z0-9_$])
fn is_ident_char(b: u8) -> bool {
    is_ident_start(b) || b.is_ascii_digit()
}

/// 全文兜底单元(语法不完整/无语义单元时保留全文)
fn fallback_unit(source: &str, parse_mode: &'static str) -> CodeUnit {
    CodeUnit {
        start_line: 1,
        end_line: source.lines().count().max(1),
        content: source.to_string(),
        symbol_type: "module".into(),
        symbol_name: "<module>".into(),
        qualified_name: "<module>".into(),
        parse_mode,
    }
}

// ==================== Python 启发式解析 ====================

/// 计算行缩进(空格计 1, tab 计 4)并返回去空白内容
fn line_indent(line: &str) -> (usize, &str) {
    let mut indent = 0;
    for c in line.chars() {
        match c {
            ' ' => indent += 1,
            '\t' => indent += 4,
            _ => break,
        }
    }
    (indent, line.trim())
}

/// 标记各行是否处于三引号字符串内(启发式; 减少字符串内 def/class 误判)
fn triple_quote_mask(lines: &[&str]) -> Vec<bool> {
    let mut mask = vec![false; lines.len()];
    let mut in_str = false;
    let mut delimiter = b'"';
    for (i, line) in lines.iter().enumerate() {
        if in_str {
            mask[i] = true;
        }
        let b = line.as_bytes();
        let mut j = 0;
        while j + 2 < b.len() + 1 {
            if !in_str && (b[j..].starts_with(b"\"\"\"") || b[j..].starts_with(b"'''")) {
                in_str = true;
                delimiter = b[j];
                mask[i] = true;
                j += 3;
            } else if in_str
                && b[j] == delimiter
                && b.get(j + 1) == Some(&delimiter)
                && b.get(j + 2) == Some(&delimiter)
            {
                in_str = false;
                j += 3;
            } else {
                j += 1;
            }
        }
    }
    mask
}

/// def/class 行判定(顶层与类体内共用)
fn def_kind(trimmed: &str) -> Option<DefKind> {
    if trimmed.starts_with("class ") && trimmed[6..].starts_with(|c: char| c.is_alphabetic() || c == '_') {
        return Some(DefKind::Class);
    }
    let rest = trimmed
        .strip_prefix("async def ")
        .or_else(|| trimmed.strip_prefix("def "))?;
    if rest.starts_with(|c: char| c.is_alphabetic() || c == '_') {
        return Some(DefKind::Function);
    }
    None
}

/// 1-based 行区间 [start, end] 的源文本
fn slice_lines(lines: &[&str], start: usize, end: usize) -> String {
    if start > end || end > lines.len() {
        return String::new();
    }
    lines[start - 1..end].concat()
}

/// 追加模块间隙单元(相邻语义单元之间的顶层代码, 对齐 _append_module_gap)
fn append_module_gap(units: &mut Vec<CodeUnit>, lines: &[&str], start: usize, end: usize) {
    if start > end {
        return;
    }
    let content = slice_lines(lines, start, end);
    if !content.trim().is_empty() {
        units.push(CodeUnit {
            start_line: start,
            end_line: end,
            content,
            symbol_type: "module".into(),
            symbol_name: "<module>".into(),
            qualified_name: "<module>".into(),
            parse_mode: "semantic",
        });
    }
}

/// 从语义单元行向上回溯连续装饰器行(@ 开头), 返回 1-based 起始行
fn decorator_start(lines: &[&str], in_string: &[bool], first_line: usize) -> usize {
    let mut start = first_line;
    while start > 1 {
        let (indent, trimmed) = line_indent(lines[start - 2]);
        if !in_string[start - 2] && indent == 0 && trimmed.starts_with('@') {
            start -= 1;
        } else {
            break;
        }
    }
    start
}

/// 修剪块尾部空行(使结束行贴近真实代码末尾, 近似 AST end_lineno)
fn trim_trailing_blank(lines: &[&str], start_line: usize, mut end_line: usize) -> usize {
    while end_line > start_line && lines[end_line - 1].trim().is_empty() {
        end_line -= 1;
    }
    end_line
}

/// Python 启发式解析: 模块级代码/函数/类上下文/类方法
fn parse_python(source: &str) -> Vec<CodeUnit> {
    if source.trim().is_empty() {
        return vec![];
    }
    let lines: Vec<&str> = source.split_inclusive('\n').collect();
    let n = lines.len();
    let in_string = triple_quote_mask(&lines);

    let mut units: Vec<CodeUnit> = Vec::new();
    let mut cursor = 1usize; // 下一个待归属行(1-based)
    let mut i = 0usize; // 0-based 行游标

    while i < n {
        if in_string[i] {
            i += 1;
            continue;
        }
        let (indent, trimmed) = line_indent(lines[i]);
        if trimmed.is_empty() || trimmed.starts_with('#') {
            i += 1;
            continue;
        }
        // 仅识别顶层(缩进 0)的 def/async def/class; 类体内方法在类块扫描中处理
        if indent != 0 {
            i += 1;
            continue;
        }
        let Some(kind) = def_kind(trimmed) else {
            i += 1;
            continue;
        };

        let start_line = decorator_start(&lines, &in_string, i + 1);
        // 块结束: 下一个缩进为 0 的有效行(排除字符串行)
        let mut j = i + 1;
        while j < n && (in_string[j] || {
            let (ind, t) = line_indent(lines[j]);
            !(!t.is_empty() && !t.starts_with('#') && ind == 0)
        }) {
            j += 1;
        }
        let block_end0 = j; // 0-based exclusive
        let end_line = trim_trailing_blank(&lines, start_line, block_end0);

        append_module_gap(&mut units, &lines, cursor, start_line - 1);
        match kind {
            DefKind::Function => {
                units.push(CodeUnit {
                    start_line,
                    end_line,
                    content: slice_lines(&lines, start_line, end_line),
                    symbol_type: "function".into(),
                    symbol_name: symbol_name_of(trimmed),
                    qualified_name: symbol_name_of(trimmed),
                    parse_mode: "semantic",
                });
            }
            DefKind::Class => {
                units.extend(python_class_units(&lines, &in_string, start_line, block_end0, trimmed));
            }
        }
        cursor = end_line + 1;
        i = block_end0;
    }

    append_module_gap(&mut units, &lines, cursor, n);
    if units.is_empty() {
        return vec![fallback_unit(source, "module")];
    }
    units.sort_by_key(|u| (u.start_line, u.symbol_type == "method"));
    units
}

/// 从 def/class 行提取符号名(如 "def foo(" → "foo", "class Bar:" → "Bar")
fn symbol_name_of(trimmed: &str) -> String {
    let rest = trimmed
        .strip_prefix("async def ")
        .or_else(|| trimmed.strip_prefix("def "))
        .or_else(|| trimmed.strip_prefix("class "))
        .unwrap_or(trimmed);
    let name: String = rest
        .chars()
        .take_while(|c| c.is_alphanumeric() || *c == '_')
        .collect();
    if name.is_empty() { "<module>".into() } else { name }
}

/// 类块解析: 无方法 → 整类单块; 有方法 → 类上下文(去方法体) + 各方法单元
///
/// :param start_line: 类起始行(含装饰器, 1-based)
/// :param block_end0: 类块结束(0-based exclusive)
fn python_class_units(
    lines: &[&str],
    in_string: &[bool],
    start_line: usize,
    block_end0: usize,
    class_trimmed: &str,
) -> Vec<CodeUnit> {
    let class_name = symbol_name_of(class_trimmed);
    let end_line = trim_trailing_blank(lines, start_line, block_end0);
    let (class_indent, _) = line_indent(lines[start_line - 1]);

    // 扫描类体内的方法(缩进 > 类缩进的 def/async def, 含装饰器回溯)
    let mut method_spans: Vec<(usize, usize)> = Vec::new();
    let mut method_names: Vec<String> = Vec::new();
    let mut j = start_line; // 0-based 从类头下一行开始
    while j < block_end0 {
        if in_string[j] {
            j += 1;
            continue;
        }
        let (indent, trimmed) = line_indent(lines[j]);
        if trimmed.is_empty() || trimmed.starts_with('#') || indent <= class_indent {
            j += 1;
            continue;
        }
        if def_kind(trimmed).is_some() {
            let m_start = {
                // 装饰器回溯(装饰器缩进须仍大于类缩进)
                let mut s = j + 1;
                while s > start_line + 1 {
                    let (ind2, t2) = line_indent(lines[s - 2]);
                    if !in_string[s - 2] && ind2 > class_indent && t2.starts_with('@') {
                        s -= 1;
                    } else {
                        break;
                    }
                }
                s
            };
            // 方法体结束: 下一个缩进 <= 方法首行缩进的有效行
            let m_end0 = {
                let mut k = j + 1;
                while k < block_end0
                    && (in_string[k] || {
                        let (ind, t) = line_indent(lines[k]);
                        !(!t.is_empty() && !t.starts_with('#') && ind <= indent)
                    })
                {
                    k += 1;
                }
                k
            };
            let m_end = trim_trailing_blank(lines, m_start, m_end0);
            method_spans.push((m_start, m_end));
            method_names.push(symbol_name_of(trimmed));
            j = m_end0;
        } else {
            j += 1;
        }
    }

    // 无方法: 整类一个单元
    if method_spans.is_empty() {
        return vec![CodeUnit {
            start_line,
            end_line,
            content: slice_lines(lines, start_line, end_line),
            symbol_type: "class".into(),
            symbol_name: class_name.clone(),
            qualified_name: class_name,
            parse_mode: "semantic",
        }];
    }

    // 类上下文保留装饰器、继承关系、文档字符串和字段, 但移除方法体
    let mut context_parts: Vec<String> = Vec::new();
    let mut context_cursor = start_line;
    for (m_start, m_end) in &method_spans {
        if context_cursor <= m_start - 1 {
            context_parts.push(slice_lines(lines, context_cursor, m_start - 1));
        }
        context_cursor = m_end + 1;
    }
    if context_cursor <= end_line {
        context_parts.push(slice_lines(lines, context_cursor, end_line));
    }
    let context = context_parts.concat();
    let context = context.trim_end();

    let mut results: Vec<CodeUnit> = Vec::new();
    if !context.trim().is_empty() {
        results.push(CodeUnit {
            start_line,
            end_line,
            content: context.to_string(),
            symbol_type: "class_context".into(),
            symbol_name: class_name.clone(),
            qualified_name: class_name.clone(),
            parse_mode: "semantic",
        });
    }
    for ((m_start, m_end), m_name) in method_spans.iter().zip(&method_names) {
        let method_source = slice_lines(lines, *m_start, *m_end);
        let method_source = method_source.trim_end().to_string();
        results.push(CodeUnit {
            start_line: *m_start,
            end_line: *m_end,
            content: method_source,
            symbol_type: "method".into(),
            symbol_name: m_name.clone(),
            qualified_name: format!("{class_name}.{m_name}"),
            parse_mode: "semantic",
        });
    }
    results
}

// ==================== Java 解析(与 Python 版算法 1:1) ====================

/// 移除注释/字符串内容但保留长度和换行, 便于安全计算大括号(对齐 _sanitize_java)
fn sanitize_java(source: &str) -> String {
    let bytes = source.as_bytes();
    let mut result = bytes.to_vec();
    #[derive(PartialEq)]
    enum State {
        Code,
        LineComment,
        BlockComment,
        Str,
    }
    let mut state = State::Code;
    let mut quote = 0u8;
    let mut i = 0usize;
    while i < bytes.len() {
        let ch = bytes[i];
        let nxt = bytes.get(i + 1).copied();
        match state {
            State::Code => {
                if ch == b'/' && nxt == Some(b'/') {
                    result[i] = b' ';
                    result[i + 1] = b' ';
                    i += 2;
                    state = State::LineComment;
                    continue;
                }
                if ch == b'/' && nxt == Some(b'*') {
                    result[i] = b' ';
                    result[i + 1] = b' ';
                    i += 2;
                    state = State::BlockComment;
                    continue;
                }
                if ch == b'"' || ch == b'\'' {
                    quote = ch;
                    result[i] = b' ';
                    state = State::Str;
                }
            }
            State::LineComment => {
                if ch == b'\n' {
                    state = State::Code;
                } else {
                    result[i] = b' ';
                }
            }
            State::BlockComment => {
                if ch == b'*' && nxt == Some(b'/') {
                    result[i] = b' ';
                    result[i + 1] = b' ';
                    i += 2;
                    state = State::Code;
                    continue;
                }
                if ch != b'\n' {
                    result[i] = b' ';
                }
            }
            State::Str => {
                if ch == b'\\' {
                    result[i] = b' ';
                    if nxt.is_some() && nxt != Some(b'\n') {
                        result[i + 1] = b' ';
                        i += 2;
                        continue;
                    }
                } else if ch == quote {
                    result[i] = b' ';
                    state = State::Code;
                } else if ch != b'\n' {
                    result[i] = b' ';
                }
            }
        }
        i += 1;
    }
    // 替换仅发生在 ASCII 字节上, 多字节 UTF-8 序列保持不变
    String::from_utf8(result).unwrap_or_else(|_| source.to_string())
}

/// 逐位置大括号深度表(长度 len+1, 对齐 _brace_depths)
fn brace_depths(text: &str) -> Vec<usize> {
    let mut depths = vec![0usize; text.len() + 1];
    let mut depth = 0usize;
    for (i, ch) in text.bytes().enumerate() {
        depths[i] = depth;
        if ch == b'{' {
            depth += 1;
        } else if ch == b'}' {
            depth = depth.saturating_sub(1);
        }
    }
    depths[text.len()] = depth;
    depths
}

/// 从 open_brace 起找配对右括号(找不到返回 None, 对齐 _matching_brace)
fn matching_brace(text: &str, open_brace: usize) -> Option<usize> {
    let bytes = text.as_bytes();
    let mut depth = 0i32;
    for (i, ch) in bytes.iter().enumerate().skip(open_brace) {
        match *ch {
            b'{' => depth += 1,
            b'}' => {
                depth -= 1;
                if depth == 0 {
                    return Some(i);
                }
            }
            _ => {}
        }
    }
    None
}

/// 方法头部解析: 从 header 尾部解析 "name(params) [throws ...]" 结构, 返回方法名
///
/// 移植正则 `([A-Za-z_$][\w$]*)\s*\([^(){};]*\)\s*(?:throws\s+[^{}]+)?$`。
fn method_header_name(header: &str) -> Option<&str> {
    let h = header.trim();
    let paren_end = h.rfind(')')?;
    // ')' 之后只允许可选的 throws 子句(不含大括号)
    let tail = h[paren_end + 1..].trim();
    if !tail.is_empty() && !(tail.starts_with("throws") && !tail.contains(['{', '}'])) {
        return None;
    }
    // 参数段不得包含 (){};(正则 [^(){};]*)
    let paren_start = h[..paren_end].rfind('(')?;
    let params = &h[paren_start + 1..paren_end];
    if params.contains(['(', ')', '{', '}', ';']) {
        return None;
    }
    // 方法名: 参数左括号前紧邻的标识符
    let before = h[..paren_start].trim_end();
    let b = before.as_bytes();
    let mut name_start = b.len();
    while name_start > 0 && is_ident_char(b[name_start - 1]) {
        name_start -= 1;
    }
    let name = &before[name_start..];
    if name.is_empty() || !is_ident_start(b[name_start]) {
        return None;
    }
    Some(name)
}

/// 字节偏移所在行号(1-based, 对齐 _line_number)
fn line_number(source: &str, offset: usize) -> usize {
    let off = offset.min(source.len());
    source[..off].matches('\n').count() + 1
}

/// 字节偏移所在行的行首偏移(对齐 _line_start)
fn line_start(source: &str, offset: usize) -> usize {
    match source[..offset.min(source.len())].rfind('\n') {
        Some(p) => p + 1,
        None => 0,
    }
}

/// 追加类型间隙单元(相邻类型声明之间的模块级代码, 对齐 _append_java_gap)
fn append_java_gap(units: &mut Vec<CodeUnit>, source: &str, start: usize, end: usize) {
    let content = &source[start..end.max(start)];
    if !content.trim().is_empty() {
        units.push(CodeUnit {
            start_line: line_number(source, start),
            end_line: line_number(source, start.max(end.saturating_sub(1))),
            content: content.to_string(),
            symbol_type: "module".into(),
            symbol_name: "<module>".into(),
            qualified_name: "<module>".into(),
            parse_mode: "semantic",
        });
    }
}

/// 扫描顶层类型声明(class/interface/enum/record + 名称 + 花括号区间)
fn find_type_ranges(
    sanitized: &str,
    depths: &[usize],
) -> Vec<(&'static str, String, usize, usize)> {
    const KEYWORDS: [&str; 4] = ["class", "interface", "enum", "record"];
    let bytes = sanitized.as_bytes();
    let mut ranges: Vec<(&'static str, String, usize, usize)> = Vec::new();
    let mut i = 0usize;
    while i < bytes.len() {
        if !is_ident_start(bytes[i]) {
            i += 1;
            continue;
        }
        let start = i;
        while i < bytes.len() && is_ident_char(bytes[i]) {
            i += 1;
        }
        let word = &sanitized[start..i];
        let Some(kind) = KEYWORDS.iter().find(|k| **k == word) else {
            continue;
        };
        // 深度非 0 处的类型声明跳过(对齐 depths[match.start()] != 0 判断)
        if depths[start] != 0 {
            continue;
        }
        // 关键字后至少一个空白 + 类型名
        let mut j = i;
        while j < bytes.len() && bytes[j].is_ascii_whitespace() {
            j += 1;
        }
        if j >= bytes.len() || !is_ident_start(bytes[j]) {
            continue;
        }
        let name_start = j;
        while j < bytes.len() && is_ident_char(bytes[j]) {
            j += 1;
        }
        let name = sanitized[name_start..j].to_string();
        // 类型名之后的第一个 '{' 为类型体开始
        let Some(open_rel) = sanitized[j..].find('{') else {
            continue;
        };
        let open_brace = j + open_rel;
        let Some(close_brace) = matching_brace(sanitized, open_brace) else {
            // 大括号不配对: 语法不完整, 保留全文兜底
            return vec![];
        };
        ranges.push((kind, name, open_brace, close_brace));
    }
    ranges
}

/// 类型块展开: 无方法 → 整类型单块; 有方法 → 类型上下文 + 各方法/构造器(对齐 _java_type_units)
fn java_type_units(
    source: &str,
    sanitized: &str,
    type_start: usize,
    open_brace: usize,
    close_brace: usize,
    type_kind: &str,
    type_name: &str,
) -> Vec<CodeUnit> {
    let method_spans = java_method_spans(sanitized, open_brace, close_brace);
    let start_line = line_number(source, type_start);
    let end_line = line_number(source, close_brace);
    if method_spans.is_empty() {
        return vec![CodeUnit {
            start_line,
            end_line,
            content: source[type_start..=close_brace].to_string(),
            symbol_type: type_kind.into(),
            symbol_name: type_name.into(),
            qualified_name: type_name.into(),
            parse_mode: "semantic",
        }];
    }

    let mut results: Vec<CodeUnit> = Vec::new();
    // 类型上下文保留头部与字段, 移除方法体
    let mut context_parts = vec![source[type_start..=open_brace].to_string()];
    let mut context_cursor = open_brace + 1;
    for (m_start, m_end, m_name) in &method_spans {
        context_parts.push(source[context_cursor..*m_start].to_string());
        context_cursor = m_end + 1;
        let method_source = source[*m_start..*m_end + 1].trim();
        let symbol_type = if m_name == type_name { "constructor" } else { "method" };
        results.push(CodeUnit {
            start_line: line_number(source, *m_start),
            end_line: line_number(source, *m_end),
            content: method_source.to_string(),
            symbol_type: symbol_type.into(),
            symbol_name: m_name.clone(),
            qualified_name: format!("{type_name}.{m_name}"),
            parse_mode: "semantic",
        });
    }
    context_parts.push(source[context_cursor..=close_brace].to_string());
    let context = context_parts.join("").trim().to_string();
    if !context.is_empty() {
        results.push(CodeUnit {
            start_line,
            end_line,
            content: context,
            symbol_type: format!("{type_kind}_context"),
            symbol_name: type_name.into(),
            qualified_name: type_name.into(),
            parse_mode: "semantic",
        });
    }
    results
}

/// 大括号深度扫描类体方法区间(对齐 _java_method_spans)
fn java_method_spans(
    sanitized: &str,
    open_brace: usize,
    close_brace: usize,
) -> Vec<(usize, usize, String)> {
    let bytes = sanitized.as_bytes();
    let mut spans: Vec<(usize, usize, String)> = Vec::new();
    let mut depth = 1i32;
    let mut statement_start = open_brace + 1;
    let mut index = open_brace + 1;

    while index < close_brace {
        let ch = bytes[index];
        if ch == b'{' && depth == 1 {
            let header = sanitized[statement_start..index].trim();
            let name = method_header_name(header).unwrap_or("");
            if !name.is_empty()
                && !JAVA_CONTROL_WORDS.contains(&name)
                && !header.contains('=')
            {
                let Some(method_end) = matching_brace(sanitized, index) else {
                    break;
                };
                if method_end > close_brace {
                    break;
                }
                let mut start = statement_start;
                while start < index && bytes[start].is_ascii_whitespace() {
                    start += 1;
                }
                spans.push((start, method_end, name.to_string()));
                index = method_end + 1;
                statement_start = index;
                continue;
            }
            // header 不是方法签名: 视为嵌套块(匿名类/lambda/初始化块等)
            depth += 1;
        } else if ch == b'{' {
            depth += 1;
        } else if ch == b'}' {
            depth -= 1;
            if depth == 1 {
                statement_start = index + 1;
            }
        } else if ch == b';' && depth == 1 {
            statement_start = index + 1;
        }
        index += 1;
    }
    spans
}

/// Java 主解析流程(对齐 _parse_java)
fn parse_java(source: &str) -> Vec<CodeUnit> {
    if source.trim().is_empty() {
        return vec![];
    }
    let sanitized = sanitize_java(source);
    let depths = brace_depths(&sanitized);
    let type_ranges = find_type_ranges(&sanitized, &depths);
    if type_ranges.is_empty() {
        return vec![fallback_unit(source, "fallback")];
    }

    let mut units: Vec<CodeUnit> = Vec::new();
    let mut cursor = 0usize;
    for (kind, name, open_brace, close_brace) in &type_ranges {
        let type_start = line_start(source, *open_brace);
        // 回溯到声明行首(注解/修饰符在声明行; open_brace 前找 '{' 之前的声明起点已由
        // line_start 覆盖, 此处按 Python 语义以匹配起点所在行首为类型区间起点)
        append_java_gap(&mut units, source, cursor, type_start);
        units.extend(java_type_units(
            source,
            &sanitized,
            type_start,
            *open_brace,
            *close_brace,
            kind,
            name,
        ));
        cursor = close_brace + 1;
    }
    append_java_gap(&mut units, source, cursor, source.len());
    units.sort_by_key(|u| (u.start_line, u.symbol_type == "method"));
    units
}
