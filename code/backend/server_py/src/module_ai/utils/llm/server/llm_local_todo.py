import os
from pathlib import Path

import numpy as np
import torch
from huggingface_hub import snapshot_download
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
from transformers import (
    AutoModel,
    AutoModelForCausalLM,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    pipeline,
)
from src.common.config.path import DIR_MODEL

# =====================
# 模型配置
# =====================
MODEL_PATH = DIR_MODEL / "temp"
# 如果你用的是 Instruct 版本，可以改成：Qwen/Qwen3.5-0.8B-Instruct
QWEN_REPO_ID = "Qwen/Qwen3.5-0.8B"
QWEN_LOCAL_PATH = MODEL_PATH / "models/Qwen3.5-0.8B"

EMBEDDING_REPO_ID = "jinaai/jina-embeddings-v5-text-small"
EMBEDDING_LOCAL_PATH = MODEL_PATH / "models/jina-embeddings-v5-text-small"

RERANKER_REPO_ID = "jinaai/jina-reranker-v3"
RERANKER_LOCAL_PATH = MODEL_PATH / "models/jina-reranker-v3"


# =====================
# 通用工具函数
# =====================


def ensure_local_model(repo_id: str, local_dir: Path) -> Path:
    """下载模型到本地；如果本地已存在则跳过。"""
    if local_dir.exists() and any(local_dir.iterdir()):
        print(f"使用本地模型：{local_dir}")
        return local_dir

    print(f"开始下载 {repo_id} 到 {local_dir} ...")
    local_dir.mkdir(parents=True, exist_ok=True)

    # 如果是私有或 gated 模型，需要提前设置环境变量 HF_TOKEN
    snapshot_download(
        repo_id=repo_id,
        local_dir=local_dir,
        token=os.getenv("HF_TOKEN"),
    )

    print(f"{repo_id} 下载完成")
    return local_dir


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算余弦相似度。"""
    x = np.asarray(a, dtype=np.float32)
    y = np.asarray(b, dtype=np.float32)
    return float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-9))


# =====================
# Qwen3.5-0.8B LLM
# =====================


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


def load_qwen_llm(model_path: Path) -> tuple[HuggingFacePipeline, AutoTokenizer]:
    """加载 Qwen3.5-0.8B，并包装成 LangChain 可调用的 LLM。"""
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True,
    )

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
            # "show_progress_bar": False,
            "task": "retrieval",  # ← 新增：指定任务类型
        },
    )


# =====================
# Jina Reranker v3
# =====================


class JinaReranker:
    """Jina Reranker v3 的简易本地推理封装。"""

    def __init__(self, model_path: Path):
        """初始化 tokenizer 和 reranker 模型。"""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model =AutoModel.from_pretrained(
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
        """对候选文档按与 query 的相关性重排。"""
        if not documents:
            return []

        results = self.model.rerank(query, documents)
        return [{"document": result['document'], "score": result['relevance_score']} for result in results]    


# =====================
# Demo
# =====================


def main() -> None:
    """运行 Qwen LLM、Jina Embedding、Jina Reranker 三个示例。"""

    # 1. 确保模型已下载到本地
    qwen_path = ensure_local_model(QWEN_REPO_ID, QWEN_LOCAL_PATH)
    embedding_path = ensure_local_model(EMBEDDING_REPO_ID, EMBEDDING_LOCAL_PATH)
    reranker_path = ensure_local_model(RERANKER_REPO_ID, RERANKER_LOCAL_PATH)

    # 2. 加载 Qwen3.5-0.8B
    llm, tokenizer = load_qwen_llm(qwen_path)

    question = "1+1? 只输出结果"
    prompt = build_chat_prompt(tokenizer, question)

    result = llm.invoke(prompt)
    print("Qwen 输出：", result.strip())

    # 3. Embedding 向量化 demo
    query = "1+1等于？"
    documents = [
        "1+1等于2。",
        "巴黎是法国的首都。",
        "Python 是一种高级编程语言。",
    ]

    embeddings = load_embeddings(embedding_path)

    query_vector = embeddings.embed_query(query)
    document_vectors = embeddings.embed_documents(documents)

    print("\nEmbedding 维度：", len(query_vector))

    for doc, vec in zip(documents, document_vectors, strict=True):
        score = cosine_similarity(query_vector, vec)
        print(f"相似度 {score:.4f} | {doc}")

    # 4. Reranker 重排序 demo
    reranker = JinaReranker(reranker_path)

    ranked_documents = reranker.rerank(
        query=query,
        documents=documents,
        top_n=2,
    )

    print("\nReranker Top2：")
    for item in ranked_documents:
        print(f"分数 {item['score']:.4f} | {item['document']}")


if __name__ == "__main__":
    main()
