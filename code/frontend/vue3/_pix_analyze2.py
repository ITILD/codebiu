# -*- coding: utf-8 -*-
"""第二轮精确采样：确认输入区/卡片/顶栏/抽屉内容"""

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


def main_color(data, tol=4, top=8):
    c = Counter()
    for p in data:
        c[(p[0] // tol * tol, p[1] // tol * tol, p[2] // tol * tol)] += 1
    n = len(data)
    return [(fmt(col), cnt, round(cnt * 100.0 / n, 1)) for col, cnt in c.most_common(top)]


def col_scan(img, x, y0, y1, step):
    """单列纵向扫描"""
    return [(y, fmt(img.getpixel((x, y)))) for y in range(y0, y1, step)]


def row_scan(img, y, x0, x1, step):
    """单行横向扫描"""
    return [(x, fmt(img.getpixel((x, y)))) for x in range(x0, x1, step)]


def grid_scan(img, x0, y0, x1, y1, stepx, stepy):
    """网格采样"""
    for y in range(y0, y1, stepy):
        row = [fmt(img.getpixel((x, y))) for x in range(x0, x1, stepx)]
        print(f'  y={y}:', row)


def dark_rows(img, box, limit=170):
    """每行暗色像素数（文字行检测），返回 (y, count) 列表"""
    d, w, h = crop_data(img, box)
    res = []
    for y in range(h):
        cnt = sum(1 for p in d[y * w:(y + 1) * w] if (p[0] + p[1] + p[2]) // 3 < limit)
        if cnt > 0:
            res.append((y + box[1], cnt))
    return res


def analyze_desktop():
    img = Image.open(BASE + r'\_chat_desktop.png').convert('RGB')
    print('===== 图1 第二轮 =====')

    # 1. 顶栏纵向结构（x=800 处从上往下）
    print('[顶栏列扫描 x=800 y0..140]:', col_scan(img, 800, 0, 140, 5))

    # 2. 顶栏横向扫描（y=35 一行）
    print('[顶栏行扫描 y=35 x300..1430 step40]:', row_scan(img, 35, 300, 1430, 40))

    # 3. 顶栏元素区 y74-117（第一轮发现的段）
    d, _, _ = crop_data(img, (300, 74, 1430, 118))
    print('[y74-117 区] 主色:', main_color(d))
    print('[y74-117 行扫描 y=95 x300..1430 step40]:', row_scan(img, 95, 300, 1430, 40))

    # 4. 问候语文字行（y180-330）
    print('[问候语暗像素行 y180..330]:', dark_rows(img, (300, 180, 1300, 330)))

    # 5. 卡片区（y330-500）
    d, _, _ = crop_data(img, (310, 330, 1430, 500))
    print('[卡片区 y330-500] 主色:', main_color(d))
    # 白色块行段（放宽: b>=248 且与米白背景距>=8）
    d, cw, ch = crop_data(img, (310, 330, 1430, 500))
    rows = []
    for y in range(ch):
        cnt = sum(1 for p in d[y * cw:(y + 1) * cw]
                  if p[2] >= 248 and p[0] >= 248 and dist(p, CREAM) >= 8)
        rows.append(cnt / cw)
    segs, start = [], None
    for i, v in enumerate(rows):
        if v > 0.3 and start is None:
            start = i
        elif v <= 0.3 and start is not None:
            if i - start >= 10:
                segs.append((start + 330, i - 1 + 330))
            start = None
    if start is not None:
        segs.append((start + 330, ch - 1 + 330))
    print('[卡片区] 白色块行段:', segs)

    # 6. 输入区主色与行段
    d, cw, ch = crop_data(img, (300, 690, 1440, 860))
    print('[输入区 y690-860] 主色:', main_color(d))
    mc = main_color(d, top=1)[0][0]
    prof = []
    for y in range(ch):
        cnt = sum(1 for p in d[y * cw:(y + 1) * cw] if dist(p, CREAM) > 14)
        prof.append(cnt / cw)
    segs, start = [], None
    for i, v in enumerate(prof):
        if v > 0.02 and start is None:
            start = i
        elif v <= 0.02 and start is not None:
            if i - start >= 3:
                segs.append((start + 690, i - 1 + 690))
            start = None
    if start is not None:
        segs.append((start + 690, ch - 1 + 690))
    print('[输入区] 非米白行段:', segs)

    # 7. 输入区网格采样
    print('[输入区网格 y715..850 step15 x360..1400 step80]:')
    grid_scan(img, 360, 715, 1400, 855, 80, 15)

    # 8. 发送按钮区精细网格（输入卡片右侧）
    print('[右下角网格 y780..850 step8 x1180..1360 step12]:')
    grid_scan(img, 1180, 780, 1360, 852, 12, 8)

    # 9. 新建按钮区域网格（左栏顶部）
    print('[新建按钮区网格 y40..130 step10 x20..270 step30]:')
    grid_scan(img, 20, 40, 280, 130, 30, 10)


def analyze_mobile():
    img = Image.open(BASE + r'\_chat_mobile_drawer.png').convert('RGB')
    print('===== 图2 第二轮 =====')

    # 1. 抽屉中部纵向扫描（x=140）
    print('[抽屉列扫描 x=140 y60..780 step20]:', col_scan(img, 140, 60, 780, 20))

    # 2. 抽屉暗文字行
    print('[抽屉暗像素行 y60..760]:', dark_rows(img, (5, 60, 285, 760)))

    # 3. 抽屉主色（细分上下）
    d, _, _ = crop_data(img, (0, 60, 285, 760))
    print('[抽屉 y60-760] 主色:', main_color(d, top=6))

    # 4. 抽屉白色块（激活会话项）
    d, cw, ch = crop_data(img, (0, 60, 285, 760))
    xs, ys = [], []
    for i, p in enumerate(d):
        if p[0] >= 250 and p[1] >= 250 and p[2] >= 248:
            xs.append(i % cw)
            ys.append(i // cw + 60)
    if xs:
        print('[抽屉] 白色块bbox:', (min(xs), min(ys), max(xs), max(ys), len(xs)))

    # 5. 遮罩与抽屉边界精确扫描
    print('[边界行扫描 y=400 x260..330 step4]:', row_scan(img, 400, 260, 332, 4))


if __name__ == '__main__':
    analyze_desktop()
    print()
    analyze_mobile()
