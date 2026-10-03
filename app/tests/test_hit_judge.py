"""search/hit_judge.py のテスト（U-08・U-09）。"""

import pytest

from search import cross_search, hit_judge


def test_u08_BM25が0件で類似度0_70なら_ヒットなし():
    """U-08: BM25=0件、類似度0.70（閾値0.80） → 「ヒットなし」と判定される。"""
    assert hit_judge.is_no_hit(bm25_count=0, top_similarity=0.70) is True


@pytest.mark.parametrize("similarity, expected", [(0.79, True), (0.80, False)])
def test_u09_閾値の境界は_0_79がヒットなし_0_80がヒットあり(similarity, expected):
    """U-09（境界値）: 類似度がちょうど0.80／0.79 → 0.80は「ヒットあり」（基準値未満のみヒットなし）、0.79は「ヒットなし」。"""
    assert hit_judge.THRESHOLD == 0.80
    assert hit_judge.is_no_hit(bm25_count=0, top_similarity=similarity) is expected


def test_BM25に1件でもあればヒットあり_類似度が低くても():
    assert hit_judge.is_no_hit(bm25_count=1, top_similarity=0.30) is False


def test_閾値は引数で変えられる():
    assert hit_judge.is_no_hit(0, 0.85, threshold=0.90) is True
    assert hit_judge.is_no_hit(0, 0.85, threshold=0.80) is False


def test_検索結果から判定できる(con):
    """反対側の件数と最高類似度で判定する。語が一致しない文は、疑似エンコーダでも類似度が低く「ヒットなし」になる。"""
    unrelated = cross_search.cross_search(con, "確定申告の書類の書き方が分からない")
    related = cross_search.cross_search(con, "皮脂が出て前髪の毛先が固まってしまう")

    assert unrelated.bm25_count == 0 and hit_judge.judge(unrelated) is True
    assert unrelated.hits  # 「ヒットなし」でも候補は空にしない
    assert hit_judge.judge(related) is False
