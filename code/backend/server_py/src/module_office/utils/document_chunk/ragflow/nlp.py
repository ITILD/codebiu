"""RAGFlow 风格 NLP 工具

改进原有 ragflow 分块逻辑:
- 直接在 Chunk 对象上操作, 避免 markdown 往返转换导致的位置信息丢失
- 合并过程中原生追踪原始 Chunk 的位置信息
- 参考 ragflow/app/naive.py 和 rag/nlp/__init__.py 的核心算法:
  - naive_merge: 分隔符拆分 → 段落分组 → overlap 注入
  - _add_context: 为独立内容(表格/图片)附加上下文
  - _merge_cks: 文本合并, 非文本独立保留
  - _is_short_header: 短标题强制合并
  - append_context2table_image4pdf: bbox 空间定位上下文
  - parse_delimiter_field: backtick 自定义正则分隔符
"""

from __future__ import annotations

import re

from module_office.utils.document_chunk.do.chunk import ChunkedItem, build_item
from module_office.utils.file_parase.do.chunk import Chunk, Position

# 句子分隔符 (参考 ragflow _add_context 的 split_pat)
_SENTENCE_SPLIT = r"([。!?？；！\n]|\. )"

# 短标题 token 上限 (参考 ragflow _is_short_header 的 max_tokens=50)
_SHORT_HEADER_MAX_TOKENS = 50


def count_tokens(text: str) -> int:
    """近似 token 计数: 英文单词 + 数字 + CJK 单字"""
    if not text:
        return 0
    parts = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text)
    return max(1, len(parts)) if text.strip() else 0


def hard_split_by_token_limit(
    text: str, chunk_token_num: int, hard_limit_token_num: int | None = None
) -> list[str]:
    """将文本按 token 上限硬切, 用于超长块的兜底保护"""
    token_iter = list(re.finditer(r"[A-Za-z0-9_]+|[一-鿿]", text or ""))
    if not token_iter:
        cleaned = (text or "").strip()
        return [cleaned] if cleaned else []

    max_tokens = max(int(chunk_token_num or 0), 1)
    hard_limit = None
    if hard_limit_token_num is not None:
        hard_limit = max(int(hard_limit_token_num or 0), max_tokens)
        if len(token_iter) <= hard_limit:
            cleaned = (text or "").strip()
            return [cleaned] if cleaned else []

    spans: list[tuple[int, int]] = []
    start = 0
    index = 0

    while index < len(token_iter):
        next_index = min(index + max_tokens, len(token_iter))
        if next_index < len(token_iter):
            end = token_iter[next_index].start()
        else:
            end = len(text)
        if text[start:end].strip():
            spans.append((start, end))
        start = end
        index = next_index

    tail = text[start:].strip()
    if tail:
        spans.append((start, len(text)))

    # 尝试将尾部两段合并以避免碎片
    if hard_limit is not None and len(spans) >= 2:
        prev_start, _ = spans[-2]
        _, tail_end = spans[-1]
        candidate = text[prev_start:tail_end].strip()
        if count_tokens(candidate) <= hard_limit:
            spans[-2] = (prev_start, tail_end)
            spans.pop()

    return [text[s:e].strip() for s, e in spans if text[s:e].strip()]


def split_by_delimiter(text: str, delimiter: str) -> list[str]:
    """按分隔符拆分文本

    支持 (参考 ragflow parse_delimiter_field / compile_delimiter_pattern):
    - 普通字符串分隔符 ("\n", "\n\n")
    - 字符集合 ("。；！？") - 逐字符匹配
    - 自定义正则模式: backtick 包裹, 如 `` `Chapter \\d+` ``
      混合使用: `` \n`第\\d+章` `` → 先按换行拆, 再按正则拆
    """
    if not text or not text.strip():
        return []
    if not delimiter:
        return [text.strip()]

    # 提取 backtick 包裹的自定义正则模式 (参考 ragflow has_wrapped_delimiter)
    custom_patterns = re.findall(r"`([^`]+)`", delimiter)
    if custom_patterns:
        # 移除 backtick 部分, 保留普通分隔符
        base_delimiter = re.sub(r"`[^`]+`", "", delimiter).strip()
        # 构建合并的正则模式
        patterns = [re.escape(base_delimiter)] if base_delimiter else []
        patterns.extend(custom_patterns)
        combined = "|".join(patterns)
        parts = re.split(f"({combined})", text)
        return [p.strip() for p in parts if p.strip() and not re.fullmatch(combined, p)]

    if delimiter in ("\n", "\r\n"):
        return [line.strip() for line in text.splitlines() if line.strip()]

    if len(delimiter) > 1 and "\\" not in delimiter:
        parts = text.split(delimiter)
        return [p.strip() for p in parts if p.strip()]

    pattern = "[" + re.escape(delimiter) + "]"
    parts = re.split(pattern, text)
    return [p.strip() for p in parts if p.strip()]


def _is_short_header(text: str, max_tokens: int = _SHORT_HEADER_MAX_TOKENS) -> bool:
    """检测短标题 (参考 ragflow _is_short_header)

    短标题不应成为独立块, 应与后续内容合并。
    判定条件: 内容是 markdown 标题格式 且 token 数低于阈值。
    """
    if not text or not text.strip():
        return False
    if not re.match(r"^#{1,6}\s+", text.strip()):
        return False
    return count_tokens(text) < max_tokens


def _is_header_sources(sources: list[Chunk]) -> bool:
    """检测来源 Chunk 是否全部为标题 (通过 heading_level)"""
    if not sources:
        return False
    return all(
        s.position and s.position.heading_level is not None for s in sources
    )


def take_sentences_from_end(text: str, need_tokens: int) -> str:
    """从文本末尾提取句子, 直到达到 need_tokens (参考 ragflow take_sentences_from_end)"""
    txts = re.split(_SENTENCE_SPLIT, text, flags=re.DOTALL)
    sents = []
    for j in range(0, len(txts), 2):
        sents.append(txts[j] + (txts[j + 1] if j + 1 < len(txts) else ""))
    acc = ""
    for s in reversed(sents):
        acc = s + acc
        if count_tokens(acc) >= need_tokens:
            break
    return acc


def take_sentences_from_start(text: str, need_tokens: int) -> str:
    """从文本开头提取句子, 直到达到 need_tokens (参考 ragflow take_sentences_from_start)"""
    txts = re.split(_SENTENCE_SPLIT, text, flags=re.DOTALL)
    acc = ""
    for j in range(0, len(txts), 2):
        acc += txts[j] + (txts[j + 1] if j + 1 < len(txts) else "")
        if count_tokens(acc) >= need_tokens:
            break
    return acc


# ---------------------------------------------------------------------------
# 上下文附着: bbox 空间定位 + 文档顺序回退 + 双向(above/below)
# ---------------------------------------------------------------------------


def _is_standalone_item(item: ChunkedItem) -> bool:
    """判断是否为独立内容块(非纯文本/标题)"""
    from module_office.utils.file_parase.do.chunk import ContentType

    text_types = {
        ContentType.TEXT.value,
        ContentType.IMAGE_CONTENT.value,
        ContentType.TITLE.value,
    }
    return not all(ct in text_types for ct in item.content_types)


def _is_pure_image_item(item: ChunkedItem) -> bool:
    """判断是否为纯图片块 (内容仅为图片路径 ![](...), 不适合作为上下文)

    区别于 _is_standalone_item: 表格/图表内容是实质性文本, 可作为上下文;
    只有纯图片块 (content_type 仅含 image) 的内容无语义价值, 需跳过。
    """
    from module_office.utils.file_parase.do.chunk import ContentType

    if not item.content_types:
        return False
    return all(ct == ContentType.IMAGE.value for ct in item.content_types)


def _take_last_sentence(text: str, max_tokens: int) -> str:
    """取文本最后一句 (按换行/句末标点切分), 超过 max_tokens 则从末尾按 token 截断

    区别于 take_sentences_from_end: 只取一句, 不向前累积多句。
    用于上文截取, 避免把不相关的远端内容 (如流程图代码尾部) 带入上下文。
    """
    txts = re.split(_SENTENCE_SPLIT, text, flags=re.DOTALL)
    sents = []
    for j in range(0, len(txts), 2):
        s = txts[j] + (txts[j + 1] if j + 1 < len(txts) else "")
        if s.strip():
            sents.append(s)
    if not sents:
        return ""
    last = sents[-1].strip()
    if count_tokens(last) <= max_tokens:
        return last
    # 最后一句过长: 按 token 从末尾截取 (保留最近的内容)
    tokens = list(re.finditer(r"[A-Za-z0-9_]+|[一-鿿]", last))
    if not tokens:
        return last
    start_idx = max(0, len(tokens) - max_tokens)
    return last[tokens[start_idx].start():].strip()


def _has_location(pos: Position) -> bool:
    """Position 是否携带有效定位信息"""
    return any(
        v is not None
        for v in (
            pos.page,
            pos.bbox,
            pos.text_range,
            pos.time_range,
            pos.heading_level,
        )
    )


def _extract_context_by_bbox(
    items: list[ChunkedItem],
    idx: int,
    need_tokens: int,
    direction: str,
) -> tuple[str, list[Position]]:
    """基于 bbox 空间邻近度查找上下文

    参考 ragflow append_context2table_image4pdf:
    对于有位置信息的独立块, 在同页查找空间相邻的文本块作为上下文。

    坐标系自适应: 自动检测 y 轴方向
    - docling 输出 y 轴向上 (t > b, 视觉上方 y 值更大)
    - deepdoc 输出 y 轴向下 (t < b, 视觉上方 y 值更小)
    归一化为 y_lo/y_hi 后, 根据检测到的方向判断 above/below。

    :param direction: "above" 找目标上方的文本, "below" 找目标下方的文本
    :return: (上下文文本, 来源 Position 列表)

    遍历按列表顺序(文档顺序: 早→晚):
    - above: 早=远, 晚=近 → append 得 [远, 近], join "远 近 target" 正确
    - below: 早=近, 晚=远 → append 得 [近, 远], join "target 近 远" 正确
    """
    target = items[idx].position
    if not target or target.page is None or target.bbox is None:
        return "", []

    target_page = target.page
    # 归一化 target y 范围 (不假设坐标系方向)
    target_y_lo = min(target.bbox[1], target.bbox[3])
    target_y_hi = max(target.bbox[1], target.bbox[3])

    # 检测同页坐标系方向: y 轴向上(t>b) 或 y 轴向下(t<b)
    same_page_bboxes = [
        it.position.bbox
        for it in items
        if it.position and it.position.page == target_page and it.position.bbox
    ]
    if not same_page_bboxes:
        return "", []
    y_axis_up = sum(1 for b in same_page_bboxes if b[1] > b[3]) > len(same_page_bboxes) // 2

    parts: list[str] = []
    picked: list[Position] = []
    remain = need_tokens

    for i, item in enumerate(items):
        if i == idx or _is_standalone_item(item):
            continue
        pos = item.position
        if not pos or pos.page != target_page or pos.bbox is None:
            continue

        # 归一化 item y 范围
        item_y_lo = min(pos.bbox[1], pos.bbox[3])
        item_y_hi = max(pos.bbox[1], pos.bbox[3])

        # 判断 item 是否在 target 的 above/below 方向 (y 范围不重叠)
        if direction == "above":
            # above: item 在 target 视觉上方
            #   y轴向上(视觉上方=y大): item_y_lo >= target_y_hi
            #   y轴向下(视觉上方=y小): item_y_hi <= target_y_lo
            is_match = (
                item_y_lo >= target_y_hi if y_axis_up else item_y_hi <= target_y_lo
            )
        else:
            # below: item 在 target 视觉下方
            #   y轴向上(视觉下方=y小): item_y_hi <= target_y_lo
            #   y轴向下(视觉下方=y大): item_y_lo >= target_y_hi
            is_match = (
                item_y_hi <= target_y_lo if y_axis_up else item_y_lo >= target_y_hi
            )

        if not is_match:
            continue

        text = item.content
        tk = count_tokens(text)
        if tk >= remain:
            if direction == "above":
                parts.append(take_sentences_from_end(text, remain))
            else:
                parts.append(take_sentences_from_start(text, remain))
            picked.append(pos)
            remain = 0
            break
        else:
            parts.append(text)
            picked.append(pos)
            remain -= tk

    return "".join(parts).strip(), picked


def _extract_context_above(
    items: list[ChunkedItem], idx: int, need_tokens: int
) -> tuple[str, list[Position]]:
    """提取上文: 取最近的一个非纯图片块 (跳过纯图片块)

    改进逻辑:
    - 从 idx-1 向前找, 仅跳过纯图片块 (内容为 ![](...) 无语义价值)
    - 表格/图表内容是实质性文本, 不跳过, 可作为上下文
    - 命中块若小于等于 need_tokens, 直接用整块
    - 命中块若超过 need_tokens, 只取最后一句 (最近的信息), 不向前累积多句
      避免把不相关的远端内容 (如流程图代码尾部) 带入上下文

    注: 暂不使用 bbox 空间定位。docling 输出 y 轴向上坐标系 (t>b),
    而 merge_positions 聚合 bbox 时假设 y 轴向下, 导致合并文本块
    的 bbox 方向与独立块不一致, bbox 路径判断不可靠。
    待解析层统一坐标系后可恢复 bbox 空间定位 (见 _extract_context_by_bbox)。

    :return: (上下文文本, 来源 Position 列表)
    """
    prev = idx - 1
    while prev >= 0:
        prev_item = items[prev]
        if _is_pure_image_item(prev_item):
            prev -= 1
            continue
        # 命中最近的非纯图片块: 小则原样, 大则只取最后一句
        text = prev_item.content
        if count_tokens(text) > need_tokens:
            text = _take_last_sentence(text, need_tokens)
        picked = [prev_item.position] if _has_location(prev_item.position) else []
        return text.strip(), picked
    return "", []


def _extract_context_below(
    items: list[ChunkedItem], idx: int, need_tokens: int
) -> tuple[str, list[Position]]:
    """提取下文: 取最近的一个非纯图片块 (跳过纯图片块)

    改进逻辑:
    - 从 idx+1 向后找, 仅跳过纯图片块 (内容为 ![](...) 无语义价值)
    - 命中块若超过 need_tokens, 取其开头 need_tokens 个 token 的句子
    - 命中即停止, 不向后累积多个块

    防污染 (下文只取"说明性正文", 避免跨块重复):
    - 跳过命中块开头的标题行 (# 开头): 标题属于新节, 归属其后内容,
      拖入会造成标题同时出现在相邻两个块
    - 过滤标题后首行是表格线 (|) 或图片引用 (!) 时放弃:
      表格/图片是下一块的实体内容, 拖入会造成大段跨块重复

    :return: (上下文文本, 来源 Position 列表)
    """
    after = idx + 1
    while after < len(items):
        after_item = items[after]
        if _is_pure_image_item(after_item):
            after += 1
            continue
        # 命中最近的非纯图片块: 跳过开头标题行后取说明性正文
        lines = (after_item.content or "").splitlines()
        start = 0
        while start < len(lines) and lines[start].lstrip().startswith("#"):
            start += 1
        body_lines = [ln for ln in lines[start:] if ln.strip()]
        if not body_lines or body_lines[0].lstrip().startswith(("|", "!")):
            return "", []
        text = "\n".join(body_lines)
        if count_tokens(text) > need_tokens:
            text = take_sentences_from_start(text, need_tokens)
        picked = [after_item.position] if _has_location(after_item.position) else []
        return text.strip(), picked
    return "", []


def attach_context(
    items: list[ChunkedItem],
    context_token_num: int,
    with_above: bool = True,
) -> list[ChunkedItem]:
    """为独立内容(表格/图片等)附加双向上下文

    参考 ragflow 的 _add_context:
    - 遍历分块结果, 找到非文本类型的独立块
    - 提取上文(context_above): 从前序文本块末尾提取句子
    - 提取下文(context_below): 从后续文本块开头提取句子
    - 基于文档顺序提取 (bbox 空间定位待坐标系统一后启用)
    - 将上下文直接接入独立块内容前后, 增强向量检索关联性

    :param items: 已分块的结果列表
    :param context_token_num: 上下文 token 数, 0 表示不附带
    :param with_above: 是否附加上文; 调用方已自行构建上文
        (如标题前缀/重叠尾部) 时传 False 避免重复
    :return: 附加上下文后的结果列表
    """
    if context_token_num <= 0 or len(items) <= 1:
        return items

    # 先从原始 items 计算所有上下文, 再统一应用
    # 避免 in-place 修改导致后续块读到已污染的内容 (如 chunk4 读到 chunk3
    # 已附加的 below 上下文, 造成循环引用)
    from module_office.utils.file_parase.do.chunk import ContentType

    pending: list[tuple[int, str, str]] = []
    for i, item in enumerate(items):
        if not _is_standalone_item(item):
            continue
        # 独立块已包含标题 (前处理时直接合并) 时, 标题即上文, 不再额外提取
        if not with_above or ContentType.TITLE.value in (item.content_types or []):
            above = ""
        else:
            above, _ = _extract_context_above(items, i, context_token_num)
        below, _ = _extract_context_below(items, i, context_token_num)
        if above or below:
            pending.append((i, above, below))

    result = list(items)
    for i, above, below in pending:
        item = result[i]
        # 上下文直接接入原内容前后 (对齐 ragflow: context_above + text + context_below)
        # 不加 [上文]/[下文] 标签, 避免污染原文
        parts: list[str] = []
        if above:
            parts.append(above)
        parts.append(item.content)
        if below:
            parts.append(below)
        # 只更新 content, 保留独立块原始 position
        # 上下文仅辅助向量检索, 不改变独立块的物理位置 (page/bbox/heading_level)
        result[i] = item.model_copy(update={"content": "\n".join(parts)})

    return result


# ---------------------------------------------------------------------------
# 朴素合并: 位置感知 + 短标题强制合并 + overlap
# ---------------------------------------------------------------------------


def naive_merge(
    chunks: list[Chunk],
    chunk_token_num: int = 512,
    delimiter: str = "\n",
    overlapped_percent: int = 10,
) -> list[ChunkedItem]:
    """位置感知的朴素合并

    改进自 ragflow naive_merge 算法:
    - 输入为 Chunk 列表 (而非文本字符串), 避免位置信息丢失
    - 合并时追踪来源 Chunk, 聚合位置信息
    - 超长块按分隔符拆分后参与合并
    - 短标题强制合并: 短标题不封存为独立块, 强制与后续内容合并
      (参考 ragflow _is_short_header)
    - 支持 overlap: 从前一个块尾部截取文本注入下一个块头部

    参考 ragflow _merge_paragraph_groups 的分组策略:
    - 累积段落直到达到 token 上限
    - 超限时封存当前块, 开启新块

    :param chunks: 原始分块列表
    :param chunk_token_num: 单块最大 token 数
    :param delimiter: 分段分隔符
    :param overlapped_percent: 重叠百分比 0-99
    :return: 合并后的 ChunkedItem 列表
    """
    if not chunks:
        return []

    # 1. 将每个 Chunk 按分隔符拆分为子段, 保留来源引用
    sub_sections: list[tuple[str, Chunk]] = []
    for chunk in chunks:
        text = (chunk.content or "").strip()
        if not text:
            continue

        token_num = count_tokens(text)
        if token_num <= chunk_token_num:
            sub_sections.append((text, chunk))
        else:
            parts = split_by_delimiter(text, delimiter)
            if len(parts) <= 1:
                hard_limit = int(chunk_token_num * 1.5)
                parts = hard_split_by_token_limit(text, chunk_token_num, hard_limit)
            for part in parts:
                if part.strip():
                    sub_sections.append((part, chunk))

    if not sub_sections:
        return []

    # 2. 朴素合并: 累积子段直到达到 token 上限 (参考 ragflow _merge_paragraph_groups)
    overlap = max(0, min(int(overlapped_percent or 0), 99))
    threshold = chunk_token_num * (100 - overlap) / 100.0

    items: list[ChunkedItem] = []
    current_texts: list[str] = []
    current_tokens = 0
    current_sources: list[Chunk] = []

    def _is_current_short_header() -> bool:
        """检查当前累积内容是否为短标题 (不应独立封存)"""
        if not current_texts:
            return False
        content = delimiter.join(current_texts)
        # markdown 标题模式 或 heading_level 标记的标题
        if _is_short_header(content):
            return True
        if _is_header_sources(current_sources) and count_tokens(content) < _SHORT_HEADER_MAX_TOKENS:
            return True
        return False

    def _finalize() -> None:
            nonlocal current_texts, current_tokens, current_sources
            if not current_texts:
                return
            content = delimiter.join(current_texts)
            if content.strip():
                items.append(build_item(content, current_sources))

            # 【优化点 2】Overlap 按句子边界提取, 避免单词/句子被硬切断
            if overlap > 0 and current_texts:
                tail_text = current_texts[-1]
                # 估算需要重叠的 token 数 (按百分比换算)
                target_overlap_tokens = int(count_tokens(tail_text) * overlap / 100)
                if target_overlap_tokens > 0:
                    # 使用句子级提取, 保证语义完整性
                    overlap_part = take_sentences_from_end(tail_text, target_overlap_tokens)
                    current_texts = [overlap_part] if overlap_part.strip() else []
                    current_tokens = count_tokens(overlap_part) if overlap_part else 0
                    current_sources = list(current_sources[-1:])
                    return
                    
            current_texts = []
            current_tokens = 0
            current_sources = []

    for text, source_chunk in sub_sections:
        token_num = count_tokens(text)

        # 超限时封存: 但短标题不封存, 强制与下一段合并 (参考 ragflow _is_short_header)
        if (
            current_texts
            and current_tokens > threshold
            and current_tokens + token_num > chunk_token_num
            and not _is_current_short_header()
        ):
            _finalize()

        current_texts.append(text)
        current_tokens += token_num
        current_sources.append(source_chunk)

    _finalize()

    # 3. 兜底: 合并后仍有超长块, 硬切保护
    result: list[ChunkedItem] = []
    hard_limit = int(chunk_token_num * 1.5)
    for item in items:
        if count_tokens(item.content) <= hard_limit:
            result.append(item)
        else:
            parts = hard_split_by_token_limit(item.content, chunk_token_num, hard_limit)
            for part in parts:
                if part.strip():
                    # 硬切时保留原 item 的位置和元数据
                    result.append(item.model_copy(update={"content": part}))

    return [item for item in result if item.content.strip()]
