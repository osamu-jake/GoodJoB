"""knowledge.db の中身を fixtures/seeds.sql に書き出す（ADR-0025）。

使い方：
    python3 tools/export_seeds.py

コミットする前に1回だけ実行する。件数に関係なく、テーブルの中身がまるごと出る。

書き出す対象は「人が手で作ったデータ」だけ：
  documents / tech_usage / evaluations / patents
除外するもの：
  embeddings  … 起動のたびにローカルで計算し直す（ADR-0020）
  search_logs … 実行中に溜まるログ。デモのたびに変わるのでコミットしない
"""

import sqlite3
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

DB_PATH = APP_DIR / "knowledge.db"
OUT_PATH = APP_DIR / "fixtures" / "seeds.sql"

TABLES = ("documents", "tech_usage", "evaluations", "patents")

HEADER = """-- 知の越境検索 — 手入力データの正本（ADR-0025）
-- knowledge.db から tools/export_seeds.py で書き出したもの。直接編集しない。
-- 編集は knowledge.db に対して行い、コミット前に書き出し直すこと。
"""


def _sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def export(db_path: Path = DB_PATH, out_path: Path = OUT_PATH) -> dict[str, int]:
    if not db_path.exists():
        raise SystemExit(f"{db_path} がありません。先にアプリを起動してDBを作ってください。")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    counts: dict[str, int] = {}
    lines = [HEADER]

    for table in TABLES:
        # id順に固定して出す。順番が毎回変わるとGitの差分が読めなくなるため
        rows = con.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
        counts[table] = len(rows)
        lines.append(f"\n-- {table}（{len(rows)}件）")
        if not rows:
            continue
        columns = rows[0].keys()
        col_list = ", ".join(columns)
        for row in rows:
            values = ", ".join(_sql_literal(row[c]) for c in columns)
            lines.append(f"INSERT INTO {table} ({col_list}) VALUES ({values});")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    con.close()
    return counts


if __name__ == "__main__":
    counts = export()
    print(f"書き出しました: {OUT_PATH.relative_to(APP_DIR)}")
    for table, n in counts.items():
        print(f"  {table}: {n}件")
    print("\nこのファイルをコミットしてください。")
