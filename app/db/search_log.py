"""検索ログの記録（F-04）。

Streamlitはボタンを押すたびにスクリプト全体を走り直す。
記録は必ず `if st.button(...)` のブロック内で呼ぶこと。
外に書くと、結果カードを開いただけでもログが増えて件数が水増しされる。

（設計.mdでは db/logging.py としていたが、標準ライブラリの logging と紛らわしいため
  search_log.py に改めた）
"""

import sqlite3
from datetime import datetime


def log_search(
    con: sqlite3.Connection,
    query: str,
    mode: str,
    user_dept: str,
    hit_count: int,
    top_score: float,
) -> None:
    con.execute(
        """
        INSERT INTO search_logs (ts, query, mode, user_dept, hit_count, top_score)
        VALUES (?,?,?,?,?,?)
        """,
        (
            datetime.now().isoformat(timespec="seconds"),
            query,
            mode,
            user_dept,
            hit_count,
            top_score,
        ),
    )
    con.commit()


def log_click(con: sqlite3.Connection, doc_id: int, doc_type: str) -> None:
    """部門またぎ検索率の元データ。詳細表示ボタンのブロック内で呼ぶ。"""
    con.execute(
        "UPDATE search_logs SET clicked_doc_id = ?, clicked_doc_type = ?"
        " WHERE id = (SELECT MAX(id) FROM search_logs)",
        (doc_id, doc_type),
    )
    con.commit()
