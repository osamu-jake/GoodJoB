"""画面の共通部品（タブ①②・詳細で同じ見た目にするもの）。"""

import html

import streamlit as st

# 権利状況のアイコン（patents.state の値 → 表示）
STATE_ICON = {"registered": "🟢", "pending": "🟡", "none": "🔴"}
NO_PATENT_ICON = "⚪️"

# どのフィールドで一致したか（cross_search の matched_field → 表示名）
FIELD_LABELS = {"problem": "解決しようとする課題", "body": "要約", "background": "背景技術"}

# 企画ごとの判断（project_techs.decision → アイコン）
DECISION_ICON = {"adopted": "✅", "dropped": "⛔", "evaluating": "🔄"}

SAMPLE_BADGE = ":gray-badge[サンプルデータ]"
AI_NOTE = "※AIによる要約です。詳細は原文でご確認ください。"


def esc(text) -> str:
    """HTML に埋め込む文字列をエスケープする（データに < や & が入っても崩れないように）。"""
    return html.escape(str(text)) if text is not None else ""


def sample_badge(is_sample) -> str:
    """ADR-0043：is_sample=1 の行にだけ「サンプルデータ」を付ける。"""
    return f"　{SAMPLE_BADGE}" if is_sample else ""


def render_plain_summary(text: str | None) -> None:
    """「平たく言うと」の箱。要約が無いときは箱ごと出さない（仕様「エラー時の挙動」）。"""
    if not text:
        return
    st.markdown(
        f"""
        <div style='background-color:#e7f3fe; color:rgb(0, 84, 163); padding:12px 16px; border-radius:8px; display:flex; gap:8px; align-items:flex-start;'>
            <div>✅</div>
            <div>
                <span style='font-size:0.8em; font-weight:bold;'>平たく言うと：</span><br>
                {esc(text)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ai_note(align: str = "right") -> None:
    """「※AIによる要約です」の注記（F-16）。"""
    st.markdown(
        f"<div style='text-align:{align}; font-size:0.85em; color:gray;'>{AI_NOTE}</div>",
        unsafe_allow_html=True,
    )


def render_section(label: str, text: str | None) -> None:
    """見出し＋本文を1つの枠にまとめる（詳細の課題・要約・背景技術）。"""
    with st.container(border=True):
        st.markdown(f"**{label}**")
        st.write(text or "—")


def render_cells(cells: list[tuple[str, str]]) -> None:
    """見出しなしの1行の表（折り返せる横並び。スマホでは縦積みになる）。"""
    row = "".join(
        # margin をマイナス1pxにして、隣どうしの枠線を重ねる（重ねないと境目が2px線になる）
        f"<div style='flex:1 1 180px; padding:6px 10px; margin:0 -1px -1px 0; "
        f"border:1px solid rgba(49,51,63,0.2)'>"
        f"<span style='color:gray; font-size:0.85em'>{esc(label)}</span>　{esc(value)}</div>"
        for label, value in cells
    )
    st.markdown(f"<div style='display:flex; flex-wrap:wrap'>{row}</div>", unsafe_allow_html=True)


def patent_text(patent: dict | None) -> str:
    """権利状況の表示（アイコン付き）。無ければ「登録なし」。"""
    if patent is None:
        return f"{NO_PATENT_ICON} 登録なし"
    return f"{STATE_ICON.get(patent['state'], NO_PATENT_ICON)} {patent['state_label']}"
