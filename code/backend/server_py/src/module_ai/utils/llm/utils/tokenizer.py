from transformers import AutoTokenizer
import tiktoken

class Tokenizer:
    # 模型到 tiktoken 编码的映射
    TIKTOKEN_MODELS = {
        "gpt-3.5-turbo": "cl100k_base",
        "gpt-4": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-4o": "o200k_base",
        "gpt-4o-mini": "o200k_base",
    }

    def __init__(self, cache_dir: str = "source/model/tokenizer"):
        self.cache_dir = cache_dir
        self._tiktoken_encodings = {}
        self._transformer_tokenizers = {}

    def _get_tiktoken_encoding(self, encoding_name: str):
        if encoding_name not in self._tiktoken_encodings:
            self._tiktoken_encodings[encoding_name] = tiktoken.get_encoding(encoding_name)
        return self._tiktoken_encodings[encoding_name]

    def _get_transformer_tokenizer(self, model_name: str):
        if model_name not in self._transformer_tokenizers:
            self._transformer_tokenizers[model_name] = AutoTokenizer.from_pretrained(
                model_name,
                cache_dir=self.cache_dir,
                trust_remote_code=True
            )
        return self._transformer_tokenizers[model_name]

    def count_tokens(self, text: str, model_name: str) -> tuple[int, list[int]]:
        model_lower = model_name.lower()

        # 优先匹配 tiktoken 支持的模型
        for key, encoding in self.TIKTOKEN_MODELS.items():
            if key in model_lower:
                enc = self._get_tiktoken_encoding(encoding)
                tokens = enc.encode(text)
                return len(tokens), tokens

        # 否则使用 transformers
        tokenizer = self._get_transformer_tokenizer(model_name)
        tokens = tokenizer.encode(text)
        return len(tokens), tokens  # ✅ 修复：返回 (count, tokens)

    def text_tokens(self, text: str, model_name: str) -> list[str]:
        """返回可读的 token 文本列表"""
        model_lower = model_name.lower()

        # Tiktoken: 需要 decode 每个 token 为 bytes，再转 str
        for key, encoding in self.TIKTOKEN_MODELS.items():
            if key in model_lower:
                enc = self._get_tiktoken_encoding(encoding)
                tokens = enc.encode(text)
                decoded = []
                for t in tokens:
                    try:
                        # 尝试 UTF-8 解码，失败则保留 repr
                        token_bytes = enc.decode_single_token_bytes(t)
                        decoded.append(token_bytes.decode('utf-8', errors='replace'))
                    except Exception:
                        decoded.append(f"<{t}>")
                return decoded

        # Transformers: 直接 convert_ids_to_tokens
        tokenizer = self._get_transformer_tokenizer(model_name)
        tokens = tokenizer.encode(text)
        return tokenizer.convert_ids_to_tokens(tokens)

# === 使用示例 ===
if __name__ == "__main__":
    tokenizer = Tokenizer()
    text = "你好，世界！Hello, World!"

    models = [
        "gpt-3.5-turbo",
        "gpt-4o",
        "Qwen/Qwen3-0.6B",
        # "meta-llama/Llama-3-8b"
    ]

    for model in models:
        try:
            count, ids = tokenizer.count_tokens(text, model)
            tokens_text = tokenizer.text_tokens(text, model)
            print(f"\n=== [{model}] ===")
            print(f"Token 数量: {count}")
            print(f"Token IDs: {ids}")
            print(f"可读 tokens: {tokens_text}")
        except Exception as e:
            print(f"[{model}] error: {e}")