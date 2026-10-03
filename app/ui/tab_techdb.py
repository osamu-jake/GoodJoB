"""タブ②技術データベース（F-17。仕様「タブ②技術データベース」）。"""

from datetime import datetime

import streamlit as st

from db import repositories, search_log

from .components import patent_text

FILTERS = ("すべて", "未使用の技術", "特許 登録済", "特許 出願中", "まだ社内に無い技術")
PATENT_FILTER = {"特許 登録済": "registered", "特許 出願中": "pending"}


def render(con) -> None:
    choice = st.radio("絞り込み", FILTERS, horizontal=True)

    if choice == "まだ社内に無い技術":
        _render_gaps(con)
        return

    techs = repositories.list_techs(
        con, unused_only=(choice == "未使用の技術"), patent_state=PATENT_FILTER.get(choice)
    )
    if not techs:
        st.info("該当する技術はありません。")
        return
    for t in techs:
        project_techs = repositories.get_project_techs(con, t["id"])
        adopted = sum(1 for r in project_techs if r["decision"] == "adopted")
        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 2, 2], vertical_alignment="center")
            with c1:
                st.markdown(f"**{t['title']}**")
                st.caption(t["category"] or "—")
            with c2:
                st.caption(patent_text(repositories.get_patent(con, t["id"])))
                st.caption(f"採用実績 {adopted}件" if adopted
                           else f"採用実績なし（{repositories.tech_status_label(project_techs)}）")
            with c3:
                if st.button("詳細", key=f"open-{t['id']}", width="stretch"):
                    st.session_state.detail_id = t["id"]
                    st.rerun()


def _render_gaps(con) -> None:
    """「まだ社内に無い技術」：頻度ランキングにせず、企画案を1件ずつ並べる。部署列は出さない（ADR-0030）。"""
    st.caption("十分な関連度の技術が返らなかった企画案の一覧です。"
               "頻度ランキングにはしていません（企画案は1件ごとに文面が異なるため）。")
    rows = search_log.list_gap_queries(con)
    if not rows:
        st.info("まだ記録がありません。タブ①で検索するとここに溜まります。")
        return
    st.dataframe(
        [{"検索日時": _format_ts(r["ts"]), "最高関連度": f"{round((r['top_score'] or 0) * 100)}%", "企画案": r["query"]}
         for r in rows],
        hide_index=True, width="stretch",
    )


def _format_ts(ts: str | None) -> str:
    """ログの日時（2026-10-04T00:40:23）を画面向けに（2026-10-04 00:40）。読めなければそのまま。"""
    if not ts:
        return "—"
    try:
        return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ts
