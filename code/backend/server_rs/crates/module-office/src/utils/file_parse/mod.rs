//! 解析器工厂(对齐 Python utils/file_parase/factory.py 的后缀注册表与 FileType 分类)
//!
//! 二进制版式文档(pdf/doc/docx/ppt/pptx)走 MinerU 引擎(远程 mineru.net API
//! 或本地 docker 部署, 配置 mineru.mode; 对齐 Python 侧默认引擎);
//! xlsx 的 docling 引擎在 Rust 服务未实现; 文本与代码后缀由原生解析器处理。

use common::utils::error::AppError;

use crate::do_::chunk::Chunk;

pub mod code;
pub mod markdown;
pub mod mineru;

/// docling 引擎未实现的二进制格式错误(文案对齐任务约定)
pub fn docling_unsupported() -> AppError {
    AppError::business("文档解析引擎未支持该格式(docling 引擎未在 Rust 服务实现)")
}

/// 字节流转文本(剥离 UTF-8 BOM; 非 UTF-8 内容按 lossy 兜底,
/// 对齐 Python 的 utf-8-sig/utf-8/gb18030 编码尝试链, gb18030 支持未引入编码库)
pub fn decode_bytes(bytes: &[u8]) -> String {
    if bytes.starts_with(&[0xEF, 0xBB, 0xBF]) {
        return String::from_utf8_lossy(&bytes[3..]).into_owned();
    }
    String::from_utf8_lossy(bytes).into_owned()
}

/// 按上传文件名提取小写后缀(含点, 如 ".py"; 对齐 pathlib.Path.suffix + lower())
///
/// 无后缀/隐藏文件(如 ".bashrc")返回空串; 路径分隔符 '/' 与 '\' 均处理。
pub fn suffix_lower(filename: &str) -> String {
    let file = filename.rsplit(['/', '\\']).next().unwrap_or(filename);
    let dot = match file.rfind('.') {
        // 点在首位且无其他点 → pathlib 视为无后缀的隐藏文件
        Some(i) if i != 0 => i,
        _ => return String::new(),
    };
    format!(".{}", file[dot + 1..].to_lowercase())
}

/// 文件类型分类(对齐 Python do/schemas.py 的 FileType 判定方法)
pub struct FileType;

impl FileType {
    /// 是否为支持解析的文本文档类型
    pub fn is_document(ext: &str) -> bool {
        matches!(
            ext,
            ".pdf" | ".docx" | ".pptx" | ".xlsx" | ".md" | ".markdown" | ".csv" | ".txt"
                | ".py" | ".java"
        )
    }

    /// 是否为支持语义拆分的源代码文件
    pub fn is_code(ext: &str) -> bool {
        matches!(ext, ".py" | ".java")
    }

    /// 是否为图片文件
    pub fn is_image(ext: &str) -> bool {
        matches!(ext, ".png" | ".jpg" | ".jpeg" | ".tiff")
    }

    /// 是否为音频文件
    pub fn is_audio(ext: &str) -> bool {
        matches!(ext, ".mp3" | ".wav")
    }

    /// 是否为视频文件
    pub fn is_video(ext: &str) -> bool {
        matches!(ext, ".mp4" | ".avi")
    }
}

/// 解析器工厂: 按后缀路由到对应解析器(对齐 ParserFactory.create + docling 注册表)
///
/// :param filename: 上传文件原始名(按后缀路由)
/// :param bytes: 文件内容
/// :return: 分块列表
pub async fn create_and_extract(filename: &str, bytes: &[u8]) -> Result<Vec<Chunk>, AppError> {
    let ext = suffix_lower(filename);
    match ext.as_str() {
        // 文本类: Rust 原生 Markdown/文本解析器
        ".md" | ".markdown" | ".csv" | ".txt" => markdown::extract(bytes),
        // 代码: 语义分块解析器
        ".py" | ".java" => code::extract(&ext, bytes, filename),
        // 版式文档: MinerU 引擎(远程/本地双支持, 对齐 Python 默认引擎)
        ".pdf" | ".docx" | ".doc" | ".pptx" | ".ppt" => mineru::parser::extract(filename, bytes).await,
        // xlsx: docling 引擎未在 Rust 服务实现
        ".xlsx" => Err(docling_unsupported()),
        _ => Err(AppError::business(format!("不支持的文件类型: {ext}"))),
    }
}
