//! module-task 请求/响应类型层(对齐 Python module_task/do/)

// 表模型层(sea-orm 实体, 对齐 Python do/task.py 的表模型部分)
pub mod entity;

// 请求/响应 DTO 层(对齐 Python do/task.py 的 schema 部分)
pub mod task;
