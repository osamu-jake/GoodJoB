"""tools/export_seeds.py のテスト（U-26）。書き出し→--rebuild で番号の対応が変わらないこと。"""

from db import build_db
from tools import export_seeds

from .conftest import TEST_SEEDS


def snapshot(con):
    """再構築の前後で比べる、番号に依存する中身。"""
    return {
        "documents": con.execute(
            "SELECT id, doc_type, source, title, body, background, problem, summary_plain FROM documents ORDER BY id"
        ).fetchall(),
        "project_techs": con.execute(
            "SELECT id, project_id, seed_id, decision, reason, detail, decided_at FROM project_techs ORDER BY id"
        ).fetchall(),
        "project_products": con.execute("SELECT * FROM project_products ORDER BY id").fetchall(),
        "projects": con.execute("SELECT * FROM projects ORDER BY id").fetchall(),
        "patents": con.execute("SELECT * FROM patents ORDER BY id").fetchall(),
    }


def as_tuples(snap):
    return {name: [tuple(r) for r in rows] for name, rows in snap.items()}


def test_u26_書き出して再構築しても番号と対応が変わらない(db_path, tmp_path):
    """U-26: 書き出し → `--rebuild` で再構築 → documents.id と project_techs の対応が前後で変わらない。"""
    con = build_db.build(db_path, seeds_path=TEST_SEEDS)
    # 番号が飛んでいる状態にする（途中の文書を消すと、id を明示しないと詰め直されて対応が崩れる）
    con.execute("DELETE FROM documents WHERE id = 14")
    # 手入力で足した行（引用符・改行・NULLを含む）
    con.execute(
        "INSERT INTO documents (id, doc_type, source, title, body) VALUES (30, 'seed', 'placeholder', 'it''s 引用符', '1行目\n2行目')"
    )
    con.execute("INSERT INTO project_techs (project_id, seed_id, decision, reason) VALUES (2, 30, 'evaluating', NULL)")
    con.commit()
    before = as_tuples(snapshot(con))
    con.close()

    out = tmp_path / "seeds.sql"
    export_seeds.export_seeds(db_path, out)
    con = build_db.build(db_path, force=True, seeds_path=out)

    assert as_tuples(snapshot(con)) == before
    # 技術30を指す判断が、番号30のまま残っている
    assert con.execute("SELECT title FROM documents WHERE id = 30").fetchone()[0] == "it's 引用符"
    assert con.execute("SELECT COUNT(*) FROM project_techs WHERE seed_id = 30").fetchone()[0] == 1


def test_書き出しはidを明示し_参照先のテーブルから順に並ぶ(db_path, tmp_path):
    build_db.build(db_path, seeds_path=TEST_SEEDS).close()
    out = tmp_path / "seeds.sql"

    counts = export_seeds.export_seeds(db_path, out)

    text = out.read_text(encoding="utf-8")
    assert counts == {"documents": 10, "projects": 2, "project_techs": 3, "project_products": 1, "patents": 2}
    assert "INSERT INTO documents (id, doc_type," in text
    positions = [text.index(f"INSERT INTO {t} ") for t in
                 ("documents", "projects", "project_techs", "project_products", "patents")]
    assert positions == sorted(positions)


def test_embeddingsとsearch_logsは書き出さない(db_path, tmp_path):
    con = build_db.build(db_path, seeds_path=TEST_SEEDS)
    con.execute("INSERT INTO search_logs (query, user_dept, hit_count) VALUES ('テスト', 'MK', 0)")
    con.commit()
    con.close()
    out = tmp_path / "seeds.sql"

    export_seeds.export_seeds(db_path, out)

    text = out.read_text(encoding="utf-8")
    assert "INSERT INTO search_logs" not in text
    assert "INSERT INTO embeddings" not in text


def test_改行はLFで書き出される(db_path, tmp_path):
    build_db.build(db_path, seeds_path=TEST_SEEDS).close()
    out = tmp_path / "seeds.sql"
    export_seeds.export_seeds(db_path, out)
    assert b"\r\n" not in out.read_bytes()


def test_書き出し先の既定は_build_dbが読む場所と同じ(tmp_path):
    """書き出した seeds.sql を、起動時にそのまま読み込める（置き場所は app/fixtures/seeds.sql）。"""
    assert export_seeds.DEFAULT_OUT == build_db.SEEDS_PATH
    assert export_seeds.DEFAULT_OUT.parent.parent.name == "app"
