-- 示例模板表结构
CREATE TABLE template (
    pid VARCHAR(255),
    value INTEGER NOT NULL,
    name VARCHAR(100),
    description VARCHAR(500),
    is_active BOOLEAN,
    id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id)
);