"""search/bm25.py のテスト（U-04だけは実データ `fixtures/seeds.sql` を使う）。"""

import pytest

from db import build_db
from search import bm25

# デモ用の短文（実在FAQ id=78・20字）。2-13（#38）で実データを実測して確定した（evidence/2-13_check_gap.txt）
DEMO_SHORT_QUERY = "シャンプーしてもヘアワックスが落ちない。"


@pytest.fixture
def demo_con(db_path, fake_encoder):
    """実データのseedsから組み立てたDB。BM25しか見ないので埋め込みは疑似エンコーダでよい。"""
    if not build_db.SEEDS_PATH.exists():
        pytest.skip("fixtures/seeds.sql がまだ無い")
    connection = build_db.build(db_path, seeds_path=build_db.SEEDS_PATH)
    yield connection
    connection.close()


def test_u04_デモ用ニーズ文でBM25が0件になる(demo_con):
    """U-04（境界値）: デモ用ニーズ文（短文）でBM25が0件になる（N-06）。

    デモ成立の必須条件なので、他のテストと違って実データに期待値を置く。
    転記で短文に一致する語が入ってしまった（＝0件でなくなった）ら、ここで気づけるようにする。
    """
    assert bm25.search(demo_con, DEMO_SHORT_QUERY, doc_type="seed") == []


def test_指定したdoc_typeだけが返る(con):
    # 「香り」はニーズ13（朝つけた香りが…）にも、シーズ6（香りが数時間で…）にもある
    seed_ids = {h.doc_id for h in bm25.search(con, "香りが消える", doc_type="seed")}
    need_ids = {h.doc_id for h in bm25.search(con, "香りが消える", doc_type="need")}

    assert 6 in seed_ids and 13 not in seed_ids
    assert 13 in need_ids and 6 not in need_ids


def test_一致する語が無ければ0件(con):
    assert bm25.search(con, "確定申告の書類", doc_type="seed") == []


def test_空のクエリや助詞だけのクエリは0件(con):
    assert bm25.search(con, "", doc_type="seed") == []
    assert bm25.search(con, "は、が。", doc_type="seed") == []


def test_語が多く一致する文書ほど上に来る(con):
    hits = bm25.search(con, "皮脂を吸着して前髪の毛先が固まらないようにする", doc_type="seed")

    assert hits[0].doc_id == 1
    assert hits[0].score > 0
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)


def test_上位k件に絞られる(con):
    assert len(bm25.search(con, "髪 肌 香り 皮膜 日焼け止め", doc_type="seed", k=2)) == 2


def test_スニペットは原文から切り出され_一致語が入る(con):
    hit = bm25.search(con, "毛先が固まる", doc_type="seed")[0]

    assert hit.doc_id == 1
    assert "毛先" in hit.snippet
    assert "固まり" in hit.matched_terms  # 「固まる」は原文の表記（活用形）で返る


def test_スニペット無しも選べる(con):
    hit = bm25.search(con, "毛先が固まる", doc_type="seed", with_snippet=False)[0]
    assert hit.snippet is None and hit.matched_terms == []


def test_problemやbackgroundだけにある語でも引ける(con):
    """I-05b: 4列すべてが索引される（背景だけにある語でヒットする）。"""
    assert [h.doc_id for h in bm25.search(con, "触る", doc_type="seed")] == [2]
