import spacy
# 模型列表
# https://spacy.io/models/xx

# 加载zh_core_web_sm模型
tokenizer = spacy.load("zh_core_web_sm")
# tokenizer = spacy.load("xx_ent_wiki_sm")
# tokenizer = spacy.load("zh_core_web_trf")
# tokenizer = spacy.load("en_core_web_sm")

# 处理文本
doc = tokenizer("""zh_core_web_sm 是1个用于中文自然语言处理的模型，属于 spaCy 库的一部分。
          spaCy 是一个强大的 Python 自然语言处理（NLP）库，
          可以执行词性分析、命名实体识别、依赖关系解析以及词嵌入向量的计算和可视化等任务。""")

# 遍历识别出的实体
"""
pos:通用词性https://universaldependencies.org/u/pos/
tag:更具体的特定语言的词性标签
dep:依赖关系标签
shape:单词的形状（例如，是否大写、是否包含数字等）
is_alpha:是否为字母
is_stop:是否为停用词
"""
for ent in doc:
    print(ent.text, ent.pos_,ent.tag_,ent.dep_, ent.shape_, ent.is_alpha, ent.is_stop)

for i, sent in enumerate(doc.sents, 1):
    print(f"句{i}: {sent.text.strip()}")
# ADJ: 形容词
# ADP: 介词
# ADV: 副词
# AUX: 助动词
# CCONJ: 并列连词
# DET: 限定词
# INTJ: 感叹词
# NOUN: 名词
# NUM: 数词
# PART: 粒子词
# PRON: 代词
# PROPN: 专有名词
# PUNCT: 标点符号
# SCONJ: 从属连词
# SYM: 符号
# VERB: 动词
# X: 其他

# ADJ: adjective
# ADP: adposition
# ADV: adverb
# AUX: auxiliary
# CCONJ: coordinating conjunction
# DET: determiner
# INTJ: interjection
# NOUN: noun
# NUM: numeral
# PART: particle
# PRON: pronoun
# PROPN: proper noun
# PUNCT: punctuation
# SCONJ: subordinating conjunction
# SYM: symbol
# VERB: verb
# X: other