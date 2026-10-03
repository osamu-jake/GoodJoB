"""実モデル（multilingual-e5-small）で、意味の近さが検索に効いていることを確認する。

疑似エンコーダでは確かめられない「言い換えでも引ける」を見るテスト。モデルの読み込みに時間がかかるため
`model` マークを付け、DBはセッションで1回だけ組み立てる。モデルを取得できない環境ではスキップする。
"""

import pytest

from db import build_db
from search import cross_search

from .conftest import TEST_SEEDS

pytestmark = pytest.mark.model


@pytest.fixture(scope="session")
def semantic_con(tmp_path_factory):
    path = tmp_path_factory.mktemp("semantic") / "knowledge.db"
    try:
        con = build_db.build(path, seeds_path=TEST_SEEDS)
    except Exception as e:  # モデルを取得できない環境（オフライン・証明書など）
        pytest.skip(f"モデルを読み込めない: {type(e).__name__}")
    yield con
    con.close()


@pytest.mark.parametrize(
    "query, expected_seed",
    [
        ("夕方になると前髪がベタついて束になる", 1),  # 「皮脂で毛先が固まる」課題と意味が近い
        ("汗をかくと日焼け止めが流れて効果が続かない", 3),
        ("朝つけた香りが昼には消えてしまう", 6),
        ("冬は肌がカサカサして粉をふく", 4),
    ],
)
def test_言い換えでも意味の近い技術が1位に来る(semantic_con, query, expected_seed):
    hits = cross_search.cross_search(semantic_con, query, same_side_k=0).hits

    assert hits[0].doc_id == expected_seed
    assert hits[0].similarity > hits[1].similarity


def test_無関係な文は関連のある文より最高類似度が低い(semantic_con):
    related = cross_search.cross_search(semantic_con, "夕方になると前髪がベタついて束になる", same_side_k=0)
    unrelated = cross_search.cross_search(semantic_con, "確定申告の書類の書き方が分からない", same_side_k=0)

    assert unrelated.top_similarity < related.top_similarity


def test_同じ側の検索では似た悩みが返る(semantic_con):
    result = cross_search.cross_search(semantic_con, "夕方になると前髪がベタついて束になる", same_side_k=3)

    assert result.same_side_hits and result.same_side_hits[0].doc_id == 11  # 夕方の前髪のべたつき


def test_ハイブリッドの表示順は関連度の降順(semantic_con):
    hits = cross_search.cross_search(semantic_con, "夕方になると前髪がベタついて束になる", same_side_k=0).hits
    sims = [h.similarity for h in hits]
    assert sims == sorted(sims, reverse=True)


def test_ハイライトは実モデルで文書側の実在する語句を返す(semantic_con):
    from search import highlight

    query = "夕方になると前髪がベタついて束になる"
    matches = highlight.highlight(semantic_con, query, doc_id=1, top_n=3)
    text_of = {
        f: semantic_con.execute(f"SELECT {f} FROM documents WHERE id = 1").fetchone()[0]
        for f in ("problem", "body", "background")
    }

    assert 1 <= len(matches) <= 3
    assert [m.similarity for m in matches] == sorted((m.similarity for m in matches), reverse=True)
    for m in matches:
        assert m.spans, m  # 原文中の位置が取れている
        assert all(text_of[m.field][s:e] for s, e in m.spans)
    print("\nハイライトのペア:", [(m.query_phrase, m.doc_phrase, round(m.similarity, 3)) for m in matches])
