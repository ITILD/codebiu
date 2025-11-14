# -*- encoding: utf-8 -*-


import copy
from functools import lru_cache
from pathlib import Path
from module_ai.config.ocr import conf_ocr_languages
import numpy as np
import cv2

from module_ai.utils.onnx.ocr_rapid.rapidocr.rapid_ocr_api import RapidOCR


@lru_cache(maxsize=None)
def load_language_model(lang="ch"):
    models = conf_ocr_languages[lang]
    print("model", models)
    return RapidOCR(models)


#
modelObj = {
    "ja": load_language_model("ja"),
    "ch": load_language_model("ch"),
}


def detect_recognize(image, lang="ch", detect=True, classify=True , inpaint = False):
    # 判断modelObj有ch
    if lang in modelObj:
        model = modelObj[lang]
    else:
        model = load_language_model(lang)
        modelObj.setdefault(lang, model)
    results, ts ,background = model(image, detect=detect, classify=classify , inpaint = inpaint)
    ts["total"] = sum(ts.values())
    return {"ts": ts, "results": results , "background":background}


def check_and_read_gif(img_path):
    if Path(img_path).suffix.lower() == "gif":
        gif = cv2.VideoCapture(img_path)
        ret, frame = gif.read()
        if not ret:
            print("Cannot read {}. This gif image maybe corrupted.")
            return None, False
        if len(frame.shape) == 2 or frame.shape[-1] == 1:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        imgvalue = frame[:, :, ::-1]
        return imgvalue, True
    return None, False


def draw_text_det_res(dt_boxes, raw_im):
    src_im = copy.deepcopy(raw_im)
    for i, box in enumerate(dt_boxes):
        box = np.array(box).astype(np.int32).reshape(-1, 2)
        cv2.polylines(src_im, [box], True, color=(0, 0, 255), thickness=1)
        cv2.putText(
            src_im,
            str(i),
            (int(box[0][0]), int(box[0][1])),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            2,
        )
    return src_im
