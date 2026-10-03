"""画面（app.py ＋ ui/）の結合テスト。Streamlit の AppTest で、実際の検索・DBにつないで動かす。

I-06（ログは検索1回で1行）・I-08（詳細がタブ①②の両方から開く）・I-09（方式で件数が変わる）・
S-02b（似た悩み・既存の訴求）・S-13（タブ②の絞り込み）・S-15（権利状況）。
データは tests/seeds/test_seeds.sql、埋め込みは疑似エンコーダ（conftest.py）。
"""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from db import connection

APP = Path(__file__).resolve().parent.parent / "app.py"


@pytest.fixture
def app(con, db_path, monkeypatch):
    """テスト用DBにつないだ AppTest。`con` fixture がDBを組み立て、疑似エンコーダを差し込む。"""
    monkeypatch.setattr(connection, "DB_PATH", db_path)
    st.cache_resource.clear()  # 前のテストのDB接続を使い回さない

    def start():
        return AppTest.from_file(str(APP), default_timeout=60).run()

    return start


def _search(at, query=None, mode=None):
    if mode:
        at.sidebar.radio[0].set_value(mode).run()
    if query is not None:
        at.text_area[0].set_value(query).run()
    next(b for b in at.button if b.key == "search-btn").click().run()
    return at


def _cards(at):
    return [b for b in at.button if (b.key or "").startswith("detail-")]


def _texts(at):
    return [m.value for m in at.markdown] + [c.value for c in at.caption]


def _log_count(con):
    return con.execute("SELECT COUNT(*) FROM search_logs").fetchone()[0]


def test_app_starts_without_error(app):
    at = app()
    assert not at.exception
    assert at.title[0].value == "Idea Bridge"


def test_search_shows_cards_and_logs_once(app, con):
    """I-06：検索ボタン1回で search_logs が1行だけ増え、カードを開いても増えない。"""
    at = _search(app())
    assert not at.exception
    assert len(_cards(at)) > 0
    assert _log_count(con) == 1

    _cards(at)[0].click().run()  # カードから詳細を開く
    at.run()  # 再実行（Streamlit はボタン以外の操作でも走り直す）
    assert _log_count(con) == 1
    row = con.execute("SELECT clicked_doc_id, clicked_doc_type FROM search_logs").fetchone()
    assert row["clicked_doc_id"] == at.session_state["detail_id"]
    assert row["clicked_doc_type"] == "seed"


def test_keyword_only_zero_vs_hybrid(app):
    """I-09：同じクエリで、キーワードのみ＝0件、両方併用＝N件。"""
    query = "夕方になるとベタついてしまう"  # テスト用seedsの技術文書と共通する語が無い
    at = _search(app(), query=query, mode="キーワードのみ")
    assert not at.exception
    assert len(_cards(at)) == 0
    assert any("キーワード検索では0件" in w.value for w in at.warning)

    at.sidebar.radio[0].set_value("両方併用").run()
    assert any("検索方式を変えました" in i.value for i in at.info)  # 前の方式の結果は出さない
    _search(at)
    assert len(_cards(at)) > 0


def test_keyword_only_search_is_not_logged(app, con):
    """検索方式の切替はデモ用の比較操作なので、両方併用以外はログに残さない。"""
    _search(app(), query="夕方になるとベタついてしまう", mode="キーワードのみ")
    assert _log_count(con) == 0


def test_detail_opens_from_search_card(app):
    """I-08：タブ①のカードから詳細（モーダル）が開く。企画ごとの判断は採用・見送りの両方を出す。"""
    at = _search(app())
    next(b for b in _cards(at) if b.key == "detail-1").click().run()
    assert not at.exception
    assert at.session_state["detail_id"] == 1
    texts = _texts(at)
    assert "## 皮脂吸着性微粒子を含有する整髪料組成物" in texts
    assert any("採用：【サンプル】夕方まで崩れないワックス" in t for t in texts)
    assert any("見送り：【サンプル】ミストタイプ整髪料" in t for t in texts)
    assert any("ミストに分散させると安定性が落ちた" in t for t in texts)
    assert any("「夕方まで前髪さらさら」" in t and "サンプルデータ" in t for t in texts)  # ADR-0043
    assert any("特許第0000001号" in t for t in texts)  # S-15
    assert any(b.key == "close-detail" for b in at.button)


def test_detail_unevaluated_and_no_patent(app):
    """判断が1件も無い技術は「未評価」、特許が無ければ「登録なし」と明示する（空欄で隠さない）。"""
    at = app()
    at.session_state["detail_id"] = 3
    at.run()
    assert not at.exception
    texts = _texts(at)
    assert any("未評価" in t for t in texts)
    assert any("登録なし" in t for t in texts)
    assert any("母集団を代表しません" in t for t in texts)  # 関連する声の注記（ADR-0028）


def test_detail_opens_from_techdb_list(app):
    """I-08：タブ②の一覧からも同じ詳細が開く。"""
    at = app()
    next(b for b in at.button if b.key == "open-2").click().run()
    assert not at.exception
    assert at.session_state["detail_id"] == 2
    assert "## 水溶性ポリマーによる柔軟なセット保持" in _texts(at)
    assert any("評価中" in t for t in _texts(at))


def test_close_button_closes_detail(app):
    at = app()
    at.session_state["detail_id"] = 1
    at.run()
    next(b for b in at.button if b.key == "close-detail").click().run()
    assert at.session_state["detail_id"] is None


def _techdb_ids(at):
    return sorted(int(b.key.split("-")[1]) for b in at.button if (b.key or "").startswith("open-"))


def test_techdb_filters(app, con):
    """S-13：未使用の技術・特許ステータス・まだ社内に無い技術で絞られる。"""
    at = app()
    radio = next(r for r in at.radio if r.label == "絞り込み")
    assert _techdb_ids(at) == [1, 2, 3, 4, 5, 6]

    radio.set_value("未使用の技術").run()
    assert 1 not in _techdb_ids(at)  # 技術1は採用済み
    assert 2 in _techdb_ids(at)  # 評価中だけなら未使用

    next(r for r in at.radio if r.label == "絞り込み").set_value("特許 登録済").run()
    assert _techdb_ids(at) == [1]
    next(r for r in at.radio if r.label == "絞り込み").set_value("特許 出願中").run()
    assert _techdb_ids(at) == [2]

    from db import search_log
    search_log.log_search(con, "朝までカールが落ちない", hit_count=0, top_score=0.41)
    next(r for r in at.radio if r.label == "絞り込み").set_value("まだ社内に無い技術").run()
    assert not at.exception
    df = at.dataframe[0].value
    assert list(df["企画案"]) == ["朝までカールが落ちない"]
    assert "T" not in df["検索日時"][0]  # 画面向けの書き方（2026-10-04 00:40）


def test_same_side_and_claims(app):
    """S-02b：折りたたみに①似た悩み（最大3件）と②既存の訴求（同じ訴求は1回だけ）。"""
    at = _search(app())
    assert any(e.label == "似た悩み・既存の訴求" for e in at.expander)
    texts = _texts(at)
    # 技術1（採用済み）は必ずヒットする（テスト用の技術は6件で、上位10件に全部入る）。
    # 訴求はちょうど1回だけ出て、サンプルデータの印が付く（ADR-0039・0043）
    claims = [t for t in texts if t.startswith("**「夕方まで前髪さらさら」**")]
    assert len(claims) == 1
    assert "サンプルデータ" in claims[0]
    heading = next(t for t in texts if t.startswith("**① 似た悩み"))
    n = int(heading.split("（")[1].split("件")[0])
    assert n <= 3


def test_shows_guidance_when_no_data(tmp_path, monkeypatch):
    """実データ（fixtures/seeds.sql）がまだ無いときは、落ちずに案内を出す（2-1a 前の状態）。"""
    from db import build_db

    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "none.db")
    monkeypatch.setattr(build_db, "SEEDS_PATH", tmp_path / "none.sql")
    st.cache_resource.clear()
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert any("データがまだありません" in e.value for e in at.error)


def test_dismissing_detail_clears_it():
    """✕・Esc・外側クリックで閉じたら、開いている技術の記録を消す（次の操作でまた開かない）。"""
    from streamlit.testing.v1 import AppTest as _AppTest

    def script():
        import streamlit as st
        from ui.detail import _on_dismiss
        st.session_state.setdefault("detail_id", 1)
        if st.button("dismiss"):  # ブラウザでの「閉じる操作」の代わりに、登録した処理を直接呼ぶ
            _on_dismiss()
        st.write(f"detail_id={st.session_state.detail_id}")

    at = _AppTest.from_function(script).run()
    at.button[0].click().run()
    assert at.session_state["detail_id"] is None


def test_cards_show_match_reasons(app):
    """S-03・S-14：結果カードに一致理由（クエリの語句 ⇔ 技術文書の語句）が出る。

    表示する結果（上位10件まで）すべてについて、検索のときに1回だけ計算する（ADR-0018）。
    """
    at = _search(app())
    assert not at.exception
    n_cards = len(_cards(at))
    reasons = [m.value for m in at.markdown if m.value.startswith("<small>一致理由</small>")]
    assert n_cards > 0
    assert len(reasons) == n_cards
    assert all("⇔" in r for r in reasons)
    # 検索のときに計算して覚えておくので、画面が描き直されても計算し直さない
    assert set(at.session_state["search"]["matches"]) == {
        h.doc_id for h in at.session_state["search"]["result"].hits
    }
