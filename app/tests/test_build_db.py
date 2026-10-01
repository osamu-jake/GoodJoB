"""db/build_db.py と db/schema.sql のテスト（実装計画 1-2。U-13・U-14・U-22・U-25・I-05・I-05b）。

tokenizer（実装計画 2-5）はまだ無いので、空白で区切るだけの関数を差し込む。
"""

import sqlite3

import pytest

from db import build_db

SEEDS = """
INSERT INTO documents (id, doc_type, source, title, body, problem, background) VALUES
  (1, 'seed', 'placeholder', '整髪料 組成物', '皮膜 形成', 'べたつき 低減', '可塑化 樹脂'),
  (2, 'need', 'dummy', NULL, '髪 べたつく', NULL, NULL);
INSERT INTO projects (id, name, status) VALUES (1, '企画X', 'ongoing'), (2, '企画Y', 'cancelled');
INSERT INTO project_techs (project_id, seed_id, decision) VALUES (1, 1, 'adopted'), (2, 1, 'dropped');
INSERT INTO patents (seed_id, state) VALUES (1, 'pending');
"""


def split_tokenize(text: str) -> list[str]:
    return text.split()


@pytest.fixture
def seeds_path(tmp_path):
    path = tmp_path / "seeds.sql"
    path.write_text(SEEDS, encoding="utf-8")
    return path


@pytest.fixture
def db_path(tmp_path, seeds_path):
    path = tmp_path / "knowledge.db"
    build_db.build(path, seeds_path=seeds_path, tokenize=split_tokenize)
    return path


def fts_hits(con: sqlite3.Connection, word: str) -> list[int]:
    rows = con.execute(
        "SELECT rowid FROM documents_fts WHERE documents_fts MATCH ? ORDER BY rowid", (word,)
    )
    return [r[0] for r in rows]


def test_u13_builds_from_schema_and_seeds_when_db_missing(tmp_path, seeds_path):
    path = tmp_path / "knowledge.db"
    assert build_db.build(path, seeds_path=seeds_path, tokenize=split_tokenize) is True

    con = sqlite3.connect(path)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "documents", "projects", "project_techs", "project_products",
        "patents", "documents_fts", "embeddings", "search_logs",
    } <= tables
    assert con.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2
    assert con.execute("SELECT COUNT(*) FROM project_techs").fetchone()[0] == 2


def test_u14_keeps_existing_db(db_path, seeds_path):
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO documents (id, doc_type, source) VALUES (99, 'need', 'dummy')")
    con.commit()
    con.close()

    assert build_db.build(db_path, seeds_path=seeds_path, tokenize=split_tokenize) is False

    con = sqlite3.connect(db_path)
    assert con.execute("SELECT COUNT(*) FROM documents WHERE id = 99").fetchone()[0] == 1


def test_rebuild_discards_local_edits(db_path, seeds_path):
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO documents (id, doc_type, source) VALUES (99, 'need', 'dummy')")
    con.commit()
    con.close()

    assert build_db.build(db_path, rebuild=True, seeds_path=seeds_path, tokenize=split_tokenize)

    con = sqlite3.connect(db_path)
    assert con.execute("SELECT COUNT(*) FROM documents WHERE id = 99").fetchone()[0] == 0


def test_failed_build_leaves_no_db(tmp_path):
    broken = tmp_path / "seeds.sql"
    broken.write_text("INSERT INTO no_such_table VALUES (1);", encoding="utf-8")
    path = tmp_path / "knowledge.db"

    with pytest.raises(sqlite3.OperationalError):
        build_db.build(path, seeds_path=broken, tokenize=split_tokenize)

    assert list(tmp_path.glob("*.db")) == []


def test_u22_and_i05b_problem_and_background_are_indexed(db_path):
    con = sqlite3.connect(db_path)
    assert fts_hits(con, "べたつき") == [1]  # problem にだけある語
    assert fts_hits(con, "可塑化") == [1]    # background にだけある語
    assert fts_hits(con, "組成物") == [1]    # title
    assert fts_hits(con, "べたつく") == [2]  # body


def test_i05_insert_alone_is_not_searchable_until_reindexed(db_path):
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO documents (id, doc_type, source, problem) VALUES (3, 'seed', 'placeholder', '静電気 抑制')"
    )
    assert fts_hits(con, "静電気") == []

    build_db.index_fts(con, split_tokenize)
    assert fts_hits(con, "静電気") == [3]


def test_u25_project_techs_rejects_duplicate_pair(db_path):
    con = sqlite3.connect(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO project_techs (project_id, seed_id, decision) VALUES (1, 1, 'dropped')")


def test_adr0046_patents_seed_id_is_not_null(db_path):
    con = sqlite3.connect(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO patents (seed_id, state) VALUES (NULL, 'none')")


def test_seeds_violating_foreign_key_fail_the_build(tmp_path):
    seeds = tmp_path / "seeds.sql"
    seeds.write_text(
        "INSERT INTO patents (seed_id, state) VALUES (404, 'pending');", encoding="utf-8"
    )
    path = tmp_path / "knowledge.db"

    with pytest.raises(sqlite3.IntegrityError):
        build_db.build(path, seeds_path=seeds, tokenize=split_tokenize)
    assert not path.exists()


def test_bundled_schema_and_seeds_build(tmp_path):
    path = tmp_path / "knowledge.db"
    assert build_db.build(path, tokenize=split_tokenize) is True
