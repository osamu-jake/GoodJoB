"""関連度の表示（ADR-0010・0023・0035）。

**表示する関連度は、コサイン類似度を100倍した整数そのもの**（0.893 → 89%）。
結果セット内での相対値にはしない。相対値にすると1位が必ず上限に張り付き、無関係なクエリでも
「96% 近い」と出て、「ヒットなし」の警告と同時に表示される自己矛盾が起きるため（ADR-0035）。

キーワード（BM25）だけでヒットした文書は、意味の近さを測っていないので数値を出さず、
「語一致」のラベルを付ける（F-14）。
"""

import math
from dataclasses import dataclass

from . import cross_search, hit_judge

KEYWORD_ONLY_LABEL = "語一致"

# 数値だけに頼らせないための言葉（ADR-0035：言葉の併記は続ける）。
# 境目は暫定。e5の類似度は0.7〜0.9に固まりやすいので、実データを入れたあとに決め直す（ADR-0010の未決）
CLOSE_FROM = 0.85  # これ以上は「近い」
# 「やや近い」の下限は「ヒットなし」の基準値にそろえる。そろえないと、ヒットなしで折りたたんだ候補に
# 「やや近い」が付いてしまう（ADR-0054）
SOMEWHAT_CLOSE_FROM = hit_judge.THRESHOLD  # これ以上は「やや近い」。未満は「応用候補」


@dataclass
class Score:
    percent: int | None  # 関連度（%）。語一致のみなら None（数値を出さない）
    label: str  # 近い／やや近い／応用候補／語一致
    keyword_only: bool


def to_percent(similarity: float) -> int:
    """コサイン類似度を百分率の整数にする（四捨五入。0〜100に収める）。"""
    return max(0, min(100, math.floor(similarity * 100 + 0.5 + 1e-9)))


def proximity_label(similarity: float) -> str:
    if similarity >= CLOSE_FROM:
        return "近い"
    if similarity >= SOMEWHAT_CLOSE_FROM:
        return "やや近い"
    return "応用候補"


def score_hit(hit: "cross_search.Hit") -> Score:
    """検索結果1件の表示用スコア。

    BM25だけで候補に入った文書（`via == 'bm25'`）は、類似度を並び順のために内部では持っていても
    数値は出さず「語一致」にする。
    """
    if hit.via == cross_search.VIA_BM25 or hit.similarity is None:
        return Score(percent=None, label=KEYWORD_ONLY_LABEL, keyword_only=True)
    return Score(
        percent=to_percent(hit.similarity), label=proximity_label(hit.similarity), keyword_only=False
    )
