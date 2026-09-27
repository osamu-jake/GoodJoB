"""デモ用クエリの実測（実装計画のタスク2-13・テスト設計 U-04／S-22／A-01・A-01b）。

デモは2本立て（ADR-0026）。このスクリプトは両方を実測する。

  ①短文（生活者の声そのまま）… キーワード0件 → ハイブリッドでN件
  ②長文（企画案の文章）      … キーワードは数件返すが正解が1位に来ない
                              → ハイブリッドで正解が1位

①だけを狙って長文でも0件にしようとしないこと。長文には「整髪料」のような製品
カテゴリ名が入り、特許の【背景技術】と普通に一致する。0件を作るにはBM25索引を
要約だけに絞るしかなく、キーワード検索をわざと弱めた形になる（ADR-0026の捨てた案）。

集めたデータ次第で成立するかどうかが決まるので、スライドを作り始める前にこれを流す。
①の候補が1件も出なければ収集条件の見直しが先。
"""

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from db import build_db  # noqa: E402
from search import cross_search, tokenizer  # noqa: E402

LONG_QUERIES = [
    "夕方になると前髪がベタついて束になる、という20〜30代男性の不満に応えたい。朝のセットが夜まで崩れず、それでいて重くならない整髪料を企画したい。",
]

CANDIDATE_QUERIES = [
    "ワックスをつけた髪が、夕方になるとベタついて束になってしまいます。",
    "カラーをした髪がパサついて広がるのを、しっとりまとめたい。",
    "洗顔のあとに肌がつっぱらない、やさしい洗顔料を作りたい。",
    "汗をかいてもメイクがよれない下地を企画したい。",
    "朝つけた香りが夕方まで続くようにしたい。",
]


def _ranking(con, q, mode):
    """指定モードでの上位5件を (順位, 表示文字列) で返す。"""
    from db import repositories

    res = cross_search.search(con, q, query_side="need", mode=mode)
    docs = repositories.get_documents(con, [h.doc_id for h in res.hits])
    out = []
    for i, h in enumerate(res.hits[:5], 1):
        # キーワードのみのヒットは関連度を持たない（U-11）ので%を出さない
        score = f"{h.percent:>3}%" if h.in_vector else "  語一致"
        out.append((i, f"{score} [{h.matched_field or '-':<10}] {docs[h.doc_id]['title']}"))
    return res, out


def _check_long(con) -> None:
    """②長文（企画案）：キーワードでは正解が1位に来ないことを見る（ADR-0026）。"""
    print("\n\n=== ②長文（企画案）— 0件ではなく「順位が壊れる」ことを見る ===")
    for q in LONG_QUERIES:
        print(f"\n■ {q[:46]}…")
        for mode, label in (
            (cross_search.MODE_KEYWORD, "キーワードのみ"),
            (cross_search.MODE_HYBRID, "両方併用"),
        ):
            res, rows = _ranking(con, q, mode)
            print(f"  [{label}] {len(res.hits)}件")
            for i, line in rows:
                print(f"    {i}位 {line}")
        print("  → キーワード側の1位と両方併用側の1位が違えばデモとして使える")


def main() -> int:
    con = build_db.build()
    print("=== ①短文（生活者の声）— キーワード0件になるものを探す ===")
    print(f"{'BM25':>5} {'Hybrid':>7} {'最高類似度':>10}  クエリ")
    print("-" * 78)
    usable = []
    for q in CANDIDATE_QUERIES:
        kw = cross_search.search(con, q, query_side="need", mode=cross_search.MODE_KEYWORD)
        hy = cross_search.search(con, q, query_side="need", mode=cross_search.MODE_HYBRID)
        bm25_n = len(kw.hits)
        hybrid_n = len(hy.hits)
        mark = "★" if bm25_n == 0 and hybrid_n > 0 else "  "
        print(f"{bm25_n:>5} {hybrid_n:>7} {hy.top_similarity:>10.3f} {mark} {q[:40]}")
        if bm25_n == 0 and hybrid_n > 0:
            usable.append((q, hy))

    print()
    if not usable:
        print("①の候補なし。収集条件の見直しが先（実装計画のリスク表を参照）。")
        return 1

    print(f"デモに使えるクエリ: {len(usable)}件")
    q, _ = usable[0]
    print(f"\n先頭候補の上位結果: {q[:40]}...")
    _, rows = _ranking(con, q, cross_search.MODE_HYBRID)
    for _, line in rows:
        print(f"  {line}")

    _check_long(con)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
