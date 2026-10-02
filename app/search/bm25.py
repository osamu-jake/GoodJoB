"""キーワード検索（SQLite FTS5のBM25。ADR-0011・0027）。

索引は `db/build_db.py` が `tokenizer` で分かち書きして張る。検索側も同じ `tokenizer` を通すので、
入れた語で必ず引ける。`title`／`body`／`problem`／`background` の4列すべてが対象
（ベクトル側は title を埋め込まないので、対象が違うのは意図的。ADR-0027）。

contentless構成のFTS5は snippet() が使えない（本文を持たないため）。スニペットは
`documents` の原文を同じ分かち書きにかけて、一致した語の周辺を切り出して作る。
"""

import sqlite3
from dataclasses import dataclass, field

from . import tokenizer

# スニペットを探すフィールドの優先順。ニーズ語に最も近い課題（problem）を先に見る（ADR-0021）
SNIPPET_FIELDS = ("problem", "body", "background", "title")
SNIPPET_RADIUS = 40  # 一致箇所の前後に残す文字数


@dataclass
class Bm25Hit:
    doc_id: int
    score: float  # 大きいほど良い（FTS5のbm25()は小さいほど良い負値なので符号を反転している）
    snippet: str | None = None
    matched_terms: list[str] = field(default_factory=list)  # 原文に現れた一致語（表記のまま）


def search(
    con: sqlite3.Connection, query_text: str, doc_type: str, k: int = 50, with_snippet: bool = True
) -> list[Bm25Hit]:
    """`doc_type` の文書を対象に、BM25の上位k件を返す。クエリから語が取れなければ空リスト。"""
    fts_query = tokenizer.to_fts_query(query_text)
    if not fts_query:
        return []

    rows = con.execute(
        """
        SELECT f.rowid AS doc_id, bm25(documents_fts) AS rank
          FROM documents_fts f
          JOIN documents d ON d.id = f.rowid
         WHERE documents_fts MATCH ?
           AND d.doc_type = ?
         ORDER BY rank
         LIMIT ?
        """,
        (fts_query, doc_type, k),
    ).fetchall()

    hits = [Bm25Hit(doc_id=r["doc_id"], score=-r["rank"]) for r in rows]
    if with_snippet:
        terms = frozenset(tokenizer.tokenize(query_text))
        for hit in hits:
            hit.snippet, hit.matched_terms = _snippet(con, hit.doc_id, terms)
    return hits


def _snippet(con: sqlite3.Connection, doc_id: int, terms: frozenset[str]) -> tuple[str | None, list[str]]:
    row = con.execute(
        "SELECT title, body, problem, background FROM documents WHERE id = ?", (doc_id,)
    ).fetchone()
    if row is None:
        return None, []

    snippet = None
    matched: list[str] = []
    for name in SNIPPET_FIELDS:
        text = row[name]
        spans = tokenizer.find_spans(text, terms)
        if not spans:
            continue
        matched.extend(text[s:e] for s, e in spans)
        if snippet is None:
            start = max(0, spans[0][0] - SNIPPET_RADIUS)
            end = min(len(text), spans[0][1] + SNIPPET_RADIUS)
            snippet = ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")
    return snippet, list(dict.fromkeys(matched))
