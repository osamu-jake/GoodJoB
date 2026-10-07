"""tools/summarize.py のテスト（U-20。ADR-0016・0020・0051）。

AIのAPIは呼ばない。「プロンプト → 要約1文」の模擬の関数を渡して、対象の選び方とDBへの書き込みを確かめる。
テスト用seedsでは、seed文書のうち id=5 だけ summary_plain が空。
"""

from tools import summarize


def fake_call(prompts):
    """受け取ったプロンプトを記録し、決まった要約を返す模擬の関数を作る。"""
    def call(prompt):
        prompts.append(prompt)
        return "模擬の要約。"
    return call


def summary_of(con, doc_id):
    return con.execute("SELECT summary_plain FROM documents WHERE id = ?", (doc_id,)).fetchone()[0]


def test_u20_要約が空のseed文書だけ生成してDBへ書き込む(con):
    prompts = []

    results = summarize.summarize(con, call=fake_call(prompts))

    assert results == [(5, "模擬の要約。")]
    assert summary_of(con, 5) == "模擬の要約。"
    assert summary_of(con, 1) == "皮脂を吸う粉で、夕方まで髪型が崩れにくくなる技術。"  # 既存の要約は変えない
    assert summary_of(con, 11) is None  # ニーズ側は対象外（要約はseed側のみ。F-16）
    assert "発明の名称: 低摩擦係数の被膜形成剤" in prompts[0] and "課題: " in prompts[0]


def test_u20_forceなら既存の要約も作り直す(con):
    results = summarize.summarize(con, call=fake_call([]), force=True)

    assert [doc_id for doc_id, _ in results] == [1, 2, 3, 4, 5, 6]
    assert summary_of(con, 1) == "模擬の要約。"


def test_u20_dry_runならDBへ書き込まない(con):
    results = summarize.summarize(con, call=fake_call([]), dry_run=True)

    assert results == [(5, "模擬の要約。")]
    assert summary_of(con, 5) is None
