"""タブ②技術データベース（F-17）。

一覧・絞り込み・詳細。「まだ社内に無い技術」は頻度ランキングにせず、
個別の企画案を検索日・部署・その時の最高関連度とともに並べる。
"""

import streamlit as st

from db import repositories
from search import cross_search

FILTERS = ("すべて", "未使用の技術", "特許 登録済", "特許 出願中", "まだ社内に無い技術")
KIND_ICON = {"evaluated": "✅", "dropped": "⛔", "unevaluated": "❓"}


def _render_detail(con, seed_id: int) -> None:
    doc = repositories.get_document(con, seed_id)
    if doc is None:
        st.warning("技術が見つかりませんでした。")
        return

    if st.button("← 一覧へ戻る"):
        st.session_state.pop("detail_id", None)
        st.rerun()

    st.subheader(doc["title"])
    st.caption(f"{doc['category']}　|　公開日 {doc['pub_date'] or '—'}")

    if doc["summary_plain"]:
        st.info(f"平たく言うと：{doc['summary_plain']}")
        st.caption("※AIによる要約です。詳細は原文でご確認ください。")

    st.markdown("**この技術が解決しようとしている課題**")
    st.write(doc["problem"] or "—")
    st.markdown("**要約**")
    st.write(doc["body"] or "—")
    with st.expander("背景技術"):
        st.write(doc["background"] or "—")

    st.divider()
    st.markdown("### エビデンス")
    if doc["source"] == "placeholder" or "example.invalid" in (doc["url"] or ""):
        st.button("原文リンクは特許の転記後に入ります", disabled=True)
    elif doc["url"]:
        st.link_button("原文を開く", doc["url"])
    evaluations = repositories.get_evaluations(con, seed_id)
    if evaluations:
        for ev in evaluations:
            icon = KIND_ICON.get(ev["kind"], "・")
            label = repositories.KIND_LABELS.get(ev["kind"], ev["kind"])
            dated = ev["dated"] or "日付なし"
            st.markdown(f"{icon} **{label}**（{dated}）　{ev['summary']}")
            if ev["detail"]:
                st.caption(ev["detail"])
    else:
        st.caption("評価記録は登録されていません（未評価）。")
    st.caption("※評価・見送り記録はデモ用のサンプルデータです。")

    st.divider()
    st.markdown("### 権利状況")
    patent = repositories.get_patent(con, seed_id)
    if patent:
        state = repositories.STATE_LABELS.get(patent["state"], "—")
        st.markdown(
            f"**{state}**　{patent['number'] or ''}　"
            f"出願 {patent['filed'] or '—'}／登録 {patent['registered'] or '—'}／"
            f"満了 {patent['expires'] or '—'}"
        )
        if patent["note"]:
            st.caption(f"⚠️ {patent['note']}")
    else:
        st.caption("権利情報は登録されていません。")

    st.divider()
    st.markdown("### 自社での使われ方")
    usages = repositories.get_tech_usage(con, seed_id)
    if usages:
        st.dataframe(
            [
                {
                    "商品": u["product"],
                    "ブランド": u["brand"],
                    "訴求": u["claim"],
                    "上市": u["launched"],
                }
                for u in usages
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.caption("採用実績なし。まだ使われていない＝差別化の余地が残っている技術です。")
    st.caption("※採用実績はデモ用のサンプルデータです。")

    seed_text = doc["problem"] or doc["body"] or ""
    if not seed_text:
        return

    # 「この技術は何に使えそうか」の根拠を、意見のサンプルではなく記録に置く（ADR-0029）。
    # 似た課題を解く技術が実際にどの商品に使われたかは事実であって、判定ではない。
    # 見送り・未評価も併せて出すので「行けるかも」と「そこは踏まれて駄目だった」が同時に渡る。
    res = cross_search.search(con, seed_text, query_side="seed", same_side_k=4)
    similar = [h for h in res.same_side_hits if h.doc_id != seed_id][:3]

    st.divider()
    st.markdown("### 似た課題を解く技術と、その使われ方")
    st.caption(
        "この技術に近い課題を解いている技術が、実際にどう使われ、何が評価され、"
        "何が見送られたかの記録です。用途を判定するものではなく、判断の材料です。"
    )
    if not similar:
        st.caption("近い課題を解く技術は登録されていません。")
    for hit in similar:
        sd = repositories.get_documents(con, [hit.doc_id]).get(hit.doc_id)
        if sd is None:
            continue
        st.markdown(f"**{sd['title']}**（関連度 {hit.percent}%）")
        for usage in repositories.get_tech_usage(con, hit.doc_id):
            st.caption(
                f"　実績：{usage['brand']} {usage['product']}"
                f"／訴求「{usage['claim']}」（{usage['launched']}）"
            )
        for ev in repositories.get_evaluations(con, hit.doc_id):
            icon = KIND_ICON.get(ev["kind"], "・")
            label = repositories.KIND_LABELS.get(ev["kind"], ev["kind"])
            st.caption(f"　{icon} {label}：{ev['summary']}")

    st.divider()
    st.markdown("### 関連する、収集済みの声")
    # 声はダミー＋実在FAQ少数で母集団を代表しない。市場性の根拠としては出さない（ADR-0028）
    st.caption(
        "⚠️ 社内で収集した声のうち、この技術に近いものです。"
        "**件数の多さは市場の大きさを意味しません**（母集団を代表しないサンプルです）。"
    )
    need_docs = repositories.get_documents(con, [h.doc_id for h in res.hits[:3]])
    for h in res.hits[:3]:
        nd = need_docs.get(h.doc_id)
        if nd is None:
            continue
        st.markdown(f"- {nd['title']}")
        # example.invalid は転記前の仮URL。押せるリンクとして出すと発表中にリンク切れを見せる
        url = nd["url"] or ""
        if url and "example.invalid" not in url:
            st.caption(f"　出典：{url}")
        else:
            st.caption("　出典：デモ用のダミーデータ（実在FAQの引用は転記時にURLを入れる）")


def _render_list(con) -> None:
    choice = st.radio("絞り込み", FILTERS, horizontal=True)

    if choice == "まだ社内に無い技術":
        st.caption(
            "十分な関連度の技術が返らなかった企画案の一覧です。"
            "頻度ランキングにはしていません（企画案は1件ごとに文面が異なるため）。"
        )
        rows = repositories.list_gap_queries(con)
        if not rows:
            st.info("まだ記録がありません。タブ①で検索するとここに溜まります。")
            return
        st.dataframe(
            [
                {
                    # 「部署」列は出さない。利用者がマーケ1種類なので全行同じ値になる（ADR-0030）
                    "検索日時": r["ts"],
                    "最高関連度": f"{r['top_score']:.3f}",
                    "企画案": r["query"],
                }
                for r in rows
            ],
            hide_index=True,
            use_container_width=True,
        )
        return

    seeds = repositories.list_seeds(con)
    shown = 0
    for doc in seeds:
        patent = repositories.get_patent(con, doc["id"])
        usages = repositories.get_tech_usage(con, doc["id"])
        state = patent["state"] if patent else None
        if choice == "未使用の技術" and usages:
            continue
        if choice == "特許 登録済" and state != "registered":
            continue
        if choice == "特許 出願中" and state != "pending":
            continue
        shown += 1
        with st.container(border=True):
            cols = st.columns([5, 2, 2])
            with cols[0]:
                st.markdown(f"**{doc['title']}**")
                st.caption(doc["category"] or "—")
            with cols[1]:
                st.caption(repositories.STATE_LABELS.get(state, "権利情報なし"))
                st.caption(f"採用実績 {len(usages)}件" if usages else "採用実績なし")
            with cols[2]:
                if st.button("詳細", key=f"open-{doc['id']}", use_container_width=True):
                    st.session_state["detail_id"] = doc["id"]
                    st.rerun()
    if shown == 0:
        st.info("該当する技術はありません。")


def render(con) -> None:
    detail_id = st.session_state.get("detail_id")
    if detail_id:
        _render_detail(con, detail_id)
    else:
        _render_list(con)
