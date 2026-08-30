# -*- coding: utf-8 -*-
"""第三轮：定位输入卡片边界、卡片网格布局、问候语居中度、深度思考胶囊、图2抽屉空态"""

from PIL import Image
from collections import Counter

BASE = r'd:\a0_wx\ITILD\codebiu\code\frontend\vue3'
CREAM = (250, 250, 245)


def dist(p, t):
    return abs(p[0] - t[0]) + abs(p[1] - t[1]) + abs(p[2] - t[2])


def fmt(p):
    return '#%02x%02x%02x' % (p[0], p[1], p[2])


def crop_data(img, box):
    w = box[2] - box[0]
    return list(img.crop(box).getdata()), w, box[3] - box[1]


def row_scan(img, y, x0, x1, step):
    out = []
    for x in range(x0, x1, step):
        out.append(fmt(img.getpixel((x, y))))
    return out


def row_diff_profile(img, box, bg=CREAM, thresh=8):
    """每行与背景差异>阈值的像素数（定位卡片边缘）"""
    d, w, h = crop_data(img, box)
    prof = []
    for y in range(h):
        cnt = sum(1 for p in d[y * w:(y + 1) * w] if dist(p, bg) > thresh)
        prof.append((y + box[1], cnt))
    return prof


def dark_line_range(img, y, x0, x1, limit=170):
    """某行暗像素的 x 范围"""
    xs = [x for x in range(x0, x1)
          if (lambda p: (p[0] + p[1] + p[2]) // 3 < limit)(img.getpixel((x, y)))]
    return (min(xs), max(xs), len(xs)) if xs else None


def analyze_desktop():
    img = Image.open(BASE + r'\_chat_desktop.png').convert('RGB')
    print('===== 图1 第三轮 =====')

    # 1. 输入卡片边缘 profile（每行非背景像素数）
    prof = row_diff_profile(img, (300, 695, 1440, 860))
    compact = [(y, c) for y, c in prof if c > 5]
    print('[输入区每行非背景数 y695-860]:', compact)

    # 2. 输入框/工具条行扫描
    for y in (757, 770, 785, 800, 812, 826, 840):
        print(f'[行扫描 y={y} x340..1420 step20]:', row_scan(img, y, 340, 1420, 20))

    # 3. 卡片区行扫描（判断 2x2 / 1x4）
    for y in (355, 393, 430, 468):
        print(f'[卡片行扫描 y={y} x310..1430 step20]:', row_scan(img, y, 310, 1430, 20))

    # 4. 卡片区白色列段与淡绿列段
    d, w, h = crop_data(img, (310, 330, 1430, 500))
    for name, cond in (('白(>=250)', lambda p: p[0] >= 250 and p[1] >= 250 and p[2] >= 248),
                       ('淡绿(f4f8f0±6)', lambda p: dist(p, (244, 248, 240)) <= 6)):
        prof = []
        for x in range(w):
            cnt = sum(1 for y_ in range(h) if cond(d[y_ * w + x]))
            prof.append(cnt / h)
        segs, start = [], None
        for i, v in enumerate(prof):
            if v > 0.4 and start is None:
                start = i
            elif v <= 0.4 and start is not None:
                if i - start >= 30:
                    segs.append((start + 310, i - 1 + 310))
                start = None
        if start is not None and w - start >= 30:
            segs.append((start + 310, w - 1 + 310))
        print(f'[卡片区]{name}列段:', segs)

    # 5. 问候语全宽暗像素 bbox（y180-320）
    d, w, h = crop_data(img, (288, 180, 1430, 320))
    xs, ys = [], []
    for i, p in enumerate(d):
        if (p[0] + p[1] + p[2]) // 3 < 170:
            xs.append(i % w + 288)
            ys.append(i // w + 180)
    if xs:
        print('[问候语] 暗像素bbox:', (min(xs), min(ys), max(xs), max(ys)),
              '中心x=', (min(xs) + max(xs)) // 2, '区域中心x=', (288 + 1430) // 2)
    # 每个文字行的 x 范围
    for y in (205, 228, 265, 294):
        print(f'[文字行 y={y} 暗像素x范围]:', dark_line_range(img, y, 288, 1430))

    # 6. 顶栏细扫（logo/知识库下拉区）
    print('[顶栏 y=95 x288..600 step8]:', row_scan(img, 95, 288, 600, 8))
    print('[顶栏 y=35 x1300..1430 step10]:', row_scan(img, 35, 1300, 1430, 10))

    # 7. 输入区蓝色像素
    d, w, h = crop_data(img, (300, 695, 1440, 860))
    bx = [(i % w + 300, i // w + 695, fmt(p)) for i, p in enumerate(d)
          if p[2] > p[0] + 15 and p[2] > p[1] + 10]
    print('[输入区] 蓝色像素:', bx[:20], '总数', len(bx))

    # 8. 发送按钮区网格
    print('[发送按钮区 y770..815 step5 x1290..1365 step6]:')
    for y in range(770, 815, 5):
        print(f'  y={y}:', row_scan(img, y, 1290, 1365, 6))

    # 9. 新建按钮精确边界（左栏右上角绿块）
    d, w, h = crop_data(img, (220, 65, 292, 130))
    xs, ys = [], []
    for i, p in enumerate(d):
        if dist(p, (107, 158, 120)) <= 40:
            xs.append(i % w + 220)
            ys.append(i // w + 65)
    if xs:
        print('[新建按钮] 绿块bbox:', (min(xs), min(ys), max(xs), max(ys)), '像素数', len(xs))


def analyze_mobile():
    img = Image.open(BASE + r'\_chat_mobile_drawer.png').convert('RGB')
    print('===== 图2 第三轮 =====')

    # 1. 抽屉唯一文字行的水平范围
    for y in (160, 164, 168):
        print(f'[抽屉文字行 y={y} 暗像素x范围]:', dark_line_range(img, y, 0, 288))

    # 2. 抽屉 y62-85（疑似搜索框）行扫描
    print('[抽屉 y=73 x0..290 step10]:', row_scan(img, 73, 0, 290, 10))

    # 3. 抽屉底部 y762-789 元素
    print('[抽屉底部 y=775 x0..290 step10]:', row_scan(img, 775, 0, 290, 10))
    for y in (765, 780):
        print(f'[抽屉底部 y={y} 暗像素x范围]:', dark_line_range(img, y, 0, 288))

    # 4. 抽屉绿色按钮行扫描（确认全宽按钮）
    print('[抽屉 y=35 x0..290 step12]:', row_scan(img, 35, 0, 290, 12))


if __name__ == '__main__':
    analyze_desktop()
    print()
    analyze_mobile()
