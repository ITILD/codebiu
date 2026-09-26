"""配置分层加载测试(common/config/index)

覆盖: 深合并语义 / 层级文件解析(指针缺失告警跳过 / CONFIG_PATH 缺失失败) /
Dynaconf 注入 + CODEBIU_* 环境变量键级覆盖(最高优先级, 自动类型转换)
"""
from pathlib import Path

import pytest
import yaml

from common.config.index import (
    _deep_merge,
    _load_merged,
    _read_layer,
    _resolve_layer_files,
)


# ==================== 深合并语义 ====================

def test_deep_merge_nested_dict():
    """嵌套 dict 逐键递归合并(覆盖层只写需要覆盖的键)"""
    base = {"a": {"x": 1, "y": 2, "sub": {"k": "v"}}, "keep": True}
    overlay = {"a": {"y": 20, "sub": {"k2": "v2"}}}
    merged = _deep_merge(base, overlay)
    assert merged == {"a": {"x": 1, "y": 20, "sub": {"k": "v", "k2": "v2"}}, "keep": True}


def test_deep_merge_list_and_scalar_replaced():
    """list 与标量整体替换(不拼接)"""
    base = {"lst": [1, 2, 3], "s": "old", "n": 1}
    overlay = {"lst": [9], "s": "new", "n": "1"}
    assert _deep_merge(base, overlay) == {"lst": [9], "s": "new", "n": "1"}


# ==================== 单层文件读取 ====================

def test_read_layer_empty_and_invalid(tmp_path: Path):
    """空文件视为空层; 顶层非映射报错"""
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    assert _read_layer(empty) == {}

    invalid = tmp_path / "bad.yaml"
    invalid.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="键值映射"):
        _read_layer(invalid)


# ==================== 层级文件解析 ====================

def _write_base(tmp_path: Path, pointer: str | None) -> Path:
    state = {"is_dev": True}
    if pointer:
        state["config_path"] = pointer
    base = tmp_path / "config.yaml"
    base.write_text(yaml.safe_dump({"state": state}), encoding="utf-8")
    return base


def test_resolve_layers_pointer_missing_warns_skips(tmp_path: Path, monkeypatch, caplog):
    """state.config_path 指向不存在的文件: 告警并跳过(新克隆环境不阻塞)"""
    monkeypatch.chdir(tmp_path)  # 隔离真实环境的 config.seed.yaml 等约定文件
    base = _write_base(tmp_path, "not_exist.yaml")
    with caplog.at_level("WARNING"):
        files = _resolve_layer_files(base)
    assert files == [base]
    assert any("not_exist.yaml" in r.message for r in caplog.records)


def test_resolve_layers_pointer_ok_and_env_missing_fails(tmp_path: Path, monkeypatch):
    """指针存在则追加; CONFIG_PATH 显式指定的文件缺失则失败(防止生产静默回退)"""
    monkeypatch.chdir(tmp_path)  # 覆盖层按启动工作目录相对路径解析
    overlay = tmp_path / "dev.yaml"
    overlay.write_text("token:\n  expire_minutes: 99\n", encoding="utf-8")
    base = _write_base(tmp_path, "dev.yaml")
    assert [f.resolve() for f in _resolve_layer_files(base)] == [base.resolve(), overlay.resolve()]

    monkeypatch.setenv("CONFIG_PATH", " nope1.yaml , nope2.yaml ")
    with pytest.raises(FileNotFoundError):
        _resolve_layer_files(base)


# ==================== 合并加载 + Dynaconf 注入 ====================

def _write_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _build(files: list[Path], env: dict[str, str] | None = None):
    """用与 index._build_conf 相同的注入链构建临时 conf(测后还原环境变量)"""
    import os

    saved = {k: os.environ.get(k) for k in (env or {})}
    for k, v in (env or {}).items():
        os.environ[k] = v
    try:
        from dynaconf import Dynaconf

        conf = Dynaconf(envvar_prefix="CODEBIU")
        conf.update(_load_merged(files))
        conf.execute_loaders()
        return conf
    finally:
        for k, old in saved.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old


def test_load_merged_and_env_override(tmp_path: Path):
    """多层深合并 + CODEBIU_* 环境变量最高优先级(字符串自动转数值)"""
    base = _write_yaml(
        tmp_path / "config.yaml",
        {
            "state": {"is_dev": True},
            "token": {"algorithm": "HS256", "expire_minutes": 30, "secret_key": "base"},
            "websearch": {"timeout": 15, "max_results": 10, "tavily": {"api_key": ""}},
        },
    )
    dev = _write_yaml(
        tmp_path / "config.dev.yaml",
        {"token": {"expire_minutes": 60}, "websearch": {"timeout": 99}},  # 部分覆盖, 不丢兄弟键
    )
    conf = _build([base, dev])
    assert conf.state.is_dev is True
    assert conf.get("token").get("algorithm") == "HS256"  # 兄弟键保留
    assert conf.get("token").get("expire_minutes") == 60
    assert conf.get("websearch").get("max_results") == 10  # 部分覆盖不丢兄弟键
    assert conf.get("websearch").get("timeout") == 99
    assert conf.get("websearch").get("tavily").get("api_key") == ""  # 嵌套子组深合并

    # 环境变量键级覆盖(最高优先级) + 类型转换
    conf2 = _build([base, dev], env={"CODEBIU_TOKEN__SECRET_KEY": "env-key", "CODEBIU_TOKEN__EXPIRE_MINUTES": "45"})
    assert conf2.get("token").get("secret_key") == "env-key"
    assert conf2.get("token").get("expire_minutes") == 45
    assert isinstance(conf2.get("token").get("expire_minutes"), int)


# ==================== 约定种子层(config.seed.yaml) ====================

def test_resolve_layers_seed_convention(tmp_path: Path, monkeypatch):
    """种子文件存在则插入基线与指针覆盖层之间; 缺失属正常(跳过)"""
    monkeypatch.chdir(tmp_path)  # SEED_FILE 相对启动工作目录解析
    seed = tmp_path / "config.seed.yaml"
    seed.write_text("token:\n  expire_minutes: 88\n", encoding="utf-8")
    overlay = tmp_path / "dev.yaml"
    overlay.write_text("token:\n  expire_minutes: 99\n", encoding="utf-8")
    base = _write_base(tmp_path, "dev.yaml")

    files = _resolve_layer_files(base)
    assert [f.name for f in files] == ["config.yaml", "config.seed.yaml", "dev.yaml"]

    # 层级顺序: 种子层覆盖基线, 指针覆盖层优先级更高
    conf = _build(files)
    assert conf.get("token").get("expire_minutes") == 99

    # 种子文件缺失: 仅基线+指针(告警跳过逻辑复用), 不报错
    seed.unlink()
    files = _resolve_layer_files(base)
    assert [f.name for f in files] == ["config.yaml", "dev.yaml"]


# ==================== 真实全局单例冒烟 ====================

def test_real_conf_loaded():
    """真实 conf 可用: 基线+覆盖层合并加载, state/server 等关键节存在"""
    from common.config.index import conf, is_dev

    assert isinstance(is_dev, bool)
    assert conf.get("state") is not None
    assert conf.get("server") is not None
    assert conf.get("dir") is not None
    assert conf.get("db_rel") is not None
