"""タブ①検索（デモの主役。F-02・F-03・F-04・F-06。仕様「タブ①検索」）。

方向はニーズ→技術に固定（`query_side='need'`。ADR-0028）。
"""

import streamlit as st

from db import repositories, search_log
from search import cross_search, highlight, hit_judge, scoring

from .cards import render_card
from .components import esc, sample_badge

LABEL = "企画案・生活者の声を、そのまま入力してください"


def render(con, mode: str) -> None:
    """`mode` はサイドバーの検索方式（cross_search.MODE_*）。"""
    # text_area の height は「見出し＋入力欄」の合計なので、見出しを外に出して入力欄だけを80pxにする
    st.markdown(LABEL, help="検索語ではなく文章を入れてください。")
    col_text, col_btn = st.columns([5, 1], vertical_alignment="bottom")
    with col_text:
        query = st.text_area(LABEL, value=st.session_state.query, height=80,
                             label_visibility="collapsed")
    with col_btn:
        # 高さは CSS で80px（app.py の <style>）。st.button には高さの指定がないため
        clicked = st.button("検索", type="primary", width="stretch", key="search-btn")

    if clicked:
        _run_search(con, query, mode)

    searched = st.session_state.search
    if searched is None:
        return
    # 方式を変えたら前の結果を捨てる。結果を残したまま表示だけ切り替えると、
    # 「キーワードのみ」にしても前の方式の結果が出て、0件→N件のデモが成立しない（I-09）
    if searched["mode"] != mode:
        st.session_state.search = None
        st.info("検索方式を変えました。もう一度「検索」を押してください。")
        return

    _render_result(con, searched)


def _run_search(con, query: str, mode: str) -> None:
    """検索してセッションに保存する。ログはこのボタンのブロック内でだけ記録する（I-06）。"""
    st.session_state.query = query
    result = cross_search.cross_search(con, query, query_side="need", mode=mode)
    no_hit = hit_judge.judge(result)
    log_id = None
    # ログは通常の検索（両方併用）だけ残す。検索方式の切替はデモ用の比較操作で、
    # 「キーワードのみ＝0件」を「まだ社内に無い技術」に数えると空白領域の一覧が汚れるため
    if mode == cross_search.MODE_HYBRID:
        log_id = search_log.log_search(
            con, query, hit_count=0 if no_hit else len(result.hits), top_score=result.top_similarity
        )
    # 一致理由（F-18）は、表示する結果（上位10件まで）について検索のときに1回だけ計算する
    # （語句のベクトルは事前に保存しない。ADR-0018）。ここで覚えておけば、カードの開閉などで
    # 画面が描き直されても計算し直さない。遅すぎる場合の撤退ラインは「上位3件に絞る」（同ADR）
    matches = {h.doc_id: highlight.highlight(con, query, h.doc_id) for h in result.hits}
    st.session_state.search = {
        "mode": mode, "result": result, "no_hit": no_hit, "log_id": log_id, "matches": matches,
    }


def _render_result(con, searched: dict) -> None:
    result, mode = searched["result"], searched["mode"]
    st.divider()
    vector_count = sum(1 for h in result.hits if h.similarity is not None)
    summary = f"キーワード検索 {result.bm25_count}件／意味検索 {vector_count}件"

    if mode == cross_search.MODE_BM25 and not result.hits:
        st.warning("キーワード検索では0件でした。生活者の言葉と技術文書の言葉が"
                   "一致しないためです。検索方式を「両方併用」に切り替えてください。")
        st.caption(summary)
        return
    if searched["no_hit"]:
        # 候補はゼロにしない。関連度の低い「応用できるかもしれない候補」は出し続ける（ADR-0008）
        # 案内は固定文だけ（ADR-0045）。「まだ社内に無い技術」への記録は裏側で行い、画面には出さない
        st.info("十分に一致する技術は見つかりませんでした")

    st.markdown(
        f"<span style='font-size:0.9em; color:gray;'>"
        f"<span style='font-size:1.5em; color:black;'>{len(result.hits)}</span> 件　（{esc(summary)}）"
        f"</span>",
        unsafe_allow_html=True,
    )

    docs = repositories.get_documents(con, [h.doc_id for h in result.hits])

    def open_detail(doc_id: int) -> None:
        if searched["log_id"] is not None:   # この検索のどの結果を開いたかを記録する
            search_log.log_click(con, searched["log_id"], doc_id, "seed")
        st.session_state.detail_id = doc_id
        st.rerun()

    for hit in result.hits:
        if hit.doc_id in docs:
            render_card(con, hit, docs[hit.doc_id], on_detail=open_detail,
                        matches=searched["matches"].get(hit.doc_id))

    _render_same_side(con, result)


def _render_same_side(con, result) -> None:
    """①似た悩み＋②既存の訴求（ADR-0024・0031・0039）。反対側の結果とは別枠で出す。"""
    st.divider()
    with st.expander("似た悩み・既存の訴求"):
        st.caption("同じ悩みが社内にすでに集まっているか、そしてその悩みに対して"
                   "自社がもう何と言って答えているかです。")

        same = result.same_side_hits
        st.markdown(f"**① 似た悩み（{len(same)}件）**")
        needs = repositories.get_documents(con, [h.doc_id for h in same])
        for h in same:
            d = needs.get(h.doc_id)
            if d is None:
                continue
            score = scoring.score_hit(h)
            with st.container(border=True):
                st.markdown(f"**{d['title']}**")
                st.caption(f"関連度 {score.percent}%" if score.percent is not None else score.label)
                st.markdown(f"> {d['body'] or d['title']}")

        st.space("small")
        st.markdown("**② この悩みに対して自社が既に打った訴求**")
        seed_ids = [h.doc_id for h in result.hits]
        claims = repositories.get_claims_for(con, seed_ids)   # 同じ商品・訴求は1回だけ
        if not claims:
            st.info("今回ヒットした技術に採用実績はありません。この訴求はまだ打っていません。")
            return
        # どの技術で採用されたかを出すため、技術ごとの訴求から逆引きする
        used_by: dict[int, list[int]] = {}
        for sid in seed_ids:
            for c in repositories.get_claims(con, sid):
                used_by.setdefault(c["product_id"], []).append(sid)
        titles = {i: d["title"] for i, d in repositories.get_documents(con, seed_ids).items()}
        for c in claims:
            with st.container(border=True):
                st.markdown(f"**「{c['claim']}」**{sample_badge(c['is_sample'])}")
                st.caption(f"{c['brand'] or ''} {c['product'] or ''}／{c['launched'] or '—'}")
                techs = "、".join(titles[s] for s in used_by.get(c["product_id"], []) if s in titles)
                if techs:
                    st.caption(f"使った技術：{techs}")
