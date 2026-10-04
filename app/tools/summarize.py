"""`summary_plain`（「平たく言うと」要約）の生成（F-16。ADR-0016・0020・0025）。

開発時に一度だけ手動実行するスクリプト。起動のたびに課金APIを呼ぶと再現性と費用の両方で
問題になるため（ADR-0020）、ここで生成したテキストを`knowledge.db`に書き込み、
`tools/export_seeds.py`で`fixtures/seeds.sql`へ書き出してコミットする。本番の起動時（`build_db.py`）は
このテキストをそのまま使うだけで、APIは一切呼ばない。

使い方:
    export ANTHROPIC_API_KEY=...
    python3 tools/summarize.py            # summary_plainが空の seed 文書だけ生成
    python3 tools/summarize.py --force    # 既存の summary_plain も作り直す
    python3 tools/summarize.py --dry-run  # 生成結果を表示するだけでDBへは書かない

**2026-10-04時点の注記**: 2-9（全20件の初回生成）は、このスクリプトを実機実行する代わりに
PM（じゃけ）がClaude Codeとの対話の中で直接要約文を作成し、`knowledge.db`へ投入した
（課金APIキーの用意が不要になるための判断）。このスクリプトは、今後 文書が増えたときや
要約の質を見直したいときに**実際にAPIを使って再生成するための実装**として用意してある。
"""

import argparse
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from db import connection  # noqa: E402

MODEL = "claude-sonnet-5"  # 要約1件あたりのコストが小さいモデルを使う想定

SYSTEM_PROMPT = (
    "あなたは化粧品会社の社内向け技術データベースの編集者です。"
    "特許の「課題」「要約（解決手段）」「背景技術」を読み、専門知識のないマーケティング担当者にも"
    "一読で伝わる日本語1文（60字以内・体言止め「〜技術。」で終える）に言い換えてください。"
    "成分名や専門用語を本質的な効果の説明に置き換え、誇張はしないでください。出力は1文のみ。"
)


def _build_prompt(doc: dict) -> str:
    return (
        f"発明の名称: {doc['title']}\n"
        f"課題: {doc['problem'] or ''}\n"
        f"要約: {doc['body'] or ''}\n"
        f"背景技術: {doc['background'] or ''}\n"
    )


def _call_llm(prompt: str) -> str:
    """Anthropic APIを1回呼び、要約1文を返す。ANTHROPIC_API_KEYが必要。"""
    import anthropic  # 遅延import。requirements.txtには入れず、このスクリプト実行時だけ要る

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="既存のsummary_plainも作り直す")
    parser.add_argument("--dry-run", action="store_true", help="DBへは書かず、生成結果を表示するだけ")
    args = parser.parse_args()

    con = connection.connect()
    where = "doc_type = 'seed'" if args.force else "doc_type = 'seed' AND (summary_plain IS NULL OR summary_plain = '')"
    rows = [dict(r) for r in con.execute(f"SELECT * FROM documents WHERE {where} ORDER BY id").fetchall()]

    if not rows:
        print("対象なし（すでに全件 summary_plain が入っています。--force で作り直せます）")
        return

    print(f"{len(rows)}件を生成します（モデル: {MODEL}）")
    for doc in rows:
        summary = _call_llm(_build_prompt(doc))
        print(f"  id={doc['id']} {doc['title']} -> {summary}")
        if not args.dry_run:
            con.execute("UPDATE documents SET summary_plain = ? WHERE id = ?", (summary, doc["id"]))

    if not args.dry_run:
        con.commit()
        print("DBへ書き込みました。続けて `python3 tools/export_seeds.py` でseeds.sqlへ書き出してください。")
    else:
        print("--dry-run のためDBへは書き込んでいません。")


if __name__ == "__main__":
    main()
