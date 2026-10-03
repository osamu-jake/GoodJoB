"""db/repositories.py のテスト（U-17・U-24）と、企画ごとの判断・訴求の取り出し（I-13の前提）。

テスト用seeds: 技術1＝企画1で採用・企画2で見送り／技術2＝企画1で評価中／技術3〜6＝判断の行なし。
権利状況は技術1（登録済）・技術2（出願中）だけにある。
"""

from db import repositories as repo


def test_u17_行が無いdoc_idでも例外にならず_登録なし_実績なしを返す(con):
    """U-17: patents／project_techs／project_products に行が無い doc_id → 例外にならず「登録なし」「実績なし」を返す。"""
    assert repo.get_patent(con, 3) is None
    assert repo.patent_label(repo.get_patent(con, 3)) == "登録なし"
    assert repo.get_claims(con, 3) == []
    assert repo.get_project_techs(con, 3) == []
    assert repo.get_claims_for(con, [3, 4]) == []
    assert repo.NO_CLAIMS_LABEL == "実績なし"


def test_存在しないdoc_idでも例外にならない(con):
    assert repo.get_patent(con, 9999) is None
    assert repo.get_claims(con, 9999) == []
    assert repo.get_project_techs(con, 9999) == []


def test_u24_判断の行が1件も無い技術は空リストで_ラベルは未評価(con):
    """U-24: project_techs に行が1件も無い技術 → get_project_techs が空リストを返し、画面用ラベルは「未評価」。"""
    techs = repo.get_project_techs(con, 4)

    assert techs == []
    assert repo.tech_status_label(techs) == "未評価"


def test_同じ技術の採用と見送りが両方返る(con):
    """I-13の前提: 企画Xでは採用、企画Yでは見送りの記録が、どちらも上書きされずに返る。"""
    techs = repo.get_project_techs(con, 1)

    assert [(t["project_id"], t["decision"]) for t in techs] == [(2, "dropped"), (1, "adopted")]  # 新しい判断が先
    dropped = techs[0]
    assert dropped["decision_label"] == "見送り"
    assert dropped["reason"] == "ミストに分散させると安定性が落ちた"
    assert dropped["project_name"].startswith("【サンプル】")
    assert dropped["is_sample"] == 1
    assert techs[1]["decision_label"] == "採用"


def test_評価中も返り_ラベルは評価中(con):
    techs = repo.get_project_techs(con, 2)

    assert [t["decision"] for t in techs] == ["evaluating"]
    assert repo.tech_status_label(techs) == "評価中"


def test_ラベルは採用実績があれば採用を優先する(con):
    assert repo.tech_status_label(repo.get_project_techs(con, 1)) == "採用"


def test_get_claimsは採用した企画の商品と訴求を返す(con):
    claims = repo.get_claims(con, 1)

    assert len(claims) == 1
    assert claims[0]["product"] == "サンプル・ハードワックス"
    assert claims[0]["claim"] == "夕方まで前髪さらさら"
    assert claims[0]["launched"] == "2025-03"
    assert claims[0]["project_name"].startswith("【サンプル】") and claims[0]["is_sample"] == 1


def test_get_claimsは見送り_評価中の企画の商品を含めない(con):
    con.execute("INSERT INTO project_products (id, project_id, product, claim) VALUES (2, 2, '見送り企画の商品', '載せない')")

    assert [c["product"] for c in repo.get_claims(con, 1)] == ["サンプル・ハードワックス"]  # 企画2は見送り
    assert repo.get_claims(con, 2) == []  # 技術2は評価中だけ


def test_get_claims_forは同じ商品を1回だけ返す(con):
    """1企画で複数の技術を採用していても、同じ商品・訴求は1回だけ（ADR-0039）。"""
    con.execute("INSERT INTO project_techs (project_id, seed_id, decision) VALUES (1, 5, 'adopted')")

    assert len(repo.get_claims(con, 1)) == 1 and len(repo.get_claims(con, 5)) == 1
    claims = repo.get_claims_for(con, [1, 5])

    assert [c["product_id"] for c in claims] == [1]


def test_get_patentは権利状況とラベルを返す(con):
    registered = repo.get_patent(con, 1)
    pending = repo.get_patent(con, 2)

    assert (registered["state"], registered["state_label"]) == ("registered", "登録済")
    assert registered["number"] == "特許第0000001号" and registered["expires"] == "2040-01-10"
    assert pending["state_label"] == "出願中" and pending["note"] == "請求範囲は要確認"
    assert repo.patent_label(pending) == "出願中"


def test_list_techsは全シーズ文書を返す(con):
    techs = repo.list_techs(con)

    assert [t["id"] for t in techs] == [1, 2, 3, 4, 5, 6]  # ニーズ文書は含まれない
    assert {t["id"]: t["patent_state"] for t in techs}[1] == "registered"
    assert {t["id"]: t["patent_state"] for t in techs}[3] is None


def test_未使用の技術は採用の行が無い技術(con):
    """F-17: 「未使用の技術」＝ decision='adopted' の行が1件も無い技術。見送り・評価中だけの技術も含む。"""
    unused = [t["id"] for t in repo.list_techs(con, unused_only=True)]

    assert unused == [2, 3, 4, 5, 6]  # 技術1は企画1で採用されているので外れる（企画2で見送りでも）


def test_特許ステータスで絞り込める(con):
    assert [t["id"] for t in repo.list_techs(con, patent_state="registered")] == [1]
    assert [t["id"] for t in repo.list_techs(con, patent_state="pending")] == [2]
    assert repo.list_techs(con, patent_state="none") == []


def test_絞り込み条件は組み合わせられる(con):
    assert [t["id"] for t in repo.list_techs(con, unused_only=True, patent_state="pending")] == [2]
    assert repo.list_techs(con, unused_only=True, patent_state="registered") == []


def test_権利状況が複数行あっても一覧で技術が重複しない(con):
    con.execute("INSERT INTO patents (seed_id, state, number) VALUES (1, 'pending', '特願2024-000009')")

    ids = [t["id"] for t in repo.list_techs(con)]
    assert ids == sorted(set(ids))
    assert repo.get_patent(con, 1)["number"] == "特願2024-000009"  # 新しい行
