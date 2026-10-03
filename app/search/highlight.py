"""一致理由のハイライト（F-18・ADR-0018）。

カードに「なぜこの技術が出たか」を見せるため、クエリの語句と文書の語句のうち**意味的に最も近い
ペア**（例：クエリの「べたつく」⇔ 文書の「皮脂」）を抜き出す。

- **語句ベクトルは事前に保存しない。** 検索結果の上位の文書に対してだけ、その場で計算する
  （専用テーブルを持たない。ADR-0018）。呼び出し側は上位の数件だけを渡すこと
- 語句は `tokenizer` で取り出した内容語（名詞・動詞・形容詞の基本形）。BM25と同じ分かち書き
- 語句同士の比較なので、どちらにも `query: ` を付けて計算する（対称な比較にはe5はこちらを勧めている）
- 1つのクエリ語句につき文書側の最近傍を1つ選び、類似度の高い順に上位 `top_n` ペアを返す。
  文書側の同じ語句は2回使わない（同じ箇所ばかり光らせない）
"""

import sqlite3
from dataclasses import dataclass

import numpy as np

from . import tokenizer, vector

FIELDS = ("problem", "body", "background")  # 課題を先に見る（ニーズ語に最も近い記述。ADR-0021）
TOP_N = 3


@dataclass
class Match:
    query_phrase: str
    doc_phrase: str
    similarity: float
    field: str  # 文書側の語句が見つかったフィールド
    spans: list[tuple[int, int]]  # そのフィールドの原文中での位置（ハイライト用。活用形は原文の表記）


def phrases(text: str | None) -> list[str]:
    """文から語句（内容語の基本形）を、重複を除いて出現順に取り出す。"""
    return list(dict.fromkeys(tokenizer.tokenize(text)))


def _encode_phrases(texts: list[str]) -> np.ndarray:
    return vector._encode([vector.with_query_prefix(t) for t in texts])


def nearest_pairs(
    query_phrases: list[str], doc_phrases: list[str], top_n: int = TOP_N
) -> list[tuple[str, str, float]]:
    """クエリ語句と文書語句から、意味的に近いペア (クエリ語句, 文書語句, 類似度) を類似度の降順で返す。"""
    if not query_phrases or not doc_phrases:
        return []
    vecs = _encode_phrases(query_phrases + doc_phrases)
    q, d = vecs[: len(query_phrases)], vecs[len(query_phrases) :]
    sims = q @ d.T  # 正規化済みなので内積がコサイン類似度

    # 類似度の高い組から採り、同じクエリ語句・同じ文書語句は1回ずつしか使わない
    pairs = sorted(
        ((float(sims[i, j]), i, j) for i in range(len(q)) for j in range(len(d))), reverse=True
    )
    used_q, used_d, chosen = set(), set(), []
    for sim, i, j in pairs:
        if i in used_q or j in used_d:
            continue
        used_q.add(i)
        used_d.add(j)
        chosen.append((query_phrases[i], doc_phrases[j], sim))
        if len(chosen) == top_n:
            break
    return chosen


def highlight(con: sqlite3.Connection, query_text: str, doc_id: int, top_n: int = TOP_N) -> list[Match]:
    """文書 `doc_id` について、クエリとの意味的に近い語句ペアを返す。検索結果の上位の文書にだけ使う。"""
    row = con.execute(
        "SELECT title, body, problem, background FROM documents WHERE id = ?", (doc_id,)
    ).fetchone()
    if row is None:
        return []

    # 語句 → それが見つかった最初のフィールド
    doc_phrases: dict[str, str] = {}
    for name in FIELDS:
        for phrase in phrases(row[name]):
            doc_phrases.setdefault(phrase, name)

    matches = []
    for q_phrase, d_phrase, sim in nearest_pairs(phrases(query_text), list(doc_phrases), top_n):
        field = doc_phrases[d_phrase]
        matches.append(
            Match(
                query_phrase=q_phrase,
                doc_phrase=d_phrase,
                similarity=sim,
                field=field,
                spans=tokenizer.find_spans(row[field], {d_phrase}),
            )
        )
    return matches
