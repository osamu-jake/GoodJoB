"""db/schema.sql と db/build_db.py のテスト（U-13・U-14・U-22・U-25／I-03・I-04・I-05・I-05b）。"""

import sqlite3

import pytest

from db import build_db
from search import tokenizer

from .conftest import TEST_SEEDS


def fts_hits(con, text):
    """分かち書きしたクエリで documents_fts を引き、ヒットした documents.id を返す。"""
    rows = con.execute(
        "SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?",
        (tokenizer.to_fts_query(text),),
    ).fetchall()
    return {r[0] for r in rows}


def test_u13_dbが無ければschemaとseedsから構築される(db_path):
    """U-13: `.db` が存在しない → schema.sql＋seedsから構築される。"""
    assert not db_path.exists()

    con = build_db.build(db_path, seeds_path=TEST_SEEDS)

    assert db_path.exists()
    counts = build_db.table_counts(con)
    assert counts["documents"] == 10
    assert counts["projects"] == 2
    assert counts["project_techs"] == 3
    assert counts["project_products"] == 1
    assert counts["patents"] == 2


def test_u13_8テーブルがそろう(con):
    names = {
        r[0]
        for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table')")
    }
    expected = {
        "documents", "projects", "project_techs", "project_products",
        "patents", "embeddings", "search_logs", "documents_fts",
    }
    assert expected <= names


def test_u14_dbが既にあれば再構築しない(db_path):
    """U-14: `.db` が既に存在する → 再構築せず既存を使う（手元で編集中のデータを守る）。"""
    con = build_db.build(db_path, seeds_path=TEST_SEEDS)
    con.execute("INSERT INTO documents (id, doc_type, source, title) VALUES (99, 'seed', 'placeholder', '手元で足した文書')")
    con.commit()
    con.close()

    con = build_db.build(db_path, seeds_path=TEST_SEEDS)

    assert con.execute("SELECT title FROM documents WHERE id = 99").fetchone()[0] == "手元で足した文書"
    assert build_db.table_counts(con)["documents"] == 11


def test_rebuildはseedsから作り直して手元の変更を置き換える(db_path):
    con = build_db.build(db_path, seeds_path=TEST_SEEDS)
    con.execute("INSERT INTO documents (id, doc_type, source, title) VALUES (99, 'seed', 'placeholder', '手元で足した文書')")
    con.commit()
    con.close()

    con = build_db.build(db_path, force=True, seeds_path=TEST_SEEDS)

    assert build_db.table_counts(con)["documents"] == 10
    assert con.execute("SELECT COUNT(*) FROM documents WHERE id = 99").fetchone()[0] == 0


def test_seedsが無くてもスキーマだけのDBができる(db_path, tmp_path):
    con = build_db.build(db_path, seeds_path=tmp_path / "none.sql")
    assert build_db.table_counts(con)["documents"] == 0


def test_接続は外部キー検査がONになっている(con):
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_u22_problemだけにある語でもFTSがヒットする(con):
    """U-22: `problem` のみに語を持つ文書 → その語で documents_fts がヒットする（4列すべてが索引される）。"""
    # 文書1の problem にだけある語（title・body・background には無い）
    assert "毛先" not in (con.execute("SELECT title||body||background FROM documents WHERE id=1").fetchone()[0])
    assert fts_hits(con, "毛先") == {1}


def test_u22_backgroundだけにある語でもFTSがヒットする(con):
    """I-05b: `background` のみにある語でもヒットする。"""
    row = con.execute("SELECT title||body||problem FROM documents WHERE id=2").fetchone()[0]
    assert "触る" not in row
    assert fts_hits(con, "触る") == {2}


def test_i05_documentsへINSERTしただけでは索引に出ず_張り直すと出る(con):
    """I-05: contentless構成のため、INSERTだけでは検索に出ない。索引を張り直すと出る（ADR-0027）。"""
    con.execute(
        "INSERT INTO documents (id, doc_type, source, title, body) VALUES (50, 'seed', 'placeholder', 'テスト', 'ヒアルロン酸を配合した化粧水')"
    )
    assert fts_hits(con, "ヒアルロン酸") == set()

    build_db.rebuild_fts(con)

    assert fts_hits(con, "ヒアルロン酸") == {50}


def test_i04_summary_plainはseedsの生成済みテキストがそのまま入る(con):
    """I-04: 要約はseedsから投入される（起動時に生成AIを呼ばない。ADR-0020）。"""
    summary = con.execute("SELECT summary_plain FROM documents WHERE id = 1").fetchone()[0]
    assert summary == "皮脂を吸う粉で、夕方まで髪型が崩れにくくなる技術。"


def test_i03_dbなしから構築して検索できる(db_path):
    """I-03: `.db` なしで構築 → `documents` に文書があり、BM25索引で検索できる。
    （embeddings は 2-4 で build_db に加わるため、そのテストは test_embeddings.py）"""
    con = build_db.build(db_path, seeds_path=TEST_SEEDS)
    assert fts_hits(con, "皮脂を吸着する微粒子") >= {1}


def test_u25_同じ企画と技術の組を2回登録すると一意制約違反(con):
    """U-25: 同じ (project_id, seed_id) を2回INSERT → 2回目が一意制約違反。"""
    con.execute("INSERT INTO project_techs (project_id, seed_id, decision) VALUES (2, 3, 'evaluating')")
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        con.execute("INSERT INTO project_techs (project_id, seed_id, decision) VALUES (2, 3, 'adopted')")


def test_patentsのseed_idはNULLを許さない(con):
    """ADR-0046: `patents.seed_id` は NOT NULL。"""
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
        con.execute("INSERT INTO patents (seed_id, state) VALUES (NULL, 'none')")


def test_seeds_sqlの既定の置き場所はapp配下のfixtures():
    """設計.md「構成」に合わせ、`app/fixtures/seeds.sql`（リポジトリ直下ではない）。"""
    assert build_db.SEEDS_PATH == build_db.APP_DIR / "fixtures" / "seeds.sql"
    assert build_db.SEEDS_PATH.parent.parent.name == "app"
