"""db/connection.py のテスト（U-27）。外部キー検査が効いていること。"""

import sqlite3

import pytest


def test_u27_存在しないseed_idでproject_techsへ登録するとエラー(con):
    """U-27: 存在しない seed_id で project_techs へ INSERT → 外部キー制約違反。"""
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        con.execute("INSERT INTO project_techs (project_id, seed_id, decision) VALUES (1, 9999, 'adopted')")


def test_u27_判断の行がある技術をdocumentsから削除するとエラー(con):
    """U-27: 判断の行がある技術を documents から DELETE → 外部キー制約違反（ON DELETE CASCADE は付けない）。"""
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        con.execute("DELETE FROM documents WHERE id = 1")
    # 消えていない
    assert con.execute("SELECT COUNT(*) FROM documents WHERE id = 1").fetchone()[0] == 1


def test_u27_存在しないseed_idでpatentsへ登録するとエラー(con):
    """ADR-0046: patents も存在しない技術を指せない。"""
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        con.execute("INSERT INTO patents (seed_id, state) VALUES (9999, 'none')")


def test_存在しない企画でproject_productsへ登録するとエラー(con):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        con.execute("INSERT INTO project_products (project_id, product) VALUES (9999, 'x')")


def test_どこからも参照されない文書は削除できる(con):
    con.execute("DELETE FROM documents WHERE id = 14")
    assert con.execute("SELECT COUNT(*) FROM documents WHERE id = 14").fetchone()[0] == 0
