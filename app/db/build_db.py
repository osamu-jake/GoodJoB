"""起動時のDB自動構築（ADR-0015・0025・0027）。

手入力データの編集先は `knowledge.db` 本体で、コミット前に `tools/export_seeds.py` で
`fixtures/seeds.sql` に書き出す。ここがやるのは逆向き：`.db` が無いとき
`schema.sql` と `seeds.sql` から組み立てる。Streamlit Community Cloud は再起動でファイルが
リポジトリの状態に戻るため、この経路がないとデモの再現性（N-04）が保てない。

- `.db` が既にあるときは**何もしない**（手元で転記中のデータを守るため）
- `git pull` で新しい seeds.sql が来たときは `python db/build_db.py --rebuild` で作り直す
- `summary_plain` は seeds.sql に入っている生成済みテキストをそのまま使う。ここでAPIは呼ばない（ADR-0020）

作り直しは、メモリ上で組み立ててから `.db` へ丸ごと書き込む（SQLiteのbackup API）。
ファイルを消す処理は使わないので、途中で失敗しても既存の `.db` は半端な状態にならない。
"""

import logging
import sqlite3
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:  # `python db/build_db.py` で直接動かしたとき用
    sys.path.insert(0, str(APP_DIR))

from db import connection  # noqa: E402
from search import tokenizer  # noqa: E402

log = logging.getLogger(__name__)

SCHEMA_PATH = APP_DIR / "db" / "schema.sql"
SEEDS_PATH = APP_DIR.parent / "fixtures" / "seeds.sql"

COUNT_TABLES = (
    "documents",
    "projects",
    "project_techs",
    "project_products",
    "patents",
    "embeddings",
    "search_logs",
)


def rebuild_fts(con: sqlite3.Connection) -> None:
    """FTS5索引を `documents` から張り直す。

    contentless構成（ADR-0027）は `documents` へのINSERTだけでは索引が空のままなので、
    文書を足したあとはこれを呼ぶ。Janomeで分かち書きしたテキストを rowid = documents.id で入れる。
    """
    # contentless表は DELETE できない。専用コマンドで全行を消す
    con.execute("INSERT INTO documents_fts(documents_fts) VALUES ('delete-all')")
    rows = con.execute("SELECT id, title, body, problem, background FROM documents").fetchall()
    con.executemany(
        "INSERT INTO documents_fts (rowid, title, body, problem, background) VALUES (?,?,?,?,?)",
        [
            (
                r["id"],
                tokenizer.to_fts_text(r["title"]),
                tokenizer.to_fts_text(r["body"]),
                tokenizer.to_fts_text(r["problem"]),
                tokenizer.to_fts_text(r["background"]),
            )
            for r in rows
        ],
    )


def _assemble(schema_path: Path, seeds_path: Path) -> sqlite3.Connection:
    """メモリ上のDBに、スキーマ→seeds→FTS索引の順で組み立てる。"""
    con = connection.connect(":memory:")
    con.executescript(schema_path.read_text(encoding="utf-8"))
    if seeds_path.exists():
        con.executescript(seeds_path.read_text(encoding="utf-8"))
    else:
        log.warning("seeds.sql が見つかりません（%s）。空のDBを作ります", seeds_path)
    rebuild_fts(con)
    con.commit()
    return con


def _exists(db_path: Path) -> bool:
    return db_path.exists() and db_path.stat().st_size > 0


def build(
    db_path: str | Path = connection.DB_PATH,
    force: bool = False,
    schema_path: Path = SCHEMA_PATH,
    seeds_path: Path = SEEDS_PATH,
) -> sqlite3.Connection:
    """DBが無ければ組み立てて接続を返す。あれば何もせず接続だけ返す。

    force=True なら、既にあっても seeds.sql から作り直して中身を置き換える。
    """
    db_path = Path(db_path)
    if _exists(db_path) and not force:
        return connection.connect(db_path)

    mem = _assemble(schema_path, seeds_path)
    dest = sqlite3.connect(str(db_path))
    try:
        mem.backup(dest)
    finally:
        dest.close()
        mem.close()
    return connection.connect(db_path)


def table_counts(con: sqlite3.Connection) -> dict[str, int]:
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in COUNT_TABLES}


if __name__ == "__main__":
    rebuild = "--rebuild" in sys.argv
    con = build(force=rebuild)
    print(f"{'rebuilt' if rebuild else 'ready'}: {connection.DB_PATH}")
    for name, n in table_counts(con).items():
        print(f"  {name}: {n}")
