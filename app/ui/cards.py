"""検索結果カード1件分（F-03・F-05・F-08・F-16・F-19。仕様「タブ①検索」）。"""

import streamlit as st

from db import repositories
from search import scoring

from .components import FIELD_LABELS, esc, patent_text, render_ai_note, render_cells, render_plain_summary


def render_card(con, hit, doc: dict, on_detail, matches=None) -> None:
    """カード1枚。`on_detail(doc_id)` は「エビデンス・使われ方を見る」が押されたときに呼ぶ。

    `matches` は一致理由（highlight.highlight の結果）。None なら一致理由の行を出さない。
    """
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

        if matches is not None:
            st.space("small")   # 表と一致理由のあいだに1行分のすきま
            render_matches(matches)

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


METER_COLOR = "#1C83E1"   # 関連度のメーターの色（Streamlit の標準の青）


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
        # メーター。st.progress はテーマの基本色（検索ボタンと同じ赤）になるので、HTMLで青に固定する（#91）
        st.markdown(
            f"<div style='height:8px; background:rgba(49,51,63,0.1); border-radius:4px; margin-top:4px;'>"
            f"<div style='width:{score.percent}%; height:100%; background:{METER_COLOR}; border-radius:4px;'></div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.caption(score.label)


def render_matches(matches) -> None:
    """一致理由（F-18）：クエリの語句と技術文書の語句のうち、意味が近い組を並べる。

    例：「夕方」⇔「時間」。利用者が「なぜこの技術が出てきたか」を確かめられるようにする。
    語の一致ではなく意味の近さなので、的外れな組が出たら、その結果は当てにならないと判断できる。
    """
    if not matches:
        st.caption("一致理由：対応する語句は見つかりませんでした")
        return
    # unsafe_allow_html で出すので、語句は他の箇所と同じく esc() を通す（データに < や & が入っても崩れない）
    pairs = "　".join(
        f":orange-background[{_md(esc(m.query_phrase))}] ⇔ :blue-background[{_md(esc(m.doc_phrase))}]"
        for m in matches
    )
    st.markdown(f"<small>一致理由</small>　{pairs}", unsafe_allow_html=True)


def _md(text: str) -> str:
    """markdown の記号として読まれる文字を無効にする（語句に [ ] などが入っても崩れないように）。"""
    return "".join(f"\\{c}" if c in "\\[]*_`" else c for c in text)
