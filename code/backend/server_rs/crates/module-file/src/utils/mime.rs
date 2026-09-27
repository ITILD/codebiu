//! MIME 类型推断(对齐 Python mimetypes + config/filetype.py 的扩展名补充)

/// 按扩展名推断 MIME 类型(未知返回 None)
///
/// mime_guess 内置 mime-db 覆盖 Office Open XML(docx/xlsx/pptx)与常见源码类型,
/// 与 Python 侧 mimetypes.add_type 补充后的行为一致
pub fn guess(filename: &str) -> Option<String> {
    mime_guess::from_path(filename)
        .first()
        .map(|m| m.to_string())
}
