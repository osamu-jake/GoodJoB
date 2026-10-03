"""knowledge.db → app/fixtures/seeds.sql の書き出し（ADR-0025・0039）。

手入力データ（特許の転記・ダミーのニーズ・架空の企画系データ）は `knowledge.db` 本体で編集する。
コミット前にこのスクリプトを1回実行して、テキストの `app/fixtures/seeds.sql` に書き出す。
`build_db.py` は逆向きに、このファイルから `.db` を組み立てる。

- 書き出すのは documents／projects／project_techs／project_products／patents の5つだけ。
  embeddings（再計算できる）・search_logs（実行時ログ）・documents_fts（再構築できる）は対象外
- **`id` を明示して書き出す。** `project_techs.seed_id` は文書の番号で技術を指すため、
  再構築で番号が変わると「どの企画がどの技術を採用したか」の対応が壊れる（ADR-0039）
- 外部キーの参照先から順に並べる（documents → projects → project_techs／project_products／patents）。
  取り込むとき（外部キー検査ON）に、参照先がまだ無いというエラーを出さないため

使い方（app/ から）:
    python tools/export_seeds.py                     # 既定: app/knowledge.db → app/fixtures/seeds.sql
    python tools/export_seeds.py --db X.db --out Y.sql
"""

import argparse
import sqlite3
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:  # `python tools/export_seeds.py` で直接動かしたとき用
    sys.path.insert(0, str(APP_DIR))

from db import build_db, connection  # noqa: E402

# 書き出し先は、build_db.py が読む場所と同じ（app/fixtures/seeds.sql）。1か所の定義を共有する
DEFAULT_OUT = build_db.SEEDS_PATH

# 参照先から順に並べる。この順序が外部キー検査ONで取り込める順序になる
EXPORT_TABLES = ("documents", "projects", "project_techs", "project_products", "patents")

HEADER = """\
-- 手入力データの正本（ADR-0025）。tools/export_seeds.py が knowledge.db から書き出したもの。
-- このファイルを直接編集しない。編集は knowledge.db で行い、書き出し直してコミットする。
-- 取り込み順: documents → projects → project_techs／project_products／patents（外部キーの参照先が先）
"""


def _columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [row["name"] for row in con.execute(f"PRAGMA table_info({table})")]


def export_table(con: sqlite3.Connection, table: str) -> list[str]:
    """1テーブル分の INSERT 文を id 順に返す。値のリテラル化は SQLite の quote() に任せる。"""
    columns = _columns(con, table)
    column_list = ", ".join(columns)
    quoted = ", ".join(f"quote({c})" for c in columns)
    rows = con.execute(f"SELECT {quoted} FROM {table} ORDER BY id").fetchall()
    return [f"INSERT INTO {table} ({column_list}) VALUES ({', '.join(r)});" for r in rows]


def export_seeds(db_path: str | Path, out_path: str | Path) -> dict[str, int]:
    """`db_path` の手入力データを `out_path` に書き出し、テーブルごとの件数を返す。"""
    con = connection.connect(db_path)
    try:
        sections = [HEADER]
        counts = {}
        for table in EXPORT_TABLES:
            statements = export_table(con, table)
            counts[table] = len(statements)
            sections.append(f"\n-- {table} ({len(statements)}件)")
            sections.extend(statements)
    finally:
        con.close()

    # 改行をLFに揃える（Windowsで書き出しても差分が出ないように）
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(sections) + "\n")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="knowledge.db を app/fixtures/seeds.sql に書き出す")
    parser.add_argument("--db", default=str(connection.DB_PATH), help="書き出し元のDB")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="書き出し先の seeds.sql")
    args = parser.parse_args()

    if not Path(args.db).exists():
        sys.exit(f"DBが見つかりません: {args.db}")
    counts = export_seeds(args.db, args.out)
    print(f"exported: {args.db} -> {args.out}")
    for table, n in counts.items():
        print(f"  {table}: {n}")


if __name__ == "__main__":
    main()
