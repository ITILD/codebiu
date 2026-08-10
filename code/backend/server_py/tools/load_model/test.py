
from huggingface_hub import snapshot_download
import os

# 可选：设置镜像
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

snapshot_download(
    repo_id="docling-project/docling-layout-heron",
    local_dir="./docling-layout-heron",
    resume_download=True,  # 支持断点续传
)
print("Download complete:", "./docling-layout-heron")