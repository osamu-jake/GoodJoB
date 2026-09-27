"""Reciprocal Rank Fusion（ADR-0003：k=60）。

BM25のスコアとコサイン類似度は尺度が違い直接比較できないため、
順位だけを使って統合する。正規化が不要で、重みの根拠を問われない。
"""

K = 60


def rrf(*rank_lists: list[int], k: int = K) -> list[tuple[int, float]]:
    """順位リストを統合し、(doc_id, スコア) を降順で返す。"""
    scores: dict[int, float] = {}
    for hits in rank_lists:
        for rank, doc_id in enumerate(hits, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
