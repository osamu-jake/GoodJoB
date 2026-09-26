"""「ヒットなし」判定（ADR-0008）。

ベクトル検索は常に上位k件を返すため、何もしないと「0件」が構造的に発生せず
「まだ社内に無い技術」が機能しない。そこで反対側の結果に限定し、
BM25が0件 かつ 最高類似度が基準値未満 の両方を満たす場合を「ヒットなし」とする。

基準値はデータ投入後に実測で調整する（暫定0.80）。
"""

THRESHOLD = 0.80


def is_no_hit(bm25_hits: list[int], top_similarity: float, threshold: float = THRESHOLD) -> bool:
    """反対側の結果に対してのみ呼ぶこと。同じ側は必ず語が一致し0件にならない。"""
    return len(bm25_hits) == 0 and top_similarity < threshold
