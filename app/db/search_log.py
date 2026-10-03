"""検索ログの記録と読み出し（F-04・F-17、ADR-0008・0030）。

**記録は必ず `if st.button(...)` のブロック内で呼ぶこと。** Streamlit はボタン操作のたびに
スクリプト全体を再実行するので、ブロックの外に書くと、カードを開いただけでログが増えて
件数が水増しされる（I-06）。

| 関数 | 用途 |
|---|---|
| `log_search(con, ...)` | 検索1回で1行INSERTし、その行の id を返す（U-16） |
| `log_click(con, log_id, ...)` | 検索結果から詳細を開いたとき、その検索の行にクリックした文書を記録する |
| `list_gap_queries(con)` | タブ②「まだ社内に無い技術」：hit_count=0 の検索を新しい順に返す |
"""

import sqlite3
from datetime import datetime

USER_DEPT = "MK"  # 利用者はマーケ／商品企画の1種類（ADR-0030）
MODE_CROSS = "cross"  # タブ①のクロス検索（ニーズ→技術）


def log_search(
    con: sqlite3.Connection, query: str, hit_count: int, top_score: float, mode: str = MODE_CROSS
) -> int:
    """検索1回分を1行INSERTし、その行の id を返す。

    `hit_count` は反対側のヒット数。「ヒットなし」（ADR-0008）なら 0 を渡す。
    """
    cur = con.execute(
        "INSERT INTO search_logs (ts, query, mode, user_dept, hit_count, top_score)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), query, mode, USER_DEPT, hit_count, top_score),
    )
    con.commit()
    return cur.lastrowid


def log_click(con: sqlite3.Connection, log_id: int, doc_id: int, doc_type: str) -> None:
    """検索 `log_id` の結果から文書を開いたことを、その行に記録する。

    「最後の行」ではなく id で指定する。複数人が同時に使うと最後の行は他人の検索になるため。
    """
    con.execute(
        "UPDATE search_logs SET clicked_doc_id = ?, clicked_doc_type = ? WHERE id = ?",
        (doc_id, doc_type, log_id),
    )
    con.commit()


def list_gap_queries(con: sqlite3.Connection, limit: int = 50) -> list[dict]:
    """「まだ社内に無い技術」：十分な関連度の技術が返らなかった検索を新しい順に返す。

    頻度ランキングにはしない（企画案は1件ごとに文面が異なるため。仕様「タブ②」）。
    各行のキー: id, ts, query, top_score
    """
    rows = con.execute(
        "SELECT id, ts, query, top_score FROM search_logs"
        " WHERE hit_count = 0 ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
