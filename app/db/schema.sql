-- 知の越境検索 スキーマ（正本：docs/5文書/仕様.md「データ」）
-- 変更したら ADR.md に1行足す（ADR-0042）。列の削除・型変更はマージ前にチームへ共有する
-- 外部キーは接続ごとに PRAGMA foreign_keys = ON で検査する。ON DELETE CASCADE は付けない（ADR-0039）

-- 文書本体
CREATE TABLE documents (
  id            INTEGER PRIMARY KEY,
  doc_type      TEXT NOT NULL,   -- 'seed' | 'need'
  source        TEXT NOT NULL,   -- 'patent_manual' | 'dummy' | 'faq' | 'placeholder'
  title         TEXT,
  body          TEXT,            -- 【要約】
  background    TEXT,            -- 【背景技術】（seed側のみ。ADR-0021）
  problem       TEXT,            -- 【発明が解決しようとする課題】（ADR-0021）
  url           TEXT,
  pub_date      TEXT,
  category      TEXT,
  dept          TEXT,            -- 'R&D' | 'MK'（PoCでは非表示）
  summary_plain TEXT,            -- 一言要約（seed側のみ。F-16・ADR-0020）
  parent_id     INTEGER,
  chunk_no      INTEGER,
  content_hash  TEXT,
  fetched_at    TEXT
);

-- 企画（ADR-0039）
CREATE TABLE projects (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  brief      TEXT,
  category   TEXT,
  status     TEXT NOT NULL,      -- 'ongoing' | 'launched' | 'cancelled'
  started    TEXT,
  is_sample  INTEGER NOT NULL DEFAULT 1  -- 1なら画面に「サンプルデータ」と表示（ADR-0022・0043）
);

-- 企画×技術の判断（N:N。ADR-0039）。行が無い技術＝未評価
CREATE TABLE project_techs (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id),
  seed_id     INTEGER NOT NULL REFERENCES documents(id),
  decision    TEXT NOT NULL,     -- 'adopted' | 'dropped' | 'evaluating'
  reason      TEXT,
  detail      TEXT,
  decided_at  TEXT,
  UNIQUE (project_id, seed_id)
);

-- 採用された企画から出た商品・訴求（ADR-0031・0039）
CREATE TABLE project_products (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id),
  product     TEXT,
  brand       TEXT,
  claim       TEXT,
  launched    TEXT,
  source_url  TEXT
);

-- 権利状況（F-19）
CREATE TABLE patents (
  id         INTEGER PRIMARY KEY,
  seed_id    INTEGER NOT NULL REFERENCES documents(id),  -- ADR-0046
  state      TEXT,               -- 'registered' | 'pending' | 'none'
  number     TEXT,
  filed      TEXT,
  registered TEXT,
  expires    TEXT,
  note       TEXT
);

-- 全文検索（contentless。分かち書き済みテキストを build_db.py が明示投入する。ADR-0011・0027）
CREATE VIRTUAL TABLE documents_fts USING fts5(
  title, body, problem, background,
  content='',
  tokenize='unicode61'
);

-- フィールド別ベクトル（title は埋め込まない。ADR-0021）
CREATE TABLE embeddings (
  doc_id INTEGER NOT NULL REFERENCES documents(id),
  field  TEXT NOT NULL,          -- 'body' | 'problem' | 'background'
  vec    BLOB NOT NULL,          -- float32 を numpy.tobytes() で格納
  PRIMARY KEY (doc_id, field)
);

-- 検索ログ（F-04）
CREATE TABLE search_logs (
  id               INTEGER PRIMARY KEY,
  ts               TEXT,
  query            TEXT,
  mode             TEXT,         -- 'cross' | 'normal'
  user_dept        TEXT,         -- 'MK'固定（ADR-0030）
  hit_count        INTEGER,
  top_score        REAL,
  clicked_doc_id   INTEGER,
  clicked_doc_type TEXT
);
