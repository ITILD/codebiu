# coding: utf-8
"""
YOLO26 测试 / 推理脚本

包含两部分:
    - predict(): 对图像/视频进行推理并保存可视化结果
    - val():     在带标注的验证/测试集上评估指标(mAP 等)

数据集目录约定(位于 temp_source/temp):
    temp_source/temp/
    ├── images/
    │   ├── test/    # 测试图像(有标注时用于 val)
    │   └── predict/ # 纯推理图像(无标注)
    ├── labels/
    │   └── test/
    └── data.yaml

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
# 结果保存目录
RUNS_DIR = PROJECT_ROOT / "temp_source" / "sys_out" / "yolo26"
# 默认推理图像目录
DEFAULT_SOURCE = DATA_DIR / "images" / "test"
# 默认模型权重: 最近一次训练的 best.pt
DEFAULT_WEIGHTS = RUNS_DIR / "train" / "weights" / "best.pt"


def predict(
    model: str | Path = DEFAULT_WEIGHTS,
    source: str | Path = DEFAULT_SOURCE,
    imgsz: int = 640,
    conf: float = 0.25,
    iou: float = 0.7,
    device: str | int | list[int] | None = None,
    save: bool = True,
    project: Path | None = None,
    name: str = "predict",
    **kwargs,
):
    """
    使用训练好的 YOLO26 模型进行推理。

    参数:
        model: 模型权重路径,默认使用最近一次训练的 best.pt
        source: 推理输入(图像目录/单张图像/视频/摄像头索引)
        imgsz: 推理图像尺寸
        conf: 置信度阈值
        iou: IoU 阈值(YOLO26 为 NMS-free 端到端结构,该参数用于结果过滤)
        device: 推理设备,如 0 / 'cpu';None 时自动选择
        save: 是否保存可视化结果
        project: 结果保存根目录
        name: 本次推理实验名
        **kwargs: 透传给 ultralytics YOLO.predict 的其他参数
    """
    project = project or RUNS_DIR

    model_path = Path(model)
    if not model_path.exists():
        raise FileNotFoundError(
            f"模型权重不存在: {model_path}\n请先运行 train.py 训练,或指定有效的 .pt 路径"
        )

    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"推理源不存在: {source_path}")

    logger.info("加载模型: %s", model_path)
    yolo = YOLO(str(model_path))

    logger.info("开始推理 | source=%s conf=%s imgsz=%s", source_path, conf, imgsz)
    results = yolo.predict(
        source=str(source_path),
        imgsz=imgsz,
        conf=conf,
        iou=iou,
        device=device,
        save=save,
        project=str(project),
        name=name,
        **kwargs,
    )
    logger.info("推理完成,共处理 %d 个结果", len(results))
    return results


def val(
    model: str | Path = DEFAULT_WEIGHTS,
    data_yaml: Path | None = None,
    imgsz: int = 640,
    batch: int = 16,
    device: str | int | list[int] | None = None,
    project: Path | None = None,
    name: str = "val",
    **kwargs,
):
    """
    在验证/测试集上评估模型指标。

    参数:
        model: 模型权重路径,默认使用最近一次训练的 best.pt
        data_yaml: 数据集配置文件,默认 temp_source/temp/data.yaml
        imgsz: 评估图像尺寸
        batch: 批次大小
        device: 评估设备,如 0 / 'cpu';None 时自动选择
        project: 结果保存根目录
        name: 本次评估实验名
        **kwargs: 透传给 ultralytics YOLO.val 的其他参数
    """
    data_yaml = data_yaml or (DATA_DIR / "data.yaml")
    project = project or RUNS_DIR

    model_path = Path(model)
    if not model_path.exists():
        raise FileNotFoundError(f"模型权重不存在: {model_path}")

    if not data_yaml.exists():
        raise FileNotFoundError(f"数据集配置不存在: {data_yaml}")

    logger.info("加载模型: %s", model_path)
    yolo = YOLO(str(model_path))

    logger.info("开始评估 | data=%s imgsz=%s", data_yaml, imgsz)
    metrics = yolo.val(
        data=str(data_yaml),
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=str(project),
        name=name,
        **kwargs,
    )
    logger.info(
        "评估完成 | mAP50=%.4f mAP50-95=%.4f precision=%.4f recall=%.4f",
        metrics.box.map50, metrics.box.map, metrics.box.mp, metrics.box.mr,
    )
    return metrics


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # 推理示例:对测试图像进行预测
    predict(
        model=DEFAULT_WEIGHTS,
        source=DEFAULT_SOURCE,
        device=0,  # GPU:0;CPU 用 'cpu'
    )
    # 评估示例:在测试集上计算 mAP(取消注释使用)
    # val(device=0)
