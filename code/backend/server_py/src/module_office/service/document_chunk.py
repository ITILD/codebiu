import logging
import re
from typing import Any, List, Dict
from module_office.do.schemas import (
    BatchProcessingResult,
    ChunkedResult,
    BatchChunkedResult,
    TextChunk,
    ContentBlock,
)
from module_office.utils.document_chunk.chunk_strategy.utils.dispatcher import (
    chunk_markdown as engine_chunk_markdown,
)
from langchain.chat_models import BaseChatModel
from module_office.utils.document_chunk.do.chunk import (
    ChunkConfig,
    ChunkStrategyEnum,
    ChunkStrategyRecommendation,
    ChunkedItem,
)
from module_office.utils.document_chunk.base import get_chunker
from module_office.utils.file_parase.do.chunk import Chunk
from module_office.dao.document_chunk_prompt import DocumentChunkPrompt

logger = logging.getLogger(__name__)


class DocumentChunkService:
    def __init__(self, document_chunk_prompt: DocumentChunkPrompt):
        self.document_chunk_prompt = document_chunk_prompt or DocumentChunkPrompt()

    async def detect_strategy(
        self, filename: str, markdown_content: str, llm: BaseChatModel
    ) -> ChunkStrategyRecommendation:
        """
        检测markdown内容,智能识别最适合的分块策略
        """
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension in {"py", "java"}:
            return ChunkStrategyRecommendation(
                strategy=ChunkStrategyEnum.CODE,
                reason="源代码文件使用类、函数和方法边界进行语义拆分",
            )

        chunk_strategy_recommendation = ChunkStrategyRecommendation(
            strategy=ChunkStrategyEnum.GENERAL
        )
        try:
            if not llm:
                logger.warning("未获取到 LLM 实例，回退到默认策略 'general'")
                return chunk_strategy_recommendation
            # 启用结构化输出，Pydantic 会自动确保返回的 strategy 是合法的枚举值
            structured_llm = llm.with_structured_output(ChunkStrategyRecommendation)
            # 调用大模型获取分块策略推荐
            strategy_prompt = await self.document_chunk_prompt.get_strategy_prompt(
                filename, markdown_content
            )
            chunk_strategy_recommendation: ChunkStrategyRecommendation = (
                await structured_llm.ainvoke(strategy_prompt)
            )
            strategy: ChunkStrategyEnum = chunk_strategy_recommendation.strategy
            logger.info(
                f"""
文档 [{filename}] 
策略: {strategy} 
理由: {chunk_strategy_recommendation.reason}"""
            )
        except Exception as e:
            logger.warning(f"智能识别分块策略失败: {e},回退到默认策略 'general'")
        return chunk_strategy_recommendation

    def chunk(
        self,
        chunks: list[Chunk],
        strategy: ChunkStrategyEnum,
        config: ChunkConfig | None = None,
        engine: str = "ragflow",
    ) -> list[ChunkedItem]:
        """
        根据策略对原始 Chunk 列表重新分块

        封装 get_chunker + chunker.chunk() 编排逻辑,
        供 parse_document 调用。

        :param chunks: 文档解析后的原始分块列表 (list[Chunk])
        :param strategy: 分块策略 (枚举或大模型推荐结果)
        :param config: 分块配置, 为 None 时使用默认配置
        :param engine: 分块引擎 ("ragflow" / "langchain")
        :return: 重新分块后的 ChunkedItem 列表
        """

        chunk_config = config or ChunkConfig()
        chunker = get_chunker(
            engine=engine,
            strategy=strategy,
            config=chunk_config,
        )
        chunked_items = chunker.chunk(chunks)
        logger.info(
            f"分块完成: 策略={strategy}, 引擎={engine}, "
            f"输入={len(chunks)}块, 输出={len(chunked_items)}块"
        )
        return chunked_items

