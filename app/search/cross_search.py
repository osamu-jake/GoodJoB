"""クロス検索（F-02・ADR-0002・0006）。

ニーズ文を入れるとシーズが、シーズ文を入れるとニーズが返る。
検索対象のdoc_typeを反対側にするだけで成立する。
"""

import sqlite3
from dataclasses import dataclass, field as dc_field

from . import bm25, hit_judge, rrf, scoring, vector

TOP_K = 10
CANDIDATE_K = 50
# 同じ側は主役（反対側）を埋もれさせない件数に抑える（ADR-0024）
SAME_SIDE_K = 3

MODE_KEYWORD = "keyword"
MODE_VECTOR = "vector"
MODE_HYBRID = "hybrid"


@dataclass
class Hit:
    doc_id: int
    similarity: float
    matched_field: str | None
    in_bm25: bool
    in_vector: bool
    percent: int = 0
    label: str = ""


@dataclass
class SearchResult:
    hits: list[Hit] = dc_field(default_factory=list)
    same_side_hits: list[Hit] = dc_field(default_factory=list)
    bm25_count: int = 0
    vector_count: int = 0
    no_hit: bool = False
    top_similarity: float = 0.0


def opposite(side: str) -> str:
    return "seed" if side == "need" else "need"


def _load_embedding_rows(con: sqlite3.Connection, doc_type: str):
    return con.execute(
        """
        SELECT e.doc_id, e.field, e.vec
          FROM embeddings e
          JOIN documents d ON d.id = e.doc_id
         WHERE d.doc_type = ?
        """,
        (doc_type,),
    ).fetchall()


def search(
    con: sqlite3.Connection,
    query_text: str,
    query_side: str,
    mode: str = MODE_HYBRID,
    top_k: int = TOP_K,
    same_side_k: int = SAME_SIDE_K,
) -> SearchResult:
    """反対側と同じ側を、別々に検索して別々に返す（ADR-0006・0024）。

    - 反対側＝この提案が本当に見せたい価値（ニーズ→技術）。主役
    - 同じ側＝似た悩み・既存の訴求。差別化の余地を判断する材料（ADR-0007）

    1つの順位表に混ぜないのは、同じ側は語が一致しやすく高スコアになり、
    上位を独占して反対側が埋もれてしまうため。
    「ヒットなし」判定も反対側に対してのみ行う（ADR-0008）。
    """
    result = _search_one_side(con, query_text, opposite(query_side), mode, top_k)
    if same_side_k > 0:
        same = _search_one_side(con, query_text, query_side, mode, same_side_k)
        result.same_side_hits = same.hits
    return result


def _search_one_side(
    con: sqlite3.Connection,
    query_text: str,
    target: str,
    mode: str,
    top_k: int,
) -> SearchResult:
    bm25_hits = (
        bm25.search(con, query_text, doc_type=target, k=CANDIDATE_K)
        if mode in (MODE_KEYWORD, MODE_HYBRID)
        else []
    )

    # 類似度は全件分を持っておく。候補集合に入った文書には必ず関連度が付く（ADR-0023）
    best: dict[int, tuple[float, str]] = {}
    vec_ranked: list[int] = []
    if mode in (MODE_VECTOR, MODE_HYBRID):
        rows = _load_embedding_rows(con, target)
        if rows:
            qv = vector.encode_query(query_text)
            best = vector.best_by_doc(qv, rows)
            vec_ranked = vector.rank(best, k=CANDIDATE_K)

    top_similarity = max((s for s, _ in best.values()), default=0.0)

    # どの文書を結果に含めるかはRRFで決める（ADR-0002・0003の利点を残す）
    if mode == MODE_KEYWORD:
        selected = bm25_hits[:top_k]
    elif mode == MODE_VECTOR:
        selected = vec_ranked[:top_k]
    else:
        selected = [doc_id for doc_id, _ in rrf.rrf(bm25_hits, vec_ranked)[:top_k]]

    bm25_set = set(bm25_hits)
    hits = [
        Hit(
            doc_id=doc_id,
            similarity=best.get(doc_id, (0.0, None))[0],
            matched_field=best.get(doc_id, (0.0, None))[1],
            in_bm25=doc_id in bm25_set,
            in_vector=doc_id in best,
        )
        for doc_id in selected
    ]

    # 表示順は関連度の降順（ADR-0023）。RRF順のままだと、BM25にもヒットした文書が
    # 上位に来つつ関連度は低い、という見た目の矛盾が起きて発表で突っ込まれる
    hits.sort(key=lambda h: h.similarity, reverse=True)

    scored = [h for h in hits if h.in_vector]
    percents = scoring.to_relative_percent([h.similarity for h in scored])
    for h, p in zip(scored, percents):
        h.percent = p
        h.label = scoring.label(p)

    return SearchResult(
        hits=hits,
        bm25_count=len(bm25_hits),
        vector_count=len(vec_ranked),
        no_hit=hit_judge.is_no_hit(bm25_hits, top_similarity),
        top_similarity=top_similarity,
    )
