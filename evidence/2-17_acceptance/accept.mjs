// 2-17（#28）受入テスト6件（A-01・A-01b・A-02・A-03・A-05・A-06）を本番URLで実施し、結果とスクショを残す。
// ヘッドレスChromeをCDPで直接操作する（追加パッケージなし。Node 22以上）。2-16 の prod_shot.mjs と同じ作り。
// 実行（リポジトリ直下から）:
//   node evidence/2-17_acceptance/accept.mjs | tee evidence/2-17_acceptance/result.txt
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const OUT = dirname(fileURLToPath(import.meta.url));
const APP_URL = "https://goodjob-idea-bridge.streamlit.app/~/+/";
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PORT = 9334;
const NO_HIT_QUERY = "宇宙ロケットの燃料タンクを軽量化したい。";   // 社内に該当しないニーズ文（A-06）

const chrome = spawn(CHROME, [
  "--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "accept_"))}`,
  "--no-first-run", "--no-default-browser-check", "--lang=ja", "about:blank",
], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(...a);

let targets;
for (let i = 0; i < 50; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json(); break; } catch { await sleep(200); }
}
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let seq = 0;
const pending = new Map();
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
});
const send = (method, params = {}) => new Promise((r) => { const i = ++seq; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => (await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
const waitFor = async (expr, ms) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (await ev(expr)) return true; await sleep(500); } return false; };
const viewport = (height) => send("Emulation.setDeviceMetricsOverride", { width: 1400, height, deviceScaleFactor: 1, mobile: false });
const shot = async (name, height = 1000) => {
  await viewport(height); await sleep(1200);
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(OUT, name), Buffer.from(r.result.data, "base64"));
  log("  スクショ:", name);
  await viewport(1000); await sleep(500);
};
const click = (text, exact = true) => ev(`(() => {
  const b = [...document.querySelectorAll('button')].find(b => ${exact ? `b.innerText.trim() === ${JSON.stringify(text)}` : `b.innerText.includes(${JSON.stringify(text)})`});
  if (!b) return false; b.click(); return true; })()`);
const pickMode = (label) => ev(`(() => {
  const l = [...document.querySelectorAll('[data-testid="stRadio"] label')].find(l => l.innerText.trim() === ${JSON.stringify(label)});
  if (!l) return false; l.click(); return true; })()`);
const body = () => ev("document.body.innerText");
const HEAD = `(document.body.innerText.match(/\\d+ 件　（[^）]+）/) || [''])[0]`;
const titles = async () => ev(`[...document.body.innerText.matchAll(/\\n([^\\n]+)\\n\\nシーズ（技術）\\n/g)].map(x => x[1])`);

const results = [];
const verdict = (id, ok, note) => { results.push([id, ok]); log(`【${id}】${ok ? "○" : "×"} ${note}`); };

// 検索窓に文を入れて検索する（サイドバーのデモボタン、または直接入力）
const setQuery = async (kind, text) => {
  if (kind) { await click(kind, false); await sleep(2500); return; }
  await ev(`(() => { const t = document.querySelector('textarea[aria-label*="企画案"]'); t.focus(); t.select(); })()`);
  await send("Input.insertText", { text });
  await ev(`document.querySelector('textarea[aria-label*="企画案"]').blur()`);
  await sleep(1500);
};
const search = async (ready) => {
  await click("検索");
  return waitFor(ready, 90000);
};
// 件数の行の数と、描画されたカードの枚数が一致し、少し待っても変わらない状態（描画の途中で数えないため）
const CARDS_READY = `(() => { const m = document.body.innerText.match(/(\\d+) 件　（/); const n = document.querySelectorAll('[class*="st-key-card-"]').length; return !!m && n === parseInt(m[1]); })()`;
const settle = async () => { await waitFor(CARDS_READY, 60000); await sleep(3000); return waitFor(CARDS_READY, 10000); };

try {
  await send("Page.enable"); await send("Runtime.enable"); await viewport(1000);
  await send("Page.navigate", { url: APP_URL });
  const up = await waitFor(`!!document.querySelector('textarea[aria-label*="企画案"]')`, 240000);
  log(`本番URL: ${APP_URL.replace("/~/+/", "/")}  起動: ${up ? "OK" : "NG"}  実施: ${new Date().toISOString()}`);
  if (!up) throw new Error("アプリが開きません");
  await sleep(2000);

  // ── A-01：短文。キーワードのみ0件 → 両方併用で1件以上
  log("\n■ A-01 ニーズ文でキーワード検索0件でもハイブリッドなら技術が返る");
  await setQuery("①生活者の声");
  log("  入力:", await ev(`document.querySelector('textarea[aria-label*="企画案"]').value`));
  await pickMode("キーワードのみ"); await sleep(2500);
  const kw0 = await search(`document.body.innerText.includes('キーワード検索では0件でした')`);
  await shot("A-01_keyword_0.png");
  await pickMode("両方併用"); await sleep(2500);
  const hy = await search(`/\\d+ 件　（/.test(document.body.innerText)`);
  await settle();
  const head1 = await ev(HEAD);
  await shot("A-01_hybrid.png", 2000);
  verdict("A-01", kw0 && hy && parseInt(head1) >= 1, `キーワードのみ=0件の案内${kw0 ? "あり" : "なし"}／両方併用=${head1}`);

  // ── A-02：シーズ／ニーズのラベル（A-01 の結果カード）
  log("\n■ A-02 シーズ／ニーズのラベルで判別できる");
  const t1 = await titles();
  const nCards = await ev(`document.querySelectorAll('[class*="st-key-card-"]').length`);
  const nBadge = await ev(`[...document.querySelectorAll('[class*="st-key-card-"]')].filter(c => /シーズ（技術）|ニーズ（生活者の声）/.test(c.innerText)).length`);
  verdict("A-02", nCards > 0 && nCards === nBadge, `カード${nCards}枚中${nBadge}枚にラベル表示（例: ${t1.slice(0, 2).join(" / ")}）`);

  // ── A-05：課題の表示（A-01 の結果カード）
  log("\n■ A-05 課題の表示で、ニーズに対応するか判断できる");
  const nProblem = await ev(`[...document.querySelectorAll('[class*="st-key-card-"]')].filter(c => c.innerText.includes('この技術が解決しようとしている課題')).length`);
  const sample = await ev(`(() => { const c = document.querySelector('[class*="st-key-card-"]'); const t = c.innerText; const i = t.indexOf('この技術が解決しようとしている課題'); return t.slice(i, i + 140).replace(/\\n+/g, ' '); })()`);
  verdict("A-05", nProblem === nCards && nCards > 0, `カード${nCards}枚中${nProblem}枚に課題を表示。例: ${sample}`);

  // ── A-01b：長文。キーワードのみでは正解が上位に来ない／両方併用で1位
  log("\n■ A-01b 企画案の長文でも、キーワードだけでは正解が上位に来ない");
  const CORRECT = "非乳化型固形状整髪剤組成物（洗い流しやすい）";   // 特開2020-152643
  await setQuery("②企画案");
  await pickMode("キーワードのみ"); await sleep(2500);
  await search(`/\\d+ 件　（/.test(document.body.innerText)`);
  await settle();
  const kwT = await titles();
  await shot("A-01b_keyword.png", 2600);
  await pickMode("両方併用"); await sleep(2500);
  await search(`/\\d+ 件　（/.test(document.body.innerText)`);
  await settle();
  const hyT = await titles();
  await shot("A-01b_hybrid.png", 2600);
  const kwRank = kwT.indexOf(CORRECT) + 1;
  verdict("A-01b", kwT[0] !== CORRECT && hyT[0] === CORRECT,
    `キーワードのみ: 1位=${kwT[0]}、正解は${kwRank ? kwRank + "位" : "圏外"}／両方併用: 1位=${hyT[0]}`);

  // ── A-03：見送り記録（頭髪用セット剤組成物 id=27 は dropped の行がある）
  log("\n■ A-03 過去に検討して断念した記録が表示される");
  const opened = await ev(`(() => { const b = document.querySelector('.st-key-detail-27 button'); if (!b) return false; b.click(); return true; })()`);
  await waitFor(`!!document.querySelector('[role="dialog"]')`, 30000); await sleep(4000);
  const dlg = await ev(`document.querySelector('[role="dialog"]')?.innerText || ''`);
  const dropped = /見送り：/.test(dlg) && dlg.includes("サンプルデータ") && /判断 \d{4}-\d{2}-\d{2}/.test(dlg);
  const line = (dlg.match(/[^\n]*見送り：[^\n]*/) || [""])[0];
  await shot("A-03_dropped.png", 2200);
  verdict("A-03", opened && dropped, `詳細を開いた=${opened}。「${line}」／サンプルデータ表示=${dlg.includes("サンプルデータ")}／判断日あり=${/判断 \d{4}/.test(dlg)}`);
  await ev(`(() => { const b = [...document.querySelectorAll('[role="dialog"] button')].find(b => b.innerText.includes('閉じる')); if (b) b.click(); })()`);
  await sleep(1500);

  // ── A-06：該当しないニーズ文
  log("\n■ A-06 十分一致する技術がない場合も画面が空にならない");
  await setQuery(null, NO_HIT_QUERY);
  log("  入力:", await ev(`document.querySelector('textarea[aria-label*="企画案"]').value`));
  const nh = await search(`document.body.innerText.includes('十分に一致する技術は見つかりませんでした')`);
  const fold = await ev(`document.body.innerText.includes('関連度の低い候補を見る')`);
  const foldText = (await ev(`(document.body.innerText.match(/関連度の低い候補を見る（\\d+件）/) || [''])[0]`));
  await shot("A-06_no_hit.png");
  verdict("A-06", nh && fold, `固定の案内文=${nh ? "あり" : "なし"}／折りたたみ=${foldText || "なし"}`);

  log(`\n結果: ${results.filter((r) => r[1]).length}/${results.length} 件 ○`);
} finally {
  ws.close();
  chrome.kill();
}
