"""DB接続の共通関数（ADR-0039）。

SQLiteは既定では REFERENCES を検査しない。接続のたびに `PRAGMA foreign_keys = ON` を
実行しないと、存在しない技術IDの登録や、判断の記録が残る技術の削除が素通りしてしまう。
DBに触る処理はすべてここ経由で接続すること。
"""

import os
import sqlite3
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent

# DBファイルの置き場所。環境変数 KNOWLEDGE_DB で差し替えられる（テスト・デプロイ用）
DB_PATH = Path(os.environ.get("KNOWLEDGE_DB", APP_DIR / "knowledge.db"))


def connect(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    """外部キー検査ONで接続する。`":memory:"` も渡せる。

    check_same_thread=False はStreamlitが再実行ごとに別スレッドで動くため。
    """
    con = sqlite3.connect(str(db_path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con
