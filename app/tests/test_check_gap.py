"""tools/check_gap.py のテスト。測定ツールが、成立する／しないを正しく判定すること。

デモ用クエリそのものの確定（U-04の期待値）は、実データ（2-1a）が入ってから実測して行う。
ここでは、テスト用seedsに対してツールの出力が正しいかだけを見る。
"""

from tools import check_gap


def ev_of(con, **candidate):
    return check_gap.evaluate(con, candidate)


def test_BM25が0件で両方併用なら返る短文は成立(con):
    ev = ev_of(con, label="短文", kind="short", text="確定申告の書類の書き方が分からない")

    assert ev["bm25_count"] == 0 and ev["keyword_count"] == 0
    assert ev["hybrid_count"] > 0
    assert check_gap.verdict(ev) == "OK"


def test_BM25がヒットしてしまう短文は成立しない(con):
    ev = ev_of(con, label="短文", kind="short", text="夕方になると前髪の毛先が固まる")

    assert ev["bm25_count"] > 0
    assert check_gap.verdict(ev).startswith("NG: BM25が")


def test_expectedをタイトルの語か文書IDで指定できる(con):
    by_word = ev_of(con, kind="long", text="汗で日焼け止めが流れる", expected="紫外線")
    by_id = ev_of(con, kind="long", text="汗で日焼け止めが流れる", expected=3)

    assert by_word["expected_ids"] == by_id["expected_ids"] == [3]


def test_キーワードのみでも正解が1位に来る長文は成立しない(con):
    ev = ev_of(con, kind="long", text="皮脂が出て前髪の毛先が固まってしまうのを防ぎたい", expected=1)

    assert ev["keyword_rank"] == 1
    assert check_gap.verdict(ev) == "NG: キーワードのみでも正解が1位に来てしまう"


def test_長文の成立条件はキーワードで1位でなく_両方併用で1位():
    base = {"kind": "long", "expected_ids": [1]}

    assert check_gap.verdict({**base, "keyword_rank": 2, "hybrid_rank": 1}) == "OK"
    assert check_gap.verdict({**base, "keyword_rank": None, "hybrid_rank": 1}) == "OK"  # キーワードでは圏外
    assert check_gap.verdict({**base, "keyword_rank": 2, "hybrid_rank": 2}).startswith("NG: 両方併用で正解が1位に来ない")
    assert check_gap.verdict({**base, "keyword_rank": 2, "hybrid_rank": None}).endswith("（圏外位）")
    assert check_gap.verdict({"kind": "long", "expected_ids": []}).startswith("NG: expected")


def test_レポートに候補ごとの実測と成立した一覧が出る(con):
    evals = [
        ev_of(con, label="短文A", kind="short", text="確定申告の書類の書き方が分からない"),
        ev_of(con, label="長文A", kind="long", text="皮脂が出て前髪の毛先が固まってしまうのを防ぎたい", expected=1),
    ]

    report = check_gap.format_report(evals)

    assert "■ 短文A（short・" in report and "■ 長文A（long・" in report
    assert "成立した短文（①）: ['短文A']" in report
    assert "成立した長文（②）: なし" in report
