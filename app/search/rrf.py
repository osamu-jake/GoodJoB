"""Reciprocal Rank Fusion（ADR-0003）。

BM25のスコアとベクトルの類似度は尺度が違い、そのままでは足せない。RRFは順位だけを使い、
各リストでの順位 rank（1始まり）から `1 / (k + rank)` を求めて文書ごとに足し合わせる。k=60。
片方のリストにしか出ない文書も、出たぶんだけ点が付いて結果に残る。

**RRFは「どの文書を結果に含めるか」の決定にだけ使い、表示順には使わない**（ADR-0023）。
"""

K = 60


def rrf(*rankings: list[int], k: int = K) -> list[tuple[int, float]]:
    """順位付きのdoc_idリスト（先頭が1位）を何本でも受け取り、統合スコアの降順で (doc_id, スコア) を返す。

    同点のときは、先に現れた順（最初のリストの順位が良い方）を保つ。
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for position, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + position)
    # dictは挿入順を保つので、同点は先に出た文書が前に来る（sortedは安定ソート）
    return sorted(scores.items(), key=lambda item: -item[1])
