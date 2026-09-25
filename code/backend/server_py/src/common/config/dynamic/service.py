"""动态配置服务: 类型化读取 + 校验写入 + TTL 缓存 + yaml 首启种子 + 更新钩子

- get(Schema): 读取并缓存(默认 10s TTL; web 进程更新后本地缓存即时失效,
  其他进程(worker)最迟 TTL 后可见——简单可靠, 多副本部署再升级 Redis pub/sub)
- update: 深合并 + secret 缺省保持 + Pydantic 校验(pydantic ValidationError 是
  ValueError 子类, 由全局异常处理器映射 400)
- describe: 组元数据 + 打码值(驱动前端通用表单, 后端加组前端零改动)
"""
from __future__ import annotations

import inspect
import time
import typing
from typing import Any, Callable, TypeVar

from common.config.dynamic.dao import SysConfigDao
from common.config.dynamic.schemas import SettingsGroup

T = TypeVar("T")


def _unwrap(annotation) -> Any:
    """解开 Optional[X]/Annotated[X, ...] 到承载类型(用于字段元数据推断)"""
    if typing.get_origin(annotation) is typing.Annotated:
        annotation = typing.get_args(annotation)[0]
    args = typing.get_args(annotation)
    if args:
        rest = [a for a in args if a is not type(None)]
        if len(rest) == 1 and len(args) == 2:  # Optional[X] → X
            annotation = rest[0]
    return annotation


def _field_type(annotation) -> tuple[str, list[str] | None]:
    """注解 → (表单控件类型, 枚举选项)"""
    ann = _unwrap(annotation)
    if ann is bool:
        return "bool", None
    if ann is int:
        return "int", None
    if ann is float:
        return "float", None
    origin = typing.get_origin(ann)
    if origin is typing.Literal:
        return "enum", [str(v) for v in typing.get_args(ann)]
    if origin in (list, typing.List):
        return "list", None
    return "str", None


def _is_group(annotation) -> bool:
    """注解是否为嵌套配置子组(所有 SettingsGroup 子类)"""
    ann = _unwrap(annotation)
    return isinstance(ann, type) and issubclass(ann, SettingsGroup)


def _secrets_of(schema) -> frozenset[str]:
    """取 schema 的密钥字段声明(子组未声明时兜底空集)"""
    return getattr(schema, "_secret_fields", frozenset())


def _dig(data: dict, dotted: str):
    """按 "a.b" 点路径取嵌套值"""
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _deep_merge(schema, old: dict, patch: dict, prefix: str = "") -> dict:
    """schema 感知的深合并: 普通字段 patch 有则覆盖; 密钥字段 缺省保持/空串清空/有值覆盖"""
    merged = {**old}
    for key, fi in schema.model_fields.items():
        if _is_group(fi.annotation):  # 嵌套子组递归(前缀携带密钥路径)
            sub = _unwrap(fi.annotation)
            merged[key] = _deep_merge(
                sub, old.get(key) or {}, patch.get(key) or {}, prefix=f"{prefix}{key}."
            )
            continue
        if key not in patch:
            continue  # 未提交 → 保持旧值
        full = f"{prefix}{key}"
        if full in _secrets_of(schema):
            v = patch[key]
            merged[key] = "" if v in (None, "") else v  # 空串=清除; 有值=覆盖
        else:
            merged[key] = patch[key]
    return merged


class SettingsService:
    _TTL = 10.0  # 秒; 其他进程(如 celery worker)的陈旧窗口

    def __init__(self):
        self._registry: dict[str, type] = {}
        self._cache: dict[str, tuple[float, Any]] = {}
        self._hooks: dict[str, list[Callable]] = {}
        self._dao = SysConfigDao()

    # #################### 注册 ####################
    def register(self, schema: type) -> None:
        self._registry[schema._group] = schema

    def _schema(self, group: str):
        schema = self._registry.get(group)
        if schema is None:
            raise ValueError(f"未知配置组: {group}")
        return schema

    def on_update(self, group: str, hook: Callable) -> None:
        """注册更新钩子(同步或协程函数; 如 tasks 组重建 celery app)"""
        self._hooks.setdefault(group, []).append(hook)

    # #################### 读取 ####################
    async def get(self, schema_or_group: type[T] | str) -> T:
        """类型化读取配置(缓存 TTL 内直返, 否则读库并以 schema 默认值兜底)"""
        group = schema_or_group if isinstance(schema_or_group, str) else schema_or_group._group
        schema = self._schema(group)
        now = time.monotonic()
        hit = self._cache.get(group)
        if hit and now - hit[0] <= self._TTL:
            return hit[1]
        row = await self._dao.get(group)
        value = schema.model_validate(row.value if row else {})
        self._cache[group] = (now, value)
        return value

    async def get_raw(self, group: str) -> dict:
        """读取配置原始 dict(未打码; 仅供服务端内部使用)"""
        return (await self.get(group)).model_dump()

    # #################### 写入 ####################
    async def update(self, group: str, data: dict, *, updated_by: str | None = None) -> Any:
        """更新配置组: 深合并(密钥缺省保持/空串清空)→校验→落库→失效缓存→触发钩子"""
        schema = self._schema(group)
        old = (await self.get(group)).model_dump()
        merged = _deep_merge(schema, old, data)
        new = schema.model_validate(merged)  # 校验失败 → ValueError → 400
        await self._dao.upsert(group, new.model_dump(), updated_by=updated_by)
        self._cache[group] = (time.monotonic(), new)
        for hook in self._hooks.get(group, []):
            result = hook()
            if inspect.isawaitable(result):
                await result
        return new

    # #################### 脱敏描述(驱动前端表单) ####################
    async def describe_all(self) -> list[dict]:
        return [await self.describe(group) for group in self._registry]

    async def describe(self, group: str) -> dict:
        schema = self._schema(group)
        row = await self._dao.get(group)
        dump = (await self.get(group)).model_dump()
        return {
            "group": group,
            "name": schema._name,
            "description": schema._description,
            "restart_required": schema._restart_required,
            "updated_at": row.updated_at.isoformat() if row else None,
            "updated_by": row.updated_by if row else None,
            "fields": self._fields(schema, dump),
        }

    def _fields(self, schema, dump: dict, prefix: str = "") -> list[dict]:
        fields = []
        for key, fi in schema.model_fields.items():
            full = f"{prefix}{key}"
            if _is_group(fi.annotation):
                fields += self._fields(_unwrap(fi.annotation), dump.get(key) or {}, prefix=full + ".")
                continue
            ftype, options = _field_type(fi.annotation)
            meta = {
                "key": full,
                "title": fi.title or key,
                "description": fi.description or "",
                "type": ftype,
                "options": options,
                "required": fi.is_required(),
            }
            if full in _secrets_of(schema):
                raw = _dig(dump, full)
                meta.update(type="secret", value=None, has_value=bool(raw))
            else:
                meta.update(value=_dig(dump, full))
            fields.append(meta)
        return fields

    # #################### 首启种子 ####################
    async def seed_from_yaml(self, conf) -> None:
        """首启种子: 组行不存在时, 以 yaml 同名节覆盖 schema 默认值建行(幂等, 不覆盖已有行)"""
        for group in self._registry:
            if await self._dao.get(group) is not None:
                continue
            try:
                section = conf.get(group, {}) or {}
            except Exception:
                section = {}
            section = dict(section) if hasattr(section, "items") else {}
            schema = self._schema(group)
            value = schema.model_validate(section).model_dump()
            await self._dao.upsert(group, value, updated_by="seed")
            self._cache.pop(group, None)


# 进程级单例(经 runtime.settings 引用; 组注册与钩子由 __init__ 完成)
settings_service = SettingsService()
