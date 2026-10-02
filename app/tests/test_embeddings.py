"""db/build_db.py の埋め込み計算のテスト（U-15）と、DBに入れる形の確認。"""

import numpy as np

from db import build_db
from search import vector


def fields_of(con, doc_id):
    rows = con.execute("SELECT field FROM embeddings WHERE doc_id = ? ORDER BY field", (doc_id,)).fetchall()
    return [r["field"] for r in rows]


def test_u15_要約_課題_背景が揃った文書は3行できる(con):
    """U-15: 要約・課題・背景が揃った文書1件 → embeddings に3行作られる。"""
    assert fields_of(con, 1) == ["background", "body", "problem"]


def test_u15_titleは埋め込まない(con):
    """U-15: titleは埋め込まない（ADR-0021）。"""
    fields = {r["field"] for r in con.execute("SELECT DISTINCT field FROM embeddings")}
    assert "title" not in fields
    assert fields <= {"body", "problem", "background"}


def test_空のフィールドは行を作らない(con):
    # 文書6は background が NULL、ニーズ文書11は body だけ
    assert fields_of(con, 6) == ["body", "problem"]
    assert fields_of(con, 11) == ["body"]


def test_全文書に少なくとも1行ある(con):
    n_docs = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    n_with = con.execute("SELECT COUNT(DISTINCT doc_id) FROM embeddings").fetchone()[0]
    assert n_with == n_docs


def test_保存されたベクトルはfloat32の正規化済み(con):
    blob = con.execute("SELECT vec FROM embeddings WHERE doc_id = 1 AND field = 'problem'").fetchone()[0]
    vec = vector.from_blob(blob)

    assert vec.dtype == np.float32
    assert vec.shape == (384,)
    assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-5


def test_再構築しても同じ行数になる(db_path, fake_encoder):
    from .conftest import TEST_SEEDS

    con = build_db.build(db_path, seeds_path=TEST_SEEDS)
    first = build_db.table_counts(con)["embeddings"]
    con.close()

    con = build_db.build(db_path, force=True, seeds_path=TEST_SEEDS)
    assert build_db.table_counts(con)["embeddings"] == first


def test_文書側のテキストにはpassageプレフィックスが付いて計算される(db_path, monkeypatch):
    from .conftest import TEST_SEEDS
    from .fake_encoder import fake_encode

    seen = []

    def spy(texts):
        seen.extend(texts)
        return fake_encode(texts)

    monkeypatch.setattr(vector, "_encode", spy)
    build_db.build(db_path, seeds_path=TEST_SEEDS).close()

    assert seen and all(t.startswith("passage: ") for t in seen)
