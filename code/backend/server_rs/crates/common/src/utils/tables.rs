//! 表级运维注册中心(对齐 Python db_rel.create_all / drop_all)
//!
//! Python 侧由 SQLModel.metadata 统一建/删表; Rust 侧实体分散在各模块 do/entity/ 后,
//! 改为"模块注册 + 公共注册中心"聚合:
//! - 各模块 lib.rs 的 register_tables() 声明本模块表(app 启动期统一调用)
//! - create_all: Schema::create_table_from_entity 逐实体建表(if_not_exists 幂等)
//! - drop_all: DROP TABLE IF EXISTS ... CASCADE(postgres)/ 普通删除(sqlite)
//!
//! 当前全部实体均未声明外键 Relation, 删表顺序无关。

use sea_orm::{ConnectionTrait, DatabaseConnection, DbBackend, DbErr, Statement};
use std::sync::Mutex;

/// 建表语句构造器(实体类型在模块侧, 以 fn 指针注册)
pub type EntityCreateFn = fn(&sea_orm::Schema) -> sea_orm::sea_query::TableCreateStatement;

/// 全局表注册表(表名, 建表构造器)
static REGISTRY: Mutex<Vec<(&'static str, EntityCreateFn)>> = Mutex::new(Vec::new());

/// 注册模块表(各模块 register_tables 内调用; 表名需与实体 table_name 一致)
pub fn register(name: &'static str, create: EntityCreateFn) {
    REGISTRY.lock().expect("表注册表锁").push((name, create));
}

/// 全量建表(if_not_exists 幂等, 已存在的表跳过)
pub async fn create_all(db: &DatabaseConnection) -> Result<(), DbErr> {
    let backend = db.get_database_backend();
    let schema = sea_orm::Schema::new(backend);
    // 拷贝出注册表再执行, 避免跨 await 持有标准互斥锁
    let creates: Vec<EntityCreateFn> =
        REGISTRY.lock().expect("表注册表锁").iter().map(|(_, f)| *f).collect();
    for create in creates {
        let mut stmt = create(&schema);
        stmt.if_not_exists();
        db.execute(backend.build(&stmt)).await?;
    }
    Ok(())
}

/// 全量删表(重置数据库用; postgres 带 CASCADE 解除依赖)
pub async fn drop_all(db: &DatabaseConnection) -> Result<(), DbErr> {
    let names: Vec<String> =
        REGISTRY.lock().expect("表注册表锁").iter().map(|(name, _)| name.to_string()).collect();
    for name in names {
        let sql = match db.get_database_backend() {
            DbBackend::Postgres => format!("DROP TABLE IF EXISTS \"{name}\" CASCADE"),
            _ => format!("DROP TABLE IF EXISTS \"{name}\""),
        };
        db.execute(Statement::from_string(db.get_database_backend(), sql)).await?;
    }
    Ok(())
}
