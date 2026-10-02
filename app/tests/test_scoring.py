"""search/scoring.py のテスト（U-10・U-10b・U-11）。"""

import pytest

from search import cross_search, scoring


def hit(similarity, via=cross_search.VIA_BOTH):
    return cross_search.Hit(doc_id=1, similarity=similarity, matched_field="problem", via=via)


def test_u10_類似度はそのまま百分率になる():
    """U-10: 0.893/0.871/0.848/0.826/0.804 → そのまま89/87/85/83/80%（相対値化しない。ADR-0035）。"""
    sims = [0.893, 0.871, 0.848, 0.826, 0.804]

    assert [scoring.to_percent(s) for s in sims] == [89, 87, 85, 83, 80]
    assert [scoring.score_hit(hit(s)).percent for s in sims] == [89, 87, 85, 83, 80]


def test_u10b_全候補が低い類似度でも1位が上限に丸められない():
    """U-10b: 全候補が低い類似度（0.30前後） → 1位でも30%前後にとどまり、上限値に丸められない（ADR-0035）。"""
    sims = [0.31, 0.30, 0.29, 0.28]

    percents = [scoring.score_hit(hit(s)).percent for s in sims]

    assert percents == [31, 30, 29, 28]
    assert max(percents) < 40  # 結果セット内の相対値なら、1位は必ず上限付近（96など）に張り付いてしまう


def test_u11_BM25のみでヒットした文書は数値を出さず_語一致ラベル():
    """U-11: BM25のみでヒットした文書 → スコアを表示せず「語一致」ラベルが付く。"""
    # 並び順のために内部では類似度を持っていても、数値は出さない
    score = scoring.score_hit(hit(0.62, via=cross_search.VIA_BM25))

    assert score.percent is None
    assert score.label == "語一致"
    assert score.keyword_only is True


def test_類似度が無い_キーワードのみの方式でも語一致():
    score = scoring.score_hit(hit(None, via=cross_search.VIA_BM25))
    assert (score.percent, score.label) == (None, "語一致")


def test_意味検索でもヒットした文書は数値が出る():
    for via in (cross_search.VIA_VECTOR, cross_search.VIA_BOTH):
        score = scoring.score_hit(hit(0.84, via=via))
        assert score.percent == 84 and score.keyword_only is False


@pytest.mark.parametrize(
    "similarity, label", [(0.90, "近い"), (0.85, "近い"), (0.84, "やや近い"), (0.80, "やや近い"), (0.79, "応用候補")]
)
def test_数値に添える言葉(similarity, label):
    assert scoring.proximity_label(similarity) == label
    assert scoring.score_hit(hit(similarity)).label == label


@pytest.mark.parametrize("similarity, percent", [(0.845, 85), (0.0, 0), (1.0, 100), (-0.05, 0), (1.02, 100)])
def test_四捨五入と範囲の丸め(similarity, percent):
    assert scoring.to_percent(similarity) == percent


def test_検索結果に対して使える(con):
    result = cross_search.cross_search(con, "皮脂が出て前髪の毛先が固まってしまう", same_side_k=0)

    scores = [scoring.score_hit(h) for h in result.hits]
    shown = [s.percent for s in scores if s.percent is not None]

    assert all(0 <= p <= 100 for p in shown)
    assert shown == sorted(shown, reverse=True)  # 表示順は関連度の降順（ADR-0023）
