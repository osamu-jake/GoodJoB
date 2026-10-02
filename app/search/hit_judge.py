"""「ヒットなし」判定（ADR-0008）。

ベクトル検索は仕組み上つねに上位N件を返すので、何もしないと「ヒットが0件」という状態が
構造的に起きず、タブ②「まだ社内に無い技術」が機能しない。そこで、**反対側の結果に対してだけ**、
次の両方を満たすときを「ヒットなし」とする。

- 反対側のBM25が0件
- 反対側の最高類似度が基準値以下（暫定0.80。実データを入れたあと確定する＝テスト設計の未決2）

同じ側は必ず語が一致して0件にならないので、判定には使わない。
「ヒットなし」でも候補カードは空にしない（関連度の低い候補は出し続ける。仕様「エラー時の挙動」）。

**境界の扱い**: 基準値ちょうどは「ヒットなし」にする（テスト設計U-09：0.80は「ヒットなし」、0.81は「ヒットあり」）。
ADR-0008・仕様は「基準値未満」と書いているので、境界だけ文書間で食い違っている（PMに確認する）。
"""

THRESHOLD = 0.80  # 暫定。実データ投入後に確定する


def is_no_hit(bm25_count: int, top_similarity: float, threshold: float = THRESHOLD) -> bool:
    """反対側のBM25ヒット数と最高類似度から、「ヒットなし」かどうかを返す。

    反対側の結果に対してのみ呼ぶこと（`SearchResult.hits` 側の値。同じ側の値は渡さない）。
    """
    return bm25_count == 0 and top_similarity <= threshold


def judge(result, threshold: float = THRESHOLD) -> bool:
    """`cross_search.cross_search()` の結果から「ヒットなし」を判定する。"""
    return is_no_hit(result.bm25_count, result.top_similarity, threshold)
