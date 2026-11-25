// Ce ajută omul în jurul editorului: chatul cu Claude (prin ACP, ca „Ask AI” din Fintaxy CRM), programele în plus
// (LibreOffice, Stirling, Node.js, instalate din aplicație fără terminal) și ghidul de la prima pornire.
// Textele sunt scrise aici direct în ambele limbi: T('română', 'English').
import { lang } from './i18n.js'

let X = null // ce primește de la editor.js: h, $, api, post, toast, openDrawer, closeDrawer, state, path(), openDoc...
const T = (ro, en) => (lang() === 'en' ? en : ro)
const SVG = {
  chat: '<g class="claude-mark"><path d="M12 12 12 2.6"/><path d="M12 12 16.6 3.9"/><path d="M12 12 20.2 7.4"/><path d="M12 12 21.5 11.4"/><path d="M12 12 20.4 16.3"/><path d="M12 12 16.9 20.2"/><path d="M12 12 12.4 21.5"/><path d="M12 12 7.6 20.4"/><path d="M12 12 3.9 17"/><path d="M12 12 2.5 12.5"/><path d="M12 12 3.7 7.9"/><path d="M12 12 7.2 3.8"/></g>',  // semnul Claude: raze dintr-un centru
  plug: '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
  fresh: '<path d="M12 5v14"/><path d="M5 12h14"/>',
  send: '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
  down: '<path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>',
  wrench: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
  fail: '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
  shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M9.1 9a3 3 0 0 1 5.82 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
  retry: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
  reply: '<path d="m15 10 5 5-5 5"/><path d="M4 4v7a4 4 0 0 0 4 4h12"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  clip: '<path d="m16 6-8.41 8.59a2 2 0 0 0 2.83 2.83l8.49-8.48a4 4 0 0 0-5.66-5.66l-8.49 8.49a6 6 0 0 0 8.49 8.49l8.48-8.49"/>',
  file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
  image: '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.09-3.09a2 2 0 0 0-2.82 0L6 21"/>',
  history: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
  star: '<path d="M11.52 2.3a.53.53 0 0 1 .95 0l2.31 4.68a2.12 2.12 0 0 0 1.6 1.16l5.17.76a.53.53 0 0 1 .29.9l-3.74 3.64a2.12 2.12 0 0 0-.61 1.88l.88 5.14a.53.53 0 0 1-.77.56l-4.62-2.43a2.12 2.12 0 0 0-1.97 0L6.4 21.01a.53.53 0 0 1-.77-.56l.88-5.13a2.12 2.12 0 0 0-.61-1.88L2.16 9.8a.53.53 0 0 1 .29-.9l5.17-.76a2.12 2.12 0 0 0 1.6-1.16z"/>',
  starFill: '<path fill="currentColor" d="M11.52 2.3a.53.53 0 0 1 .95 0l2.31 4.68a2.12 2.12 0 0 0 1.6 1.16l5.17.76a.53.53 0 0 1 .29.9l-3.74 3.64a2.12 2.12 0 0 0-.61 1.88l.88 5.14a.53.53 0 0 1-.77.56l-4.62-2.43a2.12 2.12 0 0 0-1.97 0L6.4 21.01a.53.53 0 0 1-.77-.56l.88-5.13a2.12 2.12 0 0 0-.61-1.88L2.16 9.8a.53.53 0 0 1 .29-.9l5.17-.76a2.12 2.12 0 0 0 1.6-1.16z"/>',
  pencil: '<path d="M21.17 6.81a1 1 0 0 0-3.99-3.99L3.84 16.17a2 2 0 0 0-.5.83l-1.32 4.35a.5.5 0 0 0 .62.62l4.35-1.32a2 2 0 0 0 .83-.5z"/><path d="m15 5 4 4"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
}
function svg(name) {
  const t = document.createElement('template')
  t.innerHTML = `<svg class="i" viewBox="0 0 24 24">${SVG[name] || ''}</svg>`
  return t.content.firstChild
}
// Semnul de informație de lângă titluri: textul lung stă în el (apare la trecerea cu mouse-ul), nu sub titlu.
const info = text => X.h('span', { class: 'infomark', 'data-tip': text, tabindex: '0' }, 'i')

// ---------- markdown, cât trebuie pentru răspunsurile lui Claude ----------
const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
function inline(s) {
  // linkurile ies întâi din text (ca să nu le strice stilurile), apoi se pun la loc: [text](https://…) și adresele goale
  const links = []
  const hold = (label, href) => `\u0000${links.push([label, href]) - 1}\u0000`
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (m, t, u) => hold(t, u))
    .replace(/https?:\/\/[^\s<>()\u0000]*[^\s<>().,;:!?'"\u0000]/g, u => hold(u, u))
  return esc(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, '$1<i>$2</i>')
    .replace(/\u0000(\d+)\u0000/g, (m, i) => `<a href="${esc(links[i][1])}" target="_blank" rel="noopener">${esc(links[i][0])}</a>`)
}
function markdown(src) {
  const out = []
  let list = null, code = null, table = null
  const flush = () => {
    if (list) { out.push(`<${list.tag}>${list.items.map(i => `<li>${i}</li>`).join('')}</${list.tag}>`); list = null }
    if (table) {
      const rows = table.filter(r => !/^\s*\|?[\s:|-]+\|?\s*$/.test(r)).map(r => r.replace(/^\s*\||\|\s*$/g, '').split('|').map(c => inline(c.trim())))
      out.push('<table>' + rows.map((r, i) => `<tr>${r.map(c => (i ? `<td>${c}</td>` : `<th>${c}</th>`)).join('')}</tr>`).join('') + '</table>')
      table = null
    }
  }
  for (const line of String(src).split('\n')) {
    if (/^```/.test(line)) {
      if (code) { out.push(`<pre>${esc(code.join('\n'))}</pre>`); code = null } else { flush(); code = [] }
      continue
    }
    if (code) { code.push(line); continue }
    if (/^\s*\|.*\|\s*$/.test(line)) { if (list) flush(); (table ||= []).push(line); continue }
    const li = line.match(/^\s*(?:[-*•]|(\d+)[.)])\s+(.*)$/)
    if (li) {
      if (table) flush()
      const tag = li[1] ? 'ol' : 'ul'
      if (!list || list.tag !== tag) { flush(); list = { tag, items: [] } }
      list.items.push(inline(li[2]))
      continue
    }
    flush()
    const hd = line.match(/^(#{1,4})\s+(.*)$/)
    const quote = line.match(/^\s*>\s?(.*)$/)
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) out.push('<hr>')
    else if (quote) out.push(`<blockquote>${inline(quote[1])}</blockquote>`)
    else if (hd) out.push(`<h4>${inline(hd[2])}</h4>`)
    else if (line.trim()) out.push(`<p>${inline(line)}</p>`)
  }
  if (code) out.push(`<pre>${esc(code.join('\n'))}</pre>`)
  flush()
  return out.join('')
}

// ---------- o lucrare care durează (instalare): întreabă până se termină ----------
async function follow(read, onLine, ms = 1200) {
  for (;;) {
    const j = await read()
    if (!j) return { state: 'error', line: '' }
    onLine(j.line || '')
    if (j.state !== 'running') return j
    await new Promise(r => setTimeout(r, ms))
  }
}

// ---------- componentele ----------
// LibreOffice, Stirling PDF, Node.js și legătura cu Claude fac parte din aplicație: se aduc singure, în fundal, la
// prima pornire. Aici se vede doar starea lor; un buton apare numai dacă ceva n-a reușit („Reîncearcă”).
const USE = {
  libreoffice: ['Word, Excel, PowerPoint → PDF, când nu ai Microsoft Office', 'Word, Excel, PowerPoint → PDF, when you have no Microsoft Office'],
  stirling: ['Unelte rare: conversii exotice, verificări, broșuri', 'Rare tools: exotic conversions, checks, booklets'],
  node: ['Motorul pentru chatul cu Claude', 'The engine for the Claude chat'],
  claude: ['Chatul cu Claude din editor', 'The Claude chat in the editor'],
}
const NAMES = { claude: ['Legătura cu Claude', 'Claude link'] }
function depText(it) {
  const j = it.job
  if (it.installed) return T('Gata', 'Ready')
  if (!j) return T('Urmează', 'Queued')
  if (j.state === 'error') return j.line
  if (j.state === 'waiting') return T('Urmează', 'Queued')
  const line = (j.line || '').replace(/^Se descarcă… (\d+) din (\d+) MB$/, (m, a2, b2) => T(`Se descarcă ${a2} / ${b2} MB`, `Downloading ${a2} / ${b2} MB`))
    .replace(/^Se despachetează…$/, T('Se despachetează…', 'Unpacking…')).replace(/^Se instalează… \(~1 minut\)$/, T('Se instalează…', 'Installing…'))
    .replace(/^Se pregătește…$/, T('Se pregătește…', 'Preparing…'))
  return line || T('Se pregătește…', 'Preparing…')
}
function depRow(id, it) {
  const { h } = X
  const running = it.job && (it.job.state === 'running' || it.job.state === 'waiting')
  const failed = !it.installed && it.job?.state === 'error'
  const state = h('span', { class: 'dep-state' }, it.installed ? svg('check') : running && it.job.state === 'running' ? h('span', { class: 'spin' }) : '', depText(it))
  const row = h('div', { class: `dep${it.installed ? ' ok' : ''}${failed ? ' bad' : ''}` },
    h('div', { class: 'dep-name' }, h('b', {}, NAMES[id] ? T(...NAMES[id]) : it.name), info(T(USE[id][0], USE[id][1]))), state)
  if (failed) row.append(h('button', { class: 'secondary', type: 'button', onclick: () => X.post('deps/install', { id }).catch(err => X.toast(err.message, { err: true })) }, T('Reîncearcă', 'Retry')))
  if (running && it.job.pct != null) row.append(h('div', { class: 'dep-bar' }, h('span', { style: { width: `${it.job.pct}%` } })))
  return row
}
// Lista componentelor, care se reîmprospătează singură cât timp se mai aduce ceva.
function depsBox(only, onReady) {
  const { h } = X
  const box = h('div', { class: 'deps' }, h('div', { class: 'muted' }, h('span', { class: 'spin' })))
  let was = null
  const tick = async () => {
    if (!box.isConnected && was !== null) return
    let d
    try { d = await X.api('deps') } catch (err) { box.replaceChildren(h('div', { class: 'result err' }, err.message)); return }
    const ids = Object.keys(d.items).filter(id => !only || only.includes(id))
    box.replaceChildren(...ids.map(id => depRow(id, d.items[id])))
    const all = ids.every(id => d.items[id].installed)
    if (all && was === false) onReady?.()
    was = all
    if (!all && (d.busy || ids.some(id => !d.items[id].job))) setTimeout(tick, 1200)
    else if (!all) setTimeout(tick, 4000)
  }
  tick()
  return box
}
export function openDeps() {
  const { h } = X
  const body = h('div', { class: 'db form' })
  const d = X.openDrawer(T('Componente', 'Components'), body)
  X.titleTip(d, T('Fac parte din PDF Sign și se instalează singure, în fundal, la prima pornire.', 'They are part of PDF Sign and install by themselves, in the background, on first start.'))
  body.append(depsBox())
}

// ---------- chatul cu Claude ----------
// Făcut după „Ask AI” din Fintaxy CRM: întrebarea într-o bulă la dreapta, răspunsul fără bulă, câte un rând compact
// pentru fiecare unealtă, cardul de acord cu detaliul acțiunii, „Se gândește…”, sugestii de continuare sub ultimul
// răspuns, copiere și reîncercare; mai multe conversații pe document (istoric, titlu, stea, redenumire, ștergere),
// atașamente (lipite, trase, alese), modelul și efortul, modul Manual / Auto și inelul cu limitele abonamentului.
const chats = new Map() // id conversație -> { id, path, seq, revs, events: Map(seq -> eveniment), running, title }
const current = new Map() // cale (litere mici) -> id-ul conversației deschise
let poll = 0 // schimbat la fiecare deschidere: bucla veche de citire se oprește singură
let watch = 0 // bucla din fundal (panoul închis cât Claude lucrează)
const text = s => document.createTextNode(String(s ?? '')) // textul omului și al lui Claude: netradus
const MAX_FILES = 5
const MAX_MB = 20

function chatState(id, path) {
  if (!chats.has(id)) chats.set(id, { id, path, seq: 0, revs: {}, events: new Map(), running: false, title: '' })
  return chats.get(id)
}
function apply(st, r) { // evenimentele primite de la server intră în starea conversației
  st.running = r.running
  if (r.title != null) st.title = r.title
  for (const e of r.events) {
    st.events.set(e.seq, e)
    st.revs[e.seq] = e.rev || 0
    st.seq = Math.max(st.seq, e.seq)
  }
}
const eventsOf = st => [...st.events.values()].sort((a, b) => a.seq - b.seq)

// Răspunsul fără blocul <followups> (care devine butoane); cât se scrie, un început de etichetă („<follo”) e ascuns.
const TAG = '<followups>'
function splitFollowups(txt, streaming) {
  const i = txt.indexOf(TAG)
  if (i >= 0) {
    const follow = txt.slice(i + TAG.length).replace(/<\/followups>[\s\S]*$/, '').split('\n')
      .map(l => l.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, '').trim()).filter(l => l && l.length <= 160).slice(0, 3)
    return { shown: txt.slice(0, i).trimEnd(), follow }
  }
  if (streaming) for (let k = Math.min(TAG.length - 1, txt.length); k > 0; k--) if (txt.endsWith(TAG.slice(0, k))) return { shown: txt.slice(0, -k), follow: [] }
  return { shown: txt, follow: [] }
}
// Textul răspunsului unei ture (de la întrebare până la `seq`), fără sugestii: pentru „Copiază”.
function turnText(st, seq) {
  const evs = eventsOf(st).filter(e => e.seq <= seq)
  const iUser = evs.map(e => e.type).lastIndexOf('user')
  return splitFollowups(evs.slice(iUser + 1).filter(e => e.type === 'text').map(e => e.text).join('\n\n'), false).shown
}
async function copyText(t) {
  try { await navigator.clipboard.writeText(t); X.toast(T('Copiat', 'Copied')) } catch { X.toast(T('Nu am putut copia', 'Could not copy'), { err: true }) }
}
const isPdf = f => /\.pdf$/i.test(f)
const baseName = f => String(f).split(/[\\/]/).pop()

function rel(ms) {
  const s = (Date.now() - ms) / 1000
  if (s < 60) return T('acum', 'now')
  if (s < 3600) return T(`acum ${Math.floor(s / 60)} min`, `${Math.floor(s / 60)} min ago`)
  if (s < 86400) return T(`acum ${Math.floor(s / 3600)} h`, `${Math.floor(s / 3600)} h ago`)
  if (s < 7 * 86400) return T(`acum ${Math.floor(s / 86400)} zile`, `${Math.floor(s / 86400)} days ago`)
  return new Date(ms).toLocaleDateString(lang() === 'en' ? 'en-GB' : 'ro-RO', { day: 'numeric', month: 'short' })
}

// Un meniu mic lângă un buton; se închide la clic în afară sau Esc.
let openPop = null
function popover(anchor, content, { up = false, cls = '' } = {}) {
  closePop()
  const r = anchor.getBoundingClientRect()
  const el = X.h('div', { class: `cpop ${cls}`, role: 'menu' }, content)
  el.style.right = `${Math.max(8, innerWidth - r.right)}px`
  if (up) el.style.bottom = `${innerHeight - r.top + 6}px`
  else el.style.top = `${r.bottom + 6}px`
  document.body.append(el)
  const away = e => { if (!el.contains(e.target) && !anchor.contains(e.target)) closePop() }
  const esc = e => { if (e.key === 'Escape') { e.stopPropagation(); closePop(); anchor.focus() } }
  setTimeout(() => document.addEventListener('pointerdown', away, true))
  el.addEventListener('keydown', esc)
  openPop = { el, off: () => document.removeEventListener('pointerdown', away, true) }
  return el
}
function closePop() {
  if (!openPop) return
  openPop.off()
  openPop.el.remove()
  openPop = null
}

function fileChips(files) {
  const { h } = X
  return h('div', { class: 'ct-files' }, ...files.map(f => h('span', { class: 'ct-file', title: f.name }, svg(f.kind === 'image' ? 'image' : 'file'), h('span', {}, text(f.name)))))
}

function eventNode(e, st, running) {
  const { h } = X
  if (e.type === 'user') {
    const q = h('div', { class: 'ct-q' }, text(e.text))
    if (!e.files?.length) return q
    return h('div', { class: 'ct-qwrap' }, fileChips(e.files), q)
  }
  if (e.type === 'text') {
    const shown = splitFollowups(e.text, running).shown
    return shown.trim() ? h('div', { class: 'ct-a', html: markdown(shown) }) : null
  }
  if (e.type === 'thought') {
    return h('div', { class: 'ct-thinking' }, h('span', { class: 'shimmer' }, T('Se gândește…', 'Thinking…')), h('div', { class: 'ct-thought' }, text(e.text.slice(-300))))
  }
  if (e.type === 'tool') {
    const s = e.status === 'completed' ? 'ok' : e.status === 'failed' ? 'bad' : 'run'
    return h('div', { class: `ct-tool st-${s}`, title: e.title }, svg('wrench'), h('span', { class: 'tt' }, text(e.title)),
      s === 'ok' ? svg('check') : s === 'bad' ? svg('fail') : running ? h('span', { class: 'spin' }) : null)
  }
  if (e.type === 'plan') {
    return h('div', { class: 'ct-plan' }, ...(e.entries || []).map(x => h('div', { class: `pl ${x.status}` }, h('span', { class: 'dot' }), h('span', {}, text(x.content)))))
  }
  if (e.type === 'perm') {
    if (e.state !== 'ask') return null // după răspuns cardul dispare; rândul uneltei arată ce s-a întâmplat
    const answer = choice => X.post('chat/permission', { path: st.path, chat: st.id, id: e.id, choice }).catch(err => X.toast(err.message, { err: true }))
    return h('div', { class: 'ct-perm', role: 'alertdialog' },
      h('div', { class: 'ph' }, svg('shield'), h('span', {}, T('Claude vrea să: ', 'Claude wants to: '), h('b', {}, text(e.title)))),
      e.detail ? h('pre', { class: 'ct-perm-input' }, text(e.detail)) : null,
      h('div', { class: 'ct-perm-btns' },
        h('button', { class: 'primary', type: 'button', onclick: () => answer('allow') }, T('Permite', 'Allow')),
        e.noAlways ? null : h('button', { class: 'secondary', type: 'button', onclick: () => answer('always') }, T('Mereu în acest chat', 'Always in this chat')),
        h('button', { class: 'secondary', type: 'button', onclick: () => answer('deny') }, T('Refuză', 'Deny'))))
  }
  if (e.type === 'error') {
    const box = h('div', { class: 'ct-err' }, h('span', {}, text(X.tr ? X.tr(e.text) : e.text)))
    if (e.needLogin) box.append(h('button', { class: 'primary', type: 'button', onclick: () => X.post('chat/login', {}).catch(err => X.toast(err.message, { err: true })) }, T('Conectează Claude', 'Connect Claude')))
    return box
  }
  if (e.type === 'done') {
    const box = h('div', { class: 'ct-done' })
    if (e.stop === 'cancelled') box.append(h('div', { class: 'ct-stopped' }, T('Oprit.', 'Stopped.')))
    if (e.note) box.append(h('div', { class: 'ct-note' }, text(e.note)))
    if (e.files?.length) {
      box.append(h('div', { class: 'ct-made' }, h('div', { class: 'muted' }, T('Fișiere făcute de Claude', 'Files made by Claude')),
        ...e.files.map(f => h('div', { class: 'ct-made-row', title: f }, svg('file'), h('span', { class: 'tt' }, text(baseName(f))),
          isPdf(f) ? h('button', { class: 'ct-act-btn', type: 'button', onclick: () => X.openDoc(f) }, T('Deschide', 'Open')) : null,
          h('button', { class: 'ct-act-btn', type: 'button', onclick: () => X.post('chat/reveal', { chat: st.id, file: f }).catch(err => X.toast(err.message, { err: true })) }, T('Arată în folder', 'Show in folder'))))))
    }
    const answer = turnText(st, e.seq)
    if (answer.trim()) box.append(h('div', { class: 'ct-actions' }, h('button', { class: 'icon', type: 'button', title: T('Copiază răspunsul', 'Copy answer'), onclick: () => copyText(answer) }, X.icon('copy'))))
    return box.children.length ? box : null
  }
  return null
}

// ---------- modelul și efortul (ca în CRM: ce oferă Claude Code, ținut minte pe calculator) ----------
const effortName = o => (o.value === 'xhigh' ? 'Extra' : o.value === 'default' ? T('Implicit', 'Default') : o.name)
function modelLabel(opts) {
  const m = opts?.model
  const cur = m?.options.find(o => o.value === m.current)
  return cur ? (cur.value === 'default' ? T('Model implicit', 'Default model') : cur.name) : 'Model'
}
function modelMenu(anchor, opts, onPick) {
  const { h } = X
  const box = h('div', { class: 'cpop-body' })
  if (!opts) box.append(h('div', { class: 'muted cpop-pad' }, h('span', { class: 'spin' }), T('Întreb Claude Code ce modele are…', 'Asking Claude Code for its models…')))
  else {
    if (opts.model) {
      box.append(h('div', { class: 'cpop-head' }, 'Model'))
      // ca în CRM: primele patru (cele mai noi) și cel ales; restul sub „Mai multe modele”
      const all = opts.model.options
      const few = all.length > 5 && !modelMenu.all ? all.filter((o, i) => i < 4 || o.value === opts.model.current) : all
      for (const o of few) {
        box.append(h('button', { class: `cpop-row${o.value === opts.model.current ? ' cur' : ''}`, type: 'button', title: o.description || '', onclick: () => { closePop(); if (o.value !== opts.model.current) onPick({ model: o.value }) } },
          h('span', { class: 'grow' }, text(o.value === 'default' ? T('Implicit', 'Default') : o.name)), o.value === opts.model.current ? svg('check') : null))
      }
      if (few.length < all.length) box.append(h('button', { class: 'cpop-row muted', type: 'button', onclick: () => { modelMenu.all = true; modelMenu(anchor, opts, onPick); modelMenu.all = false } }, h('span', { class: 'grow' }, T('Mai multe modele…', 'More models…'))))
    }
    if (opts.effort?.options.length) {
      box.append(h('div', { class: 'cpop-head' }, T('Efort', 'Effort'), info(T('Un efort mai mare dă răspunsuri mai atente, dar durează mai mult și consumă limita mai repede.', 'More effort gives more careful answers, but takes longer and uses up the limit faster.'))))
      for (const o of opts.effort.options.filter(x => x.value !== 'default' || x.value === opts.effort.current)) {
        box.append(h('button', { class: `cpop-row${o.value === opts.effort.current ? ' cur' : ''}`, type: 'button', onclick: () => { closePop(); if (o.value !== opts.effort.current) onPick({ effort: o.value }) } },
          h('span', { class: 'grow' }, text(effortName(o)), o.value === 'max' ? h('span', { class: 'cc-badge' }, T('consum mare', 'heavy use')) : null),
          o.value === opts.effort.current ? svg('check') : null))
      }
    }
    if (!opts.model && !opts.effort) box.append(h('div', { class: 'muted cpop-pad' }, T('Claude Code nu oferă alegerea modelului aici.', 'Claude Code offers no model choice here.')))
  }
  return popover(anchor, box, { up: true, cls: 'cpop-model' })
}

// ---------- inelul cu limitele abonamentului ----------
function until(ms) {
  if (!ms) return ''
  const m = Math.max(0, Math.round((ms - Date.now()) / 60000))
  const hh = Math.floor(m / 60), mm = m % 60
  if (hh >= 24) return T(`Se resetează în ${Math.floor(hh / 24)} zile ${hh % 24} h`, `Resets in ${Math.floor(hh / 24)} d ${hh % 24} h`)
  return hh ? T(`Se resetează în ${hh} h ${mm} min`, `Resets in ${hh} h ${mm} min`) : T(`Se resetează în ${mm} min`, `Resets in ${mm} min`)
}
const limitRo = l => (l === '5-hour limit' ? 'Limita de 5 ore' : l.replace(/^Weekly · all models$/i, 'Săptămânal · toate modelele').replace(/^Weekly ·/i, 'Săptămânal ·'))
function usageRing() {
  const { h } = X
  const btn = h('button', { class: 'icon cc-ring', type: 'button', hidden: true, title: T('Limitele abonamentului Claude', 'Claude plan limits') })
  let data = null
  const draw = () => {
    const five = data?.limits.find(l => l.id === 'five_hour') || data?.limits[0]
    btn.hidden = !five
    if (!five) return
    const p = Math.round(five.percent), c = 2 * Math.PI * 6.5
    btn.className = `icon cc-ring${p >= 90 ? ' bad' : p >= 70 ? ' warn' : ''}`
    btn.innerHTML = `<svg viewBox="0 0 18 18" class="ring"><circle cx="9" cy="9" r="6.5" class="bg"/><circle cx="9" cy="9" r="6.5" class="fg" stroke-dasharray="${(c * p) / 100} ${c}" transform="rotate(-90 9 9)"/></svg>`
    btn.title = `${T(limitRo(five.label), five.label)}: ${p}%`
  }
  btn.addEventListener('click', () => {
    if (!data) return
    popover(btn, h('div', { class: 'cpop-body cpop-pad' },
      data.plan ? h('div', { class: 'cpop-head' }, `Claude ${data.plan}`) : null,
      ...data.limits.map(l => h('div', { class: 'lim' },
        h('div', { class: 'lim-top' }, h('span', {}, T(limitRo(l.label), l.label)), h('b', {}, `${Math.round(l.percent)}%`)),
        h('div', { class: `lim-bar${l.percent >= 90 ? ' bad' : l.percent >= 70 ? ' warn' : ''}` }, h('span', { style: { width: `${l.percent}%` } })),
        h('div', { class: 'muted' }, until(l.resetsAt) || text(l.resetsText || ''))))), { cls: 'cpop-usage' })
  })
  btn.refresh = async force => {
    try { data = await X.api('chat/usage', force ? { force: 1 } : {}) } catch { data = null }
    draw()
  }
  return btn
}

// ---------- istoricul conversațiilor documentului ----------
function historyMenu(anchor, path, activeId, open) {
  const { h } = X
  const search = h('input', { type: 'search', class: 'cpop-search', placeholder: T('Caută în conversații', 'Search chats') })
  const rows = h('div', { class: 'cpop-list' }, h('div', { class: 'muted cpop-pad' }, h('span', { class: 'spin' })))
  let all = []
  const render = () => {
    const q = search.value.trim().toLowerCase()
    const list = all.filter(c => !q || c.title.toLowerCase().includes(q))
    if (!list.length) return rows.replaceChildren(h('div', { class: 'muted cpop-pad' }, q ? T('Nimic găsit.', 'Nothing found.') : T('Nicio conversație încă despre acest PDF.', 'No chats about this PDF yet.')))
    rows.replaceChildren(...list.map(c => {
      const title = h('button', { class: 'hc-title', type: 'button', title: c.title, onclick: () => { closePop(); open(c.id) } },
        c.starred ? svg('star') : null, h('span', { class: 'tt' }, text(c.title)), c.running ? h('span', { class: 'spin' }) : null, h('span', { class: 'muted hc-when' }, rel(c.updated)))
      const row = h('div', { class: `hc-row${c.id === activeId ? ' cur' : ''}` }, title,
        h('button', { class: 'icon', type: 'button', title: c.starred ? T('Scoate steaua', 'Unstar') : T('Cu stea (sus în listă)', 'Star (top of the list)'), onclick: async () => {
          await X.post('chat/star', { chat: c.id, starred: !c.starred }).catch(err => X.toast(err.message, { err: true })); load()
        } }, svg(c.starred ? 'starFill' : 'star')),
        h('button', { class: 'icon', type: 'button', title: T('Redenumește', 'Rename'), onclick: () => {
          const inp = h('input', { type: 'text', class: 'hc-rename', value: c.title, maxlength: '80' })
          title.replaceWith(inp)
          inp.focus(); inp.select()
          const save = async () => { if (inp.value.trim() && inp.value.trim() !== c.title) await X.post('chat/rename', { chat: c.id, title: inp.value }).catch(err => X.toast(err.message, { err: true })); load() }
          inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); save() } else if (e.key === 'Escape') { e.stopPropagation(); load() } })
          inp.addEventListener('blur', save)
        } }, svg('pencil')),
        h('button', { class: 'icon', type: 'button', title: T('Șterge', 'Delete'), onclick: async () => {
          if (!confirm(T(`Ștergi conversația „${c.title}”? Nu se mai poate recupera.`, `Delete the chat “${c.title}”? It cannot be recovered.`))) return
          await X.post('chat/delete', { chat: c.id }).catch(err => X.toast(err.message, { err: true }))
          chats.delete(c.id)
          if (current.get(path.toLowerCase()) === c.id) current.delete(path.toLowerCase())
          if (c.id === activeId) { closePop(); open(null) } else load()
        } }, svg('trash')))
      return row
    }))
  }
  const load = async () => {
    try { all = (await X.api('chat/list', { path })).chats } catch (err) { rows.replaceChildren(h('div', { class: 'result err' }, err.message)); return }
    render()
  }
  search.addEventListener('input', render)
  const el = popover(anchor, h('div', { class: 'cpop-body' }, search, rows), { cls: 'cpop-history' })
  load()
  search.focus()
  return el
}

// ---------- atașamentele din compozitor ----------
function readB64(file) {
  return new Promise((ok, bad) => {
    const r = new FileReader()
    r.onload = () => ok(String(r.result).split(',')[1] || '')
    r.onerror = () => bad(r.error)
    r.readAsDataURL(file)
  })
}

export async function openChat(prefill, { chat: want = null, fresh = false } = {}) {
  const { h } = X
  const path = X.path()
  if (!path) return X.toast(T('Deschide întâi un PDF.', 'Open a PDF first.'))
  const key = path.toLowerCase()
  const my = ++poll
  watch++
  closePop()
  const list = h('div', { class: 'chat-thread', tabindex: '0' })
  const input = h('textarea', { rows: '2', placeholder: T('Întreabă orice…', 'Ask anything…') })
  const send = h('button', { class: 'cc-send', type: 'button', title: T('Trimite (Enter)', 'Send (Enter)') }, svg('send'))
  const mode = h('select', { class: 'cc-mode', title: T('Manual: întreabă mereu înainte de schimbări. Auto: Claude decide singur la acțiunile de rutină.', 'Manual: always asks before changes. Auto: Claude decides by itself on routine actions.') },
    h('option', { value: 'ask' }, 'Manual'), h('option', { value: 'auto' }, 'Auto'))
  mode.addEventListener('change', () => X.post('settings', { chatMode: mode.value }).catch(() => {}))
  const fileIn = h('input', { type: 'file', multiple: true, hidden: true })
  const attach = h('button', { class: 'icon cc-attach', type: 'button', title: T('Atașează fișiere (sau lipește / trage aici)', 'Attach files (or paste / drop here)') }, svg('clip'))
  attach.addEventListener('click', () => fileIn.click())
  let opts = null
  const model = h('button', { class: 'cc-model', type: 'button', title: T('Modelul și efortul', 'Model and effort') }, h('span', { class: 'mn' }, 'Model'))
  const showModel = () => {
    const eff = opts?.effort?.options.find(o => o.value === opts.effort.current)
    model.replaceChildren(h('span', { class: 'mn' }, text(modelLabel(opts))), eff && eff.value !== 'default' ? h('span', { class: 'me' }, text(effortName(eff))) : null)
  }
  model.addEventListener('click', async () => {
    const pop = modelMenu(model, opts, pick)
    if (!opts) {
      try { opts = await X.api('chat/options') } catch (err) { opts = null; X.toast(err.message, { err: true }) }
      showModel()
      if (pop.isConnected) modelMenu(model, opts, pick)
    }
  })
  async function pick(patch) {
    try { opts = await X.post('chat/prefs', patch); showModel() } catch (err) { X.toast(T(`Nu am putut schimba: ${err.message}`, `Could not change it: ${err.message}`), { err: true }) }
  }
  const chips = h('div', { class: 'cc-chips', hidden: true })
  const composer = h('div', { class: 'chat-composer' }, chips, input, h('div', { class: 'cc-foot' }, attach, fileIn, h('span', { class: 'grow' }), model, mode, send))
  composer.addEventListener('click', e => { if (e.target === composer) input.focus() })
  const body = h('div', { class: 'chat' }, list, composer)
  const d = X.openDrawer('Claude', body)
  d.dataset.kind = 'chat'
  document.querySelector('.rail [data-panel=chat]')?.classList.add('on')
  document.querySelector('.rail [data-panel=chat]')?.classList.remove('attn')
  const head = d.querySelector('.dh')
  const titleEl = h('button', { class: 'ct-title', type: 'button', title: T('Conversațiile acestui PDF', 'Chats about this PDF') })
  head.querySelector('h2').append(info(T('Claude vede PDF-ul deschis și pagina pe care ești. În modul Manual, orice schimbare îți cere acordul.',
    'Claude sees the open PDF and the page you are on. In Manual mode, any change asks for your approval.')), titleEl)
  const ring = usageRing()
  const histBtn = h('button', { class: 'icon', type: 'button', title: T('Conversațiile acestui PDF', 'Chats about this PDF') }, svg('history'))
  const openHistory = () => historyMenu(histBtn, path, st?.id, id => openChat(null, id ? { chat: id } : {}))
  histBtn.addEventListener('click', openHistory)
  titleEl.addEventListener('click', openHistory)
  head.lastChild.before(ring, histBtn,
    h('button', { class: 'icon', type: 'button', title: T('Conversație nouă', 'New chat'), onclick: () => openChat(null, { fresh: true }) }, svg('fresh')),
    h('button', { class: 'icon', type: 'button', title: T('Conexiuni (CRM)', 'Connections (CRM)'), onclick: () => openConnections() }, svg('plug')))
  let st = null

  // Atașamentele: alese, lipite (Ctrl+V) sau trase peste chat; se urcă imediat, pleacă odată cu mesajul.
  const files = []
  const drawChips = () => {
    chips.hidden = !files.length
    chips.replaceChildren(...files.map(f => h('span', { class: `cc-chip${f.busy ? ' busy' : ''}`, title: f.name },
      f.thumb ? h('img', { src: f.thumb, alt: '' }) : svg('file'), h('span', { class: 'tt' }, text(f.name)), f.busy ? h('span', { class: 'spin' }) : null,
      h('button', { type: 'button', class: 'x', title: T('Scoate', 'Remove'), onclick: () => { files.splice(files.indexOf(f), 1); if (f.thumb) URL.revokeObjectURL(f.thumb); drawChips() } }, '×'))))
  }
  async function addFiles(list2) {
    for (const file of [...list2]) {
      if (files.length >= MAX_FILES) { X.toast(T(`Cel mult ${MAX_FILES} fișiere într-un mesaj.`, `At most ${MAX_FILES} files in one message.`), { err: true }); break }
      if (file.size > MAX_MB * 1024 * 1024) { X.toast(T(`${file.name} e prea mare (cel mult ${MAX_MB} MB).`, `${file.name} is too big (${MAX_MB} MB at most).`), { err: true }); continue }
      const name = file.name || `captura-${Date.now()}.png`
      const f = { name, busy: true, thumb: /^image\//.test(file.type) ? URL.createObjectURL(file) : '' }
      files.push(f)
      drawChips()
      try {
        const r = await X.post('chat/upload', { name, data: await readB64(file) })
        Object.assign(f, { id: r.id, kind: r.kind, busy: false })
      } catch (err) {
        files.splice(files.indexOf(f), 1)
        X.toast(err.message, { err: true })
      }
      drawChips()
    }
  }
  fileIn.addEventListener('change', () => { addFiles(fileIn.files); fileIn.value = '' })
  input.addEventListener('paste', e => { if (e.clipboardData?.files?.length) { e.preventDefault(); addFiles(e.clipboardData.files) } })
  body.addEventListener('dragover', e => { if ([...(e.dataTransfer?.types || [])].includes('Files')) { e.preventDefault(); body.classList.add('drop') } })
  body.addEventListener('dragleave', e => { if (!body.contains(e.relatedTarget)) body.classList.remove('drop') })
  body.addEventListener('drop', e => { body.classList.remove('drop'); if (e.dataTransfer?.files?.length) { e.preventDefault(); addFiles(e.dataTransfer.files) } })

  // Derularea: lista urmărește răspunsul doar cât omul stă jos; dacă a urcat să citească, rămâne unde e.
  let pinned = true
  const atBottom = () => list.scrollHeight - list.scrollTop - list.clientHeight < 6
  list.addEventListener('wheel', e => { if (e.deltaY < 0) pinned = false }, { passive: true })
  list.addEventListener('touchmove', () => { pinned = atBottom() }, { passive: true })
  list.addEventListener('keydown', e => { if (/^(ArrowUp|PageUp|Home)$/.test(e.key)) pinned = false })
  list.addEventListener('pointerdown', () => { pinned = atBottom() }) // prins bara de derulare
  const jump = h('button', { class: 'chat-jump', type: 'button', hidden: true, title: T('La ultimul mesaj', 'Jump to the latest message') }, svg('down'))
  jump.addEventListener('click', () => { pinned = true; list.scrollTop = list.scrollHeight; jump.hidden = true })
  list.addEventListener('scroll', () => { if (atBottom()) pinned = true; jump.hidden = atBottom() })
  body.insertBefore(jump, composer)
  const keep = fn => { // schimbă lista fără să miște omul din loc
    const top = list.scrollTop
    fn()
    if (pinned) list.scrollTop = list.scrollHeight
    else { list.scrollTop = top; jump.hidden = atBottom() }
  }

  const draw = e => {
    const old = list.querySelector(`[data-seq="${e.seq}"]`)
    const inner = old?.querySelector('pre')?.scrollTop || 0
    const node = eventNode(e, st, st.running)
    if (!node) return old?.remove()
    node.dataset.seq = e.seq
    node.dataset.type = e.type
    if (old) old.replaceWith(node)
    else {
      // locul lui după număr (evenimentele vin în ordine, dar unul vechi poate reapărea schimbat)
      const after = [...list.querySelectorAll('[data-seq]')].find(n => +n.dataset.seq > e.seq)
      list.insertBefore(node, after || list.querySelector('.ct-extra'))
    }
    if (inner && node.querySelector('pre')) node.querySelector('pre').scrollTop = inner
  }
  const showTitle = () => {
    titleEl.replaceChildren(text(st?.title || T('Conversație nouă', 'New chat')))
  }
  // Ce stă la coada firului și depinde de stare: „Se gândește…”, cursorul, reîncercarea, sugestiile.
  const decorate = () => {
    for (const n of list.querySelectorAll('.ct-extra')) n.remove()
    const evs = eventsOf(st)
    const last = evs[evs.length - 1]
    const nodes = [...list.querySelectorAll('[data-seq]')]
    for (const n of nodes) n.classList.remove('streaming')
    // gândirea se vede doar cât e ultimul lucru din fir, în timpul răspunsului
    for (const n of nodes) if (n.dataset.type === 'thought' && !(st.running && last && +n.dataset.seq === last.seq)) n.remove()
    showTitle()
    if (!evs.length) return empty()
    list.querySelector('.chat-empty')?.remove()
    input.placeholder = T('Răspunde…', 'Reply…')
    const lastNode = nodes[nodes.length - 1]
    if (st.running) {
      const asking = evs.some(e => e.type === 'perm' && e.state === 'ask')
      if (last.type === 'text') lastNode?.classList.add('streaming')
      else if (last.type !== 'thought' && !asking) list.append(h('div', { class: 'ct-thinking ct-extra' }, h('span', { class: 'shimmer' }, T('Se gândește…', 'Thinking…'))))
      else if (asking) list.append(h('div', { class: 'ct-thinking ct-extra' }, h('span', { class: 'shimmer' }, T('Așteaptă răspunsul tău…', 'Waiting for your answer…'))))
      return
    }
    // tura s-a terminat: reîncercarea și sugestiile de sub ultimul răspuns (copierea e la fiecare răspuns)
    const iUser = evs.map(e => e.type).lastIndexOf('user')
    const turn = evs.slice(iUser + 1)
    const answer = turn.filter(e => e.type === 'text').map(e => e.text).join('\n\n')
    const failed = turn.some(e => e.type === 'error')
    const stopped = turn.some(e => e.type === 'done' && e.stop !== 'end_turn')
    const { follow } = splitFollowups(answer, false)
    const extra = h('div', { class: 'ct-extra' })
    if ((failed || stopped) && iUser >= 0) extra.append(h('div', { class: 'ct-actions' }, h('button', { class: 'ct-act-btn', type: 'button', onclick: () => go(evs[iUser].text) }, svg('retry'), T('Reîncearcă', 'Retry'))))
    if (follow.length && !failed && !stopped) extra.append(h('div', { class: 'ct-follow' }, ...follow.map(f => h('button', { type: 'button', onclick: () => go(f) }, svg('reply'), h('span', {}, text(f))))))
    if (extra.children.length) list.append(extra)
  }
  const setRunning = on => {
    send.replaceChildren(svg(on ? 'stop' : 'send'))
    send.title = on ? T('Oprește', 'Stop') : T('Trimite (Enter)', 'Send (Enter)')
    send.classList.toggle('stop', on)
  }
  function empty() {
    if (list.querySelector('.chat-empty')) return
    input.placeholder = T('Întreabă orice…', 'Ask anything…')
    const tips = [[T('Rezumă documentul', 'Summarise the document'), T('Rezumă documentul în 5 rânduri.', 'Summarise the document in 5 lines.')],
      [T('Ce trebuie semnat?', 'What needs signing?'), T('Unde trebuie semnat documentul ăsta și de către cine?', 'Where does this document need to be signed, and by whom?')],
      [T('Verifică sumele și datele', 'Check amounts and dates'), T('Verifică sumele, datele și numele din document: sunt consecvente?', 'Check the amounts, dates and names in the document: are they consistent?')]]
    list.append(h('div', { class: 'chat-empty' }, h('div', { class: 'ce-ico' }, svg('chat')), h('b', {}, T('Întreabă orice', 'Ask anything')),
      h('span', { class: 'muted' }, T('Despre PDF-ul deschis.', 'About the open PDF.')),
      ...tips.map(([label, t]) => h('button', { class: 'ask-suggest', type: 'button', onclick: () => go(t) }, svg('reply'), h('span', {}, label)))))
  }
  const live = () => my === poll && d.isConnected && !d.hidden && d.dataset.kind === 'chat'
  const take = r => keep(() => {
    const was = st.running
    apply(st, r)
    setRunning(st.running)
    for (const e of r.events) {
      draw(e)
      if (e.type === 'done' && e.docChanged) X.reload(T('Claude a schimbat documentul: l-am reîncărcat.', 'Claude changed the document: reloaded.'))
    }
    if (was && !st.running) {
      for (const e of st.events.values()) if (e.type === 'tool') draw(e) // rotițele rămase se opresc
      ring.refresh()
    }
    decorate()
  })
  const loop = async () => {
    while (live()) {
      try {
        const r = await X.api('chat/events', { path, chat: st.id, since: st.seq, revs: JSON.stringify(st.revs), wait: 20, running: st.running ? 1 : 0, title: st.title })
        if (!live()) break
        if (r.chat !== st.id) { current.set(key, r.chat); return openChat(null, { chat: r.chat }) } // a fost ștearsă între timp
        take(r)
      } catch {
        await new Promise(res => setTimeout(res, 1500))
      }
    }
    if (my === poll && st.running) watchInBackground(st) // panoul s-a închis cât Claude lucrează: urmărim din fundal
  }
  async function go(t) {
    if (st.running) return // un singur mesaj o dată (ca în CRM): textul rămâne în casetă
    const msg = (typeof t === 'string' ? t : input.value).trim()
    const sent = typeof t === 'string' ? [] : files.filter(f => f.id)
    if (files.some(f => f.busy)) return X.toast(T('Aștept să se încarce fișierele…', 'Waiting for the files to upload…'))
    if (!msg && !sent.length) return
    if (typeof t !== 'string') {
      input.value = ''
      input.style.height = ''
      files.length = 0
      drawChips()
    }
    pinned = true
    st.running = true
    keep(() => { setRunning(true); decorate() })
    try {
      await X.post('chat/send', { path, chat: st.id, text: msg, page: X.state.cur, files: sent.map(f => f.id) })
    } catch (err) {
      st.running = false
      setRunning(false)
      decorate()
      if (typeof t !== 'string') { input.value = msg; files.push(...sent); drawChips() }
      X.toast(err.message, { err: true })
    }
  }
  send.addEventListener('click', () => (st?.running ? X.post('chat/cancel', { path, chat: st.id }).catch(() => {}) : go()))
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); go() } })
  input.addEventListener('input', () => { input.style.height = ''; input.style.height = `${Math.min(220, input.scrollHeight)}px` })

  // Ce lipsește ca să meargă chatul (motorul, legătura cu Claude, contul): apare în loc de conversație.
  let status
  try { status = await X.api('chat/status') } catch (err) { status = { available: false, step: 'error', error: err.message } }
  if (my !== poll) return
  mode.value = status.mode === 'auto' ? 'auto' : 'ask'
  if (!status.available) {
    list.append(await chatSetup(status, () => openChat(prefill)))
    input.disabled = send.disabled = mode.disabled = attach.disabled = model.disabled = true
    return
  }
  // Care conversație: cea cerută, una nouă, cea deschisă ultima dată pe acest PDF, altfel cea mai recentă.
  try {
    let id = want || (fresh ? (await X.post('chat/new', { path })).chat : current.get(key))
    let first = null
    if (!id) {
      first = await X.api('chat/events', { path, since: 0, revs: '{}', wait: 0 })
      id = first.chat
    }
    if (my !== poll) return
    st = chatState(id, path)
    current.set(key, id)
    if (first && !st.seq) apply(st, first)
  } catch (err) {
    list.append(h('div', { class: 'result err' }, err.message))
    return
  }
  for (const e of eventsOf(st)) draw(e)
  setRunning(st.running)
  decorate()
  list.scrollTop = list.scrollHeight
  loop()
  ring.refresh()
  X.api('chat/options').then(o => { opts = o; showModel() }).catch(() => {})
  if (prefill) { input.value = prefill; input.dispatchEvent(new Event('input')) }
  input.focus()
  if (prefill) input.setSelectionRange(input.value.length, input.value.length)
}

// Panoul e închis, dar Claude încă lucrează: urmărim conversația din fundal și anunțăm cererile de acord și finalul.
async function watchInBackground(st) {
  const my = ++watch
  const btn = document.querySelector('.rail [data-panel=chat]')
  const reopen = { label: T('Deschide', 'Open'), fn: () => openChat(null, { chat: st.id }) }
  const asked = new Set([...st.events.values()].filter(e => e.type === 'perm' && e.state === 'ask').map(e => e.id))
  if (asked.size) btn?.classList.add('attn')
  while (my === watch && st.running) {
    let r
    try { r = await X.api('chat/events', { path: st.path, chat: st.id, since: st.seq, revs: JSON.stringify(st.revs), wait: 20, running: 1 }) } catch { await new Promise(res => setTimeout(res, 3000)); continue }
    if (my !== watch) return
    apply(st, r)
    for (const e of r.events) {
      if (e.type === 'perm' && e.state === 'ask' && !asked.has(e.id)) {
        asked.add(e.id)
        btn?.classList.add('attn')
        X.toast(T('Claude îți cere acordul în chat.', 'Claude is asking for your approval in the chat.'), { action: reopen, ms: 15000 })
      }
      if (e.type === 'done' && e.docChanged) X.reload(T('Claude a schimbat documentul: l-am reîncărcat.', 'Claude changed the document: reloaded.'))
    }
  }
  if (my === watch) {
    btn?.classList.add('attn')
    X.toast(T('Claude a terminat de răspuns.', 'Claude has finished answering.'), { action: reopen })
  }
}

// Pornirea chatului: motorul și legătura cu Claude se aduc singure (ca orice componentă); omul face un singur lucru,
// o dată: se conectează la contul lui Claude (în browser).
async function chatSetup(status, done) {
  const { h } = X
  const box = h('div', { class: 'chat-setup' }, h('div', { class: 'ttl' }, h('b', {}, T('Pornește chatul cu Claude', 'Set up the Claude chat')),
    info(T('O singură dată pe calculator. Chatul folosește abonamentul tău Claude, fără alte costuri.', 'Once per computer. The chat uses your Claude subscription, at no extra cost.'))))
  const ready = status.node && status.adapter
  if (!ready) {
    // dacă aducerea automată e oprită sau a rămas în urmă, o pornim acum
    X.post('deps/install', { id: 'claude' }).catch(() => {})
    box.append(depsBox(['node', 'claude'], done))
  }
  const state = h('span', { class: 'dep-state' }, status.loggedIn ? svg('check') : '', status.loggedIn ? T('Conectat', 'Connected') : '')
  const btn = h('button', { class: 'primary', type: 'button', hidden: status.loggedIn || !ready }, T('Conectează', 'Connect'))
  btn.addEventListener('click', async () => {
    btn.disabled = true
    try {
      await X.post('chat/login', {})
      state.replaceChildren(h('span', { class: 'spin' }), T('Scrie /login în fereastra deschisă…', 'Type /login in the window that opened…'))
      for (let i = 0; i < 200 && box.isConnected; i++) { // până la ~10 minute: omul se conectează în browser
        await new Promise(r => setTimeout(r, 3000))
        if ((await X.api('chat/status')).loggedIn) return done()
      }
    } catch (err) { X.toast(err.message, { err: true, ms: 9000 }) }
    btn.disabled = false
  })
  box.append(h('div', { class: `dep${status.loggedIn ? ' ok' : ''}` }, h('div', { class: 'dep-name' }, h('b', {}, T('Contul Claude', 'Claude account')),
    info(T('Se deschide o fereastră: scrii /login, Enter, apoi urmezi pașii din browser.', 'A window opens: type /login, Enter, then follow the steps in the browser.'))), state, btn))
  if (status.error) box.append(h('div', { class: 'result err' }, status.error))
  return box
}

// Conexiunile chatului: servere MCP prin care Claude ajunge la alte sisteme (de ex. Fintaxy CRM), ca în CRM.
async function openConnections() {
  const { h } = X
  let st
  try { st = await X.api('chat/status') } catch (err) { return X.toast(err.message, { err: true }) }
  const rows = h('div', { class: 'conns' })
  const add = (c = {}) => {
    const name = h('input', { type: 'text', placeholder: T('nume, ex. fintaxy-crm', 'name, e.g. fintaxy-crm'), value: c.name || '' })
    const url = h('input', { type: 'text', placeholder: 'https://…/mcp', value: c.url || '' })
    const token = h('input', { type: 'password', placeholder: c.hasToken ? T('jeton salvat (lasă gol ca să rămână)', 'token saved (leave empty to keep)') : T('jeton', 'token'), autocomplete: 'off' })
    const row = h('div', { class: 'conn' }, name, url, token, h('button', { class: 'linkbtn danger', type: 'button', onclick: () => row.remove() }, T('Scoate', 'Remove')))
    row.read = () => ({ name: name.value, url: url.value, token: token.value })
    rows.append(row)
  }
  for (const c of st.connections) add(c)
  const own = h('input', { type: 'checkbox', checked: st.userSettings })
  const save = h('button', { class: 'primary', type: 'button' }, T('Salvează', 'Save'))
  const body = h('div', { class: 'db form' },
    h('div', { class: 'ttl' }, h('b', {}, T('Conexiuni', 'Connections')), info(T('Servere MCP prin care Claude ajunge la alte sisteme. Pentru Fintaxy CRM: în CRM, Setări → Conectare Claude, copiază adresa și jetonul aici.',
      'MCP servers through which Claude reaches other systems. For Fintaxy CRM: in the CRM, Settings → Connect Claude, copy the address and the token here.'))),
    rows, h('div', {}, h('button', { class: 'linkbtn', type: 'button', onclick: () => add({ name: st.connections.length ? '' : 'fintaxy-crm' }) }, T('+ Adaugă conexiune', '+ Add connection'))),
    h('label', { class: 'checkrow' }, own, h('span', {}, T('Și conexiunile mele din Claude Code', 'Also my connections from Claude Code')),
      info(T('Claude pornește cu setările, plugin-urile și serverele MCP din Claude Code de pe acest calculator. Pornește mai greu.', 'Claude starts with the settings, plugins and MCP servers of Claude Code on this computer. Starts slower.'))),
    h('div', { class: 'buttons' }, save, h('button', { class: 'secondary', type: 'button', onclick: () => openChat() }, T('Înapoi la chat', 'Back to chat'))))
  save.addEventListener('click', async () => {
    try {
      await X.post('chat/connections', { connections: [...rows.children].map(r => r.read()).filter(c => c.name || c.url), userSettings: own.checked })
      X.toast(T('Salvat. Se aplică de la următorul mesaj.', 'Saved. Applies from the next message.'))
      openChat()
    } catch (err) { X.toast(err.message, { err: true }) }
  })
  poll++
  closePop()
  X.openDrawer(T('Conexiuni', 'Connections'), body)
}

// ---------- ghidul de la prima pornire ----------
const MOD_PROMPT = () => T(`Instalează modul PDF Sign (Fintaxy) pentru Claude Code pe acest calculator:
1. Rulează: claude plugin marketplace add FintaxyOrg/FintaxyPDFEditor
2. Rulează: claude plugin install pdf-sign@fintaxy-pdf-sign
3. Verifică să existe Python 3.12; dacă lipsește, instalează-l cu winget (pe tăcute, cu acordurile acceptate). Apoi instalează pachetele din requirements.txt al modului (pip install -r requirements.txt, din folderul în care s-a instalat).
4. Spune-mi să dau /reload-plugins, apoi arată-mi pe un PDF de test că sub el apar butoanele Preview / Deschide / Semnează.
Dacă marketplace-ul nu se poate adăuga, spune-mi eroarea și oprește-te acolo.`,
`Install the PDF Sign (Fintaxy) mod for Claude Code on this computer:
1. Run: claude plugin marketplace add FintaxyOrg/FintaxyPDFEditor
2. Run: claude plugin install pdf-sign@fintaxy-pdf-sign
3. Make sure Python 3.12 exists; if it is missing, install it with winget (silently, agreements accepted). Then install the packages from the mod's requirements.txt (pip install -r requirements.txt, from the folder it was installed in).
4. Tell me to run /reload-plugins, then show me on a test PDF that the Preview / Open / Sign buttons appear under it.
If the marketplace cannot be added, tell me the error and stop there.`)

export async function openOnboarding() {
  const { h } = X
  document.querySelector('#onboard')?.remove()
  let i = 0
  const card = h('div', { class: 'ob-card' })
  const wrap = h('div', { id: 'onboard', class: 'ob' }, card)
  // Trei feluri de a ieși din ghid:
  //   finish  = l-ai parcurs sau ai ales „Sari peste tot”: nu mai apare singur la pornire;
  //   later   = l-ai închis din X / Esc: se închide doar acum; apare iar la pornirea următoare și oricând din butonul „?”;
  //   suspend = un pas te-a trimis în editor (ex. adaugă semnătura): ghidul se dă la o parte și revine la același pas.
  const finish = () => {
    wrap.remove()
    X.post('settings', { onboarded: X.state.app.version || '1' }).catch(() => {})
    X.state.app.onboarded = X.state.app.version || '1'
  }
  const later = () => {
    wrap.remove()
    X.toast(T('Ghidul rămâne la butonul „?” din bara de sus.', 'The guide stays under the “?” button in the top bar.'))
  }
  const suspend = open => {
    wrap.hidden = true
    open()
    // Ce a deschis pasul (fereastra „Semnătură nouă” sau un panou din dreapta): când se închide, cu salvare
    // sau cu Renunță, ghidul revine la același pas, cu datele proaspete.
    const d = X.$('#drawer')
    const busy = () => !!document.querySelector('.modal-back') || !d.hidden
    const back = () => {
      if (busy() || !wrap.isConnected) return
      watch.disconnect()
      wrap.hidden = false
      wrap.focus()
      render()
    }
    const watch = new MutationObserver(back)
    watch.observe(document.body, { childList: true })
    watch.observe(d, { attributes: true, attributeFilter: ['hidden'] })
    back()
  }
  const steps = [
    { title: T('Bun venit în PDF Sign', 'Welcome to PDF Sign'), body: () => h('ul', { class: 'ob-list' },
      h('li', {}, h('b', {}, T('Semnezi', 'Sign')), T(' cu semnătura ta (imagine) sau cu certificat: buletin, token, stick-ul din birou.', ' with your signature (image) or a certificate: eID card, token, the office stick.')),
      h('li', {}, h('b', {}, T('Editezi', 'Edit')), T(' text, formulare, pagini; unești, împarți, comprimi, convertești.', ' text, forms, pages; merge, split, compress, convert.')),
      h('li', {}, h('b', {}, T('Întrebi', 'Ask')), T(' pe Claude despre document, direct din editor.', ' Claude about the document, right in the editor.'))) },
    { title: T('Semnătura ta', 'Your signature'), tip: T('Poză sau scan cu semnătura pe hârtie albă. Aplicația scoate fundalul și o ține în biblioteca ta.', 'A photo or scan of your signature on white paper. The app removes the background and keeps it in your library.'),
      body: async () => {
        let lib = []
        try { lib = await X.api('lib') } catch { /* biblioteca nu se poate citi: o arătăm goală */ }
        const n = lib.length
        const names = lib.slice(0, 4).map(s => s.name).join(', ') + (n > 4 ? '…' : '')
        return h('div', {}, h('div', { class: `dep${n ? ' ok' : ''}` },
          h('div', { class: 'dep-name' }, h('b', {}, n ? T(`${n} semnături în bibliotecă`, `${n} signatures in the library`) : T('Nicio semnătură încă', 'No signature yet')),
            n ? h('span', { class: 'muted' }, names) : null),
          h('button', { class: n ? 'secondary' : 'primary', type: 'button', onclick: () => suspend(() => X.openUpload()) }, n ? T('Adaugă încă una', 'Add another') : T('Adaugă semnătura', 'Add signature'))))
      } },
    { title: T('Semnătură electronică', 'Electronic signature'), tip: T('Certificatul trebuie să fie în Windows: buletinul sau tokenul în cititor, ori FintaxySign pornit pentru stick-ul din birou. PIN-ul îl scrii doar în fereastra Windows.', 'The certificate must be in Windows: the eID card or token in the reader, or FintaxySign running for the office stick. You type the PIN only in the Windows window.'),
      body: async () => {
        const box = h('div', {}, h('div', { class: 'muted' }, h('span', { class: 'spin' })))
        Promise.all([X.api('certs').catch(() => []), X.api('signenv').catch(() => ({}))]).then(([certs, env]) => {
          const good = certs.filter(c => !c.expired && c.signing)
          const fs = env.fintaxysign || {}
          box.replaceChildren(
            ...(good.length ? good.map(c => h('div', { class: 'dep ok' }, h('div', { class: 'dep-name' }, h('b', {}, c.sourceName), h('span', { class: 'muted' }, ` ${c.name}`)), h('span', { class: 'dep-state' }, svg('check'))))
              : [h('div', { class: 'dep' }, h('div', { class: 'dep-name' }, h('b', {}, T('Niciun certificat de semnare găsit', 'No signing certificate found'))))]),
            h('div', { class: `dep${fs.running && fs.stick ? ' ok' : ''}` }, h('div', { class: 'dep-name' }, h('b', {}, 'FintaxySign'), info(T('Aplicația prin care stick-ul din birou apare pe calculatorul tău. O primești de la Cristian.', 'The app that makes the office stick appear on your computer. You get it from Cristian.'))),
              h('span', { class: 'dep-state' }, fs.running ? (fs.stick ? T('Pornit, stick conectat', 'Running, stick connected') : T('Pornit, fără stick', 'Running, no stick')) : fs.path ? T('Oprit', 'Stopped') : T('Neinstalat', 'Not installed')),
              !fs.running && fs.path ? h('button', { class: 'secondary', type: 'button', onclick: () => X.post('fintaxysign/start', {}).then(() => X.toast(T('Am pornit FintaxySign.', 'Started FintaxySign.'))).catch(err => X.toast(err.message, { err: true })) }, T('Pornește', 'Start')) : null))
        })
        return box
      } },
    { title: 'Claude', tip: T('Chatul din editor vede PDF-ul deschis. Comentariile puse pe pagină (tasta C) și capturile de zonă (R) ajung la Claude.', 'The chat in the editor sees the open PDF. Comments pinned on the page (C key) and area captures (R) go to Claude.'),
      body: async () => {
        const box = h('div', {})
        let status
        try { status = await X.api('chat/status') } catch (err) { status = { available: false, step: 'error', error: err.message } }
        if (status.available) box.append(h('div', { class: 'dep ok' }, h('div', { class: 'dep-name' }, h('b', {}, T('Chatul cu Claude e gata', 'The Claude chat is ready'))), h('span', { class: 'dep-state' }, svg('check'))))
        else box.append(await chatSetup(status, () => render()))
        const copy = h('button', { class: 'secondary', type: 'button' }, T('Copiază promptul', 'Copy the prompt'))
        copy.addEventListener('click', async () => {
          try { await navigator.clipboard.writeText(MOD_PROMPT()); X.toast(T('Prompt copiat: lipește-l în Claude Code.', 'Prompt copied: paste it into Claude Code.')) } catch (err) { X.toast(err.message, { err: true }) }
        })
        box.append(h('div', { class: 'dep' }, h('div', { class: 'dep-name' }, h('b', {}, T('PDF Sign în Claude Code', 'PDF Sign inside Claude Code')),
          info(T('Opțional. Sub fiecare PDF din chatul Claude Code apar Preview / Deschide / Semnează, iar editorul se deschide în panoul lui Claude. Lipești promptul în Claude Code și el instalează modul.', 'Optional. Under every PDF in the Claude Code chat you get Preview / Open / Sign, and the editor opens in Claude\'s panel. Paste the prompt into Claude Code and it installs the mod.'))), copy))
        return box
      } },
    { title: T('Componente', 'Components'), tip: T('Fac parte din PDF Sign. Se instalează singure, în fundal, la prima pornire: nu ai nimic de făcut. Poți lucra între timp.', 'They are part of PDF Sign. They install by themselves, in the background, on first start: nothing for you to do. You can work meanwhile.'),
      body: () => depsBox() },
    { title: T('Gata', 'All set'), body: () => h('ul', { class: 'ob-list keys' },
      h('li', {}, h('kbd', {}, 'Ctrl+K'), T(' caută orice unealtă', ' search any tool')),
      h('li', {}, h('kbd', {}, 'S'), T(' semnătură · ', ' signature · '), h('kbd', {}, 'T'), T(' text · ', ' text · '), h('kbd', {}, 'E'), T(' editează textul', ' edit text')),
      h('li', {}, h('kbd', {}, 'A'), T(' Claude · ', ' Claude · '), h('kbd', {}, 'C'), T(' comentariu · ', ' comment · '), h('kbd', {}, 'P'), T(' pagini', ' pages')),
      h('li', {}, T('Ghidul se redeschide din Ctrl+K → „Ghid de pornire”.', 'Reopen this guide from Ctrl+K → “Getting started”.'))) },
  ]
  async function render() {
    const s = steps[i]
    const last = i === steps.length - 1
    const body = h('div', { class: 'ob-body' })
    card.replaceChildren(
      h('div', { class: 'ob-head' }, h('h2', {}, s.title), s.tip ? info(s.tip) : null, h('span', { class: 'grow' }),
        h('button', { class: 'icon', type: 'button', title: T('Închide acum (ghidul rămâne la butonul „?”)', 'Close for now (the guide stays under the “?” button)'), onclick: later }, X.icon('x'))),
      body,
      h('div', { class: 'ob-foot' },
        h('div', { class: 'ob-dots' }, ...steps.map((_, k) => h('span', { class: k === i ? 'on' : k < i ? 'done' : '' }))),
        h('span', { class: 'grow' }),
        i ? h('button', { class: 'secondary', type: 'button', onclick: () => { i--; render() } }, T('Înapoi', 'Back')) : h('button', { class: 'linkbtn', type: 'button', onclick: finish }, T('Sari peste tot', 'Skip all')),
        !last && i ? h('button', { class: 'linkbtn', type: 'button', onclick: () => { i++; render() } }, T('Sari peste', 'Skip')) : null,
        h('button', { class: 'primary', type: 'button', onclick: () => { if (last) finish(); else { i++; render() } } }, last ? T('Începe', 'Start') : T('Continuă', 'Continue'))))
    const mine = i
    const content = await s.body()
    if (mine === i) body.replaceChildren(content)
  }
  wrap.tabIndex = -1
  wrap.addEventListener('keydown', e => { if (e.key === 'Escape') { e.stopPropagation(); later() } })
  document.body.append(wrap)
  wrap.focus()
  render()
}

export function init(ctx) {
  X = ctx
  const rail = document.querySelector('#rail')
  const b = ctx.h('button', { 'data-panel': 'chat', title: T('Vorbește cu Claude (A sau Ctrl+J)', 'Talk to Claude (A or Ctrl+J)') }, svg('chat'))
  b.addEventListener('click', () => {
    const d = ctx.$('#drawer')
    if (!d.hidden && d.dataset.kind === 'chat') ctx.closeDrawer()
    else openChat()
  })
  rail.append(ctx.h('span', { class: 'rail-sep' }), b)
  document.addEventListener('keydown', e => {
    if (!((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'j')) return
    e.preventDefault()
    const d = ctx.$('#drawer')
    const sel = window.getSelection()
    const picked = sel && !sel.isCollapsed && !d.contains(sel.anchorNode) ? String(sel).trim().slice(0, 4000) : ''
    const quote = picked.split('\n').map(l => l.trim()).filter(Boolean)
    if (quote.length) return openChat(quote.map(l => `> ${l}`).join('\n') + '\n\n')
    b.click()
  })
  new MutationObserver(() => { const d = ctx.$('#drawer'); if (d.hidden || d.dataset.kind !== 'chat') { b.classList.remove('on'); closePop() } })
    .observe(ctx.$('#drawer'), { attributes: true, attributeFilter: ['hidden', 'data-kind'] })
  // Ghidul de pornire e mereu la îndemână: butonul „?” din bara de sus.
  const help = ctx.h('button', { class: 'icon', id: 'btnHelp', type: 'button', title: T('Ghid de pornire', 'Getting started') }, svg('help'))
  help.addEventListener('click', () => openOnboarding())
  document.querySelector('header.top .actions').prepend(help)
}
