"""各テーブルへの参照（仕様「データ」）。

データが無い場合も例外にせず「登録なし」「未評価」を返す。
データがないことも判断材料になるため、空欄で隠さない（仕様「エラー時の挙動」）。
"""

import sqlite3

KIND_LABELS = {
    "evaluated": "評価済み",
    "dropped": "見送り",
    "unevaluated": "未評価",
}
STATE_LABELS = {
    "registered": "登録済",
    "pending": "出願中",
    "none": "未出願",
}


def get_document(con: sqlite3.Connection, doc_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()


def get_documents(con: sqlite3.Connection, doc_ids: list[int]) -> dict[int, sqlite3.Row]:
    if not doc_ids:
        return {}
    placeholders = ",".join("?" * len(doc_ids))
    rows = con.execute(
        f"SELECT * FROM documents WHERE id IN ({placeholders})", doc_ids
    ).fetchall()
    return {r["id"]: r for r in rows}


def list_seeds(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM documents WHERE doc_type='seed' ORDER BY title"
    ).fetchall()


def get_tech_usage(con: sqlite3.Connection, seed_id: int) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM tech_usage WHERE seed_id = ? ORDER BY launched DESC", (seed_id,)
    ).fetchall()


def get_evaluations(con: sqlite3.Connection, seed_id: int) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM evaluations WHERE seed_id = ? ORDER BY dated DESC", (seed_id,)
    ).fetchall()


def get_patent(con: sqlite3.Connection, seed_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM patents WHERE seed_id = ?", (seed_id,)).fetchone()


def patent_state_label(con: sqlite3.Connection, seed_id: int) -> str:
    row = get_patent(con, seed_id)
    if row is None:
        return "権利情報なし"
    return STATE_LABELS.get(row["state"], "権利情報なし")


def list_gap_queries(con: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    """「まだ社内に無い技術」＝十分な関連度の技術が返らなかった企画案の一覧。

    頻度ランキングにはしない。企画案は1件ごとに文面が異なるため集計は実態に合わない。
    個別の企画案を、検索日・部署・その時の最高関連度とともに並べる。
    """
    return con.execute(
        """
        SELECT ts, query, user_dept, top_score
          FROM search_logs
         WHERE hit_count = 0
         ORDER BY ts DESC
         LIMIT ?
        """,
        (limit,),
    ).fetchall()
