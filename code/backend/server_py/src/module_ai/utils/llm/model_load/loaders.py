"""模型加载工具

封装 Qwen LLM、Jina Embedding、Jina Reranker 的本地加载逻辑。
从原 llm_local_todo.py 迁移并整理。
"""
from pathlib import Path

import numpy as np
import torch
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
from transformers import (
    AutoModel,
    AutoModelForCausalLM,
    AutoTokenizer,
    pipeline,
)


# =====================
# 通用工具
# =====================


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度。"""
    x = np.asarray(a, dtype=np.float32)
    y = np.asarray(b, dtype=np.float32)
    return float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-9))


def build_chat_prompt(tokenizer: AutoTokenizer, question: str) -> str:
    """优先使用 Qwen 聊天模板；不支持时退回纯文本 prompt。"""
    messages = [{"role": "user", "content": question}]

    if not hasattr(tokenizer, "apply_chat_template"):
        return f"{question}\n"

    try:
        # Qwen3 / Qwen3.5 系列如果支持 thinking 控制，可关闭思考链
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    except (TypeError, ValueError):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )


# =====================
# Qwen LLM
# =====================


def load_qwen_llm(model_path: Path) -> tuple[HuggingFacePipeline, AutoTokenizer]:
    """加载 Qwen3.5-0.8B，并包装成 LangChain 可调用的 LLM。

    Args:
        model_path: 本地模型目录。

    Returns:
        (llm, tokenizer) 二元组。
    """
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        trust_remote_code=True,
        torch_dtype="auto",
    )

    model.generation_config.pad_token_id = tokenizer.pad_token_id
    model.generation_config.eos_token_id = tokenizer.eos_token_id

    use_cuda = torch.cuda.is_available()
    if use_cuda:
        model = model.to("cuda")

    text_pipeline = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        device=0 if use_cuda else -1,
        max_new_tokens=512,
        temperature=0.7,
        do_sample=True,
        return_full_text=False,
    )

    llm = HuggingFacePipeline(pipeline=text_pipeline)
    return llm, tokenizer


# =====================
# Jina Embeddings v5
# =====================


def load_embeddings(model_path: Path) -> HuggingFaceEmbeddings:
    """加载 jina-embeddings-v5-text 向量模型。"""
    return HuggingFaceEmbeddings(
        model_name=str(model_path),
        model_kwargs={
            "trust_remote_code": True,
            "device": "cuda" if torch.cuda.is_available() else "cpu",
        },
        encode_kwargs={
            "normalize_embeddings": True,
            "task": "retrieval",  # 指定任务类型
        },
    )


# =====================
# Jina Reranker v3
# =====================


class JinaReranker:
    """Jina Reranker v3 的简易本地推理封装。"""

    def __init__(self, model_path: Path):
        """初始化 tokenizer 和 reranker 模型。

        Args:
            model_path: 本地模型目录。
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = AutoModel.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype="auto",
        ).eval()

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[dict[str, str | float]]:
        """对候选文档按与 query 的相关性重排。

        Args:
            query: 查询文本。
            documents: 候选文档列表。
            top_n: 仅返回前 N 个结果，None 表示全部返回。

        Returns:
            [{"document": str, "score": float}, ...] 按分数降序排列。
        """
        if not documents:
            return []

        results = self.model.rerank(query, documents)
        ranked = [
            {"document": r["document"], "score": r["relevance_score"]} for r in results
        ]
        if top_n is not None:
            ranked = ranked[:top_n]
        return ranked
