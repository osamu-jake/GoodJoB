"""関連度の表示（ADR-0010）。

並び順はRRFで決め、表示する数値は意味検索側のコサイン類似度を使う。役割を分ける。

素のコサイン類似度をそのまま100倍してはいけない。e5は実際のスコアが0.7〜0.9に
固まるため、全候補が80%台に並んでグラデーション表示が機能しなくなる。
「検索結果の中での相対的な近さ」に変換し、数値だけに頼らせないよう言葉も併記する。

表記は「一致度」ではなく「関連度」。判定しているという印象を避けるため。
"""

FLOOR = 35  # 最下位に割り当てる％。0にすると「無関係」と誤読されるため下限を置く
CEIL = 96   # 最上位に割り当てる％。100にすると「完全一致」と誤読されるため上限を置く


def to_relative_percent(similarities: list[float]) -> list[int]:
    """検索結果内での相対値に変換する。件数が少ないときも破綻しないようにする。"""
    if not similarities:
        return []
    if len(similarities) == 1:
        return [CEIL]
    lo, hi = min(similarities), max(similarities)
    if hi - lo < 1e-9:
        return [CEIL] * len(similarities)
    span = CEIL - FLOOR
    return [round(FLOOR + (s - lo) / (hi - lo) * span) for s in similarities]


def label(percent: int) -> str:
    """数値だけに頼らせないための言葉。"""
    if percent >= 80:
        return "近い"
    if percent >= 55:
        return "やや近い"
    return "応用候補"
