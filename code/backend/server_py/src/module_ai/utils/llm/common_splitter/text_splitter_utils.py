import os
from langchain.text_splitter import Language
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.text_splitter import TokenTextSplitter
from config.index import tiktoken_cache_dir
tiktoken_path = tiktoken_cache_dir / "tiktoken"
os.environ["TIKTOKEN_CACHE_DIR"] = str(tiktoken_path)

class TextSplitterUtils:
    """通用文本和代码拆分器"""

    # 分隔符只是拆分的"机会点"，不是强制拆分点。

    def __init__(
        self,
        chunk_size=1000,
        chunk_overlap=200,
        separators=None,
        encoding_name="cl100k_base",
    ):
        """
        初始化文本拆分器工具类。

        Args:
            chunk_size (int): 每个文本块的最大大小。
            chunk_overlap (int): 文本块之间的重叠大小。
            separators (list): 分隔符列表，默认为["\n\n"]
            encoding_name (str): 编码名称，默认为"cl100k_base"
        """
        self.chunk_size = int(chunk_size)
        self.chunk_overlap = int(chunk_overlap)
        self.separators = (
            separators if separators is not None else ["\n\n","}", ". ","\n", " ", ",", "，", "。", ""]
        )
        self.encoding_name = encoding_name
        self._splitters = {}

    def _is_supported_language(self, language_str):
        """判断是否支持该编程语言"""
        try:
            language = Language(language_str.lower())
            return language
        except ValueError:
            return None

    def _get_splitter(self, language_or_key):
        """
        根据 key 获取或创建 splitter，并将其缓存。
        """
        # 使用不可变元组作为 key
        cache_key = (
            language_or_key,
            self.chunk_size,
            self.chunk_overlap,
            str(self.separators),
            self.encoding_name,
        )

        if cache_key in self._splitters:
            return self._splitters[cache_key]

        code_language = self._is_supported_language(language_or_key)
        if code_language:
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=code_language,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
        elif language_or_key == "token":
            splitter = TokenTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                encoding_name=self.encoding_name,
            )
        else:  # 默认为通用文本拆分器
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=self.separators,
            )

        self._splitters[cache_key] = splitter
        return splitter

    def split_text(self, text):
        splitter = self._get_splitter("default")
        return splitter.split_text(text)

    def split_text_by_token(self, text):
        splitter = self._get_splitter("token")
        return splitter.split_text(text)

    def split_code(self, code, language):
        splitter = self._get_splitter(language)
        return splitter.split_text(code)


if __name__ == "__main__":
    # 实例化工具类，可以自定义 chunk_size 和 chunk_overlap
    splitter_utils = TextSplitterUtils(chunk_size=40, chunk_overlap=5)
    long_text = """
    LangChain is a framework for developing applications powered by language models.
    """
    # code_chunks = splitter_utils.split_code(long_text, Language.PYTHON)
    chunks = splitter_utils.split_text(long_text)
    print(f"原始文本长度: {len(long_text)}")
    print(f"拆分后的块数量: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"块 {i+1}: \n{chunk}\n---")
    