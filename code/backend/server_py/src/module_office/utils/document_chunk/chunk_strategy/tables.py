from __future__ import annotations

import re
from typing import Any

from module_office.utils.document_chunk.chunk_strategy.utils import nlp
from module_office.utils.document_chunk.chunk_strategy import general

def chunk_markdown(markdown_content: str, parser_config: dict[str, Any] | None = None) -> list[str]:
    """
    针对 Excel (多 Sheet) 优化的分块策略。
    核心机制：双重上下文继承 (Sheet 名称 + 表格表头)。
    确保每个切分出的数据块，大模型都能明确知道它属于哪个工作表、哪一列。
    """
    parser_config = parser_config or {}
    chunk_token_num = int(parser_config.get("chunk_token_num", 512) or 512)
    
    lines = [line.strip() for line in markdown_content.split('\n') if line.strip()]
    if not lines:
        return []

    chunks = []
    current_block = []
    in_table = False
    table_header = []
    current_sheet_name = "未知工作表" # 默认 Sheet 名称
    
    # 正则 1: 匹配 Markdown 表格的分隔行 (|---|)
    separator_pattern = re.compile(r'^\|?[\s\-:]+\|?$')
    # 正则 2: 匹配 Sheet 标题 (支持 # Sheet: xxx 或 ### 工作表: xxx)
    sheet_pattern = re.compile(r'^#{1,3}\s*(?:Sheet|工作表|表)[:：\s]*(.+)$', re.IGNORECASE)

    for line in lines:
        # 1. 检测是否切换了 Sheet
        sheet_match = sheet_pattern.match(line)
        if sheet_match:
            # 如果之前有未保存的表格块，先保存
            if in_table and len(current_block) > len(table_header):
                chunks.append('\n'.join(current_block))
            
            # 更新当前 Sheet 名称，并重置表格状态
            current_sheet_name = sheet_match.group(1).strip()
            in_table = False
            current_block = []
            table_header = []
            continue # 标题行本身不作为表格数据，跳过

        is_table_row = '|' in line
        
        if is_table_row and not in_table:
            # 2. 发现新表格开始
            in_table = True
            table_header = [line]
            # 每个新表格块的开头，必须强制带上 Sheet 名称！
            current_block = [f"[所属工作表: {current_sheet_name}]", line]
            
        elif in_table and is_table_row:
            # 3. 正在处理表格数据
            if separator_pattern.match(line):
                # 表头分隔线，必须和表头绑定
                table_header.append(line)
                current_block.append(line)
            else:
                # 普通数据行
                test_block = current_block + [line]
                test_text = '\n'.join(test_block)
                
                # 检查加入此行后是否超限
                if nlp.count_tokens(test_text) <= chunk_token_num:
                    current_block.append(line)
                else:
                    # 超限：保存当前完整的表格块
                    if len(current_block) > len(table_header) + 1: # +1 是因为包含了 Sheet 名称行
                        chunks.append('\n'.join(current_block))
                    
                    # 开启新块：新块必须再次以 "Sheet 名称 + 表头" 开头！
                    current_block = [f"[所属工作表: {current_sheet_name}]"] + table_header + [line]
                    
                    # 极端兜底：如果“Sheet名 + 表头 + 单行”本身就超限，依然保存，防止死循环
                    if nlp.count_tokens('\n'.join(current_block)) > chunk_token_num:
                        chunks.append('\n'.join(current_block))
                        current_block = [f"[所属工作表: {current_sheet_name}]"] + table_header
                        
        else:
            # 4. 遇到非表格行 (普通文本)，说明当前表格已结束
            if in_table:
                if len(current_block) > len(table_header) + 1:
                    chunks.append('\n'.join(current_block))
                elif current_block:
                    chunks.append('\n'.join(current_block))
                in_table = False
                current_block = []
            
            # 将普通文本加入当前块
            current_block.append(line)
            
    # 循环结束，处理最后一个遗留的块
    if current_block:
        if in_table and len(current_block) > len(table_header) + 1:
            chunks.append('\n'.join(current_block))
        else:
            chunks.append('\n'.join(current_block))

    # 兜底：如果没有识别出任何有效分块，回退到通用策略
    if not chunks or (len(chunks) == 1 and len(chunks[0]) == len(markdown_content)):
        return general.chunk_markdown(markdown_content, parser_config)

    return [c for c in chunks if c.strip()]