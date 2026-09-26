"""検索結果カード1件分の描画（F-03・仕様「画面・操作」タブ①）。

カードに載せるもの：関連度・この技術が解決しようとしている課題・一言要約・
権利状況・使用実績・エビデンスへの導線。
"""

import streamlit as st

from db import repositories

TYPE_LABEL = {"seed": "シーズ（技術）", "need": "ニーズ（生活者の声）"}
FIELD_LABEL = {
    "problem": "解決しようとする課題",
    "body": "要約",
    "background": "背景技術",
}
STATE_BADGE = {"registered": "登録済", "pending": "出願中", "none": "未出願"}


def render(con, hit, doc, on_detail=None) -> None:
    with st.container(border=True):
        head, score = st.columns([5, 1])
        with head:
            st.markdown(f"**{doc['title']}**")
            st.caption(TYPE_LABEL.get(doc["doc_type"], doc["doc_type"]))
        with score:
            if hit.in_vector:
                st.metric("関連度", f"{hit.percent}%", label_visibility="visible")
                st.caption(hit.label)
            else:
                st.caption("語一致")

        if doc["doc_type"] == "seed":
            patent = repositories.get_patent(con, doc["id"])
            usages = repositories.get_tech_usage(con, doc["id"])
            badges = [STATE_BADGE.get(patent["state"], "権利情報なし") if patent else "権利情報なし"]
            badges.append(f"採用実績 {len(usages)}件" if usages else "採用実績なし")
            if hit.matched_field:
                badges.append(f"一致箇所：{FIELD_LABEL.get(hit.matched_field, hit.matched_field)}")
            st.caption("　|　".join(badges))

            if doc["problem"]:
                st.markdown("**この技術が解決しようとしている課題**")
                st.write(doc["problem"])

            if doc["summary_plain"]:
                st.info(f"平たく言うと：{doc['summary_plain']}")
                st.caption("※AIによる要約です。詳細は原文でご確認ください。")
        else:
            st.write(doc["body"])

        left, right = st.columns([1, 1])
        with left:
            # プレースホルダのURLは飛び先が無い。押せるボタンのまま出すと、発表中に
            # 押して「リンク切れ」を見せてしまう。実データと判別できる表示にする
            # （仕様「データソースの方針」）。実特許に転記し直せば自動でボタンに戻る
            if doc["source"] == "placeholder" or "example.invalid" in (doc["url"] or ""):
                st.button(
                    "原文リンクは特許の転記後に入ります",
                    key=f"url-placeholder-{doc['id']}",
                    disabled=True,
                    use_container_width=True,
                )
            elif doc["url"]:
                st.link_button("原文を開く", doc["url"], use_container_width=True)
        with right:
            if on_detail and doc["doc_type"] == "seed":
                if st.button(
                    "エビデンス・使われ方を見る",
                    key=f"detail-{doc['id']}",
                    use_container_width=True,
                ):
                    on_detail(doc["id"])
