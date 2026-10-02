"""各テーブルの読み出し関数（企画系・権利状況。F-05・F-08・F-17・F-19、ADR-0022・0039）。

画面（ui/）が呼ぶ側。**どの関数も、データが無いときに例外にせず「無い」と分かる値を返す**
（空リスト・None・ラベル）。データが無いことも判断材料になるため、画面は空欄で隠さず
「登録なし」「実績なし」「未評価」と明示する（仕様「エラー時の挙動」）。

元のテーブルを直接 JOIN する。互換ビューは作らない（ADR-0039）。
戻り値は行ごとの dict。`con` は `db.connection.connect()` で作った接続。

| 関数 | 返すもの |
|---|---|
| `get_project_techs(con, seed_id)` | 技術に対する企画ごとの判断。**空リスト＝未評価** |
| `get_claims(con, seed_id)` | 技術を `adopted` にした企画の商品・訴求。空リスト＝実績なし |
| `get_claims_for(con, seed_ids)` | 上の複数技術版。同じ商品・訴求は1回だけ（タブ①の折りたたみ用） |
| `get_patent(con, seed_id)` | 権利状況1件。無ければ None |
| `list_techs(con, ...)` | タブ②の一覧。「未使用の技術」「特許ステータス」で絞り込める |
"""

import sqlite3

# decision の表示名（仕様「データ」project_techs）
DECISION_LABELS = {"adopted": "採用", "dropped": "見送り", "evaluating": "評価中"}
# patents.state の表示名（F-19）
PATENT_STATE_LABELS = {"registered": "登録済", "pending": "出願中", "none": "未出願"}

NO_PATENT_LABEL = "登録なし"
NO_CLAIMS_LABEL = "実績なし"
UNEVALUATED_LABEL = "未評価"


def _rows(con: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in con.execute(sql, params).fetchall()]


def get_project_techs(con: sqlite3.Connection, seed_id: int) -> list[dict]:
    """技術 `seed_id` に対する、企画ごとの判断（採用／見送り／評価中）を新しい順に返す。

    同じ技術が企画Xでは採用、企画Yでは見送りなら、両方の行が返る（どちらも上書きしない）。
    **行が1件も無ければ空リスト。それが「未評価」**（どの企画でも検討されていない。ADR-0039）。
    各行のキー: project_id, project_name, project_status, is_sample, decision, decision_label,
    reason, detail, decided_at
    """
    rows = _rows(
        con,
        """
        SELECT pt.project_id, p.name AS project_name, p.status AS project_status, p.is_sample,
               pt.decision, pt.reason, pt.detail, pt.decided_at
          FROM project_techs pt
          JOIN projects p ON p.id = pt.project_id
         WHERE pt.seed_id = ?
         ORDER BY pt.decided_at DESC, pt.id
        """,
        (seed_id,),
    )
    for row in rows:
        row["decision_label"] = DECISION_LABELS.get(row["decision"], row["decision"])
    return rows


def tech_status_label(project_techs: list[dict]) -> str:
    """`get_project_techs` の結果から、一覧用の短いラベルを作る。行が無ければ「未評価」。"""
    if not project_techs:
        return UNEVALUATED_LABEL
    decisions = {row["decision"] for row in project_techs}
    for decision in ("adopted", "evaluating", "dropped"):  # 採用実績があれば採用を優先して見せる
        if decision in decisions:
            return DECISION_LABELS[decision]
    return UNEVALUATED_LABEL


def get_claims(con: sqlite3.Connection, seed_id: int) -> list[dict]:
    """技術 `seed_id` を `adopted` にした企画から出た商品・訴求を返す。無ければ空リスト（実績なし）。

    各行のキー: product_id, project_id, project_name, is_sample, product, brand, claim, launched, source_url
    見送り・評価中の企画の商品は含めない（採用実績ではないため）。
    """
    return _rows(
        con,
        """
        SELECT pp.id AS product_id, pp.project_id, p.name AS project_name, p.is_sample,
               pp.product, pp.brand, pp.claim, pp.launched, pp.source_url
          FROM project_techs pt
          JOIN projects p ON p.id = pt.project_id
          JOIN project_products pp ON pp.project_id = pt.project_id
         WHERE pt.seed_id = ? AND pt.decision = 'adopted'
         ORDER BY pp.launched DESC, pp.id
        """,
        (seed_id,),
    )


def get_claims_for(con: sqlite3.Connection, seed_ids: list[int]) -> list[dict]:
    """複数の技術の訴求をまとめて返す。**同じ商品・訴求（`project_products.id`）は1回だけ**。

    1企画で複数の技術を採用していると、ヒットした技術の数だけ同じ訴求が返ってしまうため
    （タブ①の「既存の訴求」。ADR-0039）。最初に現れた順を保つ。
    """
    seen: set[int] = set()
    claims = []
    for seed_id in seed_ids:
        for claim in get_claims(con, seed_id):
            if claim["product_id"] not in seen:
                seen.add(claim["product_id"])
                claims.append(claim)
    return claims


def get_patent(con: sqlite3.Connection, seed_id: int) -> dict | None:
    """技術 `seed_id` の権利状況を返す。無ければ None（画面は「登録なし」と出す）。

    キー: id, seed_id, state, state_label, number, filed, registered, expires, note。
    1技術に複数行あるときは新しい `id` の1件を返す。
    """
    rows = _rows(con, "SELECT * FROM patents WHERE seed_id = ? ORDER BY id DESC LIMIT 1", (seed_id,))
    if not rows:
        return None
    rows[0]["state_label"] = PATENT_STATE_LABELS.get(rows[0]["state"], rows[0]["state"])
    return rows[0]


def patent_label(patent: dict | None) -> str:
    """カードのバッジ用。権利状況が無ければ「登録なし」。"""
    return patent["state_label"] if patent else NO_PATENT_LABEL


def list_techs(
    con: sqlite3.Connection, *, unused_only: bool = False, patent_state: str | None = None
) -> list[dict]:
    """タブ②の技術一覧（シーズ文書）。条件を組み合わせて絞り込める。

    - `unused_only=True`: **`decision='adopted'` の行が1件も無い技術**（未評価・見送り・評価中だけの技術。ADR-0039）
    - `patent_state`: 'registered'（登録済）／'pending'（出願中）／'none'（未出願）のどれか
    各行のキー: id, title, category, source, patent_state
    """
    sql = """
        SELECT d.id, d.title, d.category, d.source, pa.state AS patent_state
          FROM documents d
          LEFT JOIN patents pa ON pa.id = (SELECT MAX(id) FROM patents WHERE seed_id = d.id)
         WHERE d.doc_type = 'seed'
    """
    params: list = []
    if unused_only:
        sql += " AND NOT EXISTS (SELECT 1 FROM project_techs pt WHERE pt.seed_id = d.id AND pt.decision = 'adopted')"
    if patent_state is not None:
        sql += " AND pa.state = ?"
        params.append(patent_state)
    sql += " ORDER BY d.id"
    return _rows(con, sql, tuple(params))
