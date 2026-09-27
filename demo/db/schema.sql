-- 知の越境検索 — スキーマ定義（仕様.md「データ」に対応）

CREATE TABLE IF NOT EXISTS documents (
  id            INTEGER PRIMARY KEY,
  doc_type      TEXT NOT NULL,   -- 'seed' | 'need'
  source        TEXT NOT NULL,   -- 'patent_manual' | 'dummy' | 'faq' | 'placeholder'
  title         TEXT,
  body          TEXT,            -- 【要約】＝解決手段の記述
  background    TEXT,            -- 【背景技術】（seed側のみ。ADR-0021）
  problem       TEXT,            -- 【発明が解決しようとする課題】＝問題の記述（ADR-0021）
  url           TEXT,
  pub_date      TEXT,
  category      TEXT,
  dept          TEXT,            -- 本番機能。PoCでは非表示
  summary_plain TEXT,            -- 「平たく言うと」要約（seed側のみ。F-16・ADR-0020）
  parent_id     INTEGER,
  chunk_no      INTEGER,
  content_hash  TEXT,            -- 差分検知キー（F-11）
  fetched_at    TEXT
);

-- 技術の使われ方（F-08）。PoCではデモ用の架空データ
CREATE TABLE IF NOT EXISTS tech_usage (
  id         INTEGER PRIMARY KEY,
  seed_id    INTEGER REFERENCES documents(id),
  product    TEXT,
  brand      TEXT,
  claim      TEXT,
  launched   TEXT,
  source_url TEXT
);

-- 評価・見送り記録（F-05・ADR-0022）。PoCではデモ用の架空データ
CREATE TABLE IF NOT EXISTS evaluations (
  id      INTEGER PRIMARY KEY,
  seed_id INTEGER REFERENCES documents(id),
  kind    TEXT,      -- 'evaluated' | 'dropped' | 'unevaluated'
  summary TEXT,
  detail  TEXT,
  dated   TEXT
);

-- 権利状況（F-19）
CREATE TABLE IF NOT EXISTS patents (
  id         INTEGER PRIMARY KEY,
  seed_id    INTEGER REFERENCES documents(id),
  state      TEXT,      -- 'registered' | 'pending' | 'none'
  number     TEXT,
  filed      TEXT,
  registered TEXT,
  expires    TEXT,
  note       TEXT
);

-- ベクトル（ADR-0004・0021）。1文書につきフィールドごとに1行
CREATE TABLE IF NOT EXISTS embeddings (
  doc_id INTEGER NOT NULL REFERENCES documents(id),
  -- 'body' | 'problem' | 'background' の3つ。titleは入れない（ADR-0021。入れると
  -- 短い文字列の類似度が一様に高く出て、最大値方式で常にタイトルが勝つ）
  field  TEXT NOT NULL,
  vec    BLOB NOT NULL,
  PRIMARY KEY (doc_id, field)
);

-- 検索ログ（F-04）
CREATE TABLE IF NOT EXISTS search_logs (
  id               INTEGER PRIMARY KEY,
  ts               TEXT,
  query            TEXT,
  mode             TEXT,     -- 'cross' | 'normal'
  user_dept        TEXT,     -- 'MK'固定。利用者はマーケ1種類のみ（ADR-0030）
  hit_count        INTEGER,  -- 反対側のヒット数。0なら空白領域（ADR-0008）
  top_score        REAL,     -- そのときの最高類似度（「まだ社内に無い技術」一覧で使う）
  clicked_doc_id   INTEGER,
  clicked_doc_type TEXT
);

-- 全文検索（BM25内蔵）。Janomeで分かち書き済みのテキストを入れるため unicode61（ADR-0011）
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
  title, body, problem, background,
  content='',            -- contentless。投入はbuild_db側で明示的に行う
  tokenize='unicode61'
);
