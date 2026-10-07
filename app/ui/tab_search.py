"""タブ①検索（デモの主役。F-02・F-03・F-04・F-06。仕様「タブ①検索」）。

方向はニーズ→技術に固定（`query_side='need'`。ADR-0028）。
"""

import streamlit as st

from db import repositories, search_log
from search import cross_search, highlight, hit_judge, scoring

from .cards import render_card
from .components import esc, sample_badge

LABEL = "企画案・生活者の声を、そのまま入力してください"


def render(con, mode: str, compare: bool = False) -> None:
    """`mode` はサイドバーの検索方式（cross_search.MODE_*）。`compare` は3方式の比較を出すか（F-10）。"""
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

    if compare:
        _render_comparison(con, searched)
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
        "query": query, "mode": mode, "result": result, "no_hit": no_hit, "log_id": log_id,
        "matches": matches,
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
        # ヒットなし：固定の案内文（ADR-0045）を出し、関連度の低い候補は折りたたみに入れる（#70）。
        # 画面は空にしない（要求.md 受入基準）が、無関係な文でも的外れなカードが前面に並ぶと
        # 「何を入れても何か出る」と見られるため。少し外れた企画案なら、開けば候補を見られる。
        # 「似た悩み・既存の訴求」も出さない。ヒットなしのときは悩みとして近くないうえ、
        # 「この悩みに対して打った訴求」という見出しが言い切りで、無関係な文にも付いてしまうため
        st.info("十分に一致する技術は見つかりませんでした。")   # すぐ下の折りたたみの見出しが候補の案内を兼ねる
        with st.expander(f"関連度の低い候補を見る（{len(result.hits)}件）"):
            _render_cards(con, searched, summary)
        return

    _render_cards(con, searched, summary)
    _render_same_side(con, result)


def _render_cards(con, searched: dict, summary: str) -> None:
    """件数の行と、反対側の結果カード。"""
    result = searched["result"]
    # 数字は文字色を指定せずテーマの色に従わせる（黒を直接指定するとダークモードで見えなくなる。#91）
    st.markdown(
        f"<span style='font-size:1.35em;'>{len(result.hits)}</span>"
        f"<span style='font-size:0.9em; color:gray;'> 件　（{esc(summary)}）</span>",
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


# 比較で並べる方式（表示名 → cross_search の mode）と件数
COMPARE_MODES = {
    "キーワードのみ": cross_search.MODE_BM25,
    "意味のみ": cross_search.MODE_VECTOR,
    "両方併用": cross_search.MODE_HYBRID,
}
COMPARE_TOP = 5


def _render_comparison(con, searched: dict) -> None:
    """F-10・S-09：同じ文で3方式の結果を横に並べる（デモ専用。ログには残さない）。

    3方式の検索は一致理由を計算しないので速い。結果は検索ごとに1回だけ計算して覚えておく。
    """
    if "compare" not in searched:
        searched["compare"] = {
            label: cross_search.cross_search(con, searched["query"], query_side="need", mode=m)
            for label, m in COMPARE_MODES.items()
        }
    results = searched["compare"]
    ids = {h.doc_id for r in results.values() for h in r.hits[:COMPARE_TOP]}
    titles = {i: d["title"] for i, d in repositories.get_documents(con, list(ids)).items()}

    st.divider()
    st.markdown("**🔬 3方式の比較**（同じ文で、それぞれの上位5件）")
    for col, (label, result) in zip(st.columns(3, border=True), results.items()):
        with col:
            st.markdown(f"**{label}**")
            st.caption(f"{len(result.hits)}件")
            if not result.hits:
                st.caption("0件（共通する単語がありません）")
                continue
            lines = []
            for rank, h in enumerate(result.hits[:COMPARE_TOP], start=1):
                score = scoring.score_hit(h)
                pct = f"{score.percent}%" if score.percent is not None else score.label
                lines.append(f"{rank}. {esc(titles.get(h.doc_id, '—'))}　<span style='color:gray'>{pct}</span>")
            st.markdown("<br>".join(lines), unsafe_allow_html=True)


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
