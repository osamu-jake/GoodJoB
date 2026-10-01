"""knowledge.db の自動構築（ADR-0015・0025・0027）。

`.db` が無ければ `schema.sql` ＋ `fixtures/seeds.sql` から組み立て、FTS5 の索引を張る。
`.db` があるときは何もしない（手元で転記中のデータを消さないため）。
`git pull` で新しい seeds.sql を取り込んだときは `python3 db/build_db.py --rebuild` で作り直す。

途中で失敗したときに作りかけの `.db` が残ると、次回の起動で「既にある」と判定されて
壊れたまま使われてしまう。そのため一時ファイルに組み立て、完成してから置き換える。

埋め込みの計算（実装計画 2-4）はこのファイルに後から足す。
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import Callable

APP_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = APP_DIR / "db" / "schema.sql"
SEEDS_PATH = APP_DIR / "fixtures" / "seeds.sql"
DB_PATH = APP_DIR / "knowledge.db"

FTS_FIELDS = ("title", "body", "problem", "background")

# 文字列を語のリストに分ける関数。索引側と検索側で同じものを使う（設計.md tokenizer.py）
Tokenize = Callable[[str], list[str]]


def _default_tokenize() -> Tokenize:
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))
    from search.tokenizer import tokenize  # 実装計画 2-5

    return tokenize


def index_fts(con: sqlite3.Connection, tokenize: Tokenize) -> None:
    """documents_fts を documents から張り直す。

    contentless 構成なので、documents へ INSERT しただけでは索引は空のまま（ADR-0027）。
    分かち書きした語を空白でつないで入れ、unicode61 に空白で区切らせる。
    contentless の表には DELETE が使えないので、FTS5 の 'delete-all' コマンドで空にする。
    """
    con.execute("INSERT INTO documents_fts (documents_fts) VALUES ('delete-all')")
    rows = con.execute(
        f"SELECT id, {', '.join(FTS_FIELDS)} FROM documents ORDER BY id"
    ).fetchall()
    con.executemany(
        f"INSERT INTO documents_fts (rowid, {', '.join(FTS_FIELDS)})"
        f" VALUES (?, {', '.join('?' * len(FTS_FIELDS))})",
        [
            (row[0], *(" ".join(tokenize(text or "")) for text in row[1:]))
            for row in rows
        ],
    )


def build(
    db_path: Path = DB_PATH,
    *,
    rebuild: bool = False,
    schema_path: Path = SCHEMA_PATH,
    seeds_path: Path = SEEDS_PATH,
    tokenize: Tokenize | None = None,
) -> bool:
    """`.db` が無ければ（`rebuild=True` なら常に）組み立てる。組み立てたら True を返す。"""
    db_path = Path(db_path)
    if db_path.exists() and not rebuild:
        return False
    if tokenize is None:
        tokenize = _default_tokenize()

    tmp_path = db_path.with_name(f"{db_path.stem}.building{db_path.suffix}")  # *.db で Git 管理外
    tmp_path.unlink(missing_ok=True)
    con = sqlite3.connect(tmp_path)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(schema_path.read_text(encoding="utf-8"))
        con.executescript(seeds_path.read_text(encoding="utf-8"))
        index_fts(con, tokenize)
        con.commit()
    except BaseException:
        con.close()
        tmp_path.unlink(missing_ok=True)
        raise
    con.close()
    os.replace(tmp_path, db_path)
    return True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="knowledge.db を schema.sql＋seeds.sql から組み立てる")
    parser.add_argument("--rebuild", action="store_true", help="既存の .db を捨てて作り直す")
    args = parser.parse_args(argv)

    built = build(rebuild=args.rebuild)
    con = sqlite3.connect(DB_PATH)
    tables = ("documents", "projects", "project_techs", "project_products", "patents", "embeddings")
    print(f"{'built' if built else 'kept'} {DB_PATH}")
    for table in tables:
        print(f"  {table}: {con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    main()
