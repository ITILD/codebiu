# coding: utf-8
import json
import math
import urllib.request

encode = "utf-8"
texts = [
    "Which country's capital is Paris?",
    "The capital of France is Paris",
    "The capital of Brazil is Brasília",
     "Which country's capital is Paris?",
]


def get_text_embedding(
    text: str, model: str = "bge-m3:latest", ollama_url: str = "http://localhost:11434"
) -> list[float]:
    """
    通过Ollama API获取文本的向量表示

    参数:
        text: 要向量化的文本
        ollama_url: Ollama服务地址

    返回:
        文本的嵌入向量

    异常:
        RuntimeError: 如果API请求失败
    """
    # 准备请求数据
    data = {"model": model, "prompt": text, "options": {}}

    # 发送HTTP请求
    req = urllib.request.Request(
        f"{ollama_url}/api/embeddings",
        data=json.dumps(data).encode(encode),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode(encode))
            return result.get("embedding", [])
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接到Ollama服务: {e}")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    计算两个向量的余弦相似度

    参数:
        a: 第一个向量
        b: 第二个向量

    返回:
        余弦相似度值 (范围[-1, 1])
    """
    # 计算点积
    dot_product = sum(x * y for x, y in zip(a, b))

    # 计算向量模
    magnitude_a = math.sqrt(sum(x**2 for x in a))
    magnitude_b = math.sqrt(sum(y**2 for y in b))

    # 避免除以零
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


def main():
    # 每次一个texts
    embedding_list = []
    for text in texts:
        try:
            embedding = get_text_embedding(text)
            embedding_list.append(embedding)
        except RuntimeError as e:
            print(f"获取向量失败: {e}")
    # 每取两个 计算余弦相似度
    for i in range(0, len(embedding_list) - 1):
        embedding1 = embedding_list[i]
        embedding2 = embedding_list[i + 1]
        similarity = cosine_similarity(embedding1, embedding2)
        print(f"\n{i} {i+1}两段文本的余弦相似度为: {similarity:.4f}")


if __name__ == "__main__":
    print("=== 文本相似度计算器 ===")
    print("使用本地Ollama服务(bge-m3模型)")
    main()
