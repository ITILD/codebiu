"""缓存格式转换工具

提供模型缓存目录的检查、权重格式互转(safetensors <-> pytorch_model.bin)
以及缓存清理能力，适配 HuggingFace / ModelScope 两种缓存布局。
"""
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# 权重文件后缀
_SAFETENSORS_SUFFIXES = (".safetensors",)
_PYTORCH_SUFFIXES = (".bin",)


class CacheConverter:
    """模型缓存格式转换器。

    主要能力:
        - inspect_cache: 列出缓存目录中的权重文件与配置。
        - safetensors_to_pytorch: 将 .safetensors 转为 pytorch_model.bin。
        - pytorch_to_safetensors: 将 pytorch_model.bin 转为 .safetensors。
        - clean_artifacts: 清理下载残留(.lock/.incomplete 等)。
        - reorganize_flat: 将 HF hub 缓存布局扁平化为 ModelScope 风格。
    """

    def __init__(self, cache_dir: Path):
        """初始化。

        Args:
            cache_dir: 模型缓存根目录或单个模型目录。
        """
        self.cache_dir = Path(cache_dir)

    # ------------------------------
    # 检查
    # ------------------------------

    def inspect_cache(self) -> dict:
        """检查缓存目录，返回权重文件与配置文件清单。

        Returns:
            {
                "path": str,
                "safetensors": [str],
                "pytorch": [str],
                "configs": [str],
                "size_mb": float,
            }
        """
        if not self.cache_dir.exists():
            return {"path": str(self.cache_dir), "exists": False}

        safetensors_files: list[str] = []
        pytorch_files: list[str] = []
        config_files: list[str] = []
        total_size = 0

        for f in self.cache_dir.rglob("*"):
            if f.is_file():
                total_size += f.stat().st_size
                name = f.name.lower()
                rel = str(f.relative_to(self.cache_dir))
                if name.endswith(_SAFETENSORS_SUFFIXES):
                    safetensors_files.append(rel)
                elif name.endswith(_PYTORCH_SUFFIXES):
                    pytorch_files.append(rel)
                elif name.endswith((".json", ".txt", ".model", ".tiktoken")):
                    config_files.append(rel)

        return {
            "path": str(self.cache_dir),
            "exists": True,
            "safetensors": safetensors_files,
            "pytorch": pytorch_files,
            "configs": config_files,
            "size_mb": round(total_size / (1024 * 1024), 2),
        }

    # ------------------------------
    # 权重格式互转
    # ------------------------------

    def safetensors_to_pytorch(self, output_name: str = "pytorch_model.bin") -> list[Path]:
        """将目录下所有 .safetensors 合并转换为单个 pytorch_model.bin。

        Args:
            output_name: 输出文件名。

        Returns:
            生成的文件路径列表。
        """
        from safetensors.torch import load_file

        merged_state: dict = {}
        for f in sorted(self.cache_dir.rglob("*.safetensors")):
            logger.info("加载 safetensors: %s", f.name)
            state = load_file(str(f))
            merged_state.update(state)

        if not merged_state:
            logger.warning("未找到任何 .safetensors 文件: %s", self.cache_dir)
            return []

        import torch

        out_path = self.cache_dir / output_name
        torch.save(merged_state, out_path)
        logger.info("已生成: %s", out_path)
        return [out_path]

    def pytorch_to_safetensors(
        self, bin_name: str = "pytorch_model.bin", output_name: str = "model.safetensors"
    ) -> list[Path]:
        """将 pytorch_model.bin 转换为 .safetensors。

        Args:
            bin_name: 输入的 pytorch 权重文件名。
            output_name: 输出的 safetensors 文件名。

        Returns:
            生成的文件路径列表。
        """
        import torch
        from safetensors.torch import save_file

        results: list[Path] = []
        targets = [self.cache_dir / bin_name]
        # 也支持分片 pytorch_model-00001-of-0000X.bin
        targets += sorted(self.cache_dir.glob("pytorch_model-*.bin"))

        for bin_path in targets:
            if not bin_path.exists():
                continue
            logger.info("加载 pytorch 权重: %s", bin_path.name)
            state_dict = torch.load(str(bin_path), map_location="cpu", weights_only=True)
            # 过滤非 tensor 值
            clean = {k: v for k, v in state_dict.items() if hasattr(v, "contiguous")}
            stem = bin_path.stem
            out_name = (
                output_name if stem == "pytorch_model" else f"{stem}.safetensors"
            )
            out_path = self.cache_dir / out_name
            save_file(clean, str(out_path))
            results.append(out_path)
            logger.info("已生成: %s", out_path)

        if not results:
            logger.warning("未找到可转换的 .bin 文件: %s", self.cache_dir)
        return results

    # ------------------------------
    # 缓存清理
    # ------------------------------

    def clean_artifacts(self, delete_blobs: bool = False) -> list[Path]:
        """清理下载残留文件。

        Args:
            delete_blobs: 是否删除 HF hub 缓存的 blobs/refs/snapshots 布局
                (仅对 HF 缓存目录生效)。

        Returns:
            已删除的文件/目录路径列表。
        """
        removed: list[Path] = []
        # 残留后缀
        artifact_suffixes = (".lock", ".incomplete", ".tmp")

        for f in self.cache_dir.rglob("*"):
            if f.is_file() and f.suffix.lower() in artifact_suffixes:
                f.unlink()
                removed.append(f)
                logger.info("删除残留文件: %s", f)

        if delete_blobs:
            for sub in ("blobs", "refs", "snapshots"):
                sub_dir = self.cache_dir / sub
                if sub_dir.exists():
                    shutil.rmtree(sub_dir)
                    removed.append(sub_dir)
                    logger.info("删除缓存目录: %s", sub_dir)

        return removed

    # ------------------------------
    # 布局扁平化
    # ------------------------------

    def reorganize_flat(self, target_dir: Path) -> Path:
        """将 HF hub 缓存布局(snapshots/xxx/...)扁平化为 ModelScope 风格。

        HF 缓存: cache_dir/models--org--name/snapshots/<sha>/...
        ModelScope 风格: target_dir/org/name/...

        Args:
            target_dir: 扁平化后的目标根目录。

        Returns:
            扁平化后的模型目录。
        """
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        # 找到 snapshots 目录
        snapshots_dir = self.cache_dir / "snapshots"
        if not snapshots_dir.exists():
            # 已经是扁平结构，直接复制
            dest = target_dir / self.cache_dir.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(self.cache_dir, dest)
            logger.info("已扁平化复制: %s -> %s", self.cache_dir, dest)
            return dest

        # 解析 org/name
        dir_name = self.cache_dir.name  # models--org--name
        parts = dir_name.split("--")
        if len(parts) >= 3:
            org, name = parts[1], "--".join(parts[2:])
        else:
            org, name = "_local", dir_name

        dest = target_dir / org / name
        dest.mkdir(parents=True, exist_ok=True)

        # snapshots 下取第一个(通常是最新版本)
        versions = [d for d in snapshots_dir.iterdir() if d.is_dir()]
        if not versions:
            logger.warning("snapshots 下无版本目录: %s", snapshots_dir)
            return dest

        src = versions[0]
        if dest.exists() and any(dest.iterdir()):
            shutil.rmtree(dest)

        # 复制文件，跟随符号链接拿到真实文件
        for item in src.iterdir():
            real = item.resolve()
            if real.is_file():
                shutil.copy2(real, dest / item.name)

        logger.info("已扁平化: %s -> %s", src, dest)
        return dest
