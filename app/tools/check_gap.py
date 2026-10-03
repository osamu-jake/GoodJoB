"""デモ用クエリの実測（N-06・U-04・ADR-0026）。

「キーワード検索は0件／外れるが、意味検索なら正解が出る」というデモが、実データで成立するかを測る。
候補クエリごとに、キーワードのみ・両方併用で何が返るかを並べる。データ投入直後、テスト着手前に実行する。

デモは2本立て（ADR-0026）:
- ① 短文（30字程度。生活者の声そのまま）: **BM25が0件**になる。→ キーワードのみ0件／両方併用でN件
- ② 長文（70字程度。企画案）: キーワードのみだと**正解が1位に来ず**、両方併用だと**正解が1位**に来る

候補ファイル（JSON）の形:
    [
      {"label": "短文A", "kind": "short", "text": "夕方になると前髪がベタついて束になる", "expected": "皮脂"},
      {"label": "長文A", "kind": "long",  "text": "…70字程度の企画案…",               "expected": "皮脂"}
    ]
`expected` は正解にしたい技術のタイトルに含まれる語（または文書ID。数値で書く）。

使い方（app/ から）:
    python tools/check_gap.py candidates.json
    python tools/check_gap.py candidates.json --db knowledge.db
"""

import argparse
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:  # `python tools/check_gap.py` で直接動かしたとき用
    sys.path.insert(0, str(APP_DIR))

from db import connection  # noqa: E402
from search import cross_search  # noqa: E402

TOP_K = 10


def _find_expected(con, expected) -> set[int]:
    """`expected`（文書ID、またはタイトルに含まれる語）に当てはまるシーズ文書のIDを返す。"""
    if isinstance(expected, int):
        rows = con.execute("SELECT id FROM documents WHERE doc_type='seed' AND id = ?", (expected,))
    else:
        rows = con.execute(
            "SELECT id FROM documents WHERE doc_type='seed' AND title LIKE ?", (f"%{expected}%",)
        )
    return {r["id"] for r in rows.fetchall()}


def _first_rank(hits, expected_ids: set[int]) -> int | None:
    for rank, hit in enumerate(hits, start=1):
        if hit.doc_id in expected_ids:
            return rank
    return None


def _title(con, doc_id: int) -> str:
    row = con.execute("SELECT title FROM documents WHERE id = ?", (doc_id,)).fetchone()
    return row["title"] if row else "?"


def evaluate(con, candidate: dict) -> dict:
    """候補1本を、キーワードのみ・意味のみ・両方併用で実測する。"""
    text = candidate["text"]
    expected_ids = _find_expected(con, candidate["expected"]) if "expected" in candidate else set()
    runs = {
        mode: cross_search.cross_search(con, text, mode=mode, top_k=TOP_K, same_side_k=0)
        for mode in (cross_search.MODE_BM25, cross_search.MODE_VECTOR, cross_search.MODE_HYBRID)
    }
    keyword, vector_, hybrid = runs["bm25"], runs["vector"], runs["hybrid"]
    return {
        "label": candidate.get("label", ""),
        "kind": candidate.get("kind", ""),
        "chars": len(text),
        "expected_ids": sorted(expected_ids),
        "bm25_count": keyword.bm25_count,
        "keyword_count": len(keyword.hits),
        "keyword_top": _title(con, keyword.hits[0].doc_id) if keyword.hits else None,
        "keyword_rank": _first_rank(keyword.hits, expected_ids),
        "vector_rank": _first_rank(vector_.hits, expected_ids),
        "hybrid_count": len(hybrid.hits),
        "hybrid_rank": _first_rank(hybrid.hits, expected_ids),
        "hybrid_top": _title(con, hybrid.hits[0].doc_id) if hybrid.hits else None,
        "hybrid_top_similarity": hybrid.hits[0].similarity if hybrid.hits else None,
    }


def verdict(ev: dict) -> str:
    """ADR-0026 の成立条件に当てはまるか。'OK' か、成立しない理由を返す。"""
    if ev["kind"] == "short":
        if ev["bm25_count"] != 0:
            return f"NG: BM25が{ev['bm25_count']}件ヒットしてしまう（0件にならない）"
        if ev["hybrid_count"] == 0:
            return "NG: 両方併用でも0件"
        return "OK"
    if ev["kind"] == "long":
        if not ev["expected_ids"]:
            return "NG: expected に当てはまる技術が無い"
        if ev["keyword_rank"] == 1:
            return "NG: キーワードのみでも正解が1位に来てしまう"
        if ev["hybrid_rank"] != 1:
            return f"NG: 両方併用で正解が1位に来ない（{ev['hybrid_rank'] or '圏外'}位）"
        return "OK"
    return "?: kind は short か long"


def format_report(evals: list[dict]) -> str:
    lines = []
    for ev in evals:
        lines += [
            f"■ {ev['label']}（{ev['kind']}・{ev['chars']}字） → {verdict(ev)}",
            f"   BM25ヒット数: {ev['bm25_count']}件 ／ キーワードのみ: {ev['keyword_count']}件"
            f"（1位: {ev['keyword_top'] or '-'}）",
            f"   正解の順位  : キーワードのみ={ev['keyword_rank'] or '圏外'} ／ 意味のみ={ev['vector_rank'] or '圏外'}"
            f" ／ 両方併用={ev['hybrid_rank'] or '圏外'}   （正解の文書ID: {ev['expected_ids'] or '指定なし'}）",
            f"   両方併用    : {ev['hybrid_count']}件（1位: {ev['hybrid_top'] or '-'}"
            + (f"・類似度{ev['hybrid_top_similarity']:.3f}" if ev["hybrid_top_similarity"] is not None else "")
            + "）",
            "",
        ]
    short_ok = [e["label"] for e in evals if e["kind"] == "short" and verdict(e) == "OK"]
    long_ok = [e["label"] for e in evals if e["kind"] == "long" and verdict(e) == "OK"]
    lines.append(f"成立した短文（①）: {short_ok or 'なし'}")
    lines.append(f"成立した長文（②）: {long_ok or 'なし'}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="デモ用クエリの候補を実測する")
    parser.add_argument("candidates", help="候補クエリのJSONファイル")
    parser.add_argument("--db", default=str(connection.DB_PATH))
    args = parser.parse_args()

    if not Path(args.db).exists():
        sys.exit(f"DBが見つかりません: {args.db}（先に python db/build_db.py）")
    candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    con = connection.connect(args.db)
    try:
        evals = [evaluate(con, c) for c in candidates]
    finally:
        con.close()
    print(format_report(evals))


if __name__ == "__main__":
    main()
