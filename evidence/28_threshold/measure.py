"""ADR-0054：「ヒットなし」の基準値0.82を、本番と同じデータ（seeds.sql）と同じモデル（e5）で確かめる。
実行：cd app && .venv/bin/python ../evidence/28_threshold/measure.py /tmp/knowledge.db"""
import sys
sys.path.insert(0, ".")
from db import build_db
from search import cross_search, hit_judge, scoring
con = build_db.build(sys.argv[1], force=True)
Q = [
    ("②企画案（デモ）", "セット力はそのままに、お風呂で簡単に洗い流せる整髪料を企画したい。毎日使うものなので、髪や頭皮への負担が少ない処方を探している。", False),
    ("①生活者の声（デモ）", "シャンプーしてもヘアワックスが落ちない。", False),
    ("ロケット（A-06）", "宇宙ロケットの燃料タンクを軽量化したい。", True),
    ("ラーメン（BM25が当たる例）", "おいしいラーメンの作り方を知りたい。", True),
    ("確定申告", "確定申告の書類の書き方が分からない", True),
    ("新幹線", "東京から大阪までの新幹線の料金", True),
]
print(f"基準値 THRESHOLD={hit_judge.THRESHOLD} / やや近いの下限={scoring.SOMEWHAT_CLOSE_FROM}")
print("| 文 | BM25件数 | 最高類似度 | 判定 | 期待 | 1位のラベル |")
ok = True
for name, q, expect in Q:
    r = cross_search.cross_search(con, q)
    nh = hit_judge.judge(r)
    top = scoring.score_hit(r.hits[0]) if r.hits else None
    good = nh == expect
    ok &= good
    print(f"| {name} | {r.bm25_count} | {r.top_similarity:.3f} | {'ヒットなし' if nh else 'ヒットあり'} | {'ヒットなし' if expect else 'ヒットあり'} {'○' if good else '×'} | {top.percent}%・{top.label} |")
print("全部期待どおり" if ok else "期待と違うものがある")
