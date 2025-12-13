# coding: utf-8
import json
import math
import urllib.request


class TextSimilarityTester:
    def __init__(self, ollama_url="http://localhost:11434"):
        self.ollama_url = ollama_url
        self.encode = "utf-8"

    def get_text_embedding(self, text, model):
        """
        通过Ollama API获取文本的向量表示

        参数:
            text: 要向量化的文本
            model: 使用的模型名称

        返回:
            文本的嵌入向量
        """
        data = {"model": model, "prompt": text, "options": {}}

        req = urllib.request.Request(
            f"{self.ollama_url}/api/embeddings",
            data=json.dumps(data).encode(self.encode),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode(self.encode))
                return result.get("embedding", [])
        except urllib.error.URLError as e:
            raise RuntimeError(f"无法连接到Ollama服务: {e}")

    def cosine_similarity(self, a, b):
        """
        计算两个向量的余弦相似度

        参数:
            a: 第一个向量
            b: 第二个向量

        返回:
            余弦相似度值 (范围[-1, 1])
        """
        dot_product = sum(x * y for x, y in zip(a, b))

        magnitude_a = math.sqrt(sum(x**2 for x in a))
        magnitude_b = math.sqrt(sum(y**2 for y in b))

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)

    def test_similarity(self, models, questions, paragraphs):
        """
        测试不同模型下问题与段落的相似度

        参数:
            models: 要测试的模型列表
            questions: 问题列表
            paragraphs: 段落列表

        返回:
            包含所有测试结果的字典
        """
        results = {}

        for model in models:
            print(f"\n=== 正在测试模型: {model} ===")
            model_results = {}

            # 获取所有问题和段落的嵌入
            question_embeddings = []
            for q in questions:
                try:
                    emb = self.get_text_embedding(q, model)
                    question_embeddings.append(emb)
                except RuntimeError as e:
                    print(f"获取问题向量失败: {e}")
                    question_embeddings.append([])

            paragraph_embeddings = []
            for p in paragraphs:
                try:
                    emb = self.get_text_embedding(p, model)
                    paragraph_embeddings.append(emb)
                except RuntimeError as e:
                    print(f"获取段落向量失败: {e}")
                    paragraph_embeddings.append([])

            # 计算每个问题与每个段落的相似度
            for i, q_emb in enumerate(question_embeddings):
                if not q_emb:
                    continue

                question_results = []
                for j, p_emb in enumerate(paragraph_embeddings):
                    if not p_emb:
                        similarity = 0.0
                    else:
                        similarity = self.cosine_similarity(q_emb, p_emb)

                    question_results.append(
                        {"paragraph_index": j, "similarity": similarity}
                    )
                    print(f"问题 {i} 与段落 {j} 的相似度: {similarity:.4f}")

                model_results[f"question_{i}"] = question_results

            results[model] = model_results

        return results


if __name__ == "__main__":
    print("=== 文本相似度测试工具 ===")

    # 配置测试参数
    models = ["bge-m3:latest", "dengcao/Qwen3-Embedding-0.6B:F16"]  # 要测试的模型列表
    questions = [
        # "TA機能説明書(TAOA30 給報報告者管理)に、イベント仕様「住所地照会票発行時」の機能概要を教えてください。",
        "数学题"
    ]
    paragraphs =[
        "1+1=?",
        "1+2=3"
    ]
#     questions = [
#         "TA機能説明書(TAOA30 給報報告者管理)に、イベント仕様「住所地照会票発行時」の機能概要を教えてください。",
#         # "給報報告者管理の業務概要を教えてください"
#     ]
#     paragraphs = [
#         """1.1.1.1 住所地照会票発行時
# 個人未特定データのみ発行可能である。受給者明細上の「個人未特定」のみにチェックをいれ、表示条件を設定するボタンで再検索することにより発行するボタン(およびプレビューするボタン)が押下可能となる。
# 受給者明細より住所地照会票を発行したいデータを選択し、発送年月日、返送期限を入力し、発行するボタン(およびプレビューするボタン)を押下する。

# 発行後のDB更新について
# 住所地照会票を発行した場合、処理区分のいかんによらず、TA給報報告者およびTA個人未特定資料基本を更新する。
# ・TA給報報告者の住所照会状況コードに’06’(発送(支払者))をセットして更新する。
# ・発送対象全てのTA個人未特定資料基本の不明者照会状況コードに’06’(お尋ね回答により転送)をセットして更新する。""",
#         "個人住民税システム...該当の作業一覧ページへリンクします>住民·外部機関:主管課 (手作業/オンライン):;システム(パッチ処理):住民·外部機関:主管課 (手作業/オンライン):;システム(パッチ処理):給報報告者管理の業務1.オンラインによる給報報告者管理>給報 設立申告書1受理法人異動届出書2給報報告者情 報のチェック 法人市民税の届出TAOLOA30給報報告者管理 給報報告者無3宛名情報の登録有4給報報告者の登録·更新·FD交換·納入書不要区分·通知書出力 順·早期送付区分·当初納期特例·代表事業所区分(番号)·業種·所轄税務署·eLTAX情報(納税者ID) 5支払者情報の保守6除籍区分保守 関与税理士宛名 無7-1無 関与税理士宛名の登録7-2関与税理士情報の保守TAOLOA30給報報告管理",
#     ]
    # paragraphs =[
    #     "個人住民税システム1 給報報告者管理 の業務 業務概要 給報報告者管理の業務 では、オンラインによる給報報告者の 管理、および、新年度の給報報告者を 作成する。総括表の業務では、事業所 に対して、給与支払報告書の提出を求 めるために、総括表の発送を行う。納 期特例管理の業務では、納期特例の登 録、確認を行う。給与支払報告書未提 出の業務では、給与支払報告者未提出 の事業所に対して、実施調査を行う4 月:;5月:;6月:;7月:;8月:;9月:;10 月: 11月:;12月:;1月:;2月:;3月:給報 報告者管理の業務オンラインによる給 報報告者管理新年度給報報告者作成 総 括表の業務 総括表発送コード一括設定 総括表発送 納期特例管理の業務 納期特 例管理給報未提出管理の業務給報未提 出者管理 給報未提出者管理2給報報告 者管理の業務のうち、新年度給報報告 者作成は10月中旬の実施を想定してい る。総括表の業務は10月下旬を想定し ている。給報未提出者管理の業務は2 月以降、給報未提出者管理2の業務は7 月以降の実施を想定している。給報報 告者管理の業務のうち、オンラインに よる給報報告者管理、納期特例管理の 業務の実施は随時を想定している 運用 想定 導入時 ポイント 下記の設定情報の 確認が必要となる",
    #     "個人住民税システム...該当の作業一覧ページへリンクします>住民·外部機関:主管課 (手作業/オンライン):;システム(パッチ処理):住民·外部機関:主管課 (手作業/オンライン):;システム(パッチ処理):給報報告者管理の業務1.オンラインによる給報報告者管理>給報 設立申告書1受理法人異動届出書2給報報告者情 報のチェック 法人市民税の届出TAOLOA30給報報告者管理 給報報告者無3宛名情報の登録有4給報報告者の登録·更新·FD交換·納入書不要区分·通知書出力 順·早期送付区分·当初納期特例·代表事業所区分(番号)·業種·所轄税務署·eLTAX情報(納税者ID) 5支払者情報の保守6除籍区分保守 関与税理士宛名 無7-1無 関与税理士宛名の登録7-2関与税理士情報の保守TAOLOA30給報報告管理",
    # ]

    # 创建测试器并运行测试
    tester = TextSimilarityTester()
    results = tester.test_similarity(models, questions, paragraphs)

    print("\n=== 测试完成 ===")
