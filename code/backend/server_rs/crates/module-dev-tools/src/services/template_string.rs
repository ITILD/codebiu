//! 模板字符串服务: 语法校验/标签提取/渲染(string.Template 等价实现)与管理编排

use std::collections::HashMap;

use sea_orm::DatabaseConnection;

use crate::do_::entity::template_string;

use common::utils::error::AppError;
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};

use crate::dao;
use crate::do_::template_string::{
    TemplateRenderRequest, TemplateRenderResponse, TemplateStringCreate, TemplateStringUpdate,
    TemplateValidateResponse,
};

/// 创建模板字符串(语法无效时 400 业务错误; 未提供 tags 时从内容提取)
///
/// :return: 新建记录ID
pub async fn add(
    db: &DatabaseConnection,
    data: TemplateStringCreate,
) -> Result<String, AppError> {
    // 语法校验(无效时拒绝创建, 返回 400)
    let validation = validate_template_syntax(&data.template_content);
    if !validation.valid {
        return Err(AppError::business(validation.message));
    }
    // 未提供 tags(缺省/null/空列表)时从模板内容提取, 对齐 Python service.add
    let tags = resolve_tags(data.tags.as_ref(), &data.template_content);
    dao::template_string::add(db, data, tags).await
}

/// 更新模板字符串(显式传入内容时先校验语法; 不存在 404)
pub async fn update(
    db: &DatabaseConnection,
    template_string_id: &str,
    data: TemplateStringUpdate,
) -> Result<(), AppError> {
    // 更新前校验模板语法(仅显式传入内容时; Python 侧该字段必填, 未传在反序列化层报 422)
    if let Some(content) = &data.template_content {
        let validation = validate_template_syntax(content);
        if !validation.valid {
            return Err(AppError::business(validation.message));
        }
    }
    dao::template_string::update(db, template_string_id, data).await
}

/// 渲染模板(优先用请求体内容, 未提供内容时按ID读库; 两者均缺省 400)
pub async fn render(
    db: &DatabaseConnection,
    request: TemplateRenderRequest,
) -> Result<TemplateRenderResponse, AppError> {
    let has_content = request
        .template_content
        .as_deref()
        .is_some_and(|c| !c.is_empty());
    let has_id = request.template_id.as_deref().is_some_and(|s| !s.is_empty());
    let mut template_content = request.template_content.clone();
    // 提供模板ID且未直接给内容时, 从数据库获取模板内容
    if has_id && !has_content {
        let template = dao::template_string::get(
            db,
            request.template_id.as_deref().unwrap_or_default(),
        )
        .await?
        .ok_or_else(|| {
            AppError::not_found(format!(
                "未找到ID为 {} 的模板",
                request.template_id.clone().unwrap_or_default()
            ))
        })?;
        template_content = Some(template.template_content);
    } else if !has_content {
        // 两者均缺省 → 400(对齐 Python ValueError 全局处理)
        return Err(AppError::business("必须提供模板ID或模板内容"));
    }
    let content = template_content.unwrap_or_default();

    // 提取模板变量并划分已使用/缺失
    let template_variables = extract_template_variables(&content);
    let mut variables_used = Vec::new();
    let mut variables_missing = Vec::new();
    for var in template_variables {
        if request.variables.contains_key(&var) {
            variables_used.push(var);
        } else {
            variables_missing.push(var);
        }
    }
    // 渲染模板(缺失变量按原样保留)
    let rendered_content = safe_substitute(&content, &request.variables);
    Ok(TemplateRenderResponse {
        rendered_content,
        template_id: request.template_id,
        variables_used,
        variables_missing,
    })
}

/// 校验模板语法(端点直接复用纯函数)
pub async fn validate(
    template_content: &str,
) -> Result<TemplateValidateResponse, AppError> {
    Ok(validate_template_syntax(template_content))
}

/// 查询单条模板字符串(不存在时由控制器决定 404 语义)
pub async fn get(
    db: &DatabaseConnection,
    template_string_id: &str,
) -> Result<Option<template_string::Model>, AppError> {
    dao::template_string::get(db, template_string_id).await
}

/// 删除模板字符串(不存在 404)
pub async fn delete(
    db: &DatabaseConnection,
    template_string_id: &str,
) -> Result<(), AppError> {
    dao::template_string::delete(db, template_string_id).await
}

/// 无限滚动查询(游标过滤与排序在 dao 层, 此处组装响应)
pub async fn scroll(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
) -> Result<InfiniteScrollResponse<template_string::Model>, AppError> {
    let items = dao::template_string::scroll(db, params).await?;
    Ok(InfiniteScrollResponse::create(
        items,
        params.limit,
        params.direction,
        |m| m.id.clone(),
    ))
}

/// 分页查询模板字符串列表(total 为全表总数)
pub async fn list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
) -> Result<PaginationResponse<template_string::Model>, AppError> {
    let total = dao::template_string::count_all(db).await?;
    let items = dao::template_string::list_paged(db, pagination).await?;
    Ok(PaginationResponse::create(items, total, pagination))
}

/// 解析创建时的 tags: 未传/显式 null/空列表 → 从模板内容提取
fn resolve_tags(tags: Option<&Option<Vec<String>>>, content: &str) -> serde_json::Value {
    match tags {
        Some(Some(list)) if !list.is_empty() => serde_json::Value::Array(
            list.iter().map(|t| serde_json::Value::String(t.clone())).collect(),
        ),
        _ => serde_json::Value::Array(
            extract_tags_from_content(content)
                .into_iter()
                .map(serde_json::Value::String)
                .collect(),
        ),
    }
}

/// 校验模板语法并提取变量(对齐 Python validate_template_syntax: 语法错误不抛异常)
pub fn validate_template_syntax(template_content: &str) -> TemplateValidateResponse {
    // Python string.Template 构造几乎不会失败, 这里等价返回 valid=true
    let variables = extract_template_variables(template_content);
    TemplateValidateResponse {
        valid: true,
        variables,
        message: "模板语法正确".to_string(),
    }
}

/// 从模板内容提取标签(Python 正则 \${(\w+)}: ${} 内须为 \w 单词字符, 去重)
pub fn extract_tags_from_content(content: &str) -> Vec<String> {
    extract_template_variables(content)
        .into_iter()
        .filter(|name| name.chars().all(is_word_char))
        .collect()
}

/// Python \w 单词字符(unicode 字母/数字/下划线)
fn is_word_char(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}

/// 从模板内容提取 ${...} 变量名(对齐 Python 正则 \${([^}]+)}, 去重, 保留首现顺序)
pub fn extract_template_variables(content: &str) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    let mut rest = content;
    while let Some(start) = rest.find("${") {
        let after = &rest[start + 2..];
        match after.find('}') {
            // [^}]+ 至少一个字符
            Some(end) if end > 0 => {
                let name = &after[..end];
                if !out.iter().any(|v| v == name) {
                    out.push(name.to_string());
                }
                rest = &after[end + 1..];
            }
            Some(_) => {
                // 空占位 ${}: 跳过 "${" 继续扫描
                rest = after;
            }
            None => break,
        }
    }
    out
}

/// Python string.Template.safe_substitute 等价实现:
/// $$ → $; ${id} / $id → 变量值(缺失按原样保留); 非法占位原样输出。
///
/// 标识符规则对齐 string.Template: ASCII [_a-zA-Z][_a-zA-Z0-9]*(IGNORECASE + (?a:))。
pub fn safe_substitute(template: &str, variables: &HashMap<String, String>) -> String {
    let chars: Vec<char> = template.chars().collect();
    let mut out = String::with_capacity(template.len());
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c != '$' {
            out.push(c);
            i += 1;
            continue;
        }
        if i + 1 >= chars.len() {
            // 末尾孤立 $: 原样保留
            out.push('$');
            break;
        }
        let next = chars[i + 1];
        if next == '$' {
            // $$ 转义为 $
            out.push('$');
            i += 2;
        } else if next == '{' {
            // 尝试解析 {id}
            let mut j = i + 2;
            while j < chars.len() && is_id_char(chars[j]) {
                j += 1;
            }
            if j > i + 2 && j < chars.len() && chars[j] == '}' {
                let name: String = chars[i + 2..j].iter().collect();
                match variables.get(&name) {
                    Some(v) => out.push_str(v),
                    None => {
                        // 缺失变量: 原样保留
                        out.push_str("${");
                        out.push_str(&name);
                        out.push('}');
                    }
                }
                i = j + 1;
            } else {
                // 非法占位: 输出 $ 后从下一字符继续(与 Python safe_substitute 一致)
                out.push('$');
                i += 1;
            }
        } else if is_id_start(next) {
            // 解析裸标识符 $id
            let mut j = i + 1;
            while j < chars.len() && is_id_char(chars[j]) {
                j += 1;
            }
            let name: String = chars[i + 1..j].iter().collect();
            match variables.get(&name) {
                Some(v) => out.push_str(v),
                None => {
                    out.push('$');
                    out.push_str(&name);
                }
            }
            i = j;
        } else {
            // $ 后跟非标识符字符: 原样输出 $
            out.push('$');
            i += 1;
        }
    }
    out
}

/// 标识符起始字符(ASCII 字母或下划线)
fn is_id_start(c: char) -> bool {
    c.is_ascii_alphabetic() || c == '_'
}

/// 标识符后续字符(ASCII 字母/数字或下划线)
fn is_id_char(c: char) -> bool {
    is_id_start(c) || c.is_ascii_digit()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extract_variables_dedup_and_order() {
        let vars = extract_template_variables("hello ${name} and ${age} again ${name}${x}");
        assert_eq!(vars, vec!["name", "age", "x"]);
        // 空占位与未闭合不产生变量
        assert!(extract_template_variables("${} ${abc").is_empty());
    }

    #[test]
    fn safe_substitute_matches_python_template() {
        let mut vars = HashMap::new();
        vars.insert("name".to_string(), "张三".to_string());
        vars.insert("n".to_string(), "42".to_string());
        // 基本替换 + 缺失保留 + $$ 转义 + 非法占位保留
        assert_eq!(safe_substitute("${name} $n $$ ${missing}", &vars), "张三 42 $ ${missing}");
        assert_eq!(safe_substitute("$name", &vars), "张三");
        assert_eq!(safe_substitute("$ name", &vars), "$ name");
        assert_eq!(safe_substitute("end$", &vars), "end$");
        // 裸标识符后紧邻标点
        assert_eq!(safe_substitute("$n.", &vars), "42.");
    }

    #[test]
    fn extract_tags_requires_word_chars() {
        assert_eq!(extract_tags_from_content("${a_1}${中文}${x y}"), vec!["a_1", "中文"]);
    }

    #[test]
    fn validate_syntax_always_valid_with_variables() {
        let r = validate_template_syntax("${v1}");
        assert!(r.valid);
        assert_eq!(r.variables, vec!["v1"]);
        assert_eq!(r.message, "模板语法正确");
    }
}
