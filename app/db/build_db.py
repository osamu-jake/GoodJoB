"""DBの自動構築（ADR-0015・0020・0025）。

**編集するのは knowledge.db 本体。** 特許の転記はDBに直接入力し、コミット前に
`tools/export_seeds.py` で `fixtures/seeds.sql`（テキスト）へ書き出す。

ここがやるのは逆方向だけ：`.db` が無いときに `schema.sql` ＋ `seeds.sql` から組み立てる。
Streamlit Community Cloudは再起動でファイルがリポジトリの状態に戻るため、この経路がないと
デモの再現性が保証できない。

`.db` が既にあるときは何もしない。手元の編集内容を上書きしないため。
git pull で新しい seeds.sql を取り込んだときは `--rebuild` で作り直す。

summary_plain は seeds.sql に生成済みのテキストが入っている前提で、ここでは生成しない
（起動のたびに課金APIを呼ばないため。ADR-0020）。
埋め込みは無料のローカル計算なので、構築のたびに作り直す。
"""

import sqlite3
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

SCHEMA_PATH = APP_DIR / "db" / "schema.sql"
SEEDS_PATH = APP_DIR / "fixtures" / "seeds.sql"
DB_PATH = APP_DIR / "knowledge.db"


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _load_seeds(con: sqlite3.Connection) -> None:
    """手入力データ（documents/tech_usage/evaluations/patents）を投入する。"""
    con.executescript(SEEDS_PATH.read_text(encoding="utf-8"))
    _rebuild_fts(con)


def _rebuild_fts(con: sqlite3.Connection) -> None:
    """FTS5索引を作り直す。contentless構成なので明示的に入れる必要がある。

    Janomeで分かち書きしたテキストを入れる（ADR-0011）。
    ここを忘れると「DBには入っているのに検索に出てこない」不具合になる。
    """
    from search import tokenizer

    con.execute("DELETE FROM documents_fts")
    rows = con.execute(
        "SELECT id, title, body, problem, background FROM documents"
    ).fetchall()
    con.executemany(
        "INSERT INTO documents_fts (rowid, title, body, problem, background)"
        " VALUES (?,?,?,?,?)",
        [
            (
                r["id"],
                tokenizer.to_fts_text(r["title"] or ""),
                tokenizer.to_fts_text(r["body"] or ""),
                tokenizer.to_fts_text(r["problem"] or ""),
                tokenizer.to_fts_text(r["background"] or ""),
            )
            for r in rows
        ],
    )


def _build_embeddings(con: sqlite3.Connection) -> None:
    """フィールドごとに別ベクトルを作る（ADR-0021）。"""
    from search import vector

    rows = con.execute(
        "SELECT id, title, body, problem, background FROM documents"
    ).fetchall()
    payload: list[tuple[int, str, str]] = []
    for row in rows:
        for field in vector.FIELDS:
            text = row[field]
            if text:
                payload.append((row["id"], field, text))
    if not payload:
        return
    vecs = vector.encode_passage([t for _, _, t in payload])
    con.executemany(
        "INSERT OR REPLACE INTO embeddings (doc_id, field, vec) VALUES (?,?,?)",
        [(doc_id, field, vector.to_blob(v)) for (doc_id, field, _), v in zip(payload, vecs)],
    )


def build(db_path: Path = DB_PATH, force: bool = False) -> sqlite3.Connection:
    """`.db`が無ければ作る。あればそのまま使う。"""
    if force and db_path.exists():
        db_path.unlink()
    exists = db_path.exists()
    con = connect(db_path)
    if exists:
        return con
    con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _load_seeds(con)
    _build_embeddings(con)
    con.commit()
    return con


if __name__ == "__main__":
    # --rebuild: seeds.sql から作り直す（git pull 後など）
    con = build(force="--rebuild" in sys.argv or "--force" in sys.argv)
    counts = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("documents", "embeddings", "tech_usage", "evaluations", "patents")
    }
    print(f"built {DB_PATH}")
    for t, n in counts.items():
        print(f"  {t}: {n}")
