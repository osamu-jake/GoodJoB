"""キーワード検索（SQLite FTS5のBM25）。

FTS5はcontentless構成のため、rowidをdocuments.idと一致させて投入している。
"""

import sqlite3

from . import tokenizer


def search(con: sqlite3.Connection, query_text: str, doc_type: str, k: int = 50) -> list[int]:
    """対象doc_typeの中からBM25で上位k件のdoc_idを返す。"""
    fts_query = tokenizer.to_fts_query(query_text)
    if not fts_query:
        return []
    rows = con.execute(
        """
        SELECT f.rowid
          FROM documents_fts f
          JOIN documents d ON d.id = f.rowid
         WHERE documents_fts MATCH ?
           AND d.doc_type = ?
         ORDER BY bm25(documents_fts)
         LIMIT ?
        """,
        (fts_query, doc_type, k),
    ).fetchall()
    return [r[0] for r in rows]
