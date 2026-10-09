// 3-7（#30）受入テスト A-07（初回）を本番URLで実施し、結果とスクショを残す。
// ヘッドレスChromeをCDPで直接操作する（追加パッケージなし。Node 22以上）。2-16 の prod_shot.mjs と同じ作り。
// 実行（リポジトリ直下から）:
//   node evidence/3-7_regression/a07.mjs > evidence/3-7_regression/a07_result.txt
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const OUT = dirname(fileURLToPath(import.meta.url));
const APP_URL = "https://goodjob-idea-bridge.streamlit.app/~/+/";
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PORT = 9335;

const chrome = spawn(CHROME, [
  "--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "a07_"))}`,
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
const dialogText = () => ev(`document.querySelector('[role="dialog"]')?.innerText || ''`);
const closeDialog = async () => {
  await ev(`(() => { const b = [...document.querySelectorAll('[role="dialog"] button')].find(b => b.innerText.includes('閉じる')); if (b) b.click(); })()`);
  await sleep(2000);
};
const openFromTab2 = async (id) => {
  const ok = await ev(`(() => { const b = document.querySelector('.st-key-open-${id} button'); if (!b) return false; b.scrollIntoView(); b.click(); return true; })()`);
  await waitFor(`!!document.querySelector('[role="dialog"]')`, 30000);
  await sleep(5000);   // 「似た課題を解く技術」「関連する声」の検索が終わるまで
  return ok;
};

try {
  await send("Page.enable"); await send("Runtime.enable"); await viewport(1000);
  await send("Page.navigate", { url: APP_URL });
  const up = await waitFor(`!!document.querySelector('textarea[aria-label*="企画案"]')`, 240000);
  log(`本番URL: ${APP_URL.replace("/~/+/", "/")}  起動: ${up ? "OK" : "NG"}  実施: ${new Date().toISOString()}`);
  if (!up) throw new Error("アプリが開きません");
  await sleep(2000);

  log("\n■ A-07 技術を1件開くと「この技術は何に使えそうか」の材料が記録で示される");
  const tab = await ev(`(() => { const t = [...document.querySelectorAll('[role="tab"]')].find(t => t.innerText.includes('技術データベース')); if (!t) return false; t.click(); return true; })()`);
  await waitFor(`!!document.querySelector('[class*="st-key-open-"]')`, 60000);
  await sleep(2000);
  log(`  タブ②を開いた: ${tab}`);
  await shot("A-07_tab2_list.png", 1400);

  // (1) 採用と見送りの両方がある技術（id=26）
  const o1 = await openFromTab2(26);
  const d1 = await dialogText();
  const title1 = (d1.match(/技術の詳細\n+([^\n]+)/) || [, ""])[1];
  log(`  開いた技術(1): id=26 ${title1}（開けた: ${o1}）`);
  await shot("A-07_detail_26.png", 3400);
  const claims = /自社での使われ方/.test(d1) && /「[^」]+」/.test(d1) && /\/\s*(\d{4}-\d{2}|\d{4})/.test(d1.replace(/／/g, "/"));
  const decisions = /企画ごとの判断/.test(d1) && /採用：/.test(d1) && /見送り：/.test(d1);
  const similar = /似た課題を解く技術と、その使われ方/.test(d1) && !/似た課題を解く技術は見つかりませんでした/.test(d1);
  const voices = /関連する収集済みの声/.test(d1) && d1.includes("母集団を代表しません");
  const sample = d1.includes("サンプルデータ");
  const claimLine = (d1.match(/自社での使われ方\n+([\s\S]*?)\n+企画ごとの判断/) || [, ""])[1].replace(/\n+/g, " ／ ");
  const decLines = [...d1.matchAll(/[✅⛔🔄] [^\n]+/g)].map((m) => m[0]).slice(0, 4);
  log(`  使われ方(商品・訴求・時期): ${claims ? "あり" : "なし"}  例: ${claimLine}`);
  log(`  企画ごとの判断: ${decisions ? "採用・見送りとも表示" : "不足"}  ${decLines.join(" | ")}`);
  log(`  似た課題を解く技術: ${similar ? "あり" : "なし"}`);
  log(`  関連する声と「母集団を代表しません」の注記: ${voices ? "あり" : "なし"}`);
  log(`  「サンプルデータ」の表示: ${sample ? "あり" : "なし"}`);
  await closeDialog();

  // (2) どの企画でも検討されていない技術（id=2）は「未評価」
  const o2 = await openFromTab2(2);
  const d2 = await dialogText();
  const title2 = (d2.match(/技術の詳細\n+([^\n]+)/) || [, ""])[1];
  log(`  開いた技術(2): id=2 ${title2}（開けた: ${o2}）`);
  await shot("A-07_detail_2_unevaluated.png", 3000);
  const uneval = /未評価/.test(d2) && d2.includes("どの企画でもまだ検討されていません");
  log(`  どの企画でも未検討: ${uneval ? "「未評価」と表示" : "表示なし"}`);

  verdict("A-07", o1 && claims && decisions && similar && voices && sample && o2 && uneval,
    `使われ方=${claims}／判断(採用・見送り)=${decisions}／似た課題の技術=${similar}／声と注記=${voices}／サンプルデータ=${sample}／未評価=${uneval}`);
  log(`\n結果: ${results.filter((r) => r[1]).length}/${results.length} 件 ○`);
} finally {
  ws.close();
  chrome.kill();
}
