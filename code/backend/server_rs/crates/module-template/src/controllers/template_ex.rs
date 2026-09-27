//! 扩展示例控制器(对齐 Python module_template/controller/template_ex.py)
//!
//! 路由前缀 /template/template-ex: multipart 上传 / SSE 流式返回 / WebSocket 聊天室。
//! 聊天室连接表为进程级全局状态(与 Python 模块级 dict 一致)。

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::Duration;

use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::Multipart;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use module_authorization::do_::entity::user;
use module_authorization::deps::{authorize, AuthUser};
use serde::Deserialize;
use tokio_stream::wrappers::IntervalStream;
use tokio_stream::StreamExt;

use common::utils::extract::AppQuery;
use common::runtime::AppState;
use common::utils::error::AppError;

/// template:template_ex 资源权限校验
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "template", "template_ex", act).await
}

/// 在线连接表: peer_id → (广播发送通道, 昵称)
type Connections = Mutex<HashMap<u64, (tokio::sync::mpsc::UnboundedSender<String>, String)>>;

/// 全局连接表(与 Python 模块级 active_connections 等价)
fn connections() -> &'static Connections {
    static CONNS: OnceLock<Connections> = OnceLock::new();
    CONNS.get_or_init(|| Mutex::new(HashMap::new()))
}

/// 连接ID分配器
static NEXT_PEER: AtomicU64 = AtomicU64::new(1);

/// 广播文本消息给所有在线连接(发送失败的连接直接移除, 与 Python 一致)
fn broadcast(message: &str) {
    let mut conns = connections().lock().expect("连接表锁");
    conns.retain(|_, (tx, _)| tx.send(message.to_string()).is_ok());
}

/// POST /upload —— 读取上传文件到内存并返回文件名/类型/大小等基础信息(不做持久化)
pub async fn upload_file(
    AuthUser(actor): AuthUser,
    mut multipart: Multipart,
) -> Result<Json<serde_json::Value>, AppError> {
    require_perm(&actor, "create").await?;
    // 与 FastAPI File(...) 语义一致: 读取名为 file 的字段
    while let Some(field) = multipart
        .next_field()
        .await
        .map_err(|e| AppError::Internal(format!("读取上传内容失败: {e}")))?
    {
        if field.name() != Some("file") {
            continue;
        }
        let filename = field.file_name().map(|s| s.to_string());
        let content_type = field.content_type().map(|s| s.to_string());
        let data = field
            .bytes()
            .await
            .map_err(|e| AppError::Internal(format!("读取文件失败: {e}")))?;
        return Ok(Json(serde_json::json!({
            "filename": filename,
            "content_type": content_type,
            "size": data.len(),
            "message": "File uploaded successfully",
        })));
    }
    // 缺少 file 字段 → 422(与 FastAPI 必填校验一致)
    Err(AppError::Validation(vec![common::utils::error::ValidationErrorItem {
        loc: vec!["body".to_string(), "file".to_string()],
        msg: "Field required".to_string(),
        error_type: "missing".to_string(),
    }]))
}

/// GET /stream —— 流式返回 10 条事件(每条间隔 0.5 秒, SSE)
pub async fn stream(AuthUser(actor): AuthUser) -> Result<Response, AppError> {
    require_perm(&actor, "read").await?;
    // tokio interval 首个 tick 立即触发, 与 Python 先发一条再 sleep 一致;
    // tokio_stream::StreamExt 无 enumerate, 用 FnMut 计数器闭包等价实现序号递增
    let mut counter = 0u64;
    let stream = IntervalStream::new(tokio::time::interval(Duration::from_millis(500)))
        .take(10)
        .map(move |_| -> Result<axum::response::sse::Event, std::convert::Infallible> {
            let i = counter;
            counter += 1;
            Ok(axum::response::sse::Event::default().data(
                serde_json::json!({ "event": "message", "data": i.to_string() }).to_string(),
            ))
        });
    Ok(axum::response::sse::Sse::new(stream).into_response())
}

/// WebSocket 握手查询参数
#[derive(Debug, Deserialize)]
pub struct WsQuery {
    /// 聊天昵称(默认 "匿名")
    #[serde(default)]
    pub name: Option<String>,
}

/// GET /ws —— WebSocket 聊天室(加入广播/消息广播/离开广播)
pub async fn websocket_endpoint(
    AuthUser(actor): AuthUser,
    AppQuery(q): AppQuery<WsQuery>,
    ws: WebSocketUpgrade,
) -> Result<Response, AppError> {
    require_perm(&actor, "read").await?;
    let name = q.name.unwrap_or_else(|| "匿名".to_string());
    Ok(ws.on_upgrade(move |socket| handle_socket(socket, name)))
}

/// 处理单个聊天连接: 注册到连接表 → 广播上线 → 双路收发 → 断开后广播离开
///
/// 说明: 为避免为 WebSocket split 单独引入 futures-util 依赖, 用 tokio::select!
/// 在单循环内同时处理"客户端下行"与"广播队列上行", 行为与 split 双任务等价。
async fn handle_socket(mut socket: WebSocket, name: String) {
    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<String>();
    let peer = NEXT_PEER.fetch_add(1, Ordering::Relaxed);
    connections()
        .lock()
        .expect("连接表锁")
        .insert(peer, (tx, name.clone()));
    tracing::info!("用户 {name} 加入聊天室");
    broadcast(
        &serde_json::json!({ "sender": "系统", "message": format!("{name} 加入了聊天室") })
            .to_string(),
    );

    // 单循环双路 select: 客户端消息→广播; 广播队列→本连接; 任一路结束即断开
    loop {
        tokio::select! {
            incoming = socket.recv() => {
                match incoming {
                    // 收到文本消息 → 广播给所有连接(Utf8Bytes 转 String 参与序列化)
                    Some(Ok(Message::Text(text))) => {
                        tracing::info!("[{name}] {text}");
                        broadcast(
                            &serde_json::json!({ "sender": name, "message": text.to_string() })
                                .to_string(),
                        );
                    }
                    // None(客户端断开) / Close 帧 / 传输错误 → 结束循环
                    _ => break,
                }
            }
            out = rx.recv() => {
                match out {
                    Some(msg) => {
                        if socket.send(Message::Text(msg.into())).await.is_err() {
                            break;
                        }
                    }
                    // 所有发送端关闭(理论不可达, 本循环持有 tx) → 结束循环
                    None => break,
                }
            }
        }
    }

    // 连接断开: 移除并广播离开
    connections().lock().expect("连接表锁").remove(&peer);
    tracing::info!("用户 {name} 离开聊天室");
    broadcast(
        &serde_json::json!({ "sender": "系统", "message": format!("{name} 离开了聊天室") })
            .to_string(),
    );
}

/// 扩展示例子路由(nest 到 /template/template-ex 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/upload", post(upload_file))
        .route("/stream", get(stream))
        .route("/ws", get(websocket_endpoint))
}
