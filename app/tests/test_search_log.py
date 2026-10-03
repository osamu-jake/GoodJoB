"""db/search_log.py（F-04・F-17。U-16）。"""

from db import repositories, search_log


def _count(con) -> int:
    return con.execute("SELECT COUNT(*) FROM search_logs").fetchone()[0]


def test_log_search_inserts_exactly_one_row(con):
    """U-16：検索1回分の引数で、search_logs に1行だけINSERTされる。"""
    before = _count(con)
    log_id = search_log.log_search(con, "夕方の前髪がべたつく", hit_count=3, top_score=0.87)
    assert _count(con) == before + 1
    row = dict(con.execute("SELECT * FROM search_logs WHERE id = ?", (log_id,)).fetchone())
    assert row["query"] == "夕方の前髪がべたつく"
    assert row["hit_count"] == 3
    assert row["top_score"] == 0.87
    assert row["user_dept"] == "MK"  # 利用者は1種類（ADR-0030）
    assert row["mode"] == "cross"
    assert row["clicked_doc_id"] is None


def test_log_click_updates_the_given_search_only(con):
    """クリックは「最後の行」ではなく、指定した検索の行に記録する（同時利用で混線しない）。"""
    first = search_log.log_search(con, "検索A", hit_count=1, top_score=0.9)
    second = search_log.log_search(con, "検索B", hit_count=1, top_score=0.9)
    search_log.log_click(con, first, doc_id=1, doc_type="seed")
    rows = {r["id"]: dict(r) for r in con.execute("SELECT * FROM search_logs")}
    assert rows[first]["clicked_doc_id"] == 1
    assert rows[first]["clicked_doc_type"] == "seed"
    assert rows[second]["clicked_doc_id"] is None
    assert _count(con) == 2  # クリックで行は増えない


def test_list_gap_queries_returns_only_no_hit_newest_first(con):
    """「まだ社内に無い技術」：hit_count=0 の検索だけを新しい順に返す（頻度で集計しない）。"""
    search_log.log_search(con, "当たった検索", hit_count=5, top_score=0.9)
    old = search_log.log_search(con, "古い空白", hit_count=0, top_score=0.41)
    new = search_log.log_search(con, "新しい空白", hit_count=0, top_score=0.38)
    search_log.log_search(con, "新しい空白", hit_count=0, top_score=0.38)  # 同じ文面も別の1件

    rows = search_log.list_gap_queries(con)
    assert [r["query"] for r in rows] == ["新しい空白", "新しい空白", "古い空白"]
    assert rows[1]["id"] == new and rows[2]["id"] == old
    assert set(rows[0]) == {"id", "ts", "query", "top_score"}


def test_get_documents_returns_rows_by_id(con):
    """文書本体を id で引く。見つからない id は含めない。"""
    docs = repositories.get_documents(con, [1, 11, 999])
    assert set(docs) == {1, 11}
    assert docs[1]["doc_type"] == "seed"
    assert docs[1]["problem"].startswith("時間の経過とともに")
    assert docs[11]["doc_type"] == "need"
    assert repositories.get_documents(con, []) == {}
