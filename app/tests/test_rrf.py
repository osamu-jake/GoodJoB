"""search/rrf.py のテスト（U-01・U-02）。"""

import pytest

from search import rrf


def test_u01_統合スコアは_1_を_k_足す_順位_の和でk_60():
    """U-01: 順位リスト2本 → 1/(k+rank)の和で統合スコアが計算される（k=60）。"""
    fused = dict(rrf.rrf([10, 20, 30], [20, 10, 40]))

    assert rrf.K == 60
    assert fused[10] == pytest.approx(1 / 61 + 1 / 62)  # 1位と2位
    assert fused[20] == pytest.approx(1 / 62 + 1 / 61)  # 2位と1位
    assert fused[30] == pytest.approx(1 / 63)  # 片方の3位のみ
    assert fused[40] == pytest.approx(1 / 63)


def test_u02_片方にしか出ない文書も統合結果に含まれる():
    """U-02: 片方にしか出ない文書を含むリスト → その文書も統合結果に含まれる。"""
    fused = rrf.rrf([1, 2], [3])

    assert {doc_id for doc_id, _ in fused} == {1, 2, 3}


def test_統合スコアの降順で返り_両方に出た文書が上に来る():
    fused = rrf.rrf([1, 2, 3], [3, 2, 9])

    ids = [doc_id for doc_id, _ in fused]
    assert set(ids[:2]) == {2, 3}  # 両方に出た2と3が、片方だけの1・9より上
    assert [s for _, s in fused] == sorted((s for _, s in fused), reverse=True)


def test_同点は先に出た文書が前に来る():
    assert [d for d, _ in rrf.rrf([5, 6], [7])][:2] == [5, 7]  # 5と7はどちらも1位で同点 → 5が先


def test_空のリストでも動く():
    assert rrf.rrf([], []) == []
    assert rrf.rrf([1], []) == [(1, pytest.approx(1 / 61))]
