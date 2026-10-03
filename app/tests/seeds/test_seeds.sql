-- テスト専用の小さな固定データ（source='placeholder'）。実データ fixtures/seeds.sql とは別物。
-- 外部キーの参照先から順に並べる（documents → projects → project_techs / project_products / patents）

INSERT INTO documents (id, doc_type, source, title, body, background, problem, url, category, summary_plain) VALUES
(1, 'seed', 'placeholder', '皮脂吸着性微粒子を含有する整髪料組成物',
 '多孔質シリカ微粒子が頭皮から出る皮脂を吸着し、時間が経っても髪の形を保つ整髪料組成物。',
 '従来の整髪料は油分が多く、皮脂と混ざると髪が重くなりやすかった。',
 '時間の経過とともに皮脂が出て、毛先が固まり整髪料の効果が落ちる。',
 'https://example.test/seed/1', 'ヘアスタイリング', '皮脂を吸う粉で、夕方まで髪型が崩れにくくなる技術。'),
(2, 'seed', 'placeholder', '水溶性ポリマーによる柔軟なセット保持',
 '水溶性ポリマーが毛髪の表面に薄い皮膜をつくり、やわらかく形を保持する。',
 '従来のセット剤は皮膜が硬く、触るとごわつくことがあった。',
 'セット剤の皮膜が硬くなり、指通りが悪くなる。',
 'https://example.test/seed/2', 'ヘアスタイリング', '薄くやわらかい膜で髪型を保つ技術。'),
(3, 'seed', 'placeholder', '耐水性紫外線吸収剤の分散組成物',
 '紫外線吸収剤を樹脂粒子に内包し、水や汗に触れても流れにくくする。',
 '従来の日焼け止めは汗で流れて効果が低下しやすかった。',
 '汗をかくと日焼け止めが流れ落ちて、紫外線防止効果が続かない。',
 'https://example.test/seed/3', 'サンケア', '汗に強い日焼け止めをつくる技術。'),
(4, 'seed', 'placeholder', '保湿成分を内包したマイクロカプセル',
 '保湿成分を内包したカプセルが角層に留まり、水分を保つ。',
 '従来の保湿剤は塗布後に短時間で失われていた。',
 '肌が乾燥して粉をふき、保湿効果が長続きしない。',
 'https://example.test/seed/4', 'スキンケア', '保湿成分を少しずつ放つカプセルの技術。'),
(5, 'seed', 'placeholder', '低摩擦係数の被膜形成剤',
 'シリコーン変性ポリマーを用いて被膜表面の摩擦係数を下げる。',
 '重い使用感の被膜剤が多く、摩擦が大きいことが課題であった。',
 '被膜の摩擦係数が高く、塗布時にひっかかりが生じる。',
 'https://example.test/seed/5', 'スキンケア', NULL),
(6, 'seed', 'placeholder', '香料の徐放性マイクロカプセル',
 '香料を内包したカプセルが摩擦で壊れ、香りを長く放出する。',
 NULL,
 '香りが数時間で消えてしまう。',
 'https://example.test/seed/6', 'フレグランス', '香りを長持ちさせるカプセルの技術。'),
(11, 'need', 'dummy', '夕方の前髪のべたつき',
 '夕方になると前髪がベタついてしまう',
 NULL, NULL, NULL, 'ヘアスタイリング', NULL),
(12, 'need', 'dummy', '汗で日焼け止めが流れる',
 '汗をかくと日焼け止めが落ちてしまうのが気になる',
 NULL, NULL, NULL, 'サンケア', NULL),
(13, 'need', 'dummy', '香りが続かない',
 '朝つけた香りが昼には消えてしまう',
 NULL, NULL, NULL, 'フレグランス', NULL),
(14, 'need', 'faq', '乾燥して粉をふく',
 '冬になると肌が乾燥して粉をふいてしまう',
 NULL, NULL, 'https://example.test/faq/1', 'スキンケア', NULL);

INSERT INTO projects (id, name, brief, category, status, started, is_sample) VALUES
(1, '【サンプル】夕方まで崩れないワックス', '夕方になっても前髪がべたつかないスタイリング剤', 'ヘアスタイリング', 'launched', '2024-04', 1),
(2, '【サンプル】ミストタイプ整髪料', '軽い使用感のミストで髪型を整える', 'ヘアスタイリング', 'cancelled', '2024-09', 1);

INSERT INTO project_techs (id, project_id, seed_id, decision, reason, detail, decided_at) VALUES
(1, 1, 1, 'adopted', '皮脂吸着で崩れにくい', '保持力の評価で従来比を上回った', '2024-06'),
(2, 2, 1, 'dropped', 'ミストに分散させると安定性が落ちた', '40℃保存で沈降', '2024-11'),
(3, 1, 2, 'evaluating', NULL, NULL, '2024-07');

INSERT INTO project_products (id, project_id, product, brand, claim, launched, source_url) VALUES
(1, 1, 'サンプル・ハードワックス', 'サンプルブランド', '夕方まで前髪さらさら', '2025-03', NULL);

INSERT INTO patents (id, seed_id, state, number, filed, registered, expires, note) VALUES
(1, 1, 'registered', '特許第0000001号', '2020-01-10', '2022-05-20', '2040-01-10', NULL),
(2, 2, 'pending', '特願2023-000002', '2023-03-01', NULL, NULL, '請求範囲は要確認');
