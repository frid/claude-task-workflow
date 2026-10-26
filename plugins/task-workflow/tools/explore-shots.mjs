#!/usr/bin/env node
// task-explore 步驟 4／5：替每個變體截桌面 1440 與手機 375 畫面、量測（溢出／文字對比／元素數／console error），
// 選配 --html 產生 variants.html 並排比較頁。零 npm 依賴；用專案的 tools/cdp-harness.mjs（需 Chrome）。
// 用法：
//   node explore-shots.mjs --harness <專案>/tools/cdp-harness.mjs --out <專案>/explore/ST-35a \
//        [--example bookstore-a] [--step 'guideGoto(1)'] [--focus '#valueChainEditor'] [--html] \
//        [--label A='橫帶疊層|取捨一句' ...] A=<worktreeA>/index.html B=<worktreeB>/index.html ...
// 輸出：<out>/<字母>-desktop.png、<字母>-desktop-focus.png、<字母>-mobile.png、metrics.json、（--html）variants.html
import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, basename } from 'node:path';
import { execSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const argv = process.argv.slice(2);
const opt = { labels: {}, variants: [] };
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--harness') opt.harness = argv[++i];
  else if (a === '--out') opt.out = argv[++i];
  else if (a === '--example') opt.example = argv[++i];
  else if (a === '--step') opt.step = argv[++i];
  else if (a === '--focus') opt.focus = argv[++i];
  else if (a === '--html') opt.html = true;
  else if (a === '--label') { const [k, v] = argv[++i].split(/=(.*)/s); opt.labels[k] = v; }
  else if (/^[A-Z]=/.test(a)) opt.variants.push({ key: a[0], file: resolve(a.slice(2)) });
  else throw new Error('不認得的參數：' + a);
}
if (!opt.harness || !opt.out || !opt.variants.length) { console.error('需要 --harness、--out 與至少一個 A=<index.html>'); process.exit(2); }
const { launch } = await import(pathToFileURL(resolve(opt.harness)).href);
mkdirSync(opt.out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));

// 頁內量測：溢出、文字對比（WCAG）、元素數
const METRIC = focus => `(()=>{
  const focusSel=${JSON.stringify(focus || '')};
  const roots=focusSel? [...document.querySelectorAll(focusSel)] : [document.body];
  const lum=c=>{const m=c.match(/[\\d.]+/g);if(!m)return null;const [r,g,b]=m.map(Number);const a=m[3]==null?1:Number(m[3]);if(a===0)return null;
    const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b)};
  // 背景：先看 backgroundColor，透明時改看 backgroundImage 漸層的第一個色（單元多用漸層底）
  const bgOf=el=>{let e=el;while(e){const cs=getComputedStyle(e);let l=lum(cs.backgroundColor);if(l==null&&cs.backgroundImage&&cs.backgroundImage!=='none'){const m=cs.backgroundImage.match(/rgba?\([^)]*\)/);if(m)l=lum(m[0]);}if(l!=null)return l;e=e.parentElement;}return 1;};
  let nodes=0, overflowEls=0, minC=99, low=0, textEls=0;
  for(const root of roots){
    const all=[root,...root.querySelectorAll('*')]; nodes+=all.length;
    for(const el of all){
      const cs=getComputedStyle(el); if(cs.display==='none'||cs.visibility==='hidden'||+cs.opacity<0.5||!el.offsetWidth) continue; // hover 才顯示的淡化元素不算
      if(el.scrollWidth>el.clientWidth+1 && cs.overflowX!=='visible' && cs.overflowX!=='auto' && cs.overflowX!=='scroll') overflowEls++;
      const own=[...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()) || (el.matches('input,textarea')&&el.value);
      if(!own) continue;
      const fl=lum(cs.color); if(fl==null) continue; const bl=bgOf(el);
      const c=(Math.max(fl,bl)+0.05)/(Math.min(fl,bl)+0.05); textEls++; if(c<minC)minC=c; if(c<4.5)low++;
    }
  }
  const r0=roots[0]?roots[0].getBoundingClientRect():null;
  return { pageOverflow: document.documentElement.scrollWidth>innerWidth, pageScrollWidth: document.documentElement.scrollWidth,
    innerWidth, focusFound: roots.length, focusWidth: r0?Math.round(r0.width):null, focusHeight: r0?Math.round(r0.height):null,
    overflowEls, textEls, minContrast: textEls?+minC.toFixed(2):null, lowContrast: low, nodes };
})()`;

async function one(v, width, height, tag) {
  const h = await launch({ width, height });
  const res = { errors: [] };
  try {
    await h.open(v.file);
    await h.ev('localStorage.clear(); 0'); await h.open(v.file);
    if (opt.example) await h.loadExample(opt.example);
    if (opt.step) { await h.ev(opt.step + '; 0'); await sleep(600); }
    await sleep(400);
    Object.assign(res, await h.ev(METRIC(opt.focus)));
    res.shot = `${v.key}-${tag}.png`; await h.shot(null, resolve(opt.out, res.shot));
    if (opt.focus && res.focusFound && tag === 'desktop') {
      res.shotFocus = `${v.key}-${tag}-focus.png`;
      try { await h.shot(opt.focus.split(',')[0].trim(), resolve(opt.out, res.shotFocus)); } catch (e) { res.shotFocus = null; }
    }
  } catch (e) { res.fatal = String(e.message || e); }
  res.errors = h.errors(); await h.close();
  return res;
}

const metrics = {};
for (const v of opt.variants) {
  const dir = v.file.replace(/\/index\.html$/, '');
  let branch = '', commit = '';
  try { branch = execSync(`git -C "${dir}" branch --show-current`).toString().trim(); commit = execSync(`git -C "${dir}" log -1 --format=%h`).toString().trim(); } catch {}
  console.log(`▶ ${v.key} ${v.file}`);
  metrics[v.key] = { file: v.file, branch, commit, label: opt.labels[v.key] || '',
    desktop: await one(v, 1440, 900, 'desktop'), mobile: await one(v, 375, 812, 'mobile') };
  const d = metrics[v.key].desktop, m = metrics[v.key].mobile;
  console.log(`   桌面：溢出 ${d.pageOverflow ? '是' : '否'}/${d.overflowEls} 元素  最低對比 ${d.minContrast}  對比不足 ${d.lowContrast}  節點 ${d.nodes}  error ${d.errors.length}${d.fatal ? '  ⚠ ' + d.fatal : ''}`);
  console.log(`   手機：溢出 ${m.pageOverflow ? '是' : '否'}/${m.overflowEls} 元素  最低對比 ${m.minContrast}  對比不足 ${m.lowContrast}  節點 ${m.nodes}  error ${m.errors.length}${m.fatal ? '  ⚠ ' + m.fatal : ''}`);
}
writeFileSync(resolve(opt.out, 'metrics.json'), JSON.stringify(metrics, null, 2));

if (opt.html) {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const row = (name, f) => `<tr><th>${name}</th>${opt.variants.map(v => `<td>${f(metrics[v.key])}</td>`).join('')}</tr>`;
  const fmt = (r) => `${r.pageOverflow ? '頁面溢出' : '無頁面溢出'}／${r.overflowEls} 元素內溢出`;
  const cols = opt.variants.map(v => {
    const m = metrics[v.key]; const [name, note] = (m.label || v.key).split('|');
    return `<section class="v"><h2><span class="k">${v.key}</span> ${esc(name)}</h2><p class="note">${esc(note || '')}</p>
      <p class="br">分支 <code>${esc(m.branch)}</code> @ <code>${esc(m.commit)}</code></p>
      <h3>桌面 1440</h3>${m.desktop.shotFocus ? `<a href="${m.desktop.shotFocus}"><img src="${m.desktop.shotFocus}" alt="${v.key} 桌面 focus"></a>` : ''}
      <a href="${m.desktop.shot}"><img src="${m.desktop.shot}" alt="${v.key} 桌面" class="full"></a>
      <h3>手機 375</h3><a href="${m.mobile.shot}"><img src="${m.mobile.shot}" alt="${v.key} 手機" class="mob"></a>
      ${m.desktop.fatal || m.mobile.fatal ? `<p class="bad">⚠ ${esc(m.desktop.fatal || m.mobile.fatal)}</p>` : ''}
      ${m.desktop.errors.length ? `<details><summary>console error ${m.desktop.errors.length}</summary><pre>${esc(m.desktop.errors.join('\n'))}</pre></details>` : ''}
    </section>`;
  }).join('');
  const html = `<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>${esc(basename(opt.out))} 變體比較</title>
<style>
:root{--bg:#f6f7f9;--fg:#1d2430;--mut:#5b6472;--card:#fff;--line:#d9dee6;--bad:#b42318}
@media(prefers-color-scheme:dark){:root{--bg:#14181f;--fg:#e8ecf2;--mut:#9aa6b6;--card:#1d232d;--line:#333c4a;--bad:#ff8a80}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,"Noto Sans TC",sans-serif}
h1{font-size:20px;margin:0 0 12px}.grid{display:grid;grid-template-columns:repeat(${opt.variants.length},minmax(0,1fr));gap:16px}
@media(max-width:1100px){.grid{grid-template-columns:1fr}}
.v{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;min-width:0}
.v h2{font-size:17px;margin:0}.k{display:inline-block;background:var(--fg);color:var(--bg);border-radius:6px;padding:0 8px;margin-right:6px}
.note{color:var(--mut);margin:4px 0}.br{font-size:12px;color:var(--mut)}h3{font-size:13px;margin:12px 0 4px;color:var(--mut)}
img{max-width:100%;border:1px solid var(--line);border-radius:6px;display:block}img.mob{max-width:260px}.bad{color:var(--bad)}
table{border-collapse:collapse;width:100%;margin-top:18px;background:var(--card)}td,th{border:1px solid var(--line);padding:6px 8px;text-align:left;font-size:13px}th{color:var(--mut);font-weight:600}
code{font-size:12px}
</style></head><body>
<h1>${esc(basename(opt.out))} 變體比較 <small style="color:var(--mut);font-weight:400">${new Date().toLocaleString('zh-TW')}${opt.example ? '　範例 ' + esc(opt.example) : ''}</small></h1>
<div class="grid">${cols}</div>
<table><thead><tr><th>量測</th>${opt.variants.map(v => `<th>${v.key}</th>`).join('')}</tr></thead><tbody>
${row('桌面 溢出', m => fmt(m.desktop))}${row('手機 溢出', m => fmt(m.mobile))}
${row('桌面 最低對比／不足數', m => `${m.desktop.minContrast ?? '-'}／${m.desktop.lowContrast}（${m.desktop.textEls} 文字元素）`)}
${row('手機 最低對比／不足數', m => `${m.mobile.minContrast ?? '-'}／${m.mobile.lowContrast}`)}
${row('焦點區 DOM 節點數', m => `${m.desktop.nodes}（手機 ${m.mobile.nodes}）`)}
${row('焦點區尺寸 桌面', m => `${m.desktop.focusWidth}×${m.desktop.focusHeight}`)}
${row('console error', m => `${m.desktop.errors.length}／${m.mobile.errors.length}`)}
</tbody></table>
<p style="color:var(--mut);margin-top:14px">回覆選擇，例「B」或「B 但用 A 的配色」，後面接「開始」。</p>
</body></html>`;
  writeFileSync(resolve(opt.out, 'variants.html'), html);
  console.log('比較頁：' + resolve(opt.out, 'variants.html'));
}
