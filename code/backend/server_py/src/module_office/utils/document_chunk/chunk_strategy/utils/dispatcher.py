from __future__ import annotations

from typing import Any

from module_office.utils.document_chunk.chunk_strategy import book, general, laws, qa, semantic, separator,tables
from module_office.utils.document_chunk.chunk_strategy.utils.presets import map_to_internal_parser_id, normalize_chunk_preset_id


def _build_chunk_records(
    text_chunks: list[str], file_id: str, filename: str, source_text: str | None = None
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    search_from = 0

    for idx, chunk_content in enumerate(text_chunks):
        text = (chunk_content or "").strip()
        if not text:
            continue

        start_char_pos = None
        end_char_pos = None
        if source_text:
            found_at = source_text.find(text, search_from)
            if found_at < 0:
                # 提取 text 的前 50 个字符作为“指纹”
                fingerprint = text[:50].strip()
                if len(fingerprint) >= 10:  # 确保指纹足够长，避免误匹配到无关内容
                    found_at = source_text.find(fingerprint, search_from)
                    
            if found_at >= 0:
                start_char_pos = found_at
                # 提取 text 的尾部 20 个字符，在 source_text 中从 found_at 开始向后查找
                tail_text = text[-20:].strip()
                if len(tail_text) >= 5:
                    tail_found = source_text.find(tail_text, found_at)
                    if tail_found >= 0:
                        end_char_pos = tail_found + len(tail_text)
                    else:
                        end_char_pos = found_at + len(text)  # 降级为近似值
                else:
                    end_char_pos = found_at + len(text)
                    
                # # 更新 search_from，确保下一个 chunk 不会匹配到当前 chunk 的前面
                # search_from = end_char_pos
                # end_char_pos = found_at + len(text)
                # search_from = end_char_pos

        records.append(
            {
                "id": f"{file_id}_chunk_{idx}",
                "content": text,
                "file_id": file_id,
                "filename": filename,
                "chunk_index": idx,
                "source": filename,
                "chunk_id": f"{file_id}_chunk_{idx}",
                "start_char_pos": start_char_pos,
                "end_char_pos": end_char_pos,
                "start_token_pos": None,
                "end_token_pos": None,
                "extraction_result": None,
            }
        )

    return records


def _dispatch_markdown_parser(
    preset_id: str, filename: str, markdown_content: str, parser_config: dict[str, Any]
) -> list[str]:
    parser_id = map_to_internal_parser_id(preset_id)

    if parser_id == "naive":
        return general.chunk_markdown(markdown_content, parser_config)
    if parser_id == "qa":
        return qa.chunk_markdown(filename, markdown_content, parser_config)
    if parser_id == "book":
        return book.chunk_markdown(markdown_content, parser_config)
    if parser_id == "laws":
        return laws.chunk_markdown(filename, markdown_content, parser_config)
    if parser_id == "semantic":
        return semantic.chunk_markdown(markdown_content, parser_config)
    if parser_id == "separator":
        return separator.chunk_markdown(markdown_content, parser_config)
    if parser_id in ("tables"):
        return tables.chunk_markdown(markdown_content, parser_config)

    return general.chunk_markdown(markdown_content, parser_config)


def chunk_markdown(
    markdown_content: str, file_id: str, filename: str, processing_params: dict[str, Any]
) -> list[dict[str, Any]]:
    params = dict(processing_params or {})
    preset_id = normalize_chunk_preset_id(params.get("chunk_preset_id"))
    parser_config = params.get("chunk_parser_config") if isinstance(params.get("chunk_parser_config"), dict) else {}

    text_chunks = _dispatch_markdown_parser(preset_id, filename, markdown_content, parser_config)
    return _build_chunk_records(text_chunks, file_id, filename, markdown_content)


def chunk_file(
    file_content: str, file_id: str, filename: str, processing_params: dict[str, Any]
) -> list[dict[str, Any]]:
    # 当前链路中入库前均已转换为 markdown，因此与 chunk_markdown 保持同实现。
    return chunk_markdown(file_content, file_id, filename, processing_params)
