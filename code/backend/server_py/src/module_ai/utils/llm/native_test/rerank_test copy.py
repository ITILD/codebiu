import json
import urllib.request
from urllib.error import URLError, HTTPError

encode = "utf-8"
url = "http://172.16.25.84:1107/v2/rerank"

# 正确的请求数据结构(注意v2接口需要"queries"和"documents")
data = {
    "model": "bge-reranker-v2-m3",
    "query": "工资申报者管理业务 业务概要",
    "documents": [
        "個人住民税システム1 給報報告者管理 の業務 業務概要 給報報告者管理の業務 では、オンラインによる給報報告者の 管理、および、新年度の給報報告者を 作成する。総括表の業務では、事業所 に対して、給与支払報告書の提出を求 めるために、総括表の発送を行う。納 期特例管理の業務では、納期特例の登 録、確認を行う。給与支払報告書未提 出の業務では、給与支払報告者未提出 の事業所に対して、実施調査を行う4 月:;5月:;6月:;7月:;8月:;9月:;10 月: 11月:;12月:;1月:;2月:;3月:給報 報告者管理の業務オンラインによる給 報報告者管理新年度給報報告者作成 総 括表の業務 総括表発送コード一括設定 総括表発送 納期特例管理の業務 納期特 例管理給報未提出管理の業務給報未提 出者管理 給報未提出者管理2給報報告 者管理の業務のうち、新年度給報報告 者作成は10月中旬の実施を想定してい る。総括表の業務は10月下旬を想定し ている。給報未提出者管理の業務は2 月以降、給報未提出者管理2の業務は7 月以降の実施を想定している。給報報 告者管理の業務のうち、オンラインに よる給報報告者管理、納期特例管理の 業務の実施は随時を想定している 運用 想定 導入時 ポイント 下記の設定情報の 確認が必要となる",
        "個人住民税システム...該当の作業一覧ページへリンクします>住民·外部機関:主管課 (手作業/オンライン):;システム(パッチ処理):住民·外部機関:主管課 (手作業/オンライン):;システム(パッチ処理):給報報告者管理の業務1.オンラインによる給報報告者管理>給報 設立申告書1受理法人異動届出書2給報報告者情 報のチェック 法人市民税の届出TAOLOA30給報報告者管理 給報報告者無3宛名情報の登録有4給報報告者の登録·更新·FD交換·納入書不要区分·通知書出力 順·早期送付区分·当初納期特例·代表事業所区分(番号)·業種·所轄税務署·eLTAX情報(納税者ID) 5支払者情報の保守6除籍区分保守 関与税理士宛名 無7-1無 関与税理士宛名の登録7-2関与税理士情報の保守TAOLOA30給報報告管理",
    ],
    # "query": "Which country's capital is Paris?",
    # "documents": [
    #     "The capital of France is Paris",
    #     "The capital of Brazil is Brasília",
    # ],
}

# 将数据转换为JSON格式
data_bytes = json.dumps(data).encode(encode)

# 创建请求对象
req = urllib.request.Request(
    url,
    data=data_bytes,
    headers={
        "Content-Type": "application/json",
        # 'Authorization': 'Bearer 123456'
    },
    method="POST",
)

try:
    # 发送请求并获取响应
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode(encode))
        print("Request successful!")
        print(json.dumps(result, indent=2, ensure_ascii=False))

except HTTPError as e:
    print(f"Request failed with status code: {e.code}")
    print(e.read().decode("utf-8"))
except URLError as e:
    print(f"URL Error: {e.reason}")
except Exception as e:
    print(f"Unexpected error: {str(e)}")
