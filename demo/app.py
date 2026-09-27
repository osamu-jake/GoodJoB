"""知の越境検索 — PoC（PROJECT ZERO / W6）

技術シーズと生活者ニーズを横断検索する。
画面はタブ2つ（①検索／②技術データベース）。ADR-0017。
"""

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import streamlit as st  # noqa: E402

from db import build_db  # noqa: E402
from ui import tab_search, tab_techdb  # noqa: E402

st.set_page_config(page_title="知の越境検索", page_icon="🔎", layout="wide")


@st.cache_resource(show_spinner="データベースを準備しています…")
def get_connection():
    # .dbが無ければschema.sqlとfixtures/から自動構築する（ADR-0015）
    return build_db.build()


def main() -> None:
    con = get_connection()

    # 利用者はマーケ／商品企画の1種類だけ。立場の選択UIは作らない（ADR-0030）。
    # search_logs.user_dept は 'MK' 固定で入れる（本番で部門が増えたときに使う列）。
    st.session_state.setdefault("stance", "MK")
    st.session_state.setdefault("detail_id", None)

    st.title("知の越境検索")
    st.caption("マーケ／商品企画の担当者が、企画案の言葉のまま社内技術を探す")

    if st.session_state.pop("goto_techdb", False):
        st.toast("技術データベースのタブを開いてください")

    search_tab, techdb_tab = st.tabs(["🔎 検索", "📚 技術データベース"])
    with search_tab:
        tab_search.render(con)
    with techdb_tab:
        tab_techdb.render(con)

    st.divider()
    st.caption(
        "PoC版。シーズはプレースホルダ（本番はJ-PlatPatから転記した実特許）、"
        "ニーズ・採用実績・評価記録はサンプルデータです。"
        "このアプリは実現可否を判定しません。判断材料を提示するところまでを担います。"
    )


if __name__ == "__main__":
    main()
