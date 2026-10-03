"""検索結果カード1件分（F-03・F-05・F-08・F-16・F-19。仕様「タブ①検索」）。"""

import streamlit as st

from db import repositories
from search import scoring

from .components import FIELD_LABELS, patent_text, render_ai_note, render_cells, render_plain_summary


def render_card(con, hit, doc: dict, on_detail) -> None:
    """カード1枚。`on_detail(doc_id)` は「エビデンス・使われ方を見る」が押されたときに呼ぶ。"""
    score = scoring.score_hit(hit)
    # key を付けると、この箱に「st-key-card-○○」という目印が付く（余白の指定は app.py の CSS）
    with st.container(border=True, key=f"card-{doc['id']}"):
        head, right = st.columns([5, 1])
        with head:
            st.markdown(f"##### {doc['title']}", anchors=False)
            st.badge("シーズ（技術）" if doc["doc_type"] == "seed" else "ニーズ（生活者の声）")
        with right:
            render_score(score)

        # 権利状況・採用実績・一致箇所（F-19・F-08）
        project_techs = repositories.get_project_techs(con, doc["id"])
        adopted = sum(1 for r in project_techs if r["decision"] == "adopted")
        render_cells([
            ("特許", patent_text(repositories.get_patent(con, doc["id"]))),
            ("採用実績", f"{adopted}件" if adopted else "なし"),
            ("一致箇所", FIELD_LABELS.get(hit.matched_field, "—") if not score.keyword_only else "語一致"),
        ])

        st.space("small")
        st.markdown("**この技術が解決しようとしている課題**")
        st.write(doc["problem"] or "—")
        if doc["summary_plain"]:
            render_plain_summary(doc["summary_plain"])
            render_ai_note()

        st.space("small")
        if st.button("エビデンス・使われ方を見る", key=f"detail-{doc['id']}", width="stretch",
                     icon=":material/description:"):
            on_detail(doc["id"])


def render_score(score) -> None:
    """関連度（コサイン類似度の百分率。ADR-0010・0035）。語一致だけのときは数値を出さない。"""
    with st.container(gap=None):   # 数値とメーターをくっつける
        st.caption("関連度")
        if score.keyword_only:
            st.markdown("**語一致**")   # キーワードだけで当たった文書は % を出さない（F-14）
            return
        # st.metric は文字サイズを変えられないので、数字と「%」を別サイズで書く
        st.markdown(
            f"<span style='font-size:1.75rem; font-weight:600; line-height:1.2'>{score.percent}</span>"
            f"<span style='font-size:1rem; font-weight:600; margin-left:2px'>%</span>",
            unsafe_allow_html=True,
        )
        st.progress(score.percent / 100)
    st.caption(score.label)
