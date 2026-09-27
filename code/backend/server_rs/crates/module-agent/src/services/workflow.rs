//! 工作流执行引擎(对齐 Python module_agent/service/workflow.py)
//!
//! - 图约定: node.type ∈ {start, end, llm, condition, template}, condition 出边以 sourceHandle=true/false 分支
//! - 变量引用: {{node_id.path.to.field}} 模板插值(整串单引用透传原对象, 否则字符串插值)
//! - 执行语义: Kahn 拓扑序驱动, 条件分支未命中的路径不激活(一期仅支持 DAG)
//! - 轨迹: 每节点记录输入/输出/耗时/状态, 失败即终止(错误携带已完成轨迹供运行历史落库)
//! - JSON 解析: 容忍 ```json 围栏与首尾杂质, 供简单/工作流两链路共用

use serde::Serialize;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::time::Instant;

use common::runtime::AppState;

use crate::do_::agent::AgentIOType;
use crate::do_::agent_run::AgentRunRequest;
use crate::do_::entity::agent;

/// 一期支持的节点类型
const NODE_TYPES: [&str; 5] = ["start", "end", "llm", "condition", "template"];

/// 条件节点支持的运算符
const CONDITION_OPERATORS: [&str; 9] = [
    "eq", "ne", "gt", "gte", "lt", "lte", "contains", "empty", "regex",
];

/// 节点执行状态
pub const STATUS_SUCCESS: &str = "success";
const STATUS_FAILED: &str = "failed";

/// 单节点执行轨迹(运行历史的节点级明细, 字段与 Python NodeTrace 一致)
#[derive(Debug, Clone, Serialize)]
pub struct NodeTrace {
    pub node_id: String,
    pub node_type: String,
    /// 执行状态: success/failed/skipped
    pub status: String,
    /// 节点输入(上游节点输出快照)
    pub input: Option<Value>,
    /// 节点输出
    pub output: Option<Value>,
    /// 执行耗时(毫秒)
    pub duration_ms: i64,
    /// 失败原因(status=failed 时)
    pub error: Option<String>,
}

/// 工作流执行失败(携带已完成节点轨迹, 供运行历史落库排查)
#[derive(Debug)]
pub struct WorkflowExecError {
    pub message: String,
    pub traces: Vec<NodeTrace>,
}

impl WorkflowExecError {
    fn new(message: impl Into<String>, traces: Vec<NodeTrace>) -> Self {
        Self { message: message.into(), traces }
    }
}

/// 从模型文本中解析 JSON(容忍 ```json 围栏与首尾杂质; 失败返回原文本)
pub fn parse_json_content(content: &str) -> Value {
    let mut text = content.trim();
    // 去掉 Markdown 代码块围栏
    if text.starts_with("```") {
        text = match text.split("```").nth(1) {
            Some(inner) => inner.trim(),
            None => text.trim_matches('`'),
        };
        if let Some(stripped) = text.strip_prefix("json") {
            text = stripped.trim();
        }
    }
    if let Ok(value) = serde_json::from_str::<Value>(text) {
        return value;
    }
    // 截取首个 { 或 [ 到最后一个 } 或 ] 之间的内容再尝试
    let start = [text.find('{'), text.find('[')]
        .into_iter()
        .flatten()
        .min();
    if let Some(start) = start {
        let end_char = if text[start..].starts_with('{') { '}' } else { ']' };
        if let Some(end) = text.rfind(end_char) {
            if end > start {
                if let Ok(value) = serde_json::from_str::<Value>(&text[start..=end]) {
                    return value;
                }
            }
        }
    }
    Value::String(text.to_string())
}

/// 提取模板中的 {{node_id.path}} 引用(text 为模板串时返回 (整段引用, 节点ID, 路径) 列表)
///
/// 引用语法: {{ node_id.path }}(节点ID后可跟点路径); 手工扫描等价 Python 正则
/// r"\{\{\s*([a-zA-Z0-9_\-]+)((?:\.[a-zA-Z0-9_\-]+)*)\s*\}\}"
fn find_var_refs(text: &str) -> Vec<(usize, usize, String, String)> {
    let bytes = text.as_bytes();
    let mut refs = Vec::new();
    let mut i = 0;
    while i + 1 < bytes.len() {
        if bytes[i] == b'{' && bytes[i + 1] == b'{' {
            // 跳过空白
            let mut j = i + 2;
            while j < bytes.len() && bytes[j].is_ascii_whitespace() {
                j += 1;
            }
            let id_start = j;
            while j < bytes.len()
                && (bytes[j].is_ascii_alphanumeric() || bytes[j] == b'_' || bytes[j] == b'-')
            {
                j += 1;
            }
            let id = &text[id_start..j];
            if id.is_empty() {
                i += 1;
                continue;
            }
            // 点路径(若干 ".name" 段)
            let path_start = j;
            while j < bytes.len() && bytes[j] == b'.' {
                let seg_start = j + 1;
                let mut k = seg_start;
                while k < bytes.len()
                    && (bytes[k].is_ascii_alphanumeric() || bytes[k] == b'_' || bytes[k] == b'-')
                {
                    k += 1;
                }
                if k == seg_start {
                    break;
                }
                j = k;
            }
            let path = &text[path_start..j];
            // 跳过空白后须紧跟 "}}"
            let mut k = j;
            while k < bytes.len() && bytes[k].is_ascii_whitespace() {
                k += 1;
            }
            if k + 1 < bytes.len() && bytes[k] == b'}' && bytes[k + 1] == b'}' {
                refs.push((i, k + 2, id.to_string(), path.to_string()));
                i = k + 2;
                continue;
            }
            i += 1;
        } else {
            i += 1;
        }
    }
    refs
}

/// 模板引用是否指向存在的节点(静态校验用)
fn ref_targets_exist(text: &str, node_map: &HashMap<&str, &Value>) -> Option<String> {
    for (_, _, ref_id, _) in find_var_refs(text) {
        if !node_map.contains_key(ref_id.as_str()) {
            return Some(ref_id);
        }
    }
    None
}

/// 静态校验工作流图, 返回错误列表(空列表=通过; 保存前与运行前均可调用)
pub fn validate_workflow(workflow: Option<&Value>) -> Vec<String> {
    let mut errors = Vec::new();
    let Some(workflow) = workflow.filter(|w| w.is_object() && !w.as_object().is_some_and(|o| o.is_empty()))
    else {
        return vec!["工作流图不能为空".to_string()];
    };
    let empty = Vec::new();
    let nodes = workflow.get("nodes").and_then(Value::as_array).unwrap_or(&empty);
    let edges = workflow.get("edges").and_then(Value::as_array).unwrap_or(&empty);

    // 节点基础校验
    let mut node_map: HashMap<&str, &Value> = HashMap::new();
    for n in nodes {
        let Some(obj) = n.as_object() else {
            errors.push("存在格式不合法的节点".to_string());
            continue;
        };
        let Some(nid) = obj.get("id").and_then(Value::as_str) else {
            errors.push("存在缺少 id 的节点".to_string());
            continue;
        };
        if node_map.contains_key(nid) {
            errors.push(format!("节点 ID 重复: {nid}"));
            continue;
        }
        let ntype = obj.get("type").and_then(Value::as_str).unwrap_or("");
        if !NODE_TYPES.contains(&ntype) {
            errors.push(format!("节点 {nid} 类型不合法: {ntype}"));
            continue;
        }
        node_map.insert(nid, n);
    }

    let starts = node_map.values().filter(|n| n["type"] == "start").count();
    let ends = node_map.values().filter(|n| n["type"] == "end").count();
    if starts != 1 {
        errors.push(format!("开始节点必须恰好 1 个, 当前 {starts} 个"));
    }
    if ends != 1 {
        errors.push(format!("结束节点必须恰好 1 个, 当前 {ends} 个"));
    }

    // 连线校验
    let mut valid_edges: Vec<(&str, &str)> = Vec::new();
    for e in edges {
        let Some(obj) = e.as_object() else {
            errors.push("存在格式不合法的连线".to_string());
            continue;
        };
        let src = obj.get("source").and_then(Value::as_str).unwrap_or("");
        let tgt = obj.get("target").and_then(Value::as_str).unwrap_or("");
        if !node_map.contains_key(src) || !node_map.contains_key(tgt) {
            errors.push(format!("连线端点不存在: {src} → {tgt}"));
            continue;
        }
        if src == tgt {
            errors.push(format!("节点 {src} 不能连接自身"));
            continue;
        }
        valid_edges.push((src, tgt));
        let is_condition = node_map[src]["type"] == "condition";
        if is_condition {
            let handle = obj.get("sourceHandle").and_then(Value::as_str).unwrap_or("");
            if handle != "true" && handle != "false" {
                errors.push(format!("条件节点 {src} 的出边必须使用 true/false 分支"));
            }
        }
    }

    // 条件节点必须同时具备 true/false 两条出边 + 数据校验; 模板引用的节点必须存在
    for (nid, n) in &node_map {
        let ntype = n["type"].as_str().unwrap_or("");
        let data = n.get("data").cloned().unwrap_or_else(|| json!({}));
        if ntype == "condition" {
            let handles: Vec<&str> = edges
                .iter()
                .filter_map(|e| e.as_object())
                .filter(|e| e.get("source").and_then(Value::as_str) == Some(*nid))
                .filter_map(|e| e.get("sourceHandle").and_then(Value::as_str))
                .collect();
            if !handles.contains(&"true") || !handles.contains(&"false") {
                errors.push(format!("条件节点 {nid} 必须同时连接 true 与 false 分支"));
            }
            let left_source = data.get("left_source").and_then(Value::as_str).unwrap_or("");
            if !node_map.contains_key(left_source) {
                errors.push(format!(
                    "条件节点 {nid} 的左值来源节点不存在: {left_source}"
                ));
            }
            let operator = data.get("operator").and_then(Value::as_str).unwrap_or("");
            if !CONDITION_OPERATORS.contains(&operator) {
                errors.push(format!("条件节点 {nid} 运算符不合法: {operator}"));
            }
        }
        // 模板引用校验(llm.prompt / template.template / end.result)
        let texts: Vec<String> = match ntype {
            "llm" => vec![data.get("prompt").and_then(Value::as_str).unwrap_or("").to_string()],
            "template" => vec![data.get("template").and_then(Value::as_str).unwrap_or("").to_string()],
            "end" => vec![data
                .get("result")
                .filter(|v| !v.is_null())
                .map(|v| v.to_string())
                .unwrap_or_default()],
            _ => vec![],
        };
        for text in texts {
            if let Some(missing) = ref_targets_exist(&text, &node_map) {
                errors.push(format!("节点 {nid} 引用了不存在的节点: {missing}"));
            }
        }
    }

    // 环检测(Kahn 拓扑): 一期仅支持 DAG
    let mut indegree: HashMap<&str, usize> = node_map.keys().map(|k| (*k, 0)).collect();
    let mut adjacency: HashMap<&str, Vec<&str>> = node_map.keys().map(|k| (*k, Vec::new())).collect();
    for (src, tgt) in &valid_edges {
        adjacency.get_mut(src).expect("邻接表已初始化").push(tgt);
        *indegree.get_mut(tgt).expect("入度表已初始化") += 1;
    }
    let mut queue: Vec<&str> = indegree
        .iter()
        .filter(|(_, deg)| **deg == 0)
        .map(|(nid, _)| *nid)
        .collect();
    let mut visited = 0usize;
    while let Some(cur) = queue.pop() {
        visited += 1;
        for nxt in adjacency.get(cur).expect("邻接表已初始化").clone() {
            let deg = indegree.get_mut(nxt).expect("入度表已初始化");
            *deg -= 1;
            if *deg == 0 {
                queue.push(nxt);
            }
        }
    }
    if visited != node_map.len() {
        errors.push("工作流存在循环连线, 暂不支持循环".to_string());
    }

    errors
}

/// 从数据中按点路径取值(路径未命中返回 None)
fn get_path<'a>(value: &'a Value, path: &str) -> Option<&'a Value> {
    let mut current = value;
    for part in path.split('.') {
        current = current.get(part)?;
    }
    Some(current)
}

/// 判断值是否为"空"(Python: None / "" / [] / {}, 注意 0 不算空)
fn is_empty_value(value: &Value) -> bool {
    match value {
        Value::Null => true,
        Value::String(s) => s.is_empty(),
        Value::Array(a) => a.is_empty(),
        Value::Object(o) => o.is_empty(),
        _ => false,
    }
}

/// 值的 Python 真值语义(条件分支激活判断用)
fn truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().map(|f| f != 0.0).unwrap_or(true),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

/// 值转比较文本(布尔统一为 true/false, 对齐 Python to_text)
fn to_text(value: &Value) -> String {
    match value {
        Value::Bool(true) => "true".to_string(),
        Value::Bool(false) => "false".to_string(),
        Value::String(s) => s.clone(),
        Value::Null => "None".to_string(),
        other => other.to_string(),
    }
}

/// 值转数值(失败返回 None, 对齐 Python to_num)
fn to_num(value: &Value) -> Option<f64> {
    match value {
        Value::Number(n) => n.as_f64(),
        Value::Bool(_) | Value::Null => None,
        Value::String(s) => s.trim().parse::<f64>().ok(),
        _ => None,
    }
}

/// 极简正则子串搜索(等价 Python re.search 的常用子集)
///
/// 支持: 字面量 / . / * / + / ? / [...] / ^ / $ / | / 分组捕获不影响结果 /
/// 转义 \\d \\w \\s \\D \\W \\S 与符号字面转义
fn regex_search(pattern: &str, text: &str) -> bool {
    // 拆分顶层 | 分支, 任一命中即成功
    let mut branches: Vec<Vec<Token>> = vec![Vec::new()];
    let mut depth = 0i32;
    let chars: Vec<char> = pattern.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        match c {
            '\\' if i + 1 < chars.len() => {
                // 逃逸序列与其后的量词一并解析(如 \d+ \w*)
                let base = escape_class(chars[i + 1]);
                i += 2;
                let token = with_quantifier(&chars, &mut i, base);
                branches.last_mut().expect("分支已初始化").push(token);
            }
            '(' => {
                depth += 1;
                i += 1;
            }
            ')' => {
                depth = (depth - 1).max(0);
                i += 1;
            }
            '|' if depth == 0 => {
                branches.push(Vec::new());
                i += 1;
            }
            _ => {
                branches.last_mut().expect("分支已初始化").push(parse_atom(&chars, &mut i));
            }
        }
    }
    let text_chars: Vec<char> = text.chars().collect();
    branches
        .iter()
        .any(|tokens| {
            (0..=text_chars.len())
                .any(|start| match_tokens(tokens, &text_chars, start).is_some())
        })
}

/// 正则 token(最小子集)
#[derive(Debug, Clone)]
enum Token {
    /// 单字符匹配
    Char(char),
    /// 任意字符(.)
    Any,
    /// 字符类(取反 + 条目: 单字符或范围)
    Class { negated: bool, items: Vec<(char, char)> },
    /// 前一原子重复 0..n
    Star(Box<Token>),
    /// 前一原子重复 1..n
    Plus(Box<Token>),
    /// 前一原子可选
    Quest(Box<Token>),
    /// 行首锚(^)
    Start,
    /// 行尾锚($)
    End,
}

/// 转义序列 → token(\\d \\w \\s \\D \\W \\S 及符号字面量)
fn escape_class(c: char) -> Token {
    match c {
        'd' => Token::Class { negated: false, items: vec![('0', '9')] },
        'D' => Token::Class { negated: true, items: vec![('0', '9')] },
        'w' => Token::Class {
            negated: false,
            items: vec![('a', 'z'), ('A', 'Z'), ('0', '9'), ('_', '_')],
        },
        'W' => Token::Class {
            negated: true,
            items: vec![('a', 'z'), ('A', 'Z'), ('0', '9'), ('_', '_')],
        },
        's' => Token::Class {
            negated: false,
            items: vec![(' ', ' '), ('\t', '\t'), ('\n', '\n'), ('\r', '\r')],
        },
        'S' => Token::Class {
            negated: true,
            items: vec![(' ', ' '), ('\t', '\t'), ('\n', '\n'), ('\r', '\r')],
        },
        'n' => Token::Char('\n'),
        't' => Token::Char('\t'),
        other => Token::Char(other),
    }
}

/// 为原子附加后缀量词(若有; 逃逸序列与字面量原子共用)
fn with_quantifier(chars: &[char], i: &mut usize, base: Token) -> Token {
    if *i < chars.len() {
        let quant = match chars[*i] {
            '*' => Some(Token::Star(Box::new(base.clone()))),
            '+' => Some(Token::Plus(Box::new(base.clone()))),
            '?' => Some(Token::Quest(Box::new(base.clone()))),
            _ => None,
        };
        if let Some(token) = quant {
            *i += 1;
            return token;
        }
    }
    base
}

/// 解析单个原子(含后缀量词; 返回后 i 已前移到下一字符)
fn parse_atom(chars: &[char], i: &mut usize) -> Token {
    let c = chars[*i];
    *i += 1;
    let base = match c {
        '.' => Token::Any,
        '^' => Token::Start,
        '$' => Token::End,
        '[' => {
            // 字符类: 支持 [^...] 与 a-z 范围与符号字面量
            let mut negated = false;
            if *i < chars.len() && chars[*i] == '^' {
                negated = true;
                *i += 1;
            }
            let mut items = Vec::new();
            while *i < chars.len() && chars[*i] != ']' {
                let lo = if chars[*i] == '\\' && *i + 1 < chars.len() {
                    // 类内转义(\\d 等展开为范围近似: 逐字符展开太重, 仅支持单字符转义)
                    let e = chars[*i + 1];
                    *i += 2;
                    match e {
                        'd' => {
                            items.push(('0', '9'));
                            continue;
                        }
                        'w' => {
                            items.extend([('a', 'z'), ('A', 'Z'), ('0', '9'), ('_', '_')]);
                            continue;
                        }
                        's' => {
                            items.push((' ', ' '));
                            items.push(('\t', '\t'));
                            items.push(('\n', '\n'));
                            continue;
                        }
                        other => other,
                    }
                } else {
                    let ch = chars[*i];
                    *i += 1;
                    ch
                };
                if *i + 1 < chars.len() && chars[*i] == '-' && chars[*i + 1] != ']' {
                    items.push((lo, chars[*i + 1]));
                    *i += 2;
                } else {
                    items.push((lo, lo));
                }
            }
            *i += 1; // 跳过 ']'
            Token::Class { negated, items }
        }
        other => Token::Char(other),
    };
    // 后缀量词
    with_quantifier(chars, i, base)
}

/// 单 token 匹配判断
fn token_matches(token: &Token, c: char) -> bool {
    match token {
        Token::Char(expected) => *expected == c,
        Token::Any => true,
        Token::Class { negated, items } => {
            let hit = items.iter().any(|(lo, hi)| c >= *lo && c <= *hi);
            hit != *negated
        }
        _ => false,
    }
}

/// 回溯匹配: 从 text[pos] 起匹配 tokens, 返回可停留的最远终点集合中的任一成功
fn match_tokens(tokens: &[Token], text: &[char], pos: usize) -> Option<usize> {
    let Some((first, rest)) = tokens.split_first() else {
        return Some(pos);
    };
    match first {
        Token::Start => {
            if pos == 0 {
                match_tokens(rest, text, pos)
            } else {
                None
            }
        }
        Token::End => {
            if pos == text.len() && rest.is_empty() {
                Some(pos)
            } else {
                None
            }
        }
        Token::Star(inner) => {
            // 贪心回溯: 先尽量多吃, 失败逐步吐出
            let mut ends = vec![pos];
            let mut cur = pos;
            while cur < text.len() && token_matches(inner, text[cur]) {
                cur += 1;
                ends.push(cur);
            }
            ends.into_iter().rev().find_map(|end| match_tokens(rest, text, end))
        }
        Token::Plus(inner) => {
            if pos < text.len() && token_matches(inner, text[pos]) {
                let tokens_starred = once_star(inner)
                    .into_iter()
                    .chain(rest.iter().cloned())
                    .collect::<Vec<_>>();
                match_tokens(&tokens_starred, text, pos)
            } else {
                None
            }
        }
        Token::Quest(inner) => {
            if pos < text.len() && token_matches(inner, text[pos]) {
                if match_tokens(rest, text, pos + 1).is_some() {
                    return Some(pos + 1);
                }
            }
            match_tokens(rest, text, pos)
        }
        token => {
            if pos < text.len() && token_matches(token, text[pos]) {
                match_tokens(rest, text, pos + 1)
            } else {
                None
            }
        }
    }
}

/// 构造 [Star(x)] 的等价序列(Plus 展开用)
fn once_star(inner: &Token) -> Vec<Token> {
    vec![Token::Star(Box::new(inner.clone()))]
}

/// 工作流执行引擎(拓扑驱动 + 节点轨迹)
pub struct WorkflowService;

impl WorkflowService {
    /// 执行工作流: 拓扑序驱动(可达性由条件分支动态决定), 返回(结束节点输出, 节点轨迹)
    ///
    /// :param agent_row: 工作流智能体(agent.workflow 为图定义)
    /// :param input: 开始节点输入; model_id 为 LLM 节点默认模型
    /// :raises: WorkflowExecError 节点失败即终止(错误携带已完成轨迹)
    pub async fn run_workflow(
        &self,
        state: &AppState,
        agent_row: &agent::Model,
        request: &AgentRunRequest,
    ) -> Result<(Value, Vec<NodeTrace>), WorkflowExecError> {
        let workflow = agent_row.workflow.clone().unwrap_or_else(|| json!({}));
        let empty = Vec::new();
        let nodes_list = workflow.get("nodes").and_then(Value::as_array).unwrap_or(&empty);
        let edges_list = workflow.get("edges").and_then(Value::as_array).unwrap_or(&empty);

        let mut nodes: HashMap<String, &Value> = HashMap::new();
        for n in nodes_list {
            if let Some(id) = n.get("id").and_then(Value::as_str) {
                nodes.insert(id.to_string(), n);
            }
        }
        let mut out_edges: HashMap<String, Vec<&Value>> = HashMap::new();
        let mut upstream: HashMap<String, Vec<String>> = HashMap::new();
        for e in edges_list {
            let (Some(src), Some(tgt)) = (
                e.get("source").and_then(Value::as_str),
                e.get("target").and_then(Value::as_str),
            ) else {
                continue;
            };
            if nodes.contains_key(src) && nodes.contains_key(tgt) {
                out_edges.entry(src.to_string()).or_default().push(e);
                upstream.entry(tgt.to_string()).or_default().push(src.to_string());
            }
        }

        let start = nodes
            .values()
            .find(|n| n["type"] == "start")
            .ok_or_else(|| WorkflowExecError::new("工作流缺少开始节点", vec![]))?;
        let end = nodes
            .values()
            .find(|n| n["type"] == "end")
            .ok_or_else(|| WorkflowExecError::new("工作流缺少结束节点", vec![]))?;

        // Kahn 拓扑排序: 保证可达上游均先于下游执行(环在保存校验拦截, 此处兜底)
        let mut indegree: HashMap<&str, usize> = nodes.keys().map(|k| (k.as_str(), 0)).collect();
        let mut adjacency: HashMap<&str, Vec<&str>> =
            nodes.keys().map(|k| (k.as_str(), Vec::new())).collect();
        for (src, targets) in &out_edges {
            for e in targets {
                let tgt = e["target"].as_str().expect("连线目标已校验");
                adjacency.get_mut(src.as_str()).expect("邻接表已初始化").push(tgt);
                *indegree.get_mut(tgt).expect("入度表已初始化") += 1;
            }
        }
        let mut queue: Vec<&str> = indegree
            .iter()
            .filter(|(_, deg)| **deg == 0)
            .map(|(nid, _)| *nid)
            .collect();
        let mut topo: Vec<String> = Vec::with_capacity(nodes.len());
        while let Some(cur) = queue.pop() {
            topo.push(cur.to_string());
            for nxt in adjacency.get(cur).expect("邻接表已初始化").clone() {
                let deg = indegree.get_mut(nxt).expect("入度表已初始化");
                *deg -= 1;
                if *deg == 0 {
                    queue.push(nxt);
                }
            }
        }
        if topo.len() != nodes.len() {
            return Err(WorkflowExecError::new("工作流存在循环连线, 暂不支持循环", vec![]));
        }

        let mut traces: Vec<NodeTrace> = Vec::new();
        let mut ctx: HashMap<String, Value> = HashMap::new();
        let mut active: std::collections::HashSet<String> =
            std::collections::HashSet::from([start["id"].as_str().expect("开始节点有 id").to_string()]);

        for node_id in &topo {
            if !active.contains(node_id) {
                continue; // 不可达节点(分支未命中路径)不执行
            }
            let node = nodes[node_id];
            let ntype = node["type"].as_str().unwrap_or("");
            let node_input: Value = match upstream.get(node_id) {
                Some(srcs) if !srcs.is_empty() => Value::Object(
                    srcs.iter()
                        .map(|src| (src.clone(), ctx.get(src).cloned().unwrap_or(Value::Null)))
                        .collect(),
                ),
                _ => Value::Null,
            };
            let mut trace = NodeTrace {
                node_id: node_id.clone(),
                node_type: ntype.to_string(),
                status: STATUS_SUCCESS.to_string(),
                input: (node_input != Value::Null).then_some(node_input),
                output: None,
                duration_ms: 0,
                error: None,
            };
            let started = Instant::now();
            let output = match self
                .execute_node(state, node, agent_row, request, &ctx, &traces)
                .await
            {
                Ok(output) => output,
                Err(e) => {
                    trace.status = STATUS_FAILED.to_string();
                    trace.error = Some(e.clone());
                    trace.duration_ms = started.elapsed().as_millis() as i64;
                    traces.push(trace);
                    return Err(WorkflowExecError::new(
                        format!("节点 {node_id}({ntype}) 执行失败: {e}"),
                        traces,
                    ));
                }
            };
            trace.output = Some(output.clone());
            trace.duration_ms = started.elapsed().as_millis() as i64;
            traces.push(trace);
            ctx.insert(node_id.clone(), output.clone());

            // 激活下游(条件节点仅激活布尔结果对应分支)
            for edge in out_edges.get(node_id).into_iter().flatten() {
                let target = edge["target"].as_str().expect("连线目标已校验");
                let hit = match ntype {
                    "condition" => {
                        let expected = if truthy(&output) { "true" } else { "false" };
                        edge["sourceHandle"].as_str() == Some(expected)
                    }
                    _ => true,
                };
                if hit {
                    active.insert(target.to_string());
                }
            }
        }

        match ctx.get(end["id"].as_str().expect("结束节点有 id")) {
            Some(output) => Ok((output.clone(), traces)),
            None => Err(WorkflowExecError::new(
                "结束节点不可达(分支路径未连通结束节点)",
                traces,
            )),
        }
    }

    /// 执行单个节点(按类型分发)
    #[allow(clippy::too_many_arguments)]
    async fn execute_node(
        &self,
        state: &AppState,
        node: &Value,
        agent_row: &agent::Model,
        request: &AgentRunRequest,
        ctx: &HashMap<String, Value>,
        traces: &[NodeTrace],
    ) -> Result<Value, String> {
        let ntype = node["type"].as_str().unwrap_or("");
        let data = node.get("data").cloned().unwrap_or_else(|| json!({}));
        match ntype {
            "start" => Ok(request.input.0.clone()),
            "llm" => self.run_llm_node(state, &data, agent_row, request, ctx).await,
            "condition" => evaluate_condition(&data, ctx).map(Value::Bool),
            "template" => resolve_value(data.get("template").and_then(Value::as_str).unwrap_or(""), ctx),
            "end" => {
                if let Some(result_text) = data.get("result").filter(|v| !v.is_null()) {
                    let text = result_text.as_str().map(str::to_string).unwrap_or_else(|| result_text.to_string());
                    return resolve_value(&text, ctx);
                }
                // 默认取最后一个成功的 LLM 节点输出
                for trace in traces.iter().rev() {
                    if trace.node_type == "llm" && trace.status == STATUS_SUCCESS {
                        return Ok(ctx.get(&trace.node_id).cloned().unwrap_or(Value::Null));
                    }
                }
                Err("结束节点未配置结果引用, 且工作流中没有已执行的 LLM 节点".to_string())
            }
            other => Err(format!("不支持的节点类型: {other}")),
        }
    }

    /// 执行 LLM 节点: prompt 模板插值 → 模型推理(str 直出 / json 结构化解析)
    async fn run_llm_node(
        &self,
        state: &AppState,
        data: &Value,
        agent_row: &agent::Model,
        request: &AgentRunRequest,
        ctx: &HashMap<String, Value>,
    ) -> Result<Value, String> {
        let prompt_value =
            resolve_value(data.get("prompt").and_then(Value::as_str).unwrap_or(""), ctx)?;
        // 提示词转文本形态(整串单引用透传的非字符串 JSON 序列化, 对齐 Python str() 语义)
        let mut user_content = match prompt_value {
            Value::String(s) => s,
            other => other.to_string(),
        };
        let model_id = data
            .get("model_id")
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty())
            .unwrap_or(&request.model_id);
        let target = module_ai::services::llm::get_llm(&state.db, model_id, false)
            .await
            .map_err(|e| e.to_string())?
            .ok_or_else(|| format!("模型配置不存在或不可用: {model_id}"))?;

        let output_type = data
            .get("output_type")
            .and_then(Value::as_str)
            .map(AgentIOType::parse)
            .unwrap_or(AgentIOType::Str);
        if output_type == AgentIOType::Json {
            if let Some(schema) = data.get("output_schema").filter(|v| !v.is_null()) {
                user_content += &format!(
                    "\n\n### 输出结构要求(必须严格遵循此 JSON Schema)\n{}",
                    serde_json::to_string(schema).unwrap_or_default()
                );
            } else {
                user_content += "\n\n### 输出结构要求\n输出合法的 JSON(对象或数组), 不要包含 Markdown 代码块标记。";
            }
        }
        let messages = vec![
            module_ai::do_::llm::Message {
                role: "system".to_string(),
                content: agent_row.system_prompt.clone(),
                additional_kwargs: Value::Null,
            },
            module_ai::do_::llm::Message {
                role: "user".to_string(),
                content: user_content,
                additional_kwargs: Value::Null,
            },
        ];
        if output_type == AgentIOType::Json {
            let content = module_ai::utils::llm::chat_once(&state.http, &target, &messages)
                .await
                .map_err(|e| e.to_string())?;
            Ok(parse_json_content(&content_text(&content)))
        } else {
            let content = module_ai::utils::llm::chat_once(&state.http, &target, &messages)
                .await
                .map_err(|e| e.to_string())?;
            // 对齐 Python: content 为字符串直出, 非字符串(分段数组)JSON 序列化为文本
            Ok(match content {
                Value::String(s) => Value::String(s),
                other => Value::String(other.to_string()),
            })
        }
    }
}

/// 提取模型响应文本(兼容 str/list 形态的 content)
pub fn content_text(content: &Value) -> String {
    match content {
        Value::String(s) => s.clone(),
        Value::Array(items) => items
            .iter()
            .map(|part| match part {
                Value::String(s) => s.clone(),
                Value::Object(_) => part
                    .get("text")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
                other => other.to_string(),
            })
            .collect(),
        Value::Null => String::new(),
        other => other.to_string(),
    }
}

/// 缺失路径的兜底空值(等价 Python None, 供条件左值路径回落)
static NULL_VALUE: Value = Value::Null;

/// 计算条件节点布尔结果(left_source.left_path 与 right 按 operator 比较)
fn evaluate_condition(data: &Value, ctx: &HashMap<String, Value>) -> Result<bool, String> {
    let left_source = data.get("left_source").and_then(Value::as_str).unwrap_or("");
    let left_value = ctx
        .get(left_source)
        .ok_or_else(|| format!("条件左值来源节点尚未执行: {left_source}"))?;
    let mut left = left_value;
    let left_path = data.get("left_path").and_then(Value::as_str).unwrap_or("");
    if !left_path.is_empty() {
        for part in left_path.split('.') {
            // Python 语义: 缺失键等价 None(空), 不视为错误; 仅来源节点未执行才报错
            left = left.get(part).unwrap_or(&NULL_VALUE);
        }
    }
    let op = data.get("operator").and_then(Value::as_str).unwrap_or("");
    let right = data.get("right").cloned().unwrap_or(Value::Null);

    match op {
        "empty" => Ok(is_empty_value(left)),
        "contains" => Ok(match left {
            Value::Array(items) => items.contains(&right),
            // Python 语义: right in dict 检查的是键
            Value::Object(map) => right.as_str().map(|k| map.contains_key(k)).unwrap_or(false),
            _ => to_text(left).contains(&to_text(&right)),
        }),
        "regex" => Ok(regex_search(&to_text(&right), &to_text(left))),
        "gt" | "gte" | "lt" | "lte" => {
            let (Some(left_num), Some(right_num)) = (to_num(left), to_num(&right)) else {
                return Err(format!(
                    "运算符 {op} 需要可比较的数值, 左值={} 右值={}",
                    to_text(left),
                    to_text(&right)
                ));
            };
            Ok(match op {
                "gt" => left_num > right_num,
                "gte" => left_num >= right_num,
                "lt" => left_num < right_num,
                _ => left_num <= right_num,
            })
        }
        // eq / ne: 数值可比按数值, 否则按文本(布尔统一为 true/false)
        "eq" | "ne" => {
            let equal = match (to_num(left), to_num(&right)) {
                (Some(a), Some(b)) => a == b,
                _ => to_text(left) == to_text(&right),
            };
            Ok(if op == "eq" { equal } else { !equal })
        }
        other => Err(format!("不支持的运算符: {other}")),
    }
}

/// 解析模板中的 {{node_id.path}} 引用
///
/// - 整串仅一个引用且完全匹配时透传原对象(可为 dict/list/标量)
/// - 否则做字符串插值(引用值非字符串时 JSON 序列化)
/// - 引用节点未执行或路径未命中时报错
fn resolve_value(text: &str, ctx: &HashMap<String, Value>) -> Result<Value, String> {
    let refs = find_var_refs(text);
    if refs.is_empty() {
        return Ok(Value::String(text.to_string()));
    }
    let lookup = |ref_id: &str, path: &str| -> Result<Value, String> {
        let value = ctx
            .get(ref_id)
            .ok_or_else(|| format!("引用的节点尚未执行: {ref_id}"))?;
        if path.is_empty() {
            return Ok(value.clone());
        }
        get_path(value, path.trim_start_matches('.'))
            .cloned()
            .ok_or_else(|| format!(
                "节点 {ref_id} 输出中不存在字段路径: {}",
                path.trim_start_matches('.')
            ))
    };
    if refs.len() == 1 && refs[0].0 == 0 && refs[0].1 == text.len() {
        return lookup(&refs[0].2, &refs[0].3);
    }
    let mut result = text.to_string();
    // 从后往前替换, 避免前文替换改变后续偏移
    for (start, end, ref_id, path) in refs.iter().rev() {
        let value = lookup(ref_id, path)?;
        let replacement = match value {
            Value::String(s) => s,
            other => serde_json::to_string(&other).unwrap_or_default(),
        };
        result.replace_range(*start..*end, &replacement);
    }
    Ok(Value::String(result))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use crate::do_::agent::AgentType;

    #[test]
    fn 围栏与杂质文本解析json() {
        assert_eq!(parse_json_content("{\"a\": 1}"), json!({"a": 1}));
        assert_eq!(
            parse_json_content("```json\n{\"a\": 1}\n```"),
            json!({"a": 1})
        );
        assert_eq!(parse_json_content("结果 [1, 2] 完"), json!([1, 2]));
        assert_eq!(parse_json_content("纯文本"), json!("纯文本"));
    }

    #[test]
    fn 变量引用扫描覆盖路径与空白() {
        let refs = find_var_refs("前缀 {{ n1.a.b }} 后缀 {{n2}}");
        assert_eq!(refs.len(), 2);
        assert_eq!(refs[0].2, "n1");
        assert_eq!(refs[0].3, ".a.b");
        assert_eq!(refs[1].2, "n2");
        assert_eq!(refs[1].3, "");
        assert!(find_var_refs("{{ }}").is_empty());
    }

    #[test]
    fn 模板解析整串透传与插值() {
        let mut ctx = HashMap::new();
        ctx.insert("n1".to_string(), json!({"a": {"b": 3}}));
        ctx.insert("n2".to_string(), json!("文本"));
        // 整串单引用透传原对象
        assert_eq!(resolve_value("{{ n1.a.b }}", &ctx).unwrap(), json!(3));
        assert_eq!(resolve_value("{{n1}}", &ctx).unwrap(), json!({"a": {"b": 3}}));
        // 插值: 非字符串 JSON 序列化
        assert_eq!(
            resolve_value("值: {{ n1.a.b }} / {{n2}}", &ctx).unwrap(),
            json!("值: 3 / 文本")
        );
        // 未执行节点报错
        assert!(resolve_value("{{ n9 }}", &ctx).is_err());
    }

    #[test]
    fn 条件运算符语义对齐python() {
        let mut ctx = HashMap::new();
        ctx.insert("n1".to_string(), json!({"score": 88, "tags": ["a"], "name": "x"}));
        let case = |op: &str, right: Value, path: &str| {
            evaluate_condition(
                &json!({"left_source": "n1", "left_path": path, "operator": op, "right": right}),
                &ctx,
            )
            .unwrap()
        };
        assert!(case("gt", json!(80), "score"));
        assert!(!case("lt", json!("80.5"), "score"));
        assert!(case("eq", json!("x"), "name"));
        assert!(case("contains", json!("a"), "tags"));
        assert!(case("empty", json!(null), "none"));
        assert!(case("ne", json!("y"), "name"));
        assert!(case("regex", json!("^x$"), "name"));
    }

    #[test]
    fn 极简正则支持常用子集() {
        assert!(regex_search("abc", "xxabcxx"));
        assert!(regex_search("^ab", "abc"));
        assert!(regex_search("c$", "abc"));
        assert!(regex_search("a.c", "abc"));
        assert!(regex_search("a+", "caaat"));
        assert!(regex_search("colou?r", "color"));
        assert!(regex_search("\\d+", "abc123"));
        assert!(regex_search("cat|dog", "hotdog"));
        assert!(!regex_search("^dog", "hotdog"));
        assert!(regex_search("A[0-9]B", "xA5B"));
        assert!(regex_search("[^0-9]+", "abc"));
    }

    #[test]
    fn 校验器覆盖缺节点与环() {
        // 空图
        assert_eq!(validate_workflow(None), vec!["工作流图不能为空".to_string()]);
        // 缺结束节点 + 条件缺分支
        let bad = json!({
            "nodes": [
                {"id": "s", "type": "start", "data": {}},
                {"id": "c", "type": "condition", "data": {"left_source": "s", "operator": "eq"}},
                {"id": "l", "type": "llm", "data": {"prompt": "hi {{ s }}"}}
            ],
            "edges": [
                {"source": "s", "target": "c"},
                {"source": "c", "target": "l", "sourceHandle": "true"}
            ]
        });
        let errors = validate_workflow(Some(&bad));
        assert!(errors.iter().any(|e| e.contains("结束节点必须恰好 1 个")));
        assert!(errors.iter().any(|e| e.contains("必须同时连接 true 与 false")));
        // 正常图
        let good = json!({
            "nodes": [
                {"id": "s", "type": "start", "data": {}},
                {"id": "e", "type": "end", "data": {"result": "{{ s }}"}}
            ],
            "edges": [{"source": "s", "target": "e"}]
        });
        assert!(validate_workflow(Some(&good)).is_empty());
        // 环
        let cycle = json!({
            "nodes": [
                {"id": "s", "type": "start", "data": {}},
                {"id": "e", "type": "end", "data": {}},
                {"id": "t", "type": "template", "data": {"template": "x"}}
            ],
            "edges": [
                {"source": "s", "target": "t"},
                {"source": "t", "target": "e"},
                {"source": "e", "target": "t"}
            ]
        });
        let errors = validate_workflow(Some(&cycle));
        assert!(errors.iter().any(|e| e.contains("循环连线")));
    }

    #[test]
    fn 智能体类型与工作流枚举解析() {
        assert_eq!(AgentType::parse("workflow"), AgentType::Workflow);
        assert_eq!(AgentType::parse("other"), AgentType::Simple);
        assert_eq!(AgentIOType::parse("json"), AgentIOType::Json);
        assert_eq!(AgentIOType::parse("str"), AgentIOType::Str);
    }
}
