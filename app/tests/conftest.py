"""pytest共通のfixture。

テストは `tests/seeds/test_seeds.sql`（小さな固定データ）から組み立てたDBに対して実行する
（ADR-0015・0025。実データ `app/fixtures/seeds.sql` は転記で変わるのでテストの期待値には使わない）。
"""

from pathlib import Path

import pytest

from db import build_db

TEST_SEEDS = Path(__file__).parent / "seeds" / "test_seeds.sql"


@pytest.fixture
def db_path(tmp_path):
    """まだ存在しないDBファイルのパス（一時ディレクトリ内）。"""
    return tmp_path / "knowledge.db"


@pytest.fixture
def con(db_path):
    """テスト用seedsから組み立てた、外部キー検査ONのDB接続。"""
    connection = build_db.build(db_path, seeds_path=TEST_SEEDS)
    yield connection
    connection.close()
