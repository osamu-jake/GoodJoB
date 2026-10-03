"""クロス検索（F-02・F-06。ADR-0002・0003・0021・0023・0024・0028）。

企画案の文章（ニーズ側）を入れると、反対側の技術（シーズ側）が返る。流れ:

1. 反対側を BM25 で上位50件、ベクトルで上位50件取る（ベクトルは文書ごとに最大類似度。ADR-0021）
2. RRF（k=60）で統合して上位10件を**候補集合として選ぶ**（どの文書を含めるかの決定にだけ使う）
3. 候補を**関連度（コサイン類似度）の降順に並べ直す**（ADR-0023）
4. 同じ手順を**同じ側**にも行い、最大3件を `same_side_hits` として**別のリストで**返す（ADR-0024）。
   1つの順位表には混ぜない。同じ側は必ず語が一致して上位を独占し、主役の反対側が埋もれるため

検索方式（F-06）は `mode` で切り替える。
- `hybrid`  : BM25＋ベクトルをRRFで統合。表示順は関連度の降順
- `bm25`    : キーワードのみ。BM25の順位のまま返す（ベクトルは計算しない。語が一致しなければ0件）
- `vector`  : 意味のみ。類似度の降順

「ヒットなし」の判定（hit_judge）は反対側の結果に対してだけ行う（ADR-0008）。
そのための材料として、反対側のBM25件数と最高類似度を `SearchResult` に載せて返す。
"""

import sqlite3
from dataclasses import dataclass, field

from . import bm25, rrf, vector

TOP_K = 10  # 反対側の件数（RRF統合後）
CANDIDATE_K = 50  # BM25・ベクトルそれぞれの取得件数
SAME_SIDE_K = 3  # 同じ側の件数（ADR-0024）

MODE_BM25 = "bm25"
MODE_VECTOR = "vector"
MODE_HYBRID = "hybrid"
MODES = (MODE_BM25, MODE_VECTOR, MODE_HYBRID)

VIA_BM25 = "bm25"  # キーワードだけでヒット（画面では「語一致」。F-14）
VIA_VECTOR = "vector"  # 意味検索だけでヒット
VIA_BOTH = "both"


@dataclass
class Hit:
    doc_id: int
    similarity: float | None  # コサイン類似度。意味検索を使わない方式（bm25）では None
    matched_field: str | None  # 最も類似度が高かったフィールド（body／problem／background）
    via: str  # どちらの検索で候補に入ったか（VIA_*）
    bm25_rank: int | None = None
    vector_rank: int | None = None
    rrf_score: float | None = None
    snippet: str | None = None
    matched_terms: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    hits: list[Hit] = field(default_factory=list)  # 反対側（主役）
    same_side_hits: list[Hit] = field(default_factory=list)  # 同じ側（別枠。最大3件）
    bm25_count: int = 0  # 反対側のBM25ヒット数（hit_judge の材料）
    top_similarity: float = 0.0  # 反対側の最高類似度（同上。意味検索を使わない方式では0）


def opposite(side: str) -> str:
    return "seed" if side == "need" else "need"


def cross_search(
    con: sqlite3.Connection,
    query_text: str,
    query_side: str = "need",
    mode: str = MODE_HYBRID,
    top_k: int = TOP_K,
    same_side_k: int = SAME_SIDE_K,
    candidate_k: int = CANDIDATE_K,
) -> SearchResult:
    """反対側と同じ側を、別々に検索して別々に返す。

    `query_side` はタブ①では 'need' 固定（ADR-0028）。双方向の口は、タブ②の詳細画面が
    'seed' で呼ぶために残してある。
    """
    if mode not in MODES:
        raise ValueError(f"mode は {MODES} のどれか: {mode!r}")
    if not query_text or not query_text.strip():
        return SearchResult()

    result = _search_one_side(con, query_text, opposite(query_side), mode, top_k, candidate_k)
    if same_side_k > 0:
        result.same_side_hits = _search_one_side(
            con, query_text, query_side, mode, same_side_k, candidate_k
        ).hits
    return result


def _search_one_side(
    con: sqlite3.Connection, query_text: str, doc_type: str, mode: str, top_k: int, candidate_k: int
) -> SearchResult:
    bm25_hits = (
        bm25.search(con, query_text, doc_type, k=candidate_k) if mode != MODE_VECTOR else []
    )
    # 類似度は対象の全文書分を持つ。候補に入った文書すべてに関連度を付けるため（ADR-0023）
    best = vector.search(con, query_text, doc_type) if mode != MODE_BM25 else {}
    vector_ids = vector.rank(best, candidate_k)

    bm25_by_id = {h.doc_id: h for h in bm25_hits}
    bm25_ids = [h.doc_id for h in bm25_hits]
    bm25_rank = {doc_id: i for i, doc_id in enumerate(bm25_ids, start=1)}
    vector_rank = {doc_id: i for i, doc_id in enumerate(vector_ids, start=1)}

    if mode == MODE_BM25:
        selected, scores = bm25_ids[:top_k], {}
    elif mode == MODE_VECTOR:
        selected, scores = vector_ids[:top_k], {}
    else:
        fused = rrf.rrf(bm25_ids, vector_ids)[:top_k]
        selected, scores = [doc_id for doc_id, _ in fused], dict(fused)

    hits = []
    for doc_id in selected:
        sim, matched_field = best.get(doc_id, (None, None))
        in_bm25, in_vector = doc_id in bm25_rank, doc_id in vector_rank
        bm25_hit = bm25_by_id.get(doc_id)
        hits.append(
            Hit(
                doc_id=doc_id,
                similarity=sim,
                matched_field=matched_field,
                via=VIA_BOTH if in_bm25 and in_vector else VIA_BM25 if in_bm25 else VIA_VECTOR,
                bm25_rank=bm25_rank.get(doc_id),
                vector_rank=vector_rank.get(doc_id),
                rrf_score=scores.get(doc_id),
                snippet=bm25_hit.snippet if bm25_hit else None,
                matched_terms=bm25_hit.matched_terms if bm25_hit else [],
            )
        )

    # 表示順は関連度の降順（ADR-0023）。RRF順のままだと「BM25にも当たった文書が上に来るが、
    # 表示する%は低い」という矛盾が起きる。キーワードのみの方式は類似度が無いのでBM25順のまま
    if mode != MODE_BM25:
        hits.sort(key=lambda h: -(h.similarity if h.similarity is not None else -1.0))

    return SearchResult(
        hits=hits,
        bm25_count=len(bm25_hits),
        top_similarity=max((s for s, _ in best.values()), default=0.0),
    )
