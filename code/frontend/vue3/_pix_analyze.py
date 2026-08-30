# -*- coding: utf-8 -*-
"""聊天界面截图像素采样分析（纯 PIL + 标准库，不读图仅采像素）"""

from PIL import Image
from collections import Counter

BASE = r'd:\a0_wx\ITILD\codebiu\code\frontend\vue3'

PALE_GREEN = (244, 248, 242)   # f4f8f2 会话列表背景
CREAM = (250, 250, 245)        # fafaf5 消息区背景
BTN_GREEN = (107, 158, 120)    # 6b9e78 绿色按钮


def dist(p, t):
    return abs(p[0] - t[0]) + abs(p[1] - t[1]) + abs(p[2] - t[2])


def lum(p):
    return (p[0] * 299 + p[1] * 587 + p[2] * 114) // 1000


def crop_data(img, box):
    w = box[2] - box[0]
    return list(img.crop(box).getdata()), w, box[3] - box[1]


def fmt(c):
    return '#%02x%02x%02x' % c


def main_color(data, tol=6, top=5):
    """量化统计主色"""
    c = Counter()
    for p in data:
        c[(p[0] // tol * tol, p[1] // tol * tol, p[2] // tol * tol)] += 1
    n = len(data)
    return [(col, cnt, round(cnt * 100.0 / n, 1)) for col, cnt in c.most_common(top)]


def near_bbox(data, w, h, target, tol=50, ox=0, oy=0):
    """接近目标色的像素边界框（输出绝对坐标）"""
    xs, ys = [], []
    for i, p in enumerate(data):
        if dist(p, target) <= tol:
            xs.append(i % w + ox)
            ys.append(i // w + oy)
    if not xs:
        return None
    return dict(x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys), n=len(xs))


def dark_bbox(data, w, h, limit=170, ox=0, oy=0):
    """暗色文字像素边界框"""
    xs, ys = [], []
    for i, p in enumerate(data):
        if (p[0] + p[1] + p[2]) // 3 < limit:
            xs.append(i % w + ox)
            ys.append(i // w + oy)
    if not xs:
        return None
    return dict(x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys), n=len(xs))


def white_bbox(data, w, h, ox=0, oy=0):
    """接近纯白的像素边界框（排除米白背景 250,250,245）"""
    xs, ys = [], []
    for i, p in enumerate(data):
        if p[0] >= 252 and p[1] >= 252 and p[2] >= 250:
            xs.append(i % w + ox)
            ys.append(i // w + oy)
    if not xs:
        return None
    return dict(x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys), n=len(xs))


def count_blue(data):
    """蓝色主导像素数量（用于排查蓝色主题）"""
    n = 0
    for r, g, b in data:
        if b > r + 25 and b > g + 15 and b > 80:
            n += 1
    return n


def row_profile(data, w, h, bg, thresh=18):
    """每行非背景像素比例"""
    prof = []
    for y in range(h):
        base = y * w
        cnt = 0
        for i in range(base, base + w):
            p = data[i]
            if abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > thresh:
                cnt += 1
        prof.append(cnt / w)
    return prof


def col_profile(data, w, h, bg, thresh=18):
    """每列非背景像素比例"""
    prof = []
    for x in range(w):
        cnt = 0
        for y in range(h):
            p = data[y * w + x]
            if abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > thresh:
                cnt += 1
        prof.append(cnt / h)
    return prof


def col_profile_white(data, w, h):
    """每列接近纯白的像素比例（用于定位白色卡片）"""
    prof = []
    for x in range(w):
        cnt = 0
        for y in range(h):
            p = data[y * w + x]
            if p[0] >= 252 and p[1] >= 252 and p[2] >= 250:
                cnt += 1
        prof.append(cnt / h)
    return prof


def segments(prof, min_len=4, ratio=0.015):
    """把投影切分为内容段"""
    segs, start = [], None
    for i, v in enumerate(prof):
        if v > ratio and start is None:
            start = i
        elif v <= ratio and start is not None:
            if i - start >= min_len:
                segs.append((start, i - 1))
            start = None
    if start is not None and len(prof) - start >= min_len:
        segs.append((start, len(prof) - 1))
    return segs


def analyze_desktop():
    img = Image.open(BASE + r'\_chat_desktop.png').convert('RGB')
    w, h = img.size
    print(f'===== 图1 桌面版 {w}x{h} =====')

    # -- 1. 左栏背景（期望淡绿 f4f8f2）
    d, _, _ = crop_data(img, (0, 0, 288, h))
    print('[左栏 0-288] 主色:', [(fmt(c), n, f'{p}%') for c, n, p in main_color(d)])

    # -- 2. 主区背景（期望米白 fafaf5）
    d, _, _ = crop_data(img, (340, 80, 1430, 680))
    print('[主区中部] 主色:', [(fmt(c), n, f'{p}%') for c, n, p in main_color(d)])

    # -- 3. 左栏边界扫描（y=430 行，x 260-330）
    cols = [(x, fmt(img.getpixel((x, 430)))) for x in range(260, 332, 4)]
    print('[边界扫描 y=430]:', cols)

    # -- 4. 新建按钮（左栏顶部绿色块）
    d, cw, ch = crop_data(img, (8, 30, 288, 180))
    bb = near_bbox(d, cw, ch, BTN_GREEN, 55, ox=8, oy=30)
    print('[新建按钮] 绿色bbox:', bb)

    # -- 5. 发送按钮（底部绿色圆）
    d, cw, ch = crop_data(img, (850, 690, 1440, 860))
    bb = near_bbox(d, cw, ch, BTN_GREEN, 55, ox=850, oy=690)
    print('[发送按钮] 绿色bbox:', bb)

    # -- 6. 输入卡片（底部白色块）
    wb = white_bbox(d, cw, ch, ox=850, oy=690)
    print('[输入卡片] 白色bbox:', wb)

    # -- 7. 蓝色主题排查（缩到 1/3 采样）
    small = img.resize((w // 3, h // 3))
    sd = list(small.getdata())
    nb = count_blue(sd)
    print(f'[全图] 蓝色像素: {nb}/{len(sd)} = {nb * 100.0 / len(sd):.2f}%')

    # -- 8. 问候语（中部暗色文字）
    d, cw, ch = crop_data(img, (400, 140, 1300, 400))
    db = dark_bbox(d, cw, ch, ox=400, oy=140)
    print('[问候语区] 暗色文字bbox:', db)

    # -- 9. 内容区行投影（定位问候语/卡片/消息行段）
    d, cw, ch = crop_data(img, (300, 70, 1430, 690))
    mc = main_color(d)[0][0]
    print('[内容区] 实测背景:', fmt(mc))
    prof = row_profile(d, cw, ch, mc, 18)
    print('[内容区] 行段(y+70):', segments(prof, min_len=5, ratio=0.012))

    # -- 10. 内容区白色卡片列段（2x2 卡片检测）
    wprof = col_profile_white(d, cw, ch)
    print('[内容区] 白色列段(x+300):', segments(wprof, min_len=25, ratio=0.30))

    # -- 11. 顶栏内容（知识库下拉 + 深度思考胶囊）
    d, cw, ch = crop_data(img, (288, 0, 1440, 70))
    mct = main_color(d)[0][0]
    print('[顶栏] 实测背景:', fmt(mct))
    cprof = col_profile(d, cw, ch, mct, 16)
    print('[顶栏] 内容列段(x+288):', segments(cprof, min_len=8, ratio=0.02))
    tb = dark_bbox(d, cw, ch, 150, ox=288, oy=0)
    print('[顶栏] 暗色文字bbox:', tb)

    # -- 12. 左栏会话列表内容
    d, cw, ch = crop_data(img, (0, 0, 288, h))
    mcl = main_color(d)[0][0]
    lprof = row_profile(d, cw, ch, mcl, 16)
    print('[左栏] 行段:', segments(lprof, min_len=6, ratio=0.015))

    # -- 13. 底部输入区上方（检查建议卡片与输入框间距/重叠）
    d, cw, ch = crop_data(img, (300, 660, 1430, 710))
    mc2 = main_color(d)[0][0]
    prof2 = row_profile(d, cw, ch, mc2, 16)
    print('[y660-710 过渡区] 行段(y+660):', segments(prof2, min_len=4, ratio=0.02))


def analyze_mobile():
    img = Image.open(BASE + r'\_chat_mobile_drawer.png').convert('RGB')
    w, h = img.size
    print(f'===== 图2 移动端 {w}x{h} =====')
    data = list(img.getdata())

    # -- 1. 逐列平均亮度（行步进 2 采样）
    lums = []
    for x in range(w):
        s = n = 0
        for y in range(0, h, 2):
            s += lum(data[y * w + x])
            n += 1
        lums.append(s // n)
    print('[列亮度 x:0..390 step15]:', [(x, lums[x]) for x in range(0, w, 15)])

    # -- 2. 抽屉边界：亮度从亮(>210)突降到暗(<190)
    edge = None
    for x in range(5, w - 6):
        if lums[x] > 210 and lums[x + 5] < 190:
            edge = x
            break
    print('[抽屉边界估计]:', edge)

    if edge:
        # -- 3. 抽屉区主色 + 新建按钮
        d, cw, ch = crop_data(img, (0, 0, edge, h))
        print('[抽屉区] 主色:', [(fmt(c), n, f'{p}%') for c, n, p in main_color(d)])
        dg, cwg, chg = crop_data(img, (0, 20, edge, 260))
        bb = near_bbox(dg, cwg, chg, BTN_GREEN, 55, ox=0, oy=20)
        print('[抽屉顶部] 绿色按钮bbox:', bb)
        # 抽屉内容行段
        mcd = main_color(d)[0][0]
        lprof = row_profile(d, cw, ch, mcd, 16)
        print('[抽屉区] 行段:', segments(lprof, min_len=6, ratio=0.015))

        # -- 4. 遮罩区（半透明黑）
        dm, _, _ = crop_data(img, (min(edge + 15, w - 1), 0, w, h))
        avg = sum(lum(p) for p in dm) // len(dm)
        bright = sum(1 for p in dm if lum(p) > 215)
        print('[遮罩区] 主色:', [(fmt(c), n, f'{p}%') for c, n, p in main_color(dm, tol=8, top=3)],
              '平均亮度:', avg, f'亮色占比: {bright * 100.0 / len(dm):.1f}%')
    else:
        print('!! 未检测到抽屉/遮罩亮度分界')

    # -- 5. 蓝色主题排查
    nb = count_blue(data)
    print(f'[全图] 蓝色像素: {nb}/{len(data)} = {nb * 100.0 / len(data):.2f}%')


if __name__ == '__main__':
    analyze_desktop()
    print()
    analyze_mobile()
