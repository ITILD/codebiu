from enum import StrEnum

class Language(StrEnum):
    JA = "ja"
    EN = "en"
    ZH = "zh"
    CH = "ch"
    CHT = "cht"
    FR = "fr"
    ES = "es"
    DE = "de"
    
    @property # 属性方法
    def full_name(self):
        mapping = {
            "ja": "japanese",
            "en": "english",
            "zh": "chinese",
            "ch": "chinese",
            "cht": "traditional chinese",
            "fr": "french",
            "es": "spanish",
            "de": "german"
        }
        return mapping[self]

if __name__ == "__main__":
    # 使用示例
    print(Language.ZH)  # 输出: zh
    print(Language.ZH.full_name)  # 输出: chinese
    print(Language["FR"].full_name)  # 输出: french