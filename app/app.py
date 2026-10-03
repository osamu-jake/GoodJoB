"""Idea Bridge（知の越境検索）— PoC のエントリーポイント。

画面はタブ2つ（①検索／②技術データベース。ADR-0017）。技術の詳細はモーダルで開き、
タブ①②で同じ部品を使う（ui/detail.py。ADR-0032・0034）。

起動（リポジトリ直下から）: app/.venv/bin/streamlit run app/app.py
"""

import streamlit as st

from db import build_db, connection
from search import cross_search, vector
from ui import tab_search, tab_techdb
from ui.detail import show_detail

st.set_page_config(page_title="Idea Bridge", page_icon="🔎", layout="wide")

# 見た目の調整（<style> だけの st.html は画面に場所を取らない）
st.html("""
<style>
/* 結果カード（key が "card-" で始まる箱）の内側の余白を広げる */
[class*="st-key-card-"] { padding: 1.5rem !important; }

/* 「エビデンス・使われ方を見る」（key が "detail-" で始まるボタン）と「閉じる」を紺の塗りつぶしに */
[class*="st-key-detail-"] button, .st-key-close-detail button {
  background:#1F3864; color:#fff; border:1px solid #1F3864;
}
[class*="st-key-detail-"] button:hover, .st-key-close-detail button:hover {
  background:#2B4C85; color:#fff; border-color:#2B4C85;
}

/* 検索ボタンの高さを入力欄（height=80）にそろえる */
.st-key-search-btn button { height: 80px; }
</style>
""")

# デモ用の入力例（ADR-0026：①短文＝キーワード0件、②長文＝キーワードだと順位が崩れる）。
# 文面は 2-13（check_gap で実データを実測）の結果に合わせて差し替える
DEMO_QUERIES = {
    "①生活者の声（短文）": "ワックスをつけた髪が、夕方になるとベタついて束になってしまいます。",
    "②企画案（長文）": ("夕方になると前髪がベタついて束になる、という20〜30代男性の不満に応えたい。"
                        "朝のセットが夜まで崩れず、それでいて重くならない整髪料を企画したい。"),
}

# 検索方式（F-06・F-10）。表示名 → (cross_search の mode, 説明)
MODES = {
    "キーワードのみ": (cross_search.MODE_BM25, "共通する単語が無いと0件になります。"),
    "意味のみ": (cross_search.MODE_VECTOR, "意味では引けますが、成分名などの固有名詞に弱く順位が安定しません。"),
    "両方併用": (cross_search.MODE_HYBRID, "キーワードと意味の両方を使い、RRF で統合した結果です。"),
}


@st.cache_resource(show_spinner="データベースを準備しています…")
def get_connection():
    """.db が無ければ schema.sql と fixtures/seeds.sql から組み立てて接続する（ADR-0015・0025）。"""
    return build_db.build(connection.DB_PATH)


@st.cache_resource(show_spinner="AIモデルを準備しています…（起動時に1回だけ。十数秒かかります）")
def warm_up_model() -> bool:
    """埋め込みモデルを起動時に読み込んでおく。

    読み込みは最初の1回に十数秒かかる。先に済ませておかないと、最初の検索ボタンで画面が固まる
    （発表のデモで1回目の検索が止まって見える）。
    """
    vector.encode_query("準備")
    return True


def main() -> None:
    if not connection.DB_PATH.exists() and not build_db.SEEDS_PATH.exists():
        st.error("データがまだありません（`app/fixtures/seeds.sql` が未作成。実装計画 2-1a）。")
        st.markdown("テスト用データで動かすときは、リポジトリ直下で次を実行してください。")
        st.code(
            "cd app && KNOWLEDGE_DB=/tmp/knowledge_test.db .venv/bin/python -c \"from pathlib import Path; "
            "from db import build_db, connection; "
            "build_db.build(connection.DB_PATH, seeds_path=Path('tests/seeds/test_seeds.sql'))\"\n"
            "KNOWLEDGE_DB=/tmp/knowledge_test.db .venv/bin/streamlit run app.py",
            language="bash",
        )
        st.stop()
    con = get_connection()
    warm_up_model()

    st.session_state.setdefault("query", DEMO_QUERIES["①生活者の声（短文）"])
    st.session_state.setdefault("search", None)      # 直近の検索結果（方式・結果・ログID）
    st.session_state.setdefault("detail_id", None)   # 詳細を開いている技術の id

    with st.sidebar:
        st.subheader("デモ用")
        st.caption("入力例（ADR-0026）。押すと検索窓に入ります。")
        for label, text in DEMO_QUERIES.items():
            if st.button(label, width="stretch"):
                st.session_state.query = text
                st.session_state.search = None
                st.rerun()
        st.divider()
        st.caption("🔬 仕組みの比較（通常の画面には出しません）")
        mode_label = st.radio("検索方式", list(MODES), index=2, label_visibility="collapsed")
        mode, note = MODES[mode_label]
        st.caption(note)

    st.title("Idea Bridge")
    st.caption("マーケ／商品企画の担当者が、企画案の言葉のまま社内技術を探す")

    search_tab, techdb_tab = st.tabs([" 🔎 検索 ", " 📚 技術データベース "])
    with search_tab:
        st.container(height=30, border=False)
        tab_search.render(con, mode)
    with techdb_tab:
        st.container(height=30, border=False)
        tab_techdb.render(con)

    # 詳細はモーダルで開く。タブ①②のどちらからでも同じものを使う
    if st.session_state.detail_id:
        show_detail(con, st.session_state.detail_id)

    st.divider()
    st.caption("PoC版。企画・採用実績・判断の記録は「サンプルデータ」と表示したものが架空データです。"
               "このアプリは実現可否を判定しません。判断材料を提示するところまでを担います。")


main()
