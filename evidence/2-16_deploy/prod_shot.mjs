// 2-16（#42）本番URLの画面を撮る：ヘッドレスChromeをCDPで直接操作する（追加パッケージなし。Node 22以上）
// トップ → ①短文で検索 → ②長文で検索 → ②の1位の詳細（モーダル）の順に撮り、このフォルダに保存する
// 実行（リポジトリ直下から）:
//   node evidence/2-16_deploy/prod_shot.mjs
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const OUT = dirname(fileURLToPath(import.meta.url));
// Streamlit Community Cloud は外枠のページの中に iframe でアプリを入れる。アプリ本体（/~/+/）を直接開く
const APP_URL = "https://goodjob-idea-bridge.streamlit.app/~/+/";
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PORT = 9333;

const chrome = spawn(CHROME, [
  "--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "prod_shot_"))}`,
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
const shot = async (name) => {
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(OUT, name), Buffer.from(r.result.data, "base64"));
  log("保存:", name);
};
// ボタンを文字で探して押す（exact=false なら部分一致）
const click = (text, exact = true) => ev(`(() => {
  const b = [...document.querySelectorAll('button')].find(b => ${exact ? `b.innerText.trim() === ${JSON.stringify(text)}` : `b.innerText.includes(${JSON.stringify(text)})`});
  if (!b) return false; b.click(); return true; })()`);
const RESULT_HEAD = `(document.body.innerText.match(/\\d+ 件　（[^）]+）/) || [''])[0]`;
const TITLES = `[...document.body.innerText.matchAll(/\\n([^\\n]+)\\n\\nシーズ（技術）\\n\\n関連度\\n\\n(\\d+)%/g)].map(x => x[1] + ' ' + x[2] + '%')`;

try {
  await send("Page.enable");
  await send("Runtime.enable");
  await viewport(1000);
  const t0 = Date.now();
  await send("Page.navigate", { url: APP_URL });
  const ready = await waitFor(`!!document.querySelector('textarea[aria-label*="企画案"]')`, 180000);
  log(`検索窓の表示: ${ready ? "OK" : "NG"}（${((Date.now() - t0) / 1000).toFixed(1)} 秒。ログイン画面なし）`);
  await sleep(2000);
  await shot("prod_top.png");

  for (const [label, name] of [["①生活者の声", "prod_demo1.png"], ["②企画案", "prod_demo2.png"]]) {
    await ev(`window.__prev = ${RESULT_HEAD}`);
    await click(label, false); // サイドバーの入力例ボタンで検索窓に入れる
    await sleep(2500);
    log(`\n■ ${label}: ${await ev(`document.querySelector('textarea[aria-label*="企画案"]').value`)}`);
    await click("検索");
    await waitFor(`(${RESULT_HEAD}) && (${RESULT_HEAD}) !== window.__prev`, 60000);
    await sleep(3000);
    log(await ev(RESULT_HEAD));
    (await ev(TITLES)).forEach((t, i) => log(`  ${i + 1}. ${t}`));
    await viewport(2600);
    await sleep(1500);
    await shot(name);
    await viewport(1000);
    await sleep(800);
  }

  await click("エビデンス・使われ方を見る", false); // ②の1位の詳細
  await waitFor(`!!document.querySelector('[role="dialog"]')`, 30000);
  await sleep(3000);
  await viewport(1800);
  await sleep(1500);
  await shot("prod_detail.png");
} finally {
  ws.close();
  chrome.kill();
}
