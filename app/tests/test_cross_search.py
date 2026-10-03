"""search/cross_search.py のテスト（U-21・U-23／I-01・I-02・I-10）と検索方式の切替（F-06）。

疑似エンコーダ（文字の重なりで似ているかを測る）で、検索の配管（候補の選び方・並び順・別リスト）を確認する。
意味の近さそのものは test_semantic.py（実モデル）で確認する。
"""

import pytest

from db import build_db
from search import cross_search, vector

QUERY = "皮脂が出て前髪の毛先が固まってしまうのを防ぎたい"


def doc_types(con, hits):
    return {con.execute("SELECT doc_type FROM documents WHERE id = ?", (h.doc_id,)).fetchone()[0] for h in hits}


def test_u21_表示順は関連度の降順(con):
    """U-21: BM25とベクトル両方にヒットがある状態 → 表示順が関連度の降順になっている（ADR-0023）。"""
    result = cross_search.cross_search(con, QUERY)

    assert any(h.via == cross_search.VIA_BOTH for h in result.hits)  # 両方にヒットした文書がある
    sims = [h.similarity for h in result.hits]
    assert sims == sorted(sims, reverse=True)


def test_u23_同じ側は最大3件で_反対側とは別のリスト(con):
    """U-23: same_side_k=3 で検索 → 同じ側が最大3件、反対側とは別のリストで返る（ADR-0024）。"""
    result = cross_search.cross_search(con, "髪も肌も香りも日焼け止めも気になる", query_side="need", same_side_k=3)

    assert 0 < len(result.same_side_hits) <= 3
    assert doc_types(con, result.hits) == {"seed"}  # 反対側（技術）
    assert doc_types(con, result.same_side_hits) == {"need"}  # 同じ側（似た悩み）


def test_i10_同じ側の結果は反対側と重複しない(con):
    """I-10: same_side_hits が最大3件返り、反対側の hits と重複しない。"""
    result = cross_search.cross_search(con, QUERY, same_side_k=3)

    assert len(result.same_side_hits) <= 3
    assert {h.doc_id for h in result.hits}.isdisjoint(h.doc_id for h in result.same_side_hits)


def test_same_side_kが0なら同じ側は検索しない(con):
    assert cross_search.cross_search(con, QUERY, same_side_k=0).same_side_hits == []


def test_seed側から検索すると反対側はneedになる(con):
    """タブ②の詳細画面が使う向き（query_side='seed'）。"""
    result = cross_search.cross_search(con, "皮脂を吸着する微粒子", query_side="seed")
    assert doc_types(con, result.hits) == {"need"}


def add_seed_docs(con, n):
    for i in range(100, 100 + n):
        con.execute(
            "INSERT INTO documents (id, doc_type, source, title, body, problem) VALUES (?, 'seed', 'placeholder', ?, ?, ?)",
            (i, f"皮脂対策技術{i}", f"皮脂を抑える方法{i}に関する技術", f"皮脂が増えて髪がべたつく問題{i}"),
        )
    build_db.rebuild_fts(con)
    build_db.build_embeddings(con)


def test_i01_BM25上位50件とベクトル上位50件がRRFで統合され上位10件が返る(con):
    """I-01: BM25上位50件とベクトル上位50件がRRFで統合され、上位10件が返る。"""
    add_seed_docs(con, 60)

    result = cross_search.cross_search(con, "皮脂が増えて髪がべたつく")

    assert result.bm25_count == 50  # 60件が語に一致するが、取得は上位50件まで
    assert len(result.hits) == 10
    for h in result.hits:  # 統合スコアは 1/(60+BM25順位) + 1/(60+ベクトル順位)
        expected = sum(1 / (60 + r) for r in (h.bm25_rank, h.vector_rank) if r)
        assert h.rrf_score == pytest.approx(expected)


def test_i02_複数フィールドを持つ文書はdoc_idごとに最大類似度が採用され重複しない(con):
    """I-02: 複数フィールドを持つ文書を検索 → doc_idごとに最大類似度が採用され、同一文書が重複して返らない。"""
    result = cross_search.cross_search(con, QUERY, same_side_k=0)

    ids = [h.doc_id for h in result.hits]
    assert len(ids) == len(set(ids))
    query_vec = vector.encode_query(QUERY)
    for h in result.hits:
        rows = con.execute("SELECT doc_id, field, vec FROM embeddings WHERE doc_id = ?", (h.doc_id,)).fetchall()
        assert len(rows) > 1  # シーズ文書1〜6は複数フィールドを持つ
        per_field = {f: s for _, f, s in vector.similarities(query_vec, rows)}
        assert h.similarity == pytest.approx(max(per_field.values()))
        assert h.matched_field == max(per_field, key=per_field.get)


def test_キーワードのみは語が一致しなければ0件_両方併用なら候補が返る(con):
    """F-06: 方式を切り替えると件数が変わる（0件→N件）。"""
    q = "確定申告の書類の書き方が分からない"

    assert cross_search.cross_search(con, q, mode="bm25").hits == []
    assert len(cross_search.cross_search(con, q, mode="hybrid").hits) > 0
    assert len(cross_search.cross_search(con, q, mode="vector").hits) > 0


def test_キーワードのみは類似度を持たずBM25順_意味のみはBM25を使わない(con):
    kw = cross_search.cross_search(con, QUERY, mode="bm25", same_side_k=0)
    assert kw.hits and all(h.similarity is None and h.via == "bm25" for h in kw.hits)
    assert [h.bm25_rank for h in kw.hits] == sorted(h.bm25_rank for h in kw.hits)

    vec = cross_search.cross_search(con, QUERY, mode="vector", same_side_k=0)
    assert vec.bm25_count == 0 and all(h.via == "vector" and h.bm25_rank is None for h in vec.hits)


def test_hit_judgeの材料として反対側のBM25件数と最高類似度を返す(con):
    result = cross_search.cross_search(con, QUERY)

    assert result.bm25_count > 0
    assert result.top_similarity >= max(h.similarity for h in result.hits)


def test_空のクエリは空の結果(con):
    for q in ("", "   "):
        r = cross_search.cross_search(con, q)
        assert r.hits == [] and r.same_side_hits == []


def test_不正なmodeは例外(con):
    with pytest.raises(ValueError):
        cross_search.cross_search(con, QUERY, mode="semantic")


def test_BM25でヒットした文書にはスニペットが付く(con):
    hits = cross_search.cross_search(con, QUERY, same_side_k=0).hits
    with_bm25 = [h for h in hits if h.bm25_rank]

    assert with_bm25 and all(h.snippet for h in with_bm25)
    assert all(h.snippet is None for h in hits if not h.bm25_rank)
