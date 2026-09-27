"""タブ①検索（デモの主役）。

企画案の文章をそのまま入力すると、語彙の違う社内技術が返る。
検索方式トグルはデモ専用で、控えめな帯に置く（仕様「画面・操作」）。
"""

import streamlit as st

from db import repositories, search_log
from search import cross_search, rephrase
from ui import cards

MODE_LABELS = {
    "キーワードのみ": cross_search.MODE_KEYWORD,
    "意味のみ": cross_search.MODE_VECTOR,
    "両方併用": cross_search.MODE_HYBRID,
}
# デモの台本は2本立て（ADR-0026）。本番で長文を打ち直すのは事故のもとなのでボタンにする。
#   ①短文 … キーワード0件 → 両方併用でN件。「語彙の断絶」そのものを見せる
#   ②長文 … キーワードでも数件返るが1位が無関係。「順位が壊れる」ほうを見せる
# 実特許に差し替えたら check_gap.py を流し直し、ここの文面も実測に合わせて置き換える。
DEMO_QUERIES = {
    "①生活者の声（短文）": "ワックスをつけた髪が、夕方になるとベタついて束になってしまいます。",
    "②企画案（長文）": (
        "夕方になると前髪がベタついて束になる、という20〜30代男性の不満に応えたい。"
        "朝のセットが夜まで崩れず、それでいて重くならない整髪料を企画したい。"
    ),
}
EXAMPLE = DEMO_QUERIES["①生活者の声（短文）"]


def render(con) -> None:
    st.caption("デモ用の入力例（ADR-0026）。押すと検索窓に入ります。")
    example_cols = st.columns(len(DEMO_QUERIES))
    for col, (label, text) in zip(example_cols, DEMO_QUERIES.items()):
        if col.button(label, use_container_width=True):
            st.session_state["query"] = text
            # 前のクエリの結果が残っていると、切り替えた直後に古い結果を見せてしまう
            st.session_state.pop("result", None)
            st.rerun()

    query = st.text_area(
        "企画案・生活者の声を、そのまま入力してください",
        value=st.session_state.get("query", EXAMPLE),
        height=100,
        help="検索語ではなく文章を入れてください。短い単語より文章のほうが意味検索は効きます。",
    )

    with st.container(border=False):
        cols = st.columns([2, 3])
        with cols[0]:
            mode_label = st.radio(
                "検索方式（デモ用）",
                list(MODE_LABELS),
                index=2,
                horizontal=True,
                label_visibility="collapsed",
            )
        with cols[1]:
            st.caption("検索方式：デモ用の切替です。通常利用では「両方併用」固定です。")
    mode = MODE_LABELS[mode_label]

    if st.button("検索", type="primary"):
        # タブ①はニーズ→技術の片方向に固定（ADR-0028）。所属部署では向きを変えない。
        # 技術側から「何に使えるか」を探る用途はタブ②の詳細画面が担う（ADR-0029）。
        result = cross_search.search(con, query, query_side="need", mode=mode)
        # ログ記録はボタンのブロック内で行う。外に書くと件数が水増しされる（F-04）
        search_log.log_search(
            con,
            query=query,
            mode="cross",
            user_dept=st.session_state["stance"],
            hit_count=0 if result.no_hit else len(result.hits),
            top_score=result.top_similarity,
        )
        st.session_state["query"] = query
        st.session_state["result"] = result

    result = st.session_state.get("result")
    if result is None:
        return

    st.divider()
    summary = f"キーワード検索 {result.bm25_count}件／意味検索 {result.vector_count}件"
    if mode == cross_search.MODE_KEYWORD:
        if not result.hits:
            # デモ①：語彙の断絶そのもの（ADR-0026）
            st.warning(
                "キーワード検索では0件でした。"
                "生活者の言葉と技術文書の言葉が一致しないためです。"
                "検索方式を「両方併用」に切り替えてください。"
            )
            st.caption(summary)
            return
        # デモ②：0件にはならないが、並び順が語の一致順で意味を持たない（ADR-0026）
        st.info(
            "キーワード検索でも何件か返りました。ただし並び順は語が一致した順で、"
            "内容がどれだけ近いかは見ていません（関連度も出ません）。"
            "「両方併用」に切り替えると順位が変わります。"
        )

    if result.no_hit:
        st.warning("十分に一致する技術は見つかりませんでした。近い候補を関連度順に表示します。")
        suggestions = rephrase.suggest(st.session_state.get("query", ""))
        if suggestions:
            st.caption("もしかして：" + "、".join(suggestions) + " も検索しますか？")
        st.caption("この検索は「まだ社内に無い技術」として記録しました。")

    st.caption(f"{len(result.hits)}件　（{summary}）")
    docs = repositories.get_documents(con, [h.doc_id for h in result.hits])

    def open_detail(doc_id: int) -> None:
        st.session_state["detail_id"] = doc_id
        st.session_state["goto_techdb"] = True

    for hit in result.hits:
        doc = docs.get(hit.doc_id)
        if doc is not None:
            cards.render(con, hit, doc, on_detail=open_detail)

    # 主役（反対側）を埋もれさせないため折りたたみで下に置く（ADR-0024）。
    # 中身は2つ。ADR-0007の「同じ悩みに対する既存の訴求」は、同じ側検索だけでは満たせない
    # （同じ側が返すのは悩みだけで、訴求は tech_usage にしか無い）ため2点セットにする（ADR-0031）。
    usages = [(h, repositories.get_tech_usage(con, h.doc_id)) for h in result.hits]
    usages = [(h, u) for h, u in usages if u]
    if result.same_side_hits or usages:
        st.divider()
        with st.expander("似た悩み・既存の訴求"):
            st.caption(
                "同じ悩みが社内にすでに集まっているか、"
                "そしてその悩みに対して自社がもう何と言って答えているかです。"
                "**同じ訴求で既に出ていれば差別化になりにくく、出ていなければ余地が残っています。**"
            )

            st.markdown(f"**① 似た悩み（{len(result.same_side_hits)}件）**")
            if not result.same_side_hits:
                st.caption("　似た悩みは登録されていません。")
            same_docs = repositories.get_documents(
                con, [h.doc_id for h in result.same_side_hits]
            )
            for hit in result.same_side_hits:
                doc = same_docs.get(hit.doc_id)
                if doc is not None:
                    st.markdown(f"- **{doc['title']}**（関連度 {hit.percent}%）")
                    if doc["body"]:
                        st.caption(doc["body"])

            st.markdown("**② この悩みに対して自社が既に打った訴求**")
            if not usages:
                st.caption("　今回ヒットした技術に採用実績はありません＝この訴求はまだ打っていません。")
            hit_docs = repositories.get_documents(con, [h.doc_id for h, _ in usages])
            for hit, rows in usages:
                title = hit_docs[hit.doc_id]["title"]
                for u in rows:
                    st.markdown(f"- 「{u['claim']}」（{u['brand']} {u['product']}／{u['launched']}）")
                    st.caption(f"　使った技術：{title}")
            st.caption("※採用実績はデモ用のサンプルデータです。")
