"""模型测试器

下载完成后，对 Qwen LLM、Jina Embedding、Jina Reranker 进行快速冒烟测试，
验证模型可正常加载与推理。
"""
import logging
from pathlib import Path

from module_ai.utils.llm.model_load.constants import get_model_spec
from module_ai.utils.llm.model_load.loaders import (
    JinaReranker,
    build_chat_prompt,
    cosine_similarity,
    load_embeddings,
    load_qwen_llm,
)

logger = logging.getLogger(__name__)


class ModelTester:
    """模型冒烟测试器。

    依赖模型已下载到本地目录。可通过 key 测试预置模型，
    也可直接传入本地路径测试任意模型。

    Examples:
        >>> tester = ModelTester()
        >>> tester.test_llm()        # 测试预置的 Qwen LLM
        >>> tester.test_embeddings() # 测试预置的 Jina Embedding
        >>> tester.test_reranker()   # 测试预置的 Jina Reranker
        >>> tester.test_all()        # 全部测试
    """

    # 默认测试用例
    LLM_QUESTION = "1+1? 只输出结果"
    EMBEDDING_QUERY = "1+1等于？"
    EMBEDDING_DOCS = [
        "1+1等于2。",
        "巴黎是法国的首都。",
        "Python 是一种高级编程语言。",
    ]
    RERANKER_QUERY = "1+1等于？"
    RERANKER_DOCS = EMBEDDING_DOCS

    def __init__(self, reranker_top_n: int = 2):
        """初始化测试器。

        Args:
            reranker_top_n: reranker 测试时返回的 top N 数量。
        """
        self.reranker_top_n = reranker_top_n

    # ------------------------------
    # LLM 测试
    # ------------------------------

    def test_llm(self, key: str = "qwen_llm") -> str:
        """测试 Qwen LLM 生成。

        Args:
            key: 注册表中的模型 key。

        Returns:
            LLM 生成的文本。
        """
        spec = get_model_spec(key)
        return self._test_llm_path(spec.local_dir, self.LLM_QUESTION)

    def _test_llm_path(self, model_path: Path, question: str) -> str:
        logger.info("加载 LLM: %s", model_path)
        llm, tokenizer = load_qwen_llm(model_path)

        prompt = build_chat_prompt(tokenizer, question)
        result = llm.invoke(prompt)
        text = result.strip()

        print(f"\n[LLM] 问题: {question}")
        print(f"[LLM] 输出: {text}")
        return text

    # ------------------------------
    # Embedding 测试
    # ------------------------------

    def test_embeddings(self, key: str = "embedding") -> dict:
        """测试 Jina Embedding 向量化与相似度计算。

        Args:
            key: 注册表中的模型 key。

        Returns:
            {"dim": int, "scores": [(doc, score), ...]}
        """
        spec = get_model_spec(key)
        return self._test_embeddings_path(
            spec.local_dir, self.EMBEDDING_QUERY, self.EMBEDDING_DOCS
        )

    def _test_embeddings_path(
        self, model_path: Path, query: str, documents: list[str]
    ) -> dict:
        logger.info("加载 Embedding: %s", model_path)
        embeddings = load_embeddings(model_path)

        query_vec = embeddings.embed_query(query)
        doc_vecs = embeddings.embed_documents(documents)

        scores = [
            (doc, cosine_similarity(query_vec, vec))
            for doc, vec in zip(documents, doc_vecs, strict=True)
        ]

        print(f"\n[Embedding] 维度: {len(query_vec)}")
        for doc, score in scores:
            print(f"[Embedding] 相似度 {score:.4f} | {doc}")

        return {"dim": len(query_vec), "scores": scores}

    # ------------------------------
    # Reranker 测试
    # ------------------------------

    def test_reranker(self, key: str = "reranker") -> list[dict]:
        """测试 Jina Reranker 重排序。

        Args:
            key: 注册表中的模型 key。

        Returns:
            [{"document": str, "score": float}, ...]
        """
        spec = get_model_spec(key)
        return self._test_reranker_path(
            spec.local_dir, self.RERANKER_QUERY, self.RERANKER_DOCS
        )

    def _test_reranker_path(
        self, model_path: Path, query: str, documents: list[str]
    ) -> list[dict]:
        logger.info("加载 Reranker: %s", model_path)
        reranker = JinaReranker(model_path)

        ranked = reranker.rerank(
            query=query,
            documents=documents,
            top_n=self.reranker_top_n,
        )

        print(f"\n[Reranker] Top{self.reranker_top_n}:")
        for item in ranked:
            print(f"[Reranker] 分数 {item['score']:.4f} | {item['document']}")

        return ranked

    # ------------------------------
    # 全部测试
    # ------------------------------

    def test_all(self) -> dict:
        """依次测试 LLM、Embedding、Reranker。

        Returns:
            {"llm": str, "embeddings": dict, "reranker": list}
        """
        print("\n========== 开始模型冒烟测试 ==========")
        results: dict = {}

        try:
            results["llm"] = self.test_llm()
        except Exception as e:
            logger.error("LLM 测试失败: %s", e)
            results["llm"] = f"<error: {e}>"

        try:
            results["embeddings"] = self.test_embeddings()
        except Exception as e:
            logger.error("Embedding 测试失败: %s", e)
            results["embeddings"] = {"error": str(e)}

        try:
            results["reranker"] = self.test_reranker()
        except Exception as e:
            logger.error("Reranker 测试失败: %s", e)
            results["reranker"] = [{"error": str(e)}]

        print("\n========== 模型冒烟测试完成 ==========")
        return results
