"""启动内存剖析(诊断脚本, 可反复运行, 不影响业务)

用法(在 server_py 目录下):
    .venv/Scripts/python.exe tools/test/profile_mem.py          # 总览: 各依赖库独立 import 的内存增量
    .venv/Scripts/python.exe tools/test/profile_mem.py trace    # 追踪: import app 实际加载链 + tracemalloc Top
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable

# 候选依赖库(逗号分隔的一组=一次测完), 结果以实测为准
LIBS: list[str] = [
    "fastapi,uvicorn",
    "pydantic,dynaconf",
    "sqlalchemy,sqlmodel",
    "redis.asyncio",
    "celery",
    "langchain_core",
    "langchain,langchain_openai,langchain_text_splitters",
    "langchain_ollama",
    "langchain_aws",
    "langgraph",
    "deepagents",
    "pymilvus",
    "pyarrow,lancedb",
    "numpy",
    "networkx,neo4j",
    "spacy",
    "docling,docling_core",
    "cv2",
    "onnxruntime",
    "sherpa_onnx",
    "PIL,shapely",
    "playwright",
    "openpyxl,polars,fastexcel",
    "aiohttp,httpx,aioboto3,boto3",
    "casbin",
    "fastmcp",
    "torch,transformers",
    "nltk",
    "sqlite_vec",
    "pypdfium2,lxml,bs4",
    "ezdxf,geoalchemy2",
    "sentence_transformers,peft",
]

# 启动链路最可能引入的重库(用于 trace 模式判定"是否已被加载")
HEAVY_WATCH = [
    "torch", "transformers", "cv2", "spacy", "docling", "lancedb", "pyarrow",
    "pymilvus", "sherpa_onnx", "playwright", "networkx", "neo4j", "nltk",
    "onnxruntime", "celery", "fastmcp", "polars", "openpyxl", "langgraph",
    "deepagents", "langchain_aws", "langchain_ollama", "sentence_transformers",
    "ultralytics", "fastexcel", "aioboto3", "geoalchemy2", "pypdfium2",
]


def _run(code: str, env_extra: dict[str, str] | None = None) -> str:
    import os
    env = os.environ.copy()
    env.update(env_extra or {})
    return subprocess.run(
        [PY, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=300
    )


def overview() -> None:
    """各库独立 import 的内存增量(子进程隔离, 互不污染)"""
    base = int(
        _run("import psutil;print(psutil.Process().memory_info().rss)").stdout.strip()
    )
    rows: list[tuple[str, int]] = []
    for mods in LIBS:
        code = (
            "import psutil,sys;"
            "base=psutil.Process().memory_info().rss;"
            f"import {mods};"
            "print(int((psutil.Process().memory_info().rss-base)/1048576))"
        )
        r = _run(code)
        if r.returncode != 0:
            print(f"[跳过] {mods}: import 失败 -> {r.stderr.strip().splitlines()[-1][:80] if r.stderr else '?'}")
            continue
        rows.append((mods, int(r.stdout.strip() or 0)))
    rows.sort(key=lambda x: -x[1])
    print("\n===== 各依赖库独立 import 内存增量(RSS, 子进程隔离) =====")
    for mods, mb in rows:
        print(f"{mb:>6} MB  {mods}")
    print(f"{'':>6} ---  解释器基线 {base // 1048576} MB")


def trace() -> None:
    """实际 import app: 打印总增量 + 被加载的重库 + tracemalloc 按文件 Top"""
    code = r"""
import os, sys, tracemalloc
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
import psutil
base = psutil.Process().memory_info().rss
tracemalloc.start(5)
import app  # noqa
rss = psutil.Process().memory_info().rss
print(f"APP_TOTAL_MB={int((rss-base)/1048576)}")
loaded = []
watch = %WATCH%
for name in watch:
    if name in sys.modules:
        loaded.append(name)
print("LOADED_HEAVY=" + ",".join(loaded))
snap = tracemalloc.take_snapshot()
agg = {}
for st in snap.statistics("lineno"):
    f = st.traceback[0].filename.replace("\\", "/")
    f = "/".join(f.split("/")[-3:])
    agg[f] = agg.get(f, 0) + st.size
print("===== tracemalloc Top25 (Python 堆分配, 按源文件聚合) =====")
for f, sz in sorted(agg.items(), key=lambda x: -x[1])[:25]:
    print(f"{sz/1048576:8.1f} MB  {f}")
""" .replace("%WATCH%", repr(HEAVY_WATCH))
    r = _run(code)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr[-2000:])


def edges() -> None:
    """记录 import app 期间的 import 调用边, 反推重库是被谁引入的"""
    code = r"""
import builtins, os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
HEAVY = %WATCH%
real = builtins.__import__
LOG: list[tuple[str, str]] = []
def spy(name, globals=None, *a, **k):
    parent = (globals or {}).get("__name__", "?") if globals else "?"
    LOG.append((parent, name))
    return real(name, globals, *a, **k)
builtins.__import__ = spy
import app  # noqa
# 只保留子模块为重库的边
edges = [(p, n) for p, n in LOG if n.split(".")[0] in HEAVY]
# 父模块名 -> 文件(用 sys.modules 反查)
def loc(mod):
    m = sys.modules.get(mod)
    f = getattr(m, "__file__", None) or getattr(getattr(m, "__spec__", None), "origin", None)
    return (f or mod).replace("\\", "/").split("site-packages/")[-1].split("src/")[-1]
print("===== 谁引入了重库 (父模块 -> 重库) =====")
seen = set()
for p, n in edges:
    key = (p.split(".")[0] if p.startswith(("app", "module_")) else p, n)
    line = f"{loc(p) if p in sys.modules else p}  ->  {n}"
    if line in seen:
        continue
    seen.add(line)
    print(line)
""" .replace("%WATCH%", repr(HEAVY_WATCH))
    r = _run(code)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr[-2000:])


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "trace":
        trace()
    elif mode == "edges":
        edges()
    else:
        overview()
