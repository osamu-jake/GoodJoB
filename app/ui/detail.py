"""技術1件の詳細（F-05・F-08・F-19。ADR-0029・0032・0034・0039・0047）。

タブ①のカードとタブ②の一覧の両方から、同じ部品（このダイアログ）で開く（I-08）。
開き方はモーダル（st.dialog）。タブ切替は st.tabs にアクティブタブを変えるAPIが無いため使わない。
原文へのリンクは置かない（ADR-0047）。
"""

import streamlit as st

from db import repositories
from search import cross_search, scoring

from .components import (
    DECISION_ICON,
    esc,
    patent_text,
    render_ai_note,
    render_plain_summary,
    render_section,
    sample_badge,
)

RELATED_K = 3  # 似た課題を解く技術・関連する声の件数


def _on_dismiss() -> None:
    """✕・Escキー・外側のクリックで閉じたとき、開いている技術の記録を消す。

    消さないと、次にどのボタンを押しても（＝画面が描き直されると）モーダルがまた開いてしまう。
    「閉じる」ボタンは自分で消しているが、それ以外の閉じ方はここを通る。
    """
    st.session_state.detail_id = None


@st.dialog("技術の詳細", width="large", on_dismiss=_on_dismiss)
def show_detail(con, seed_id: int) -> None:
    doc = repositories.get_documents(con, [seed_id]).get(seed_id)
    if doc is None:
        st.warning("技術が見つかりませんでした。")
        _close_button()
        return

    st.markdown(f"## {doc['title']}", anchors=False)
    st.caption(f"{doc['category'] or '—'}　|　公開日 {doc['pub_date'] or '—'}")
    if doc["summary_plain"]:
        render_plain_summary(doc["summary_plain"])
        render_ai_note()          # 検索カードと同じく右揃え
        st.space("small")         # 注記と下の「課題」の枠のあいだに1行分のすきま

    render_section("この技術が解決しようとしている課題", doc["problem"])
    render_section("要約", doc["body"])
    if doc["background"]:   # 背景技術は転記していない特許もある。空の枠は出さない
        render_section("背景技術", doc["background"])

    st.space("small")
    col_pat, col_use, col_dec = st.columns(3, border=True)
    with col_pat:
        _render_patent(repositories.get_patent(con, seed_id))
    with col_use:
        _render_claims(repositories.get_claims(con, seed_id))
    with col_dec:
        _render_decisions(repositories.get_project_techs(con, seed_id))

    st.space("small")
    similar, voices = _related(con, doc)
    _render_similar(con, similar)
    _render_voices(con, voices)

    st.space("small")
    _close_button()


# ─────────────────────────────── 権利・実績・判断（3列）
def _render_patent(patent: dict | None) -> None:
    st.markdown("**特許**")
    st.markdown(patent_text(patent))
    if patent is None:
        return
    if patent["state"] == "none":   # 未出願の技術には番号も日付も無い
        return
    # 番号は、登録された特許なら特許番号、登録前・不成立なら出願番号（要件F-19）
    number_label = "特許番号" if patent["state"] in ("registered", "expired") else "出願番号"
    _render_facts([
        (number_label, patent["number"]),
        ("出願日", patent["filed"]),
        ("登録日", patent["registered"]),
        ("存続期間満了日", patent["expires"]),
    ])
    if patent["note"]:
        st.caption(patent["note"])


def _render_facts(rows: list[tuple[str, str | None]]) -> None:
    """見出し（灰色）と値を1行ずつ並べる。値が無ければ「—」。"""
    st.markdown(
        "<br>".join(f"<span style='color:gray; font-size:0.85em'>{esc(label)}</span>　{esc(value or '—')}"
                    for label, value in rows),
        unsafe_allow_html=True,
    )


def _render_claims(claims: list[dict]) -> None:
    """自社での使われ方：この技術を採用した企画の商品・訴求（F-08）。"""
    st.markdown("**自社での使われ方**")
    if not claims:
        st.success("まだどの商品にも使われていません。社内に眠っている技術です。", icon="💤")
        return
    for c in claims:
        st.markdown(f"「{c['claim']}」{sample_badge(c['is_sample'])}")
        st.caption(f"{c['brand'] or ''} {c['product'] or ''}／{c['launched'] or '—'}")


def _render_decisions(rows: list[dict]) -> None:
    """企画ごとの判断：採用／見送り／評価中と理由。行が無ければ未評価（ADR-0039）。"""
    st.markdown("**企画ごとの判断**")
    if not rows:
        st.markdown(f"❓ {repositories.UNEVALUATED_LABEL}")
        st.caption("どの企画でもまだ検討されていません。")
        return
    for r in rows:
        icon = DECISION_ICON.get(r["decision"], "・")
        st.markdown(f"{icon} {r['decision_label']}：{r['project_name']}{sample_badge(r['is_sample'])}")
        notes = [x for x in (r["reason"], r["detail"]) if x]
        if notes:
            st.caption("　".join(notes))
        if r["decided_at"]:
            st.caption(f"判断 {r['decided_at']}")


# ─────────────────────────────── 似た課題を解く技術・関連する声
def _related(con, doc: dict):
    """技術の課題文で検索し、同じ側（似た技術）と反対側（関連する声）を返す。

    cross_search を query_side='seed' で呼ぶと、反対側＝ニーズ、同じ側＝シーズになる。
    同じ技術を開き直したときに埋め込みを再計算しないよう、結果をセッションに覚えておく。
    """
    cache = st.session_state.setdefault("related_cache", {})
    if doc["id"] not in cache:
        text = doc["problem"] or doc["body"] or doc["title"]
        result = cross_search.cross_search(
            con, text, query_side="seed", mode=cross_search.MODE_HYBRID,
            top_k=RELATED_K, same_side_k=RELATED_K + 1,
        )
        similar = [h for h in result.same_side_hits if h.doc_id != doc["id"]][:RELATED_K]
        cache[doc["id"]] = (similar, result.hits[:RELATED_K])
    return cache[doc["id"]]


def _render_similar(con, hits) -> None:
    """似た課題を解く技術と、その使われ方（ADR-0029）。判定はせず記録を並べる。"""
    st.markdown("**似た課題を解く技術と、その使われ方**")
    if not hits:
        st.caption("似た課題を解く技術は見つかりませんでした。")
        return
    docs = repositories.get_documents(con, [h.doc_id for h in hits])
    for h in hits:
        d = docs.get(h.doc_id)
        if d is None:
            continue
        score = scoring.score_hit(h)
        rows = repositories.get_project_techs(con, h.doc_id)
        with st.container(border=True):
            pct = f"関連度 {score.percent}%" if score.percent is not None else score.label
            st.markdown(f"**{d['title']}**　:gray-badge[{pct}]")
            if not rows:
                st.caption(f"❓ {repositories.UNEVALUATED_LABEL}")
            for r in rows:
                icon = DECISION_ICON.get(r["decision"], "・")
                st.caption(f"{icon} {r['decision_label']}：{r['project_name']}"
                           + (f"（{r['reason']}）" if r["reason"] else ""))
            for c in repositories.get_claims(con, h.doc_id):
                st.caption(f"「{c['claim']}」{c['brand'] or ''} {c['product'] or ''}／{c['launched'] or '—'}")


def _render_voices(con, hits) -> None:
    """関連する収集済みの声（反対方向の検索結果）。市場性の根拠にはしない（ADR-0028）。"""
    st.markdown("**関連する収集済みの声**")
    st.caption("※収集済みの声の一部で、母集団を代表しません。市場性の根拠としては使わないでください。")
    if not hits:
        st.caption("関連する声は見つかりませんでした。")
        return
    docs = repositories.get_documents(con, [h.doc_id for h in hits])
    for h in hits:
        d = docs.get(h.doc_id)
        if d is None:
            continue
        with st.container(border=True):
            st.markdown(f"> {d['body'] or d['title']}")
            source = "FAQ" if d["source"] == "faq" else "ダミー"
            st.caption(f"出典：{source}" + (f"　{d['url']}" if d["url"] else ""))


def _close_button() -> None:
    with st.container(horizontal_alignment="center"):
        if st.button("閉じる", key="close-detail", width=160):
            st.session_state.detail_id = None
            st.rerun()
