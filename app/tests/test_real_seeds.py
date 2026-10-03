"""実データ `fixtures/seeds.sql`（じゃけさんの転記・書き出し）が組み立てられることの確認。

期待値は実データに依存させない（転記のたびに変わるため。ADR-0015）。
「取り込める」「外部キーが壊れていない」だけを見て、転記のPRが機能を壊していないことを守る。
seeds.sql がまだ無いあいだはスキップする。
"""

import pytest

from db import build_db


@pytest.fixture
def real_con(db_path):
    if not build_db.SEEDS_PATH.exists():
        pytest.skip("fixtures/seeds.sql がまだ無い")
    con = build_db.build(db_path, seeds_path=build_db.SEEDS_PATH)
    yield con
    con.close()


def test_実データのseedsからDBを組み立てられる(real_con):
    counts = build_db.table_counts(real_con)
    assert counts["documents"] > 0


def test_実データの外部キーが壊れていない(real_con):
    assert real_con.execute("PRAGMA foreign_key_check").fetchall() == []


def test_実データのdoc_typeとsourceが仕様の値である(real_con):
    rows = real_con.execute("SELECT DISTINCT doc_type, source FROM documents").fetchall()
    assert {r["doc_type"] for r in rows} <= {"seed", "need"}
    assert {r["source"] for r in rows} <= {"patent_manual", "dummy", "faq", "placeholder"}
