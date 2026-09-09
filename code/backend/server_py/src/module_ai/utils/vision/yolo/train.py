# coding: utf-8
"""
YOLO26 训练脚本

数据集目录约定(位于 temp_source/temp):
    temp_source/temp/
    ├── images/
    │   ├── train/   # 训练图像
    │   ├── val/     # 验证图像
    │   └── test/    # 测试图像
    ├── labels/
    │   ├── train/   # 训练标注(YOLO txt 格式)
    │   ├── val/     # 验证标注
    │   └── test/    # 测试标注
    └── data.yaml    # 数据集配置(不存在时由本脚本按 class_names 自动生成)

Windows 多进程提示: 训练入口必须放在 if __name__ == "__main__": 块中,否则会触发 RuntimeError。
依赖: ultralytics (pip install ultralytics)
"""
import logging
from pathlib import Path

from ultralytics import YOLO

logger = logging.getLogger(__name__)

# 项目根目录: src/module_ai/utils/usual/yolo -> server_py
PROJECT_ROOT = Path(__file__).resolve().parents[5]
# 数据集根目录
DATA_DIR = PROJECT_ROOT / "temp_source" / "temp"
# 数据集配置文件
DATA_YAML = DATA_DIR / "data.yaml"
# 训练产物保存目录
RUNS_DIR = PROJECT_ROOT / "temp_source" / "sys_out" / "yolo26"


def ensure_data_yaml(
    data_yaml: Path,
    data_dir: Path,
    class_names: list[str] | None = None,
) -> None:
    """
    确保数据集配置 data.yaml 存在;不存在则按默认结构自动生成。

    参数:
        data_yaml: data.yaml 路径
        data_dir:  数据集根目录(写入 path 字段)
        class_names: 类别名称列表,自动生成配置时必填
    """
    if data_yaml.exists():
        logger.info("使用已有数据集配置: %s", data_yaml)
        return

    if class_names is None:
        raise ValueError(
            f"数据集配置 {data_yaml} 不存在,请通过 class_names 提供类别名以自动生成,"
            "或手动创建该文件"
        )

    data_yaml.parent.mkdir(parents=True, exist_ok=True)
    names_block = "\n".join(f"  {i}: {n}" for i, n in enumerate(class_names))
    content = (
        "# 由 train.py 自动生成\n"
        f"path: {data_dir.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "names:\n"
        f"{names_block}\n"
    )
    data_yaml.write_text(content, encoding="utf-8")
    logger.info("已生成数据集配置: %s", data_yaml)


def train(
    model: str | Path = "yolo26n.pt",
    data_yaml: Path | None = None,
    epochs: int = 100,
    imgsz: int = 640,
    batch: int = 16,
    device: str | int | list[int] | None = None,
    project: Path | None = None,
    name: str = "train",
    class_names: list[str] | None = None,
    **kwargs,
):
    """
    训练 YOLO26 模型。

    参数:
        model: 预训练模型名或路径,如 yolo26n.pt / yolo26s.pt / yolo26m.pt
        data_yaml: 数据集配置文件路径,默认 temp_source/temp/data.yaml
        epochs: 训练轮次
        imgsz: 训练图像尺寸
        batch: 批次大小
        device: 训练设备,如 0 / [0, 1] / 'cpu';None 时自动选择
        project: 训练结果保存根目录
        name: 本次训练实验名(结果保存在 project/name 下)
        class_names: 类别名称列表,首次运行时用于自动生成 data.yaml
        **kwargs: 透传给 ultralytics YOLO.train 的其他超参数
    """
    data_yaml = data_yaml or DATA_YAML
    project = project or RUNS_DIR
    ensure_data_yaml(data_yaml, DATA_DIR, class_names)

    project.mkdir(parents=True, exist_ok=True)

    logger.info("加载模型: %s", model)
    yolo = YOLO(str(model))

    logger.info(
        "开始训练 | data=%s epochs=%s imgsz=%s batch=%s device=%s",
        data_yaml, epochs, imgsz, batch, device,
    )
    results = yolo.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=str(project),
        name=name,
        **kwargs,
    )
    logger.info("训练完成,结果保存于: %s", project / name)
    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    train(
        model="yolo26n.pt",
        epochs=100,
        imgsz=640,
        batch=16,
        device=0,  # GPU:0;CPU 用 'cpu';多卡用 [0, 1]
        class_names=["cat", "dog"],  # TODO: 替换为实际类别名
    )
