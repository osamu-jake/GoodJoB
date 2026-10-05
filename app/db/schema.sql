-- 知の越境検索 — スキーマ定義（仕様.md「データ」の8テーブル。ADR-0039・0046）
-- DBに触るときは db/connection.py の connect() を使うこと（外部キー検査をONにするため）

-- 文書本体
CREATE TABLE documents (
  id            INTEGER PRIMARY KEY,
  doc_type      TEXT NOT NULL,   -- 'seed' | 'need'
  source        TEXT NOT NULL,   -- 'patent_manual' | 'dummy' | 'faq' | 'placeholder'
  title         TEXT,
  body          TEXT,            -- 【要約】＝解決手段の記述
  background    TEXT,            -- 【背景技術】（seed側のみ。ADR-0021）
  problem       TEXT,            -- 【発明が解決しようとする課題】（ADR-0021）
  url           TEXT,
  pub_date      TEXT,
  category      TEXT,
  dept          TEXT,            -- 本番機能。PoCでは非表示
  summary_plain TEXT,            -- 「平たく言うと」要約（seed側のみ。ADR-0020）
  parent_id     INTEGER,
  chunk_no      INTEGER,
  content_hash  TEXT,
  fetched_at    TEXT
);

-- 企画（社内の商品企画・検討案件。ADR-0039）
CREATE TABLE projects (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  brief      TEXT,
  category   TEXT,
  status     TEXT NOT NULL,       -- 'ongoing' | 'launched' | 'cancelled'
  started    TEXT,
  is_sample  INTEGER NOT NULL DEFAULT 1  -- 1なら画面に「サンプルデータ」と表示（ADR-0022・0043）
);

-- 企画×技術の判断（N:N。1行＝1組の企画・技術。ADR-0039）
-- 「未評価」は行を持たない。その技術の行が1件も無いことで表す
CREATE TABLE project_techs (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id),
  seed_id     INTEGER NOT NULL REFERENCES documents(id),
  decision    TEXT NOT NULL,      -- 'adopted' | 'dropped' | 'evaluating'
  reason      TEXT,
  detail      TEXT,
  decided_at  TEXT,
  UNIQUE (project_id, seed_id)
);

-- 採用された企画から出た商品・訴求（1企画＝1商品の前提。ADR-0031・0039）
CREATE TABLE project_products (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id),
  product     TEXT,
  brand       TEXT,
  claim       TEXT,
  launched    TEXT,
  source_url  TEXT
);

-- 権利状況（F-19）。seed_id は NOT NULL（どの技術にも紐づかない権利状況は意味を持たない。ADR-0046）
CREATE TABLE patents (
  id         INTEGER PRIMARY KEY,
  seed_id    INTEGER NOT NULL REFERENCES documents(id),
  state      TEXT,      -- 'registered' | 'pending' | 'expired' | 'rejected' | 'none'（ADR-0053）
  number     TEXT,
  filed      TEXT,
  registered TEXT,
  expires    TEXT,
  note       TEXT
);

-- 全文検索（FTS5、BM25内蔵）。4列すべてを索引する contentless 構成（ADR-0027）。
-- documents へ INSERT しただけでは索引は空のまま。build_db.py が Janome で分かち書きした
-- テキストを rowid = documents.id で明示的に入れる（トリガ同期は使わない）
CREATE VIRTUAL TABLE documents_fts USING fts5(
  title, body, problem, background,
  content='',
  tokenize='unicode61'
);

-- ベクトル（ADR-0004・0021）。1文書につきフィールドごとに1行
-- field は 'body' | 'problem' | 'background' の3つ。title は埋め込まない（ADR-0021）
CREATE TABLE embeddings (
  doc_id INTEGER NOT NULL REFERENCES documents(id),
  field  TEXT NOT NULL,
  vec    BLOB NOT NULL,   -- float32配列を numpy.tobytes() で格納（正規化済み）
  PRIMARY KEY (doc_id, field)
);

-- 検索ログ（F-04）
CREATE TABLE search_logs (
  id               INTEGER PRIMARY KEY,
  ts               TEXT,
  query            TEXT,
  mode             TEXT,     -- 'cross' | 'normal'
  user_dept        TEXT,     -- 'MK'固定（ADR-0030）
  hit_count        INTEGER,  -- 反対側のヒット数。0なら空白領域（ADR-0008）
  top_score        REAL,
  clicked_doc_id   INTEGER,
  clicked_doc_type TEXT
);
