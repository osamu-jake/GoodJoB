"""db/repositories.py のテスト（骨組み。2-4b (#40) で中身を書く）。"""

import pytest


def test_u17_行が無くても例外にならない():
    """U-17: patents／project_techs／project_products に行が無い doc_id → 例外にならず「登録なし」「実績なし」を返す"""
    pytest.skip("2-4b (#40) で実装")


def test_u24_未評価は空リスト():
    """U-24: project_techs に行が1件も無い技術 → get_project_techs が空リストを返し、画面用ラベルは「未評価」になる"""
    pytest.skip("2-4b (#40) で実装")
