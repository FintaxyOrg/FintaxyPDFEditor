// Editorul PDF din panoul lui Claude: pagini, semnături, text nou, editarea textului existent,
// comentarii și capturi pentru Claude, plus toate uneltele Stirling PDF.
// Toate pozițiile sunt în puncte PDF (pt), în pagina așa cum se vede; pe ecran = pt × scale.
import { FIELD_LABELS, GROUPS, TOOLS } from './tools.js'
import { lang, setLang, tr } from './i18n.js'
import { toolIconSvg } from './tool-icons.js'
import { init as initAssist, openChat, openDeps, openOnboarding } from './assist.js'

const Q = new URLSearchParams(location.search)
const TOKEN = Q.get('t') || ''
let PATH = Q.get('path') || ''

// Bara de sus poate trece pe mai multe rânduri când panoul e îngust: --top ține înălțimea ei reală.
const topBar = document.querySelector('header.top')
const syncTop = () => document.documentElement.style.setProperty('--top', `${Math.ceil(topBar.getBoundingClientRect().height)}px`)
new ResizeObserver(syncTop).observe(topBar)
syncTop()

// ---------- mărunțișuri ----------
const $ = (s, el = document) => el.querySelector(s)
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue
    if (k === 'class') el.className = v
    else if (k === 'style') Object.assign(el.style, v)
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v)
    else if (k === 'html') el.innerHTML = v
    else el.setAttribute(k, v === true ? '' : /^(title|placeholder|alt)$/.test(k) ? tr(v) : v)
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(tr(String(kid))))
  return el
}
const ICONS = {
  pointer: '<path d="M4.04 4.69a.5.5 0 0 1 .65-.65l16 6.5a.5.5 0 0 1-.06.95l-6.13 1.58a2 2 0 0 0-1.43 1.43l-1.58 6.13a.5.5 0 0 1-.95.06z"/>',
  sig: '<path d="m21 17-2.16-1.87a.5.5 0 0 0-.84.37v.5a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1c0-2.55-4-3.97-8.5-4a1 1 0 0 0 0 5c4.15 0 4.75-11.3 5.71-13.5a2.5 2.5 0 1 1 3.31 3.28"/><path d="M3 21h18"/>',
  type: '<polyline points="4 7 4 4 20 4 20 7"/><line x1="9" x2="15" y1="20" y2="20"/><line x1="12" x2="12" y1="4" y2="20"/>',
  edit: '<path d="M12 20h9"/><path d="M16.38 3.62a1 1 0 0 1 3 3L7.37 18.64a2 2 0 0 1-.86.5l-2.87.84a.5.5 0 0 1-.62-.62l.84-2.87a2 2 0 0 1 .5-.85z"/>',
  comment: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  region: '<path d="M5 3a2 2 0 0 0-2 2"/><path d="M19 3a2 2 0 0 1 2 2"/><path d="M21 19a2 2 0 0 1-2 2"/><path d="M5 21a2 2 0 0 1-2-2"/><path d="M9 3h1"/><path d="M9 21h1"/><path d="M14 3h1"/><path d="M14 21h1"/><path d="M3 9v1"/><path d="M21 9v1"/><path d="M3 14v1"/><path d="M21 14v1"/>',
  grid: '<rect width="7" height="7" x="3" y="3" rx="1.5"/><rect width="7" height="7" x="14" y="3" rx="1.5"/><rect width="7" height="7" x="14" y="14" rx="1.5"/><rect width="7" height="7" x="3" y="14" rx="1.5"/>',
  pages: '<path d="M15 2h-4a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V8z"/><path d="M15 2v6h6"/><path d="M5 7v12a2 2 0 0 0 2 2h9"/>',
  left: '<path d="m15 18-6-6 6-6"/>', right: '<path d="m9 18 6-6-6-6"/>',
  rotL: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
  rotR: '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
  minus: '<path d="M5 12h14"/>', plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  up: '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>', x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  move: '<path d="M12 2v20"/><path d="m15 19-3 3-3-3"/><path d="m19 9 3 3-3 3"/><path d="M2 12h20"/><path d="m5 9-3 3 3 3"/><path d="m9 5 3-3 3 3"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  open: '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
  tool: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
  copy: '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  back: '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  printer: '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6"/><rect x="6" y="14" width="12" height="8" rx="1"/>',
}
function icon(name) {
  const t = document.createElement('template')
  t.innerHTML = `<svg class="i" viewBox="0 0 24 24">${ICONS[name] || ''}</svg>`
  return t.content.firstChild
}
async function api(p, q = {}) {
  const r = await fetch(`/api/${p}?` + new URLSearchParams({ t: TOKEN, ...q }))
  const j = await r.json().catch(() => ({ ok: false, error: r.statusText }))
  if (!r.ok || j.ok === false) throw new Error(j.error || r.statusText)
  return j
}
async function post(p, body) {
  const r = await fetch(`/api/${p}?t=${encodeURIComponent(TOKEN)}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  const j = await r.json().catch(() => ({ ok: false, error: r.statusText }))
  if (!r.ok || j.ok === false) throw Object.assign(new Error(j.error || r.statusText), { data: j })
  return j
}
const url = (p, q) => `/api/${p}?` + new URLSearchParams({ t: TOKEN, ...q })
const base = p => (p || '').split(/[\\/]/).pop()
const typing = () => {
  const a = document.activeElement
  return a && (a.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName))
}
const FONT_CSS = { arial: 'Arial, sans-serif', times: '"Times New Roman", serif', calibri: 'Calibri, sans-serif', cour: '"Courier New", monospace',
  georgia: 'Georgia, serif', verdana: 'Verdana, sans-serif', tahoma: 'Tahoma, sans-serif', segoe: '"Segoe UI", sans-serif', cambria: 'Cambria, serif' }
const INK = [['#141720', 'Negru'], ['#1f3fbf', 'Albastru'], ['#c62828', 'Roșu']]

function toast(text, opts = {}) {
  const t = h('div', { class: 'toast' + (opts.err ? ' err' : '') }, h('span', {}, text))
  if (opts.action) t.append(h('button', { onclick: () => { t.remove(); opts.action.fn() } }, opts.action.label))
  $('#toasts').append(t)
  setTimeout(() => t.remove(), opts.ms || (opts.action ? 9000 : 4200))
  return t
}

// ---------- starea ----------
const S = {
  doc: null, pages: [], scale: 1, zoom: 1, tool: 'select', lib: [], sig: '', sigW: 113, fs: 11, color: '#141720', bold: false,
  items: [], sel: null, comments: [], runs: {}, uid: 0, pop: null, cur: 1, spec: null, sigQuery: '',
  app: { standalone: false, apps: [], ai: '' }, // aplicația separată (desktop.py): comentariile merg la o aplicație AI
}

// În panoul lui Claude comentariile ajung la Claude; în aplicația separată, la aplicația AI aleasă.
const aiName = () => (!S.app.standalone || S.app.ai === 'chat' ? 'Claude' : S.app.ai === 'copy' ? 'AI' : S.app.apps.find(a => a.id === S.app.ai)?.name || 'AI')
function applyAiName() {
  const n = aiName()
  HINTS.comment = `Click pe pagină unde vrei să-i spui ceva lui ${n}`
  HINTS.region = `Trage un dreptunghi peste zona pe care vrei s-o trimiți lui ${n}`
  $('.rail [data-tool=comment]').title = tr(`Comentariu pentru ${n} (C)`)
  $('.rail [data-tool=region]').title = tr(`Captură zonă pentru ${n} (R)`)
  if (HINTS[S.tool]) $('#hint').textContent = tr(HINTS[S.tool])
}
// Unde pleacă un comentariu: cele două feluri de Claude sunt butoane la vedere (panoul din dreapta, prin ACP, sau
// aplicația Claude Desktop); restul (Claude Code, ChatGPT, Gemini, clipboard) stau în lista „Altele”.
function aiPicker(onChange) {
  const main = [['chat', 'Claude · panou'], ['claude', 'Claude Desktop']].filter(([id]) => S.app.apps.some(a => a.id === id))
  const rest = S.app.apps.filter(a => !main.some(([id]) => id === a.id))
  const box = h('span', { class: 'aiseg' })
  const set = id => {
    S.app.ai = id
    post('settings', { ai: id }).catch(() => {})
    applyAiName()
    draw()
    onChange?.()
  }
  const draw = () => {
    const sel = h('select', { class: 'aipick', title: 'Altă aplicație AI (rămâne ținută minte)' },
      h('option', { value: '' }, 'Altele'), ...rest.map(a => h('option', { value: a.id, title: a.hint, selected: a.id === S.app.ai }, a.name)))
    sel.addEventListener('change', () => { if (sel.value) set(sel.value) })
    box.replaceChildren(...main.map(([id, label]) => h('button', { type: 'button', class: S.app.ai === id ? 'on' : '', title: S.app.apps.find(a => a.id === id)?.hint,
      onclick: () => set(id) }, label)), sel)
  }
  draw()
  return box
}
function sentToast(r, fallback) {
  if (r.sendError) toast(r.sendError, { err: true, ms: 8000 })
  else if (r.sent?.app === 'chat') openChat() // comentariul a plecat în chatul din editor: îl arătăm
  else toast(r.sent ? r.sent.note : fallback, { ms: r.sent ? 7000 : undefined })
}
const main = $('#pages')
const ghost = h('img', { class: 'ghost', alt: '' })

// ---------- documentul și paginile ----------
async function openDoc(path, page) {
  closePop()
  PATH = path
  const q = new URLSearchParams(location.search)
  q.set('path', path)
  q.delete('sig')
  history.replaceState(null, '', '?' + q)
  S.doc = await api('doc', { path })
  // paginile se țin în cache o oră; la fiecare deschidere cerem imaginea din fișierul de acum
  S.ver = Date.now()
  document.title = S.doc.name
  $('#docName').textContent = S.doc.name
  $('#docName').title = S.doc.path
  S.items = []
  S.sel = null
  S.runs = {}
  S.fields = {}
  buildPages()
  renderDocBar()
  layout()
  dirty()
  await loadComments()
  if (page && page > 1) S.pages[page - 1]?.el.scrollIntoView({ block: 'start' })
  updatePg()
  if (S.doc.signed) toast('PDF-ul are semnătură digitală: îl poți citi și comenta, dar orice modificare ar strica semnătura.', { ms: 7000 })
}

let observer
function buildPages() {
  main.replaceChildren()
  observer?.disconnect()
  observer = new IntersectionObserver(entries => {
    for (const en of entries) {
      if (!en.isIntersecting) continue
      const p = S.pages[+en.target.dataset.n - 1]
      loadImg(p)
      if (S.tool === 'edit') ensureRuns(p)
      if (S.doc.fields) ensureFields(p)
    }
  }, { root: main, rootMargin: '800px 0px' })
  S.pages = S.doc.pages.map((pg, i) => {
    const img = h('img', { alt: '' })
    const layer = h('div', { class: 'layer' })
    const el = h('div', { class: 'page', 'data-n': i + 1 }, img, layer, h('span', { class: 'num' }, `${i + 1}`))
    main.append(el)
    const p = { n: i + 1, w: pg.w, h: pg.h, el, img, layer, want: 0, canvas: null }
    img.addEventListener('load', () => { p.canvas = null })
    observer.observe(el)
    return p
  })
}

function loadImg(p) {
  const want = Math.min(3000, Math.ceil((p.w * S.scale * (window.devicePixelRatio || 1)) / 300) * 300)
  if (want <= p.want) return
  p.want = want
  p.img.src = url('page', { path: PATH, n: p.n, w: want, v: S.ver })
}

function layout() {
  if (!S.doc) return
  const avail = Math.max(240, main.clientWidth - 48)
  const maxW = Math.max(...S.pages.map(p => p.w))
  S.scale = (Math.min(avail, 1000) / maxW) * S.zoom
  for (const p of S.pages) {
    p.el.style.width = `${p.w * S.scale}px`
    p.el.style.height = `${p.h * S.scale}px`
    if (p.want) loadImg(p)
    for (const r of Array.isArray(S.runs[p.n]) ? S.runs[p.n] : []) placeRun(r)
  }
  S.items.forEach(place)
  S.comments.forEach(placeComment)
  const bar = $('#docbar')
  if (bar) bar.style.width = `${Math.max(320, maxW * S.scale)}px`
  sizeGhost()
  $('#zpct').textContent = `${Math.round(S.zoom * 100)}%`
  positionPop()
}

function updatePg() {
  if (!S.pages.length) return
  const mid = main.getBoundingClientRect().top + main.clientHeight / 2
  let best = 1, dist = Infinity
  for (const p of S.pages) {
    const r = p.el.getBoundingClientRect()
    const d = r.top <= mid && r.bottom >= mid ? 0 : Math.min(Math.abs(r.top - mid), Math.abs(r.bottom - mid))
    if (d < dist) { dist = d; best = p.n }
  }
  S.cur = best
  $('#pg').textContent = `${best} / ${S.pages.length}`
  $('#prev').disabled = best <= 1
  $('#next').disabled = best >= S.pages.length
}
const goTo = n => S.pages[n - 1]?.el.scrollIntoView({ behavior: 'smooth', block: 'start' })
const ZOOMS = [0.5, 0.67, 0.8, 1, 1.25, 1.5, 2, 2.5]
function setZoom(z) {
  const keep = S.cur
  S.zoom = z
  layout()
  S.pages[keep - 1]?.el.scrollIntoView({ block: 'start' })
  updatePg()
}
function stepZoom(d) {
  const i = ZOOMS.findIndex(z => z >= S.zoom - 0.001)
  setZoom(ZOOMS[Math.max(0, Math.min(ZOOMS.length - 1, (i < 0 ? ZOOMS.length - 1 : i) + d))])
}

const pageOf = e => {
  const el = e.target.closest?.('.page')
  return el ? S.pages[+el.dataset.n - 1] : null
}
function ptAt(p, e) {
  const r = p.el.getBoundingClientRect()
  return { x: (e.clientX - r.left) / S.scale, y: (e.clientY - r.top) / S.scale }
}
function pageAtPoint(clientY) {
  return S.pages.find(p => { const r = p.el.getBoundingClientRect(); return clientY >= r.top && clientY <= r.bottom }) || null
}

// ---------- unelte ----------
const HINTS = {
  select: 'Trage de semnături și texte ca să le muți · Delete le șterge',
  sig: 'Click pe pagină pune semnătura · Ctrl+rotiță sau glisorul = mărimea',
  text: 'Click pe pagină și scrie · trage de ✥ ca să muți textul',
  edit: 'Click pe orice rând din PDF și rescrie-l · Enter = gata · Esc = renunți',
  comment: 'Click pe pagină unde vrei să-i spui ceva lui Claude',
  region: 'Trage un dreptunghi peste zona pe care vrei s-o trimiți lui Claude',
  sigbox: 'Trage un dreptunghi unde vrei semnătura electronică · Esc = renunți',
}
function setTool(t) {
  if (S.boxPick && t !== 'sigbox') { const cb = S.boxPick; S.boxPick = null; cb(null) }
  S.tool = t
  document.body.dataset.tool = t
  for (const b of document.querySelectorAll('.rail [data-tool]')) b.classList.toggle('on', b.dataset.tool === t)
  if (t !== 'sig') { ghost.style.display = 'none'; $('#sigFlyout').hidden = true }
  if (t === 'sig' && !S.sig) openFlyout()
  if (t === 'edit') visiblePages().forEach(ensureRuns)
  closePop()
  renderCtx()
  $('#hint').textContent = tr(HINTS[t] || '')
}
function visiblePages() {
  const m = main.getBoundingClientRect()
  return S.pages.filter(p => { const r = p.el.getBoundingClientRect(); return r.bottom > m.top - 400 && r.top < m.bottom + 400 })
}

// ---------- semnături ----------
// O semnătură e identificată după fișierul ei (S.sig = calea), nu după poziția în listă:
// o semnătură nouă în bibliotecă schimbă ordinea, iar ce e deja pus pe pagină trebuie să rămână același.
const libBy = f => S.lib.find(s => s.file.toLowerCase() === String(f || '').toLowerCase())
const sigUrl = f => url('sig', { f })
const norm = s => String(s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
async function loadLib() {
  S.lib = await api('lib').catch(() => [])
  if (!$('#sigFlyout').hidden) renderFlyout()
}
function renderFlyout() {
  const fly = $('#sigFlyout')
  const q = h('input', { class: 'sigsearch', placeholder: 'Caută după nume', value: S.sigQuery || '' })
  const list = h('div', { class: 'siglist' })
  const draw = () => {
    S.sigQuery = q.value
    const k = norm(q.value.trim())
    const items = S.lib.filter(s => !k || norm(s.name).includes(k))
    list.replaceChildren()
    if (!items.length) list.append(h('div', { class: 'empty' }, S.lib.length ? 'Nicio semnătură cu numele ăsta.' : 'Biblioteca e goală.'))
    for (const s of items) {
      list.append(h('button', { class: 'sigopt' + (s.file === S.sig ? ' on' : ''), onclick: () => chooseSig(s.file) },
        h('img', { src: sigUrl(s.file), alt: '', loading: 'lazy' }), h('span', {}, s.name)))
    }
  }
  q.addEventListener('input', draw)
  q.addEventListener('keydown', e => { if (e.key === 'Enter') list.querySelector('.sigopt')?.click() })
  const pathIn = h('input', { class: 'sigsearch', placeholder: 'Calea folderului cu semnături', value: S.app.library || '', title: S.app.library || '' })
  const savePath = async () => {
    try {
      const r = await post('library', { path: pathIn.value })
      S.app.library = r.library
      await loadLib()
      renderFlyout()
      toast(`Folder setat: ${S.lib.length} semnături.`)
    } catch (e) { toast(e.message) }
  }
  pathIn.addEventListener('keydown', e => { if (e.key === 'Enter') savePath() })
  fly.replaceChildren(
    h('div', { class: 'flyhead' }, h('h3', {}, 'Alege semnătura'),
      h('span', { class: 'flyicons' }, h('button', { class: 'linkbtn iconbtn', title: 'Recitește folderul Semnaturi', 'aria-label': 'Actualizează', onclick: async () => {
        await loadLib()
        renderFlyout()
        toast(`Lista e la zi: ${S.lib.length} semnături.`)
      } }, icon('refresh')), ' ', h('button', { class: 'linkbtn', onclick: () => openUpload() }, '+ Nouă'),
      S.app.library ? [' ', h('button', { class: 'linkbtn iconbtn', title: 'Deschide folderul', 'aria-label': 'Folder',
        onclick: () => post('open', { path: S.app.library, how: 'explorer' }).catch(e => toast(e.message)) }, icon('folder'))] : null)),
    h('div', { class: 'libpath' }, pathIn, h('button', { class: 'linkbtn', onclick: savePath }, 'Setează')),
    h('label', { class: 'search' }, icon('search'), q), list)
  draw()
  return q
}
function openFlyout() {
  const fly = $('#sigFlyout')
  fly.hidden = false
  const q = renderFlyout()
  setTimeout(() => q.focus(), 0)
}
function chooseSig(f) {
  if (!libBy(f)) return
  S.sig = f
  ghost.src = sigUrl(f)
  $('#sigFlyout').hidden = true
  if (S.tool !== 'sig') setTool('sig')
  sizeGhost()
  renderCtx()
}
const ratio = f => libBy(f)?.ratio || 0.4
function sizeGhost() {
  if (!S.sig) return
  ghost.style.width = `${S.sigW * S.scale}px`
  ghost.style.height = `${S.sigW * ratio(S.sig) * S.scale}px`
}

// ---------- elementele puse pe pagină ----------
function changed() {
  return S.items.filter(it => (it.type === 'sig') || (it.type === 'text' && it.text.trim()) || (it.type === 'edit' && it.text !== it.orig) ||
    (it.type === 'field' && it.value !== it.orig))
}
function dirty() {
  const n = changed().length
  const btn = $('#btnSave')
  btn.disabled = !n || S.doc?.signed
  btn.textContent = tr(n ? `Salvează (${n})` : 'Salvează')
}
function select(it) {
  S.sel = it
  for (const o of S.items) o.el?.classList.toggle('sel', o === it && it.type !== 'edit')
  if (it?.type === 'sig') S.sigW = it.w
  if (it?.type === 'text') { S.fs = it.fs; S.color = it.color; S.bold = it.bold }
  renderCtx()
}
function removeItem(it) {
  it.el?.remove()
  S.items = S.items.filter(o => o !== it)
  if (S.sel === it) select(null)
  dirty()
}
function addItem(it) {
  it.id = ++S.uid
  S.items.push(it)
  renderItem(it)
  select(it)
  dirty()
  if (it.type === 'text') setTimeout(() => it.el.querySelector('.txt').focus(), 0)
}
function renderItem(it) {
  const p = S.pages[it.page - 1]
  const el = h('div', { class: 'item' })
  it.el = el
  const x = h('div', { class: 'x', title: 'Șterge' }, icon('x'))
  x.addEventListener('pointerdown', e => { e.stopPropagation(); e.preventDefault(); removeItem(it) })
  const grip = h('div', { class: 'grip', title: 'Mută' }, icon('move'))
  grip.addEventListener('pointerdown', e => startDrag(e, it))
  if (it.type === 'sig') {
    const img = h('img', { src: sigUrl(it.sig), alt: '' })
    img.addEventListener('pointerdown', e => startDrag(e, it))
    el.append(img)
  } else {
    const t = h('div', { class: 'txt', contenteditable: 'plaintext-only', spellcheck: 'false' })
    t.textContent = it.text
    t.addEventListener('input', () => { it.text = t.innerText.replace(/\n$/, ''); dirty() })
    t.addEventListener('focus', () => select(it))
    t.addEventListener('blur', () => { if (!it.text.trim()) removeItem(it) })
    t.addEventListener('pointerdown', e => e.stopPropagation())
    el.append(t)
  }
  el.append(grip, x)
  el.addEventListener('click', e => { e.stopPropagation(); select(it) })
  p.layer.append(el)
  place(it)
}
function place(it) {
  const k = S.scale
  if (it.type === 'edit') return placeEdit(it)
  if (it.type === 'field') return placeField(it)
  it.el.style.left = `${it.x * k}px`
  it.el.style.top = `${it.y * k}px`
  if (it.type === 'sig') {
    it.el.style.width = `${it.w * k}px`
    it.el.style.height = `${it.w * ratio(it.sig) * k}px`
  } else {
    const t = it.el.querySelector('.txt')
    Object.assign(t.style, { fontSize: `${it.fs * k}px`, fontFamily: FONT_CSS.arial, fontWeight: it.bold ? '700' : '400', color: it.color })
  }
}
let drag = null
function startDrag(e, it) {
  e.preventDefault()
  e.stopPropagation()
  select(it)
  const r = it.el.getBoundingClientRect()
  drag = { it, dx: e.clientX - r.left, dy: e.clientY - r.top }
}
window.addEventListener('pointermove', e => {
  if (!drag) return
  const p = pageAtPoint(e.clientY) || S.pages[drag.it.page - 1]
  if (p.n !== drag.it.page) { drag.it.page = p.n; p.layer.append(drag.it.el) }
  const r = p.el.getBoundingClientRect()
  drag.it.x = (e.clientX - drag.dx - r.left) / S.scale
  drag.it.y = (e.clientY - drag.dy - r.top) / S.scale
  place(drag.it)
})
window.addEventListener('pointerup', () => { drag = null })

// ---------- câmpurile formularului ----------
// Câmpurile PDF-ului (text, bife, liste) se completează direct pe pagină; Salvează le scrie în PDF.
// Cele doar de citit rămân transparente: pagina de dedesubt arată deja valoarea lor.
async function ensureFields(p) {
  if (S.fields[p.n]) return
  S.fields[p.n] = true
  const doc = S.doc
  try {
    const list = await api('fields', { path: PATH, n: p.n })
    if (doc !== S.doc) return
    for (const f of list) {
      const it = { ...f, type: 'field', page: p.n, orig: f.value, id: ++S.uid }
      S.items.push(it)
      renderField(it)
    }
  } catch (err) {
    S.fields[p.n] = false
    toast(`Nu am putut citi câmpurile de pe pagina ${p.n}: ${err.message}`, { err: true })
  }
}
function renderField(it) {
  const p = S.pages[it.page - 1]
  const off = it.readonly || S.doc.signed
  const title = it.label || it.name
  let el
  if (it.kind === 'check' || it.kind === 'radio') {
    el = h('input', { type: 'checkbox', class: 'ffield chk', title, disabled: off, checked: !!it.value })
    el.addEventListener('change', () => {
      it.value = el.checked
      // butoanele radio cu același nume: doar unul bifat
      if (it.kind === 'radio' && el.checked) {
        for (const o of S.items) if (o !== it && o.type === 'field' && o.kind === 'radio' && o.name === it.name) { o.value = false; o.el.checked = false }
      }
      for (const o of S.items) if (o.type === 'field' && o.el?.classList.contains('chk')) o.el.classList.toggle('changed', !!o.value !== !!o.orig)
      dirty()
    })
  } else if (it.kind === 'combo' || it.kind === 'list') {
    el = h('select', { class: 'ffield', title, disabled: off }, h('option', { value: '' }, ''),
      ...it.options.map(o => h('option', { value: o, selected: o === it.value }, o)))
    el.addEventListener('change', () => { it.value = el.value; el.classList.toggle('changed', it.value !== it.orig); dirty() })
  } else {
    el = h(it.multiline ? 'textarea' : 'input', { class: 'ffield', title, disabled: off, maxlength: it.maxlen || null, spellcheck: 'false' })
    el.value = it.value
    el.addEventListener('input', () => { it.value = el.value; el.classList.toggle('changed', it.value !== it.orig); dirty() })
  }
  el.addEventListener('pointerdown', e => e.stopPropagation())
  it.el = el
  p.layer.append(el)
  placeField(it)
}
function placeField(it) {
  const k = S.scale
  const [x0, y0, x1, y1] = it.rect
  const hgt = y1 - y0
  Object.assign(it.el.style, { left: `${x0 * k}px`, top: `${y0 * k}px`, width: `${(x1 - x0) * k}px`, height: `${hgt * k}px`,
    fontSize: `${(it.fs || Math.max(6, Math.min(11, it.multiline ? 10 : hgt * 0.62))) * k}px` })
}

// ---------- editarea textului existent ----------
async function ensureRuns(p) {
  if (S.runs[p.n]) return
  S.runs[p.n] = 'loading'
  try {
    const runs = await api('runs', { path: PATH, n: p.n })
    S.runs[p.n] = runs
    runs.forEach((r, i) => {
      r.i = i
      r.el = h('div', { class: 'run', title: r.text })
      r.el.addEventListener('click', e => { e.stopPropagation(); startEdit(p, r) })
      p.layer.append(r.el)
      placeRun(r)
    })
  } catch (err) {
    S.runs[p.n] = null
    toast(`Nu am putut citi textul paginii ${p.n}: ${err.message}`, { err: true })
  }
}
function placeRun(r) {
  const k = S.scale
  Object.assign(r.el.style, { left: `${r.bbox[0] * k}px`, top: `${r.bbox[1] * k}px`, width: `${(r.bbox[2] - r.bbox[0]) * k}px`, height: `${(r.bbox[3] - r.bbox[1]) * k}px` })
}
function sampleBg(p, xPt, yPt) {
  try {
    const img = p.img
    if (!img.complete || !img.naturalWidth) return '#fff'
    if (!p.canvas) {
      p.canvas = document.createElement('canvas')
      p.canvas.width = img.naturalWidth
      p.canvas.height = img.naturalHeight
      p.canvas.getContext('2d', { willReadFrequently: true }).drawImage(img, 0, 0)
    }
    const k = img.naturalWidth / p.w
    const d = p.canvas.getContext('2d').getImageData(Math.max(0, Math.round(xPt * k)), Math.max(0, Math.round(yPt * k)), 1, 1).data
    return `rgb(${d[0]}, ${d[1]}, ${d[2]})`
  } catch {
    return '#fff'
  }
}
// Fonturile din PDF în browser: cel încorporat (dacă browserul îl poate citi), apoi cel instalat, apoi cel apropiat.
// O literă care lipsește din primul (PDF-urile păstrează doar literele folosite) se ia din următorul, ca la salvare.
const FONT_FAMS = new Map()
function fontStack(sg) {
  const fams = []
  const f = sg.fonts || {}
  for (const ref of [f.embeddedWeb ? f.embedded : null, /\.(ttf|otf)$/i.test(f.system || '') ? f.system : null]) {
    if (!ref) continue
    const key = `${PATH}|${ref}`
    let fam = FONT_FAMS.get(key)
    if (!fam) {
      fam = `pdffont${FONT_FAMS.size}`
      FONT_FAMS.set(key, fam)
      const face = new FontFace(fam, `url("${url('font', { path: PATH, ref })}")`)
      document.fonts.add(face)
      face.load().catch(() => {})
    }
    fams.push(`"${fam}"`)
  }
  fams.push(FONT_CSS[sg.font] || FONT_CSS.arial)
  return fams.join(', ')
}
const segStyle = (sg, k) => ({ fontSize: `${sg.size * k}px`, fontFamily: fontStack(sg), fontWeight: sg.bold ? '700' : '400',
  fontStyle: sg.italic ? 'italic' : 'normal', color: sg.color, fontSynthesis: 'none' })

// Un rând se editează întreg: fiecare bucată (segment) e un <span> cu stilul ei; la salvare restul rândului se mută
// cât s-a lungit sau scurtat textul, deci nimic nu ajunge peste altceva.
function fillEditBox(it) {
  it.el.replaceChildren(...it.segments.map((sg, i) => {
    const sp = h('span', { 'data-i': i })
    sp.textContent = sg.orig // fără tr(): e text din PDF
    return sp
  }))
}
function readEditBox(it) {
  const texts = it.segments.map(() => '')
  let last = 0
  for (const node of it.el.childNodes) {
    const i = node.nodeType === 1 && node.dataset?.i != null ? +node.dataset.i : last
    texts[i] += node.textContent.replace(/\n/g, ' ')
    last = i
  }
  it.segments.forEach((sg, i) => { sg.text = texts[i] })
  it.text = texts.join('')
}
function startEdit(p, r) {
  if (S.doc.signed) return toast('PDF-ul are semnătură digitală; nu-l modific.', { err: true })
  let it = S.items.find(o => o.type === 'edit' && o.page === p.n && o.ri === r.i)
  if (!it) {
    const x = r.bbox[0] > 4 ? r.bbox[0] - 3 : r.bbox[2] + 3
    it = { type: 'edit', page: p.n, ri: r.i, raw: r.raw, bbox: r.bbox, segments: r.segments.map(sg => ({ ...sg, orig: sg.text })),
      text: r.text, orig: r.text, bg: sampleBg(p, x, (r.bbox[1] + r.bbox[3]) / 2) }
    it.id = ++S.uid
    const el = h('div', { class: 'editbox', contenteditable: 'true', spellcheck: 'false' })
    it.el = el
    fillEditBox(it)
    el.addEventListener('input', () => {
      readEditBox(it)
      el.classList.toggle('changed', it.text !== it.orig)
      dirty()
    })
    el.addEventListener('paste', e => {
      e.preventDefault()
      document.execCommand('insertText', false, (e.clipboardData?.getData('text/plain') || '').replace(/\s*\n\s*/g, ' '))
    })
    el.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && /^[biu]$/i.test(e.key)) e.preventDefault() // fără formatare HTML
      if (e.key === 'Enter') { e.preventDefault(); el.blur() }
      if (e.key === 'Escape') { e.preventDefault(); fillEditBox(it); placeEdit(it); readEditBox(it); el.blur() }
    })
    el.addEventListener('blur', () => { if (it.text === it.orig) removeItem(it) })
    el.addEventListener('pointerdown', e => e.stopPropagation())
    el.addEventListener('click', e => e.stopPropagation())
    S.items.push(it)
    p.layer.append(el)
    placeEdit(it)
  }
  it.el.focus()
  const sel = getSelection()
  sel.selectAllChildren(it.el)
  sel.collapseToEnd()
}
function placeEdit(it) {
  const k = S.scale
  const [x0, y0, x1, y1] = it.bbox
  Object.assign(it.el.style, {
    left: `${x0 * k - 1}px`, top: `${y0 * k}px`, minWidth: `${(x1 - x0) * k + 2}px`, height: `${(y1 - y0) * k}px`,
    lineHeight: `${(y1 - y0) * k}px`, background: it.bg, ...segStyle(it.segments[0], k),
  })
  for (const sp of it.el.querySelectorAll('[data-i]')) {
    const i = +sp.dataset.i
    const sg = it.segments[i]
    const gap = i ? sg.origin[0] - it.segments[i - 1].raw[2] : 0 // spațiul dintre bucăți, ca în PDF
    Object.assign(sp.style, segStyle(sg, k), { marginLeft: gap > 0.5 ? `${gap * k}px` : '' })
  }
}

// ---------- click-uri pe pagină ----------
main.addEventListener('click', e => {
  if (e.target.closest('.item, .pin, .editbox, .run, .ffield, .docbar')) return
  const p = pageOf(e)
  if (!p) return
  const pt = ptAt(p, e)
  if (S.tool === 'sig') {
    if (!S.sig) return openFlyout()
    if (S.doc.signed) return toast('PDF-ul are semnătură digitală; nu-l modific.', { err: true })
    const w = S.sigW
    addItem({ type: 'sig', page: p.n, sig: S.sig, w, x: pt.x - w / 2, y: pt.y - (w * ratio(S.sig)) / 2 })
    hold = { x: e.clientX, y: e.clientY }
    ghost.style.display = 'none'
  } else if (S.tool === 'text') {
    if (document.activeElement?.classList.contains('txt')) return document.activeElement.blur()
    if (S.doc.signed) return toast('PDF-ul are semnătură digitală; nu-l modific.', { err: true })
    addItem({ type: 'text', page: p.n, x: pt.x, y: pt.y - S.fs * 0.6, fs: S.fs, text: '', color: S.color, bold: S.bold, font: 'arial' })
  } else if (S.tool === 'comment') {
    openDraft(p, { kind: 'point', x: pt.x, y: pt.y })
  } else if (S.tool === 'select') {
    select(null)
    closePop()
  }
})
let hold = null
main.addEventListener('pointermove', e => {
  if (S.tool !== 'sig' || !S.sig || drag) return
  const p = pageOf(e)
  if (!p || e.target.closest('.item')) { ghost.style.display = 'none'; return }
  if (hold && Math.hypot(e.clientX - hold.x, e.clientY - hold.y) < 12) return
  hold = null
  if (ghost.parentNode !== p.layer) p.layer.append(ghost)
  const pt = ptAt(p, e)
  ghost.style.display = 'block'
  ghost.style.left = `${(pt.x - S.sigW / 2) * S.scale}px`
  ghost.style.top = `${(pt.y - (S.sigW * ratio(S.sig)) / 2) * S.scale}px`
})
main.addEventListener('pointerleave', () => { ghost.style.display = 'none' })

// captură de zonă
let zone = null
main.addEventListener('pointerdown', e => {
  if ((S.tool !== 'region' && S.tool !== 'sigbox') || e.button !== 0 || e.target.closest('.pin')) return
  const p = pageOf(e)
  if (!p) return
  e.preventDefault()
  closePop()
  const a = ptAt(p, e)
  zone = { p, a, el: h('div', { class: 'zone draft' }) }
  p.layer.append(zone.el)
  main.setPointerCapture(e.pointerId)
})
main.addEventListener('pointermove', e => {
  if (!zone) return
  const b = ptAt(zone.p, e)
  zone.rect = [Math.max(0, Math.min(zone.a.x, b.x)), Math.max(0, Math.min(zone.a.y, b.y)), Math.min(zone.p.w, Math.max(zone.a.x, b.x)), Math.min(zone.p.h, Math.max(zone.a.y, b.y))]
  const k = S.scale
  Object.assign(zone.el.style, { left: `${zone.rect[0] * k}px`, top: `${zone.rect[1] * k}px`, width: `${(zone.rect[2] - zone.rect[0]) * k}px`, height: `${(zone.rect[3] - zone.rect[1]) * k}px` })
})
main.addEventListener('pointerup', () => {
  if (!zone) return
  const z = zone
  zone = null
  if (!z.rect || (z.rect[2] - z.rect[0]) * S.scale < 10 || (z.rect[3] - z.rect[1]) * S.scale < 10) return z.el.remove()
  if (S.tool === 'sigbox') {
    // locul semnăturii electronice, ales din formularul de semnare
    const cb = S.boxPick
    S.boxPick = null
    z.el.classList.add('sigzone')
    setTool('select')
    return cb ? cb({ p: z.p, rect: z.rect, el: z.el }) : z.el.remove()
  }
  openDraft(z.p, { kind: 'region', rect: z.rect, zoneEl: z.el })
})

// ---------- comentarii ----------
async function loadComments() {
  for (const c of S.comments) { c.pin?.remove(); c.zone?.remove() }
  S.comments = await api('comments', { path: PATH }).catch(() => [])
  S.comments.forEach(renderComment)
  countComments()
}
function countComments() {
  const n = S.comments.length
  const el = $('#commentCount')
  el.hidden = !n
  el.textContent = n
}
function renderComment(c) {
  const p = S.pages[c.page - 1]
  if (!p) return
  c.pin = h('div', { class: 'pin', title: c.text }, String(c.number || '•'))
  c.pin.addEventListener('click', e => { e.stopPropagation(); openView(c) })
  if (c.kind === 'region') { c.zone = h('div', { class: 'zone' }); p.layer.append(c.zone) }
  p.layer.append(c.pin)
  placeComment(c)
}
function placeComment(c) {
  const k = S.scale
  if (!c.pin) return
  if (c.kind === 'region') {
    const [x0, y0, x1, y1] = c.rect
    Object.assign(c.zone.style, { left: `${x0 * k}px`, top: `${y0 * k}px`, width: `${(x1 - x0) * k}px`, height: `${(y1 - y0) * k}px` })
    Object.assign(c.pin.style, { left: `${x1 * k - 4}px`, top: `${y0 * k + 6}px` })
  } else {
    Object.assign(c.pin.style, { left: `${c.x * k}px`, top: `${c.y * k}px` })
  }
}
async function contextFor(p, spec) {
  await ensureRuns(p)
  const runs = Array.isArray(S.runs[p.n]) ? S.runs[p.n] : []
  if (spec.kind === 'region') {
    const [x0, y0, x1, y1] = spec.rect
    const inside = runs.filter(r => r.bbox[0] < x1 && r.bbox[2] > x0 && r.bbox[1] < y1 && r.bbox[3] > y0).map(r => r.text)
    return inside.join(' ').replace(/\s+/g, ' ').trim()
  }
  let best = '', dist = 1e9
  for (const r of runs) {
    const dx = spec.x < r.bbox[0] ? r.bbox[0] - spec.x : spec.x > r.bbox[2] ? spec.x - r.bbox[2] : 0
    const dy = spec.y < r.bbox[1] ? r.bbox[1] - spec.y : spec.y > r.bbox[3] ? spec.y - r.bbox[3] : 0
    const d = dx + dy * 1.5
    if (d < dist) { dist = d; best = r.text }
  }
  return dist < 120 ? best : ''
}
const short = (s, n = 48) => (s.length > n ? s.slice(0, n - 1) + '…' : s)
function crumbFor(n, ctx, kind) {
  return `Pagina ${n}${kind === 'region' ? ' › zonă selectată' : ''}${ctx ? ` › „${short(ctx)}”` : ''}`
}

async function openDraft(p, spec) {
  closePop()
  const draftPin = h('div', { class: 'pin draft' }, '+')
  p.layer.append(draftPin)
  const k = S.scale
  if (spec.kind === 'region') Object.assign(draftPin.style, { left: `${spec.rect[2] * k - 4}px`, top: `${spec.rect[1] * k + 6}px` })
  else Object.assign(draftPin.style, { left: `${spec.x * k}px`, top: `${spec.y * k}px` })
  const crumb = h('div', { class: 'crumb' }, crumbFor(p.n, '', spec.kind))
  const ta = h('textarea', { rows: 2, placeholder: spec.kind === 'region' ? `Ce vrei să facă ${aiName()} cu zona asta?` : `Ce vrei să-i spui lui ${aiName()} aici?` })
  const send = h('input', { type: 'checkbox', checked: true })
  const btn = h('button', { class: 'send', title: 'Trimite (Enter)', disabled: true }, icon('up'))
  const mention = h('span', { class: 'mention' }, `@${aiName()}`)
  const pop = h('div', { class: 'pop' }, crumb, mention, ta,
    h('div', { class: 'row' }, h('label', {}, send, S.app.standalone ? 'Trimite la' : 'Trimite lui Claude'),
      S.app.standalone ? aiPicker(() => { mention.textContent = `@${aiName()}`; ta.focus() }) : null, h('span', { class: 'grow' }), btn))
  document.body.append(pop)
  S.pop = { el: pop, anchor: draftPin, cleanup: () => { draftPin.remove(); spec.zoneEl?.remove() } }
  positionPop()
  ta.focus()
  contextFor(p, spec).then(ctx => { spec.context = ctx; crumb.textContent = tr(crumbFor(p.n, ctx, spec.kind)) })
  const autosize = () => { ta.style.height = 'auto'; ta.style.height = `${ta.scrollHeight}px` }
  ta.addEventListener('input', () => { btn.disabled = !ta.value.trim(); autosize() })
  const submit = async () => {
    if (!ta.value.trim()) return
    btn.disabled = true
    btn.replaceChildren(h('span', { class: 'spin', style: { margin: 0, borderTopColor: '#fff' } }))
    try {
      const body = { path: PATH, page: p.n, kind: spec.kind, text: ta.value, send: send.checked, ai: S.app.ai }
      if (spec.kind === 'region') body.rect = spec.rect
      else Object.assign(body, { x: spec.x, y: spec.y })
      const r = await post('comment', body)
      S.pop.cleanup()
      S.pop.el.remove()
      S.pop = null
      S.comments.push(r.comment)
      renderComment(r.comment)
      countComments()
      sentToast(r, send.checked ? 'Trimis lui Claude: îl găsești în chat.' : 'Comentariu salvat.')
    } catch (err) {
      btn.disabled = false
      btn.replaceChildren(icon('up'))
      toast(err.message, { err: true })
    }
  }
  btn.addEventListener('click', submit)
  ta.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
    if (e.key === 'Escape') { e.preventDefault(); closePop() }
  })
}
function openView(c) {
  closePop()
  const body = [h('div', { class: 'crumb' }, crumbFor(c.page, c.context || '', c.kind)), h('div', { class: 'body' }, c.text)]
  if (c.capture) body.push(h('img', { class: 'shot', src: url('capture', { path: PATH, id: c.id }), alt: 'Captura zonei' }))
  const sendBtn = h('button', { class: 'linkbtn', onclick: async () => {
    try {
      const r = await post('comment/send', { path: PATH, id: c.id, ai: S.app.ai })
      c.send = true
      if (r.comment?.sentTo) c.sentTo = r.comment.sentTo
      sentToast(r, 'Trimis lui Claude.')
      openView(c)
    } catch (err) { toast(err.message, { err: true }) }
  } }, S.app.standalone ? (c.send ? 'Trimite din nou' : 'Trimite') : 'Trimite lui Claude')
  const del = h('button', { class: 'linkbtn danger', onclick: async () => {
    try {
      await post('comment/delete', { path: PATH, id: c.id })
      c.pin?.remove(); c.zone?.remove()
      S.comments = S.comments.filter(o => o !== c)
      countComments()
      closePop()
    } catch (err) { toast(err.message, { err: true }) }
  } }, 'Șterge')
  body.push(h('div', { class: 'row' }, h('span', { class: 'meta' }, c.send ? `Trimis ${c.sentTo ? `la ${c.sentTo}` : 'lui Claude'} · ${c.created || ''}` : `Doar notă · ${c.created || ''}`),
    h('span', { class: 'grow' }), c.send && !S.app.standalone ? null : sendBtn, del))
  if (S.app.standalone) body.push(h('div', { class: 'row' }, h('span', { class: 'meta' }, 'Trimite la'), aiPicker()))
  const pop = h('div', { class: 'pop' }, ...body)
  document.body.append(pop)
  S.pop = { el: pop, anchor: c.pin, cleanup: () => {} }
  positionPop()
}
function positionPop() {
  if (!S.pop) return
  const a = S.pop.anchor.getBoundingClientRect()
  const w = S.pop.el.offsetWidth, hh = S.pop.el.offsetHeight
  let left = a.right + 8, top = a.top
  if (left + w > innerWidth - 8) left = Math.max(8, a.left - w - 8)
  if (top + hh > innerHeight - 8) top = Math.max(56, innerHeight - hh - 8)
  S.pop.el.style.left = `${left}px`
  S.pop.el.style.top = `${Math.max(56, top)}px`
}
function closePop() {
  if (!S.pop) return
  S.pop.cleanup()
  S.pop.el.remove()
  S.pop = null
}

// ---------- bara contextuală ----------
function renderCtx() {
  const bar = $('#ctxbar')
  bar.replaceChildren()
  const it = S.sel
  if ((S.tool === 'sig' && S.sig) || it?.type === 'sig') {
    const f = it?.type === 'sig' ? it.sig : S.sig
    const range = h('input', { type: 'range', min: 40, max: 340, step: 2, value: S.sigW })
    range.addEventListener('input', () => setSigW(+range.value))
    bar.append(h('button', { class: 'secondary', onclick: openFlyout, title: 'Schimbă semnătura' },
      h('img', { src: sigUrl(f), alt: '', style: { height: '18px', maxWidth: '60px', objectFit: 'contain', verticalAlign: 'middle', marginRight: '6px' } }),
      libBy(f)?.name || ''), h('span', { class: 'lbl' }, 'Mărime'), range)
  } else if (S.tool === 'text' || it?.type === 'text') {
    const val = h('span', { class: 'val' }, `${S.fs} pt`)
    const keep = e => e.preventDefault() // textul rămâne în editare
    bar.append(
      h('button', { class: 'icon', title: 'Mai mic', onpointerdown: keep, onclick: () => { setFs(S.fs - 1); val.textContent = `${S.fs} pt` } }, icon('minus')), val,
      h('button', { class: 'icon', title: 'Mai mare', onpointerdown: keep, onclick: () => { setFs(S.fs + 1); val.textContent = `${S.fs} pt` } }, icon('plus')),
      h('span', { class: 'sep' }),
      h('button', { class: 'icon' + (S.bold ? ' on' : ''), title: 'Bold', onpointerdown: keep, onclick: e => { S.bold = !S.bold; e.currentTarget.classList.toggle('on', S.bold); if (S.sel?.type === 'text') { S.sel.bold = S.bold; place(S.sel) } } }, h('b', {}, 'B')),
      h('span', { class: 'sep' }),
      ...INK.map(([c, name]) => h('button', { class: 'swatch' + (S.color === c ? ' on' : ''), title: name, style: { background: c }, onpointerdown: keep, onclick: e => {
        S.color = c
        bar.querySelectorAll('.swatch').forEach(s => s.classList.toggle('on', s === e.currentTarget))
        if (S.sel?.type === 'text') { S.sel.color = c; place(S.sel) }
      } })))
  }
}
function setSigW(v) {
  S.sigW = Math.max(40, Math.min(340, v))
  sizeGhost()
  const it = S.sel
  if (it?.type === 'sig') {
    const cx = it.x + it.w / 2, cy = it.y + (it.w * ratio(it.sig)) / 2
    it.w = S.sigW
    it.x = cx - it.w / 2
    it.y = cy - (it.w * ratio(it.sig)) / 2
    place(it)
  }
  const range = $('#ctxbar input[type=range]')
  if (range) range.value = S.sigW
}
function setFs(v) {
  S.fs = Math.max(6, Math.min(48, v))
  if (S.sel?.type === 'text') { S.sel.fs = S.fs; place(S.sel) }
}

// ---------- salvarea ----------
function serialize() {
  return changed().map(it => {
    const { el, id, ri, bg, orig, bbox, ...rest } = it
    return rest
  })
}
async function save(rotate) {
  const items = serialize()
  if (!items.length && !rotate) return
  if (document.activeElement?.isContentEditable) document.activeElement.blur()
  const btn = $('#btnSave')
  btn.disabled = true
  btn.textContent = tr('Se salvează…')
  const source = PATH
  try {
    const r = await post('save', { path: PATH, items: serialize(), rotate })
    await openDoc(r.out, S.cur)
    toast(`${rotate ? 'Rotit și salvat' : 'Salvat'}: ${base(r.out)}`, { action: { label: 'Anulează', fn: () => undo(r.out, source) } })
  } catch (err) {
    dirty()
    toast(err.message, { err: true, ms: 8000 })
  }
}
// Rotirea se scrie imediat în fișier, împreună cu ce s-a pus deja pe pagini (în pagina de dinainte de rotire).
function rotate(angle, all) {
  if (!S.doc) return
  if (S.doc.signed) return toast('PDF-ul are semnătură digitală; rotirea ar strica-o.', { err: true })
  save({ pages: all ? S.pages.map(p => p.n) : [S.cur], angle })
}
async function undo(out, source) {
  try {
    const r = await post('undo', { path: out })
    await openDoc(r.removed ? source : out, S.cur)
    toast('Am anulat ultima salvare.')
  } catch (err) {
    toast(err.message, { err: true })
  }
}

// ---------- printarea ----------
// Pe hârtie ies doar paginile, câte una pe foaie, fiecare întreagă pe foaia aleasă în dialog (A4, Letter), fără interfață.
// Foaia n-are margini (editor.css), deci browserul n-are unde să pună antetul și subsolul lui (data, titlul, adresa).
// Butonul de printare și Ctrl+P: serverul scrie în memorie ce e pus în editor și nesalvat încă, exact ca la salvare,
// și dă paginile ca imagini de tipar. Printarea din meniul browserului nu poate aștepta serverul: ia paginile de pe
// ecran, cu tot ce e pus pe ele, într-un SVG care le potrivește pe foaie.
const SVGNS = 'http://www.w3.org/2000/svg'
const endPrint = () => $('#printRoot')?.remove()
// Rezoluția de tipar: 300 dpi la documentele obișnuite, mai puțin la cele foarte lungi (memoria browserului).
function printDpi() {
  const inch2 = S.pages.reduce((a, p) => a + (p.w / 72) * (p.h / 72), 0)
  return Math.max(120, Math.min(300, Math.floor(Math.sqrt(120e6 / Math.max(inch2, 1)))))
}
async function printDoc() {
  if (!S.doc || S.printing) return
  if (typing()) document.activeElement.blur()
  S.printing = true
  endPrint()
  const note = toast(`Pregătesc printarea: 0 din ${S.pages.length} pagini…`, { ms: 120000 })
  try {
    const r = await post('print', { path: PATH, items: serialize() })
    const dpi = printDpi()
    const root = h('div', { id: 'printRoot' })
    const imgs = r.pages.map((pg, i) => {
      const img = h('img', { alt: '', class: pg.w > pg.h ? 'land' : 'port', src: url('printpage', { id: r.id, n: i + 1, dpi }) })
      root.append(h('div', { class: 'sheet' }, img))
      return img
    })
    document.body.append(root)
    let ready = 0
    const failed = []
    await Promise.all(imgs.map((img, i) => img.decode().then(() => {
      note.firstChild.textContent = tr(`Pregătesc printarea: ${++ready} din ${imgs.length} pagini…`)
    }, () => failed.push(i + 1))))
    if (failed.length) {
      endPrint()
      return toast(`Nu am putut pregăti pagina ${failed.sort((a, b) => a - b).join(', ')}; nu printez.`, { err: true, ms: 8000 })
    }
    note.remove()
    window.print()
  } catch (err) {
    endPrint()
    toast(err.message, { err: true, ms: 8000 })
  } finally {
    note.remove()
    S.printing = false
  }
}
function printRootFromScreen() {
  const root = h('div', { id: 'printRoot' })
  for (const p of S.pages) {
    const W = p.w * S.scale, H = p.h * S.scale
    const svg = document.createElementNS(SVGNS, 'svg')
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`)
    svg.setAttribute('class', p.w > p.h ? 'land' : 'port')
    const fo = document.createElementNS(SVGNS, 'foreignObject')
    fo.setAttribute('width', W)
    fo.setAttribute('height', H)
    const page = p.el.cloneNode(true)
    const from = p.el.querySelectorAll('.ffield'), to = page.querySelectorAll('.ffield')
    from.forEach((f, i) => { to[i].value = f.value; to[i].checked = f.checked }) // valorile nu se copiază cu cloneNode
    fo.append(page)
    svg.append(fo)
    root.append(h('div', { class: 'sheet' }, svg))
  }
  return root
}
addEventListener('beforeprint', () => {
  if (S.printing || !S.doc || $('#printRoot')) return
  const missing = S.pages.some(p => !p.img.complete || !p.img.naturalWidth)
  document.body.append(printRootFromScreen())
  if (missing) setTimeout(() => toast('Unele pagini nu erau încărcate. Printează cu butonul de printare (Ctrl+P), care le pregătește pe toate.', { err: true, ms: 9000 }), 0)
})
addEventListener('afterprint', endPrint)

// ---------- sertarul din dreapta ----------
function openDrawer(title, ...content) {
  const d = $('#drawer')
  d.hidden = false
  delete d.dataset.kind
  d.replaceChildren(h('div', { class: 'dh' }, h('h2', {}, title), h('button', { class: 'icon', title: 'Închide', onclick: closeDrawer }, icon('x'))), ...content)
  return d
}
function closeDrawer() {
  $('#drawer').hidden = true
  document.querySelector('.rail [data-panel=tools]').classList.remove('on')
}

function openCommentsList() {
  const list = h('div', { class: 'db clist' })
  if (!S.comments.length) list.append(h('div', { class: 'empty' }, 'Nu ai comentarii pe acest PDF. Alege 💬 sau ⬚ din stânga și dă click pe pagină.'))
  for (const c of [...S.comments].sort((a, b) => a.page - b.page || (a.number || 0) - (b.number || 0))) {
    list.append(h('div', { class: 'c', onclick: () => { closeDrawer(); c.pin.scrollIntoView({ block: 'center', behavior: 'smooth' }); setTimeout(() => openView(c), 350) } },
      h('span', { class: 'n' }, String(c.number || '•')),
      h('div', {}, h('div', {}, c.text), h('div', { class: 'ct' }, crumbFor(c.page, c.context || '', c.kind) + (c.send ? ' · trimis' : '')))))
  }
  openDrawer(`Comentarii (${S.comments.length})`, list)
}

async function loadSpec() {
  if (!S.spec) S.spec = api('stirling/tools').catch(err => { S.spec = null; throw err })
  return S.spec
}
function toolsCatalog() {
  return TOOLS.filter(t => !t.native || t.native)
}
function openTools(filter = '') {
  document.querySelector('.rail [data-panel=tools]').classList.add('on')
  const input = h('input', { placeholder: 'Caută o unealtă (ex. comprimă, parolă, word)', value: filter })
  const list = h('div', { class: 'db' })
  const draw = async () => {
    const q = input.value.trim().toLowerCase()
    list.replaceChildren()
    const match = t => !q || `${t.label} ${t.desc || ''} ${tr(t.label)} ${tr(t.desc || '')} ${t.endpoint || ''}`.toLowerCase().includes(q)
    for (const g of GROUPS) {
      const tools = toolsCatalog().filter(t => t.group === g.id && match(t))
      if (!tools.length) continue
      list.append(h('div', { class: 'grp' }, g.label))
      for (const t of tools) list.append(toolRow(t))
    }
    // tot ce mai are Stirling și nu e în catalog
    const known = new Set(TOOLS.map(t => t.endpoint))
    const spec = await loadSpec().catch(() => null)
    if (!spec) {
      return list.append(h('div', { class: 'empty' }, S.app.stirling
        ? 'Uneltele Stirling se încarcă când deschizi una (pornesc Stirling PDF dacă e nevoie).'
        : 'Uneltele marcate „Stirling” (OCR, conversii rare) au nevoie de Stirling PDF instalat; restul merg direct.'))
    }
    const rest = Object.entries(spec.tools).filter(([ep, s]) => !known.has(ep) && !/text-editor|pipeline/.test(ep) && match({ label: s.summary, endpoint: ep }))
    if (rest.length) {
      list.append(h('div', { class: 'grp' }, `Toate uneltele Stirling ${spec.version || ''}`))
      for (const [ep, s] of rest.sort((a, b) => a[1].summary.localeCompare(b[1].summary))) {
        list.append(toolRow({ id: ep, label: s.summary || ep, endpoint: ep, desc: ep.replace('/api/v1/', ''), suffix: ep.split('/').pop() }))
      }
    }
  }
  input.addEventListener('input', draw)
  openDrawer('Unelte PDF', h('label', { class: 'search' }, icon('search'), input), list)
  draw()
  input.focus()
}
// Ca în Stirling: iconiță + nume; descrierea apare la hover (și rămâne căutabilă).
function toolRow(t) {
  const ic = document.createElement('template')
  ic.innerHTML = toolIconSvg(t)
  return h('button', { class: 'tool', title: t.desc || '', onclick: () => (t.native ? (closeDrawer(), setTool(t.native)) : openToolForm(t)) },
    ic.content.firstChild, h('span', { class: 'tl' }, t.label),
    needsStirling(t) ? h('span', { class: 'needs', title: 'Are nevoie de Stirling PDF instalat' }, 'Stirling') : null)
}

const humanize = n => n.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/^./, c => c.toUpperCase())
function fileToB64(file) {
  return new Promise((res, rej) => {
    const r = new FileReader()
    r.onload = () => res({ name: file.name, type: file.type, b64: r.result })
    r.onerror = rej
    r.readAsDataURL(file)
  })
}

// ---------- uneltele din aplicație (bin/localtools.py) ----------
// Formularul se face din câmpurile scrise în catalog (tools.js): text, pagini, număr, listă, bifă, parolă, fișiere.
function localField(form, f) {
  const label = h('span', {}, f.label + (f.required ? ' *' : ''))
  if (f.type === 'files') {
    const files = []
    const list = h('div', { class: 'blist' })
    const draw = () => {
      list.replaceChildren(...files.map((p, i) => h('div', { class: 'brow' }, h('span', { class: 'bn', title: p }, base(p)),
        h('button', { class: 'linkbtn danger', type: 'button', onclick: () => { files.splice(i, 1); draw() } }, 'Scoate'))))
      if (!files.length) list.append(h('div', { class: 'empty' }, 'Niciun fișier ales.'))
    }
    const add = h('button', { class: 'secondary', type: 'button' }, '+ Adaugă fișiere…')
    add.addEventListener('click', async () => {
      try {
        const r = await post('pickmany', { dir: S.doc?.dir || '', kind: f.kind || 'pdf' })
        for (const p of r.paths) if (!files.some(x => x.toLowerCase() === p.toLowerCase())) files.push(p)
        draw()
      } catch (err) {
        toast(err.message, { err: true })
      }
    })
    draw()
    form.append(h('div', { class: 'field' }, label, list, h('div', {}, add)))
    return () => files
  }
  let el
  if (f.type === 'select') {
    el = h('select', {}, ...f.options.map(([v, l]) => h('option', { value: v, selected: String(v) === String(f.def ?? '') }, l)))
  } else if (f.type === 'check') {
    el = h('input', { type: 'checkbox', checked: !!f.def })
    form.append(h('label', { class: 'field' }, h('span', { class: 'check' }, el, f.label)))
    return () => el.checked
  } else {
    const ph = f.type === 'pages' ? 'toate; sau ex. 1-3, 5, 8-' : f.ph || ''
    el = h('input', { type: f.type === 'password' ? 'password' : f.type === 'number' ? 'number' : 'text', placeholder: ph })
    if (f.def != null) el.value = String(f.def)
  }
  form.append(h('label', { class: 'field' }, label, el))
  return () => el.value
}
function openLocalTool(t) {
  const form = h('div', { class: 'form' })
  const d = openDrawer(t.label, h('div', { class: 'db' }, form))
  d.querySelector('.dh').prepend(h('button', { class: 'icon', title: 'Înapoi la unelte', onclick: () => openTools() }, icon('back')))
  if (t.desc) form.append(h('p', { class: 'desc' }, t.desc))
  if (changed().length && !t.noDoc) form.append(h('div', { class: 'warn' }, 'Ai modificări nesalvate. Unealta lucrează pe fișierul salvat; apasă întâi Salvează dacă vrei să le includă.'))
  const reads = (t.fields || []).map(f => [f, localField(form, f)])
  const go = h('button', { class: 'primary' }, 'Rulează')
  const result = h('div')
  form.append(h('div', { class: 'buttons' }, go), result)
  go.addEventListener('click', async () => {
    const fields = {}
    for (const [f, read] of reads) {
      const v = read()
      if (f.required && (v === '' || (Array.isArray(v) && !v.length))) return result.replaceChildren(h('div', { class: 'result err' }, tr(`Completează: ${f.label}`)))
      fields[f.name] = v
    }
    go.disabled = true
    result.replaceChildren(h('div', { class: 'result' }, h('span', { class: 'spin' }), 'Lucrez…'))
    try {
      const r = await post('local', { tool: t.local, path: t.noDoc ? '' : PATH, dir: S.doc?.dir || '', fields, label: t.label })
      result.replaceChildren(showResult(r))
    } catch (err) {
      const box = h('div', { class: 'result err' }, err.message)
      if (/LibreOffice/.test(err.message) && /în fundal/.test(err.message)) {
        box.append(h('div', { class: 'rb' }, h('button', { class: 'secondary', type: 'button', onclick: () => openDeps() }, 'Vezi starea componentelor')))
      }
      result.replaceChildren(box)
    } finally {
      go.disabled = false
    }
  })
}
// Uneltele care au rămas doar în Stirling: fără el, un mesaj cu ce e de instalat în loc de o eroare.
const needsStirling = t => !t.local && !t.custom && !t.native && t.endpoint && !S.app.stirling
const refreshStirling = async () => { if (!S.app.stirling) { try { S.app.stirling = (await api('info')).stirling } catch { /* rămâne cum era */ } } }

async function openToolForm(t) {
  if (t.custom === 'certsign') return openCertSign()
  if (t.custom === 'bulksign') return openBulkSign()
  if (t.custom === 'organize') return openOrganize()
  if (t.local) return openLocalTool(t)
  await refreshStirling()
  const body = h('div', { class: 'db' })
  const d = openDrawer(t.label, body)
  d.querySelector('.dh').prepend(h('button', { class: 'icon', title: 'Înapoi la unelte', onclick: () => openTools() }, icon('back')))
  if (needsStirling(t)) {
    return body.replaceChildren(h('div', { class: 'form' }, t.desc ? h('p', { class: 'desc' }, t.desc) : null,
      h('div', { class: 'warn' }, 'Unealta asta face parte din pachetul Stirling, care se instalează singur în fundal la prima pornire. Încearcă din nou în câteva minute.'),
      h('div', { class: 'buttons' }, h('button', { class: 'secondary', type: 'button', onclick: () => openDeps() }, 'Vezi starea componentelor'))))
  }
  body.append(h('div', { class: 'form' }, h('p', { class: 'desc' }, h('span', { class: 'spin' }), 'Încarc unealta din Stirling PDF…')))
  let spec
  try {
    spec = (await loadSpec()).tools[t.endpoint]
  } catch (err) {
    return body.replaceChildren(h('div', { class: 'form' }, h('div', { class: 'result err' }, `Stirling PDF nu răspunde: ${err.message}`)))
  }
  if (!spec) return body.replaceChildren(h('div', { class: 'form' }, h('div', { class: 'result err' }, 'Unealta nu există în versiunea ta de Stirling PDF.')))
  const form = h('div', { class: 'form' })
  body.replaceChildren(form)
  form.append(h('p', { class: 'desc' }, t.desc || spec.description || spec.summary))
  if (changed().length && !t.noDoc) form.append(h('div', { class: 'warn' }, 'Ai modificări nesalvate. Unealta lucrează pe fișierul salvat; apasă întâi Salvează dacă vrei să le includă.'))
  const controls = []
  const mainName = spec.fields.find(f => f.name === 'fileInput' || f.name === 'file')?.name
  const extra = {}
  {
    for (const f of spec.fields) {
      if (f.name === 'fileId' || f.name === 'clientFileIds') continue
      const isFile = f.format === 'binary' || f.itemFormat === 'binary'
      if (f.name === mainName && !t.noDoc) {
        if (f.type === 'array') {
          const inp = h('input', { type: 'file', multiple: true, accept: '.pdf,application/pdf' })
          extra[f.name] = inp
          form.append(h('label', { class: 'field' }, h('span', {}, 'Alte fișiere (după cel deschis)'), inp))
        }
        continue
      }
      if (isFile) {
        const inp = h('input', { type: 'file', multiple: f.type === 'array' })
        extra[f.name] = inp
        form.append(h('label', { class: 'field' }, h('span', {}, (FIELD_LABELS[f.name] || humanize(f.name)) + (f.required ? ' *' : '')), inp,
          f.description ? h('small', {}, f.description) : null))
        continue
      }
      form.append(fieldControl(f, controls, t))
    }
  }
  const result = h('div')
  const go = h('button', { class: 'primary' }, 'Rulează')
  form.append(h('div', { class: 'buttons' }, go), result)
  go.addEventListener('click', async () => {
    const fields = {}
    for (const c of controls) {
      const v = c.read()
      if (v !== undefined && v !== '' && !(Array.isArray(v) && !v.length)) fields[c.name] = v
    }
    const files = {}
    for (const [name, inp] of Object.entries(extra)) {
      if (inp.files.length) files[name] = await Promise.all([...inp.files].map(fileToB64))
    }
    if (t.noDoc && !Object.keys(files).length && !fields.urlInput) return result.replaceChildren(h('div', { class: 'result err' }, 'Alege fișierul de convertit.'))
    go.disabled = true
    result.replaceChildren(h('div', { class: 'result' }, h('span', { class: 'spin' }), 'Rulez unealta…'))
    try {
      const firstFile = Object.values(files)[0]?.[0]?.name
      const r = await post('stirling/run', { path: PATH, endpoint: t.endpoint, fields, files, suffix: t.suffix || t.id, label: t.label,
        usesDocument: !t.noDoc, outStem: t.noDoc && firstFile ? firstFile.replace(/\.[^.]+$/, '') : undefined })
      result.replaceChildren(showResult(r))
    } catch (err) {
      result.replaceChildren(h('div', { class: 'result err' }, err.message))
    } finally {
      go.disabled = false
    }
  })
}

function fieldControl(f, controls, t) {
  const label = (FIELD_LABELS[f.name] || humanize(f.name)) + (f.required ? ' *' : '')
  // Doar valorile implicite reale; exemplele din API (ex. 25KB la comprimare) rămân sugestii.
  const def = t?.defaults?.[f.name] ?? f.default
  const hintVal = f.example != null && typeof f.example !== 'object' ? String(f.example) : ''
  const help = f.description ? h('small', {}, f.description) : null
  let el, read
  if (f.type === 'boolean') {
    el = h('input', { type: 'checkbox', checked: def === true || def === 'true' })
    read = () => el.checked
    controls.push({ name: f.name, read })
    return h('label', { class: 'field' }, h('span', { class: 'check' }, el, label), help)
  }
  if (f.type === 'array' && f.enum) {
    el = h('select', { multiple: true, size: Math.min(6, f.enum.length) }, ...f.enum.map(v => h('option', { value: v, selected: Array.isArray(def) ? def.includes(v) : v === def }, String(v))))
    read = () => [...el.selectedOptions].map(o => o.value)
  } else if (f.enum) {
    el = h('select', {}, ...(f.required ? [] : [h('option', { value: '' }, '—')]), ...f.enum.map(v => h('option', { value: v, selected: String(v) === String(def) }, String(v))))
    read = () => el.value
  } else if (f.type === 'integer' || f.type === 'number') {
    el = h('input', { type: 'number', step: f.type === 'integer' ? 1 : 'any', value: def ?? '', placeholder: hintVal })
    read = () => el.value
  } else if (f.type === 'array') {
    el = h('textarea', { rows: 3, placeholder: 'câte unul pe rând' })
    if (Array.isArray(def)) el.value = def.join('\n')
    read = () => el.value.split('\n').map(s => s.trim()).filter(Boolean)
  } else if (f.type === 'object') {
    el = h('textarea', { rows: 4, placeholder: 'JSON' })
    read = () => el.value
  } else {
    const long = /listOfText|Text$|text$|json|fields|edits|names|javascript/i.test(f.name)
    el = long ? h('textarea', { rows: 3, placeholder: hintVal }) : h('input', { type: /password/i.test(f.name) ? 'password' : 'text', placeholder: hintVal })
    if (def != null) el.value = String(def)
    read = () => el.value
  }
  controls.push({ name: f.name, read })
  return h('label', { class: 'field' }, h('span', {}, label), el, help)
}

// ---------- semnătura electronică (certificat) ----------
// Semnează prin Windows (bin/certsign.py), fără Stirling: buletinul electronic, un token sau stick-ul din birou
// prin FintaxySign (cititor de card virtual). Windows cere PIN-ul în fereastra lui; la mai multe PDF-uri, o dată.
const NO_CERT = 'Buletinul electronic: e în cititor? Stick-ul din birou: pornește FintaxySign și verifică să scrie „connected” și „Driver installed”, apoi apasă Reîncarcă.'
// Rândul de stare al FintaxySign (stick-ul din birou, folosit de la distanță): pornit?, driver?, stick conectat?
async function fintaxySignRow(box, reload) {
  let fs
  try { fs = (await api('signenv')).fintaxysign } catch { return box.replaceChildren() }
  const start = h('button', { class: 'linkbtn', type: 'button' }, 'Pornește FintaxySign')
  start.addEventListener('click', async () => {
    start.disabled = true
    try {
      await post('fintaxysign/start', {})
      toast('Am pornit FintaxySign. Așteaptă să scrie „connected”, apoi apasă Reîncarcă.')
      setTimeout(reload, 6000)
    } catch (err) { toast(err.message, { err: true }) }
    start.disabled = false
  })
  let cls = 'ok', text = 'FintaxySign: pornit, stick conectat'
  let extra = null
  if (!fs.running) { cls = 'off'; text = fs.path ? 'FintaxySign: oprit' : 'FintaxySign: neinstalat pe acest calculator'; extra = fs.path ? start : null }
  else if (!fs.driver) { cls = 'warn'; text = 'FintaxySign: pornit, dar lipsește driverul (apasă „Install driver…” în FintaxySign)' }
  else if (!fs.stick) { cls = 'warn'; text = 'FintaxySign: pornit, stick-ul nu e conectat încă (verifică să scrie „connected”)' }
  box.replaceChildren(...[h('span', { class: `dot ${cls}` }), h('span', {}, text), extra].filter(Boolean))
}
function certPicker(form) {
  const sel = h('select', {}, h('option', { value: '' }, 'Se încarcă certificatele…'))
  const help = h('small', {})
  const pin = h('div', { class: 'pinhint', hidden: true })
  const fsRow = h('div', { class: 'fsrow' })
  const reload = h('button', { class: 'linkbtn', type: 'button' }, '↻ Reîncarcă')
  form.append(h('label', { class: 'field' }, h('span', {}, 'Certificat *'), sel, help), pin, h('div', { class: 'certrow' }, reload, fsRow))
  let list = []
  let again = 0
  const showPin = () => {
    const c = list.find(x => x.thumb === sel.value)
    pin.hidden = !c?.pinHint
    pin.textContent = c?.pinHint ? tr(c.pinHint) : ''
  }
  const draw = () => {
    let last = ''
    try { last = localStorage.getItem('fx-cert') || '' } catch { /* fără memorie, alegem primul */ }
    const keep = sel.value || last
    sel.replaceChildren(...list.map(c => h('option', { value: c.thumb, disabled: c.expired }, c.label)))
    const usable = list.filter(c => !c.expired)
    sel.value = usable.some(c => c.thumb === keep) ? keep : usable[0]?.thumb || ''
    showPin()
  }
  const load = async fresh => {
    clearTimeout(again)
    if (fresh !== 'quiet') sel.replaceChildren(h('option', { value: '' }, 'Se încarcă certificatele…'))
    help.textContent = ''
    fintaxySignRow(fsRow, () => load(true))
    try {
      list = await api('certs', fresh === true ? { fresh: 1 } : {})
      if (!list.length) {
        sel.replaceChildren(h('option', { value: '' }, 'Niciun certificat de semnare în Windows'))
        help.textContent = tr(NO_CERT)
        pin.hidden = true
        return
      }
      draw()
      // Stick-ul de la distanță răspunde uneori abia după câteva secunde: mai întrebăm o dată, fără să clipească lista.
      if (list.some(c => c.pending) && sel.isConnected) again = setTimeout(() => load('quiet'), 4000)
    } catch (err) {
      sel.replaceChildren(h('option', { value: '' }, `Eroare: ${err.message}`))
    }
  }
  reload.addEventListener('click', () => load(true))
  sel.addEventListener('change', () => { showPin(); try { localStorage.setItem('fx-cert', sel.value) } catch { /* nu e esențial */ } })
  load()
  return () => sel.value
}
// Trimite semnarea și arată, cât durează, ce se întâmplă (se deschide cheia, Windows cere PIN-ul, se semnează),
// cu buton de anulare: fereastra de PIN e a Windows-ului și omul trebuie să știe mereu unde să se uite.
const SIGN_PHASE = {
  open: 'Deschid cheia certificatului…',
  wait: 'Aștept fereastra de PIN de la Windows… Cu stick-ul din birou, dacă e la un coleg, aștepți câteva secunde rândul.',
  pin: 'Scrie PIN-ul în fereastra „Windows Security”, care a apărut peste editor.',
  hidden: 'Windows a deschis fereastra de PIN, dar o ține ascunsă. Apasă Anulează și încearcă din nou.',
  sign: 'PIN primit. Se semnează…',
}
async function runSign(body, result) {
  const text = h('span', {}, SIGN_PHASE.open)
  const stop = h('button', { class: 'linkbtn danger', type: 'button' }, 'Anulează')
  stop.addEventListener('click', () => { stop.disabled = true; post('certsign/cancel', {}).catch(() => {}) })
  result.replaceChildren(h('div', { class: 'result signing' }, h('span', { class: 'spin' }), text, stop))
  let on = true
  const poll = async () => {
    while (on) {
      await new Promise(r => setTimeout(r, 600))
      if (!on) break
      try {
        const st = await api('certsign/status')
        if (!st.active) continue
        const key = st.phase === 'pin' && st.dialog === 'hidden' ? 'hidden' : st.phase
        const many = st.total > 1 ? ` (${Math.min(st.done + 1, st.total)}/${st.total}: ${st.file})` : ''
        text.textContent = tr(SIGN_PHASE[key] || SIGN_PHASE.open) + many
      } catch { /* serverul e ocupat cu semnarea: mai întrebăm */ }
    }
  }
  poll()
  try {
    return await post('certsign', body)
  } finally {
    on = false
  }
}
function textInputs(form, ...names) {
  return names.map(([label, ph]) => {
    const inp = h('input', { type: 'text', placeholder: ph || '' })
    form.append(h('label', { class: 'field' }, h('span', {}, label), inp))
    return inp
  })
}

function openCertSign() {
  if (!S.doc) return toast('Deschide întâi un PDF.')
  closePop()
  const form = h('div', { class: 'form' })
  const d = openDrawer('Semnătură electronică', h('div', { class: 'db' }, form))
  form.append(h('p', { class: 'desc' }, 'Semnătură digitală calificată cu un certificat din Windows: buletinul electronic, un token sau stick-ul din birou (FintaxySign). Windows îți cere PIN-ul.'))
  if (changed().length) form.append(h('div', { class: 'warn' }, 'Ai modificări nesalvate. Semnătura se pune pe fișierul salvat: apasă întâi Salvează.'))
  if (S.doc.signed) form.append(h('div', { class: 'warn' }, 'PDF-ul are deja o semnătură; a ta se adaugă după ea, fără s-o strice.'))
  const thumb = certPicker(form)
  const empty = S.doc.sigfields.filter(f => !f.signed && f.visible)
  const opts = [...empty.map(f => [`field:${f.name}`, `În câmpul de semnătură de pe pagina ${f.page}`]),
    ['box', 'Aleg locul pe pagină (trag un dreptunghi)'], ['none', 'Invizibilă (se vede în panoul de semnături)']]
  const where = h('select', {}, ...opts.map(([v, l]) => h('option', { value: v }, l)))
  const boxInfo = h('small', {})
  form.append(h('label', { class: 'field' }, h('span', {}, 'Unde apare semnătura'), where, boxInfo))
  let box = null
  const pick = () => {
    d.hidden = true
    toast('Trage un dreptunghi pe pagină unde vrei semnătura.')
    S.boxPick = z => {
      d.hidden = false
      if (!z) { if (!box) where.value = 'none'; return }
      box?.el.remove()
      box = z
      boxInfo.replaceChildren(tr(`Pe pagina ${z.p.n}.`) + ' ', h('button', { class: 'linkbtn', type: 'button', onclick: pick }, 'Alege alt loc'))
    }
    setTool('sigbox')
  }
  where.addEventListener('change', () => {
    if (where.value === 'box') return pick()
    box?.el.remove()
    box = null
    boxInfo.replaceChildren()
  })
  const [reason, location] = textInputs(form, ['Motiv (opțional)'], ['Locul (opțional)', 'ex. București'])
  const go = h('button', { class: 'primary' }, 'Semnează')
  const result = h('div')
  form.append(h('div', { class: 'buttons' }, go), result)
  go.addEventListener('click', async () => {
    const t = thumb()
    if (!t) return result.replaceChildren(h('div', { class: 'result err' }, 'Alege certificatul.'))
    let place = null
    if (where.value.startsWith('field:')) place = { field: where.value.slice(6) }
    else if (where.value === 'box') {
      if (!box) return pick()
      place = { page: box.p.n, rect: box.rect }
    }
    go.disabled = true
    try {
      const r = await runSign({ thumb: t, items: [{ path: PATH, place }], reason: reason.value, location: location.value }, result)
      const res = r.results[0]
      if (!res?.ok) throw new Error(res?.error || 'Semnarea nu a reușit.')
      box?.el.remove()
      await openDoc(res.out, S.cur)
      result.replaceChildren(showResult({ kind: 'pdf', out: res.out }))
      toast(`Semnat electronic: ${base(res.out)}`)
    } catch (err) {
      result.replaceChildren(h('div', { class: 'result err' }, err.message))
    } finally {
      go.disabled = false
    }
  })
}

function openBulkSign() {
  closePop()
  const files = S.doc ? [S.doc.path] : []
  const form = h('div', { class: 'form' })
  openDrawer('Semnează mai multe PDF-uri', h('div', { class: 'db' }, form))
  form.append(h('p', { class: 'desc' }, 'Semnătură electronică pe mai multe PDF-uri deodată, cu un singur PIN. Fiecare PDF e semnat în câmpul lui de semnătură gol (declarațiile ANAF, formularele) sau, dacă nu are, invizibil. Lângă fiecare apare <nume>_semnat.pdf.'))
  const list = h('div', { class: 'blist' })
  const add = h('button', { class: 'secondary', type: 'button' }, '+ Adaugă PDF-uri…')
  const go = h('button', { class: 'primary' })
  const draw = () => {
    list.replaceChildren(...files.map((f, i) => h('div', { class: 'brow' }, h('span', { class: 'bn', title: f }, base(f)),
      h('button', { class: 'linkbtn danger', type: 'button', onclick: () => { files.splice(i, 1); draw() } }, 'Scoate'))))
    if (!files.length) list.append(h('div', { class: 'empty' }, 'Adaugă PDF-urile de semnat.'))
    go.textContent = `${tr('Semnează toate')} (${files.length})`
    go.disabled = !files.length
  }
  add.addEventListener('click', async () => {
    try {
      const r = await post('pickmany', { dir: S.doc?.dir || '' })
      for (const p of r.paths) if (!files.some(f => f.toLowerCase() === p.toLowerCase())) files.push(p)
      draw()
    } catch (err) {
      toast(err.message, { err: true })
    }
  })
  form.append(h('div', { class: 'field' }, h('span', {}, 'Fișiere'), list, h('div', {}, add)))
  const thumb = certPicker(form)
  const [reason, location] = textInputs(form, ['Motiv (opțional)'], ['Locul (opțional)', 'ex. București'])
  form.append(h('div', { class: 'warn' }, 'Cu stick-ul din birou (FintaxySign): apasă întâi „Reserve 2 min” în FintaxySign, ca să nu-l ia un coleg între fișiere (altfel PIN-ul se cere din nou).'))
  const result = h('div')
  form.append(h('div', { class: 'buttons' }, go), result)
  draw()
  go.addEventListener('click', async () => {
    const t = thumb()
    if (!t) return result.replaceChildren(h('div', { class: 'result err' }, 'Alege certificatul.'))
    go.disabled = true
    try {
      const r = await runSign({ thumb: t, items: files.map(path => ({ path, place: 'auto' })), reason: reason.value, location: location.value }, result)
      const ok = r.results.filter(x => x.ok).length
      const rows = r.results.map(x => h('div', { class: 'brow' }, h('span', { class: 'bn', title: x.out || x.path }, `${x.ok ? '✓' : '✗'} ${base(x.out || x.path)}`),
        x.ok ? h('button', { class: 'linkbtn', type: 'button', onclick: () => post('open', { path: x.out, how: 'explorer' }) }, 'Explorer') : h('small', {}, x.error)))
      const skipped = files.length - r.results.length
      result.replaceChildren(h('div', { class: `result ${ok === files.length ? 'ok' : 'err'}` },
        h('div', {}, `${ok} din ${files.length} semnate` + (skipped ? ` · ${skipped} nesemnate (semnarea a fost oprită)` : '')), ...rows))
      const mine = r.results.find(x => x.ok && x.path.toLowerCase() === (S.doc?.path || '').toLowerCase())
      if (mine) await openDoc(mine.out, S.cur)
    } catch (err) {
      result.replaceChildren(h('div', { class: 'result err' }, err.message))
    } finally {
      go.disabled = !files.length
    }
  })
}

// ---------- bara documentului: formulare XFA (ANAF), atașamente, câmp de semnătură gol ----------
function renderDocBar() {
  $('#docbar')?.remove()
  const d = S.doc
  const rows = []
  if (d.xfa) {
    rows.push(h('div', { class: 'row' }, h('b', {}, 'Formular inteligent (XFA)'),
      h('span', {}, 'ca declarațiile ANAF. Îl poți citi și semna electronic aici; datele se completează în programul ANAF sau în Adobe Reader.')))
  } else if (d.fields && !d.signed) {
    rows.push(h('div', { class: 'row' }, h('b', {}, `Formular cu ${d.fields} câmpuri`), h('span', {}, 'completează-le direct pe pagină, apoi Salvează.')))
  }
  for (const a of d.attachments) {
    const act = how => post('attachment', { path: PATH, key: a.key, how }).catch(err => toast(err.message, { err: true }))
    rows.push(h('div', { class: 'row' }, h('b', {}, 'Atașat:'), h('span', { class: 'att' }, a.name),
      h('span', { class: 'meta' }, a.size ? `${Math.max(1, Math.round(a.size / 1024))} KB` : ''),
      h('button', { class: 'secondary', onclick: () => act('open') }, 'Deschide'),
      h('button', { class: 'secondary', onclick: () => act('folder') }, 'Arată în folder')))
  }
  const empty = d.sigfields.filter(f => !f.signed && f.visible)
  if (empty.length) {
    rows.push(h('div', { class: 'row' }, h('b', {}, 'Câmp de semnătură gol'), h('span', {}, `pe pagina ${empty[0].page}.`),
      h('button', { class: 'primary', onclick: openCertSign }, 'Semnează electronic')))
  }
  if (rows.length) main.prepend(h('div', { class: 'docbar', id: 'docbar' }, ...rows))
}

function showResult(r) {
  const notes = (r.lines || []).map(l => h('div', { style: { fontSize: '12.5px', marginTop: '4px' } }, l))
  if (r.kind === 'report') return h('div', { class: 'result ok' }, ...notes)
  if (r.kind === 'json') {
    const text = JSON.stringify(r.json, null, 2)
    return h('div', { class: 'result ok' }, '✓ Gata', h('pre', {}, text),
      h('div', { class: 'rb' }, h('button', { class: 'secondary', onclick: () => navigator.clipboard.writeText(text).then(() => toast('Copiat.')) }, 'Copiază')))
  }
  const name = base(r.out)
  const rb = h('div', { class: 'rb' })
  if (r.kind === 'pdf') rb.append(h('button', { class: 'primary', onclick: () => { closeDrawer(); openDoc(r.out) } }, 'Deschide aici'))
  else rb.append(h('button', { class: 'primary', onclick: () => post('open', { path: r.out }) }, r.kind === 'folder' ? 'Deschide folderul' : 'Deschide'))
  rb.append(h('button', { class: 'secondary', onclick: () => post('open', { path: r.out, how: 'explorer' }) }, 'Arată în Explorer'))
  return h('div', { class: 'result ok' }, h('div', {}, `✓ Gata: ${name}`), h('div', { style: { color: 'var(--muted)', fontSize: '12px', wordBreak: 'break-all' } }, r.out),
    ...notes, r.files ? h('div', { style: { fontSize: '12px', marginTop: '6px' } }, r.files.join(', ')) : null, rb)
}

// ---------- semnătură nouă în bibliotecă ----------
// Poza (telefon, scan, WhatsApp) trece prin scriptul skill-ului semnare-pdf: fundalul devine transparent,
// apoi o salvăm ca „Semnatura <Nume>.png” în bibliotecă, iar originalul în Semnaturi\Originale.
function openUpload() {
  $('#sigFlyout').hidden = true
  document.querySelector('.modal-back')?.remove()
  const st = { id: null, file: null, b64: null, strength: 1, color: 'original', timer: 0 }
  const file = h('input', { type: 'file', accept: 'image/*', hidden: true })
  const drop = h('div', { class: 'drop' },
    h('div', { class: 'big' }, 'Trage aici poza semnăturii'),
    h('div', {}, 'sau ', h('button', { class: 'linkbtn', onclick: () => file.click() }, 'alege un fișier'), ', ori lipește cu Ctrl+V'),
    h('small', {}, 'Merge și o poză făcută cu telefonul pe hârtie albă: fundalul se scoate singur.'))
  const img = h('img', { alt: 'Semnătura cu fundal transparent' })
  const shot = h('div', { class: 'shotbox', hidden: true }, img)
  const strength = h('input', { type: 'range', min: 0.4, max: 2.2, step: 0.1, value: 1 })
  const colorRow = h('div', { class: 'seg' }, ...[['original', 'Ca în poză'], ['blue', 'Albastru'], ['black', 'Negru']].map(([v, l]) =>
    h('button', { class: v === st.color ? 'on' : '', 'data-v': v, onclick: e => {
      st.color = v
      colorRow.querySelectorAll('button').forEach(b => b.classList.toggle('on', b === e.currentTarget))
      run()
    } }, l)))
  const name = h('input', { type: 'text', placeholder: 'Al cui e semnătura (ex. Ion Popescu)' })
  const msg = h('div', { class: 'msg' })
  const save = h('button', { class: 'primary', disabled: true }, 'Salvează în bibliotecă')
  const controls = h('div', { class: 'ctl', hidden: true },
    h('label', { class: 'field' }, h('span', {}, 'Curățare'), h('div', { class: 'range' }, h('small', {}, 'mai curat'), strength, h('small', {}, 'păstrează mai mult'))),
    h('div', { class: 'field' }, h('span', {}, 'Culoarea cernelii'), colorRow),
    h('label', { class: 'field' }, h('span', {}, 'Nume'), name))
  const back = h('div', { class: 'modal-back' }, h('div', { class: 'modal' },
    h('div', { class: 'mh' }, h('h2', {}, 'Semnătură nouă'), h('button', { class: 'icon', title: 'Închide', onclick: () => close() }, icon('x'))),
    drop, shot, controls, msg,
    h('div', { class: 'buttons' }, h('button', { class: 'secondary', onclick: () => close() }, 'Renunță'), save), file))
  document.body.append(back)
  const canSave = () => { save.disabled = !st.id || !name.value.trim() }
  async function run(f) {
    if (f) {
      if (!/^image\//.test(f.type)) return (msg.textContent = tr('Alege o imagine (PNG, JPG, HEIC salvat ca JPG).'))
      const r = await fileToB64(f)
      Object.assign(st, { id: null, file: f.name, b64: r.b64 })
    }
    if (!st.b64 && !st.id) return
    msg.replaceChildren(h('span', { class: 'spin' }), tr('Scot fundalul…'))
    try {
      const r = await post('lib/process', { id: st.id, b64: st.id ? undefined : st.b64, filename: st.file, strength: st.strength, color: st.color })
      st.id = r.id
      img.src = r.png
      shot.hidden = false
      controls.hidden = false
      drop.classList.add('small')
      if (!name.value.trim() && r.name) name.value = r.name
      msg.textContent = ''
      canSave()
      if (!name.value.trim()) name.focus()
    } catch (err) {
      msg.textContent = tr(err.message)
    }
  }
  async function doSave(replace = false) {
    save.disabled = true
    try {
      const r = await post('lib/save', { id: st.id, name: name.value, replace })
      await loadLib()
      close()
      chooseSig(r.file)
      toast(`Am adăugat „${r.name}” în bibliotecă.`)
    } catch (err) {
      canSave()
      if (err.data?.exists) {
        msg.replaceChildren(tr(err.message), ' ', h('button', { class: 'linkbtn', onclick: () => doSave(true) }, 'Înlocuiește'), tr(' (cea veche merge în Semnaturi\\_Arhiva)'))
      } else {
        msg.textContent = tr(err.message)
      }
    }
  }
  function close() {
    back.remove()
    document.removeEventListener('paste', onPaste)
  }
  function onPaste(e) {
    const f = [...(e.clipboardData?.files || [])].find(x => x.type.startsWith('image/'))
    if (f) { e.preventDefault(); run(f) }
  }
  file.addEventListener('change', () => file.files[0] && run(file.files[0]))
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over') })
  drop.addEventListener('dragleave', () => drop.classList.remove('over'))
  drop.addEventListener('drop', e => { e.preventDefault(); drop.classList.remove('over'); const f = e.dataTransfer.files[0]; if (f) run(f) })
  strength.addEventListener('input', () => { st.strength = +strength.value; clearTimeout(st.timer); st.timer = setTimeout(() => run(), 350) })
  name.addEventListener('input', canSave)
  name.addEventListener('keydown', e => { if (e.key === 'Enter' && !save.disabled) doSave() })
  save.addEventListener('click', () => doSave())
  back.addEventListener('keydown', e => { if (e.key === 'Escape') { e.stopPropagation(); close() } })
  back.addEventListener('click', e => { if (e.target === back) close() })
  document.addEventListener('paste', onPaste)
}

// ---------- organizarea paginilor ----------
// Toate paginile ca miniaturi: le tragi în ordinea dorită (una sau mai multe selectate), le ștergi sau le rotești;
// Salvează scrie o dată copia _editat.pdf, cu Anulează ca la orice salvare.
function openOrganize() {
  if (!S.doc || $('#organize')) return
  if (S.doc.signed) return toast('PDF-ul are semnătură digitală; reordonarea paginilor ar strica-o.', { err: true })
  if (changed().length) return toast('Ai modificări nesalvate pe pagini: apasă întâi Salvează, apoi organizează paginile.', { err: true, ms: 7000 })
  closePop()
  closeDrawer()
  $('#sigFlyout').hidden = true
  let pages = S.pages.map(p => ({ n: p.n, rot: 0 }))
  const sel = new Set()
  let anchor = null
  let moving = null
  const grid = h('div', { class: 'ogrid' })
  const info = h('span', { class: 'oinfo' })
  const btn = (label, title, fn, cls = 'secondary') => h('button', { class: cls, title, type: 'button', onclick: fn }, label)
  const delBtn = btn('Șterge', 'Șterge paginile selectate (Delete)', () => removePages([...sel]))
  const rotLBtn = btn('⟲', 'Rotește spre stânga paginile selectate', () => turn([...sel], -90))
  const rotRBtn = btn('⟳', 'Rotește spre dreapta paginile selectate', () => turn([...sel], 90))
  const resetBtn = btn('Ca la început', 'Renunță la toate schimbările de aici', () => { pages = S.pages.map(p => ({ n: p.n, rot: 0 })); sel.clear(); draw() })
  const saveBtn = btn('Salvează', 'Scrie paginile în noua ordine (Ctrl+S)', () => commit(), 'primary')
  const back = h('div', { class: 'organize', id: 'organize' },
    h('div', { class: 'ohead' }, h('h2', {}, 'Organizează paginile'), info, h('span', { class: 'grow' }),
      delBtn, rotLBtn, rotRBtn, resetBtn, btn('Închide', 'Închide fără să salvezi (Esc)', () => close()), saveBtn),
    h('p', { class: 'ohint' }, 'Trage paginile în ordinea dorită · click = selectezi, Ctrl/Shift + click = mai multe · Delete = ștergi · Ctrl+A = toate'),
    grid)
  const changedO = () => pages.length !== S.pages.length || pages.some((p, i) => p.n !== i + 1 || p.rot % 360)
  const close = (force) => {
    if (!force && changedO() && !confirm(tr('Renunți la schimbările din ordinea paginilor?'))) return
    back.remove()
    removeEventListener('keydown', keys, true)
  }
  function removePages(list) {
    if (!list.length) return
    if (list.length >= pages.length) return toast('Trebuie să rămână cel puțin o pagină.', { err: true })
    pages = pages.filter(p => !list.includes(p))
    list.forEach(p => sel.delete(p))
    draw()
  }
  function turn(list, deg) {
    for (const p of list) p.rot = (p.rot + deg + 360) % 360
    draw()
  }
  function pick(p, i, e) {
    if (e.shiftKey && anchor) {
      const a = pages.indexOf(anchor)
      const [from, to] = a < i ? [a, i] : [i, a]
      if (!e.ctrlKey) sel.clear()
      pages.slice(from, to + 1).forEach(x => sel.add(x))
    } else if (e.ctrlKey || e.metaKey) {
      sel.has(p) ? sel.delete(p) : sel.add(p)
      anchor = p
    } else {
      const only = sel.size === 1 && sel.has(p)
      sel.clear()
      if (!only) sel.add(p)
      anchor = p
    }
    draw()
  }
  function card(p, i) {
    const img = h('img', { src: url('page', { path: PATH, n: p.n, w: 300, v: S.ver }), alt: '', draggable: 'false', loading: 'lazy' })
    img.style.transform = `rotate(${p.rot}deg)`
    const small = (label, title, fn) => {
      const b = h('button', { class: 'obtn', title, type: 'button' }, label)
      b.addEventListener('click', e => { e.stopPropagation(); fn() })
      return b
    }
    const el = h('div', { class: 'ocard' + (sel.has(p) ? ' sel' : ''), draggable: 'true' },
      h('div', { class: 'othumb' }, img),
      h('div', { class: 'ofoot' }, h('b', {}, String(i + 1)), p.n !== i + 1 ? h('small', {}, tr(`era ${p.n}`)) : null, h('span', { class: 'grow' }),
        small('⟲', 'Rotește spre stânga', () => turn([p], -90)), small('⟳', 'Rotește spre dreapta', () => turn([p], 90)),
        small('✕', 'Șterge pagina', () => removePages(sel.has(p) ? [...sel] : [p]))))
    el.addEventListener('click', e => pick(p, i, e))
    el.addEventListener('dblclick', () => { close(true); goTo(p.n) })
    el.addEventListener('dragstart', e => {
      moving = sel.has(p) ? pages.filter(x => sel.has(x)) : [p]
      e.dataTransfer.effectAllowed = 'move'
      e.dataTransfer.setData('text/plain', String(p.n))
      requestAnimationFrame(() => grid.querySelectorAll('.ocard').forEach((c, k) => c.classList.toggle('dragging', moving.includes(pages[k]))))
    })
    el.addEventListener('dragover', e => {
      if (!moving) return
      e.preventDefault()
      const r = el.getBoundingClientRect()
      const after = e.clientX > r.left + r.width / 2
      grid.querySelectorAll('.before, .after').forEach(c => c.classList.remove('before', 'after'))
      el.classList.add(after ? 'after' : 'before')
    })
    el.addEventListener('drop', e => {
      e.preventDefault()
      if (!moving || moving.includes(p)) return
      const after = el.classList.contains('after')
      const rest = pages.filter(x => !moving.includes(x))
      const at = rest.indexOf(p) + (after ? 1 : 0)
      pages = [...rest.slice(0, at), ...moving, ...rest.slice(at)]
      draw()
    })
    el.addEventListener('dragend', () => { moving = null; draw() })
    return el
  }
  function draw() {
    grid.replaceChildren(...pages.map(card))
    const gone = S.pages.length - pages.length
    info.textContent = tr(`${pages.length} pagini`) + (gone ? tr(` · ${gone} șterse`) : '') + (sel.size ? tr(` · ${sel.size} selectate`) : '')
    saveBtn.disabled = !changedO()
    for (const b of [delBtn, rotLBtn, rotRBtn]) b.disabled = !sel.size
    resetBtn.disabled = !changedO()
  }
  async function commit() {
    if (!changedO()) return
    saveBtn.disabled = true
    saveBtn.textContent = tr('Se salvează…')
    const source = PATH
    try {
      const r = await post('organize', { path: PATH, pages: pages.map(p => ({ n: p.n, rot: p.rot })) })
      close(true)
      await openDoc(r.out, 1)
      toast(`Paginile sunt salvate: ${base(r.out)}`, { action: { label: 'Anulează', fn: () => undo(r.out, source) } })
    } catch (err) {
      saveBtn.textContent = tr('Salvează')
      saveBtn.disabled = false
      toast(err.message, { err: true, ms: 8000 })
    }
  }
  function keys(e) {
    if (!back.isConnected) return
    const k = e.key.toLowerCase()
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); return close() }
    if ((e.ctrlKey || e.metaKey) && k === 's') { e.preventDefault(); e.stopPropagation(); return commit() }
    if ((e.ctrlKey || e.metaKey) && k === 'a') { e.preventDefault(); e.stopPropagation(); pages.forEach(p => sel.add(p)); return draw() }
    if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); e.stopPropagation(); return removePages([...sel]) }
    e.stopPropagation() // celelalte scurtături ale editorului nu merg cât e deschis ecranul ăsta
  }
  addEventListener('keydown', keys, true)
  document.body.append(back)
  draw()
}

// ---------- căutarea globală (Ctrl+K) ----------
// O singură căsuță pentru tot: acțiunile editorului, uneltele din catalog și, dacă Stirling e instalat, toate uneltele lui.
function paletteItems() {
  const act = (label, run, ic, key, keywords = '') => ({ label, run, ic, key, keywords, group: 'Editor' })
  const items = [
    act('Selectează și mută', () => setTool('select'), 'pointer', 'V'),
    act('Semnătură olografă', () => setTool('sig'), 'sig', 'S', 'semnatura imagine'),
    act('Adaugă text', () => setTool('text'), 'type', 'T', 'scrie'),
    act('Editează textul din PDF', () => setTool('edit'), 'edit', 'E', 'modifica rescrie'),
    act(`Comentariu pentru ${aiName()}`, () => setTool('comment'), 'comment', 'C', 'ai claude'),
    act(`Captură zonă pentru ${aiName()}`, () => setTool('region'), 'region', 'R', 'ai claude'),
    act('Semnătură electronică', openCertSign, null, '', 'certificat cei buletin token fintaxysign stick digitala calificata'),
    act('Semnează mai multe PDF-uri', openBulkSign, null, '', 'bloc bulk lot certificat'),
    act('Semnătură nouă în bibliotecă', openUpload, 'sig', '', 'adauga poza scan'),
    act('Salvează', () => save(), null, 'Ctrl+S'),
    act('Printează', () => printDoc(), 'printer', 'Ctrl+P', 'print tipareste imprimanta'),
    act('Deschide alt PDF', () => openOther(), 'open', 'Ctrl+O'),
    act('Organizează paginile', openOrganize, 'pages', 'P', 'ordoneaza muta sterge pagini reordoneaza organize'),
    act('Rotește pagina spre dreapta', () => rotate(90, false), 'rotR'),
    act('Rotește pagina spre stânga', () => rotate(-90, false), 'rotL'),
    act('Rotește toate paginile spre dreapta', () => rotate(90, true), 'rotR'),
    act('Mărește', () => stepZoom(1), 'plus', '', 'zoom'),
    act('Micșorează', () => stepZoom(-1), 'minus', '', 'zoom'),
    act('Potrivește lățimea', () => setZoom(1), null, '', 'zoom 100'),
    act('Comentariile', openCommentsList, 'comment'),
    act('Arată în Explorer', () => post('open', { path: PATH, how: 'explorer' }), 'folder', '', 'folder'),
    act('Copiază calea fișierului', () => $('#btnCopyPath').click(), 'copy'),
    act('Toate uneltele PDF', () => openTools(), 'grid'),
    act('Vorbește cu Claude', () => openChat(), 'comment', 'A', 'chat ai intreaba asistent acp'),
    act('Componente', () => openDeps(), 'tool', '', 'libreoffice stirling node claude instaleaza dependente programe'),
    act('Ghid de pornire', () => openOnboarding(), null, '', 'onboarding ajutor help tutorial bun venit'),
  ]
  const groups = Object.fromEntries(GROUPS.map(g => [g.id, g.label]))
  for (const t of toolsCatalog()) {
    if (t.native === 'edit' || ['certsign', 'bulksign', 'organize'].includes(t.id)) continue // sunt deja la acțiuni
    items.push({ label: t.label, desc: t.desc, group: groups[t.group] || '', tool: t, keywords: t.endpoint || '',
      run: () => (t.native ? setTool(t.native) : openToolForm(t)) })
  }
  if (S.specData) {
    const known = new Set(TOOLS.map(t => t.endpoint))
    for (const [ep, s] of Object.entries(S.specData.tools)) {
      if (known.has(ep) || /text-editor|pipeline/.test(ep)) continue
      const t = { id: ep, label: s.summary || ep, endpoint: ep, desc: ep.replace('/api/v1/', ''), suffix: ep.split('/').pop() }
      items.push({ label: t.label, desc: t.desc, group: 'Stirling', tool: t, keywords: ep, run: () => openToolForm(t) })
    }
  }
  return items
}
function paletteScore(it, q) {
  if (!q) return 1
  const label = norm(tr(it.label)), ro = norm(it.label)
  const rest = norm(`${it.desc || ''} ${tr(it.desc || '')} ${it.group} ${it.keywords}`)
  const words = q.split(/\s+/).filter(Boolean)
  let score = 0
  for (const w of words) {
    if (label.startsWith(w) || ro.startsWith(w)) score += 30
    else if (new RegExp(`(^|[\\s(/-])${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`).test(`${label} ${ro}`)) score += 20
    else if (label.includes(w) || ro.includes(w)) score += 10
    else if (rest.includes(w)) score += 3
    else return 0 // fiecare cuvânt trebuie să se potrivească undeva
  }
  return score
}
function openPalette() {
  if ($('#palette')) return $('#palette input').focus()
  closePop()
  $('#sigFlyout').hidden = true
  const input = h('input', { placeholder: 'Caută o unealtă sau o acțiune (ex. semnătură, comprimă, rotește)', spellcheck: 'false' })
  const list = h('div', { class: 'plist' })
  const back = h('div', { class: 'palette-back', id: 'palette' },
    h('div', { class: 'palette' }, h('label', { class: 'psearch' }, icon('search'), input, h('kbd', {}, 'Esc')), list))
  let shown = []
  let cur = 0
  const close = () => back.remove()
  const runAt = i => {
    const it = shown[i]
    if (!it) return
    close()
    it.run()
  }
  const mark = () => {
    list.querySelectorAll('.prow').forEach((el, i) => el.classList.toggle('on', i === cur))
    list.querySelector('.prow.on')?.scrollIntoView({ block: 'nearest' })
  }
  const draw = () => {
    const q = norm(input.value.trim())
    shown = paletteItems().map(it => ({ it, s: paletteScore(it, q) })).filter(x => x.s > 0)
      .sort((a, b) => b.s - a.s).slice(0, 60).map(x => x.it)
    cur = 0
    list.replaceChildren(...shown.map((it, i) => {
      let ic
      if (it.tool) {
        const tpl = document.createElement('template')
        tpl.innerHTML = toolIconSvg(it.tool)
        ic = tpl.content.firstChild
      } else {
        ic = it.ic ? icon(it.ic) : icon('tool')
      }
      const row = h('button', { class: 'prow', type: 'button', title: it.desc || '' }, ic,
        h('span', { class: 'pl' }, it.label), h('span', { class: 'pg' }, it.group), it.key ? h('kbd', {}, it.key) : null)
      row.addEventListener('mousemove', () => { if (cur !== i) { cur = i; mark() } })
      row.addEventListener('click', () => runAt(i))
      return row
    }))
    if (!shown.length) list.append(h('div', { class: 'empty' }, 'Nimic găsit.'))
    mark()
  }
  input.addEventListener('input', draw)
  input.addEventListener('keydown', e => {
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); return close() }
    if (e.key === 'ArrowDown') { e.preventDefault(); cur = Math.min(shown.length - 1, cur + 1); return mark() }
    if (e.key === 'ArrowUp') { e.preventDefault(); cur = Math.max(0, cur - 1); return mark() }
    if (e.key === 'Enter') { e.preventDefault(); return runAt(cur) }
  })
  back.addEventListener('pointerdown', e => { if (e.target === back) close() })
  document.body.append(back)
  draw()
  input.focus()
  // Uneltele Stirling apar în listă când răspunde (dacă e instalat); până atunci, catalogul.
  if (!S.specData) loadSpec().then(spec => { S.specData = spec; if (back.isConnected) draw() }).catch(() => {})
}

// ---------- tastatură, butoane, pornire ----------
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); return }
  if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'p') { e.preventDefault(); printDoc(); return }
  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette(); return }
  if ($('#palette')) return // tastele merg în căutare
  if (e.key === 'Escape') {
    if (S.pop) return closePop()
    if (!$('#sigFlyout').hidden) { $('#sigFlyout').hidden = true; return }
    if (!$('#drawer').hidden) return closeDrawer()
    if (typing()) return document.activeElement.blur()
    return setTool('select')
  }
  if (typing()) return
  if ((e.key === 'Delete' || e.key === 'Backspace') && S.sel && S.sel.type !== 'edit' && S.sel.type !== 'field') return removeItem(S.sel)
  if (e.key.toLowerCase() === 'p' && !e.ctrlKey && !e.metaKey && !e.altKey) return openOrganize()
  if (e.key.toLowerCase() === 'a' && !e.ctrlKey && !e.metaKey && !e.altKey) return openChat()
  const keys = { v: 'select', s: 'sig', t: 'text', e: 'edit', c: 'comment', r: 'region' }
  if (keys[e.key.toLowerCase()] && !e.ctrlKey && !e.metaKey && !e.altKey) setTool(keys[e.key.toLowerCase()])
})
main.addEventListener('wheel', e => {
  if (!e.ctrlKey) return
  e.preventDefault()
  if (S.tool === 'sig' || S.sel?.type === 'sig') setSigW(S.sigW + (e.deltaY < 0 ? 6 : -6))
  else stepZoom(e.deltaY < 0 ? 1 : -1)
}, { passive: false })
main.addEventListener('scroll', () => { updatePg(); positionPop() }, { passive: true })
addEventListener('resize', layout)
addEventListener('beforeunload', e => { if (changed().length) { e.preventDefault(); e.returnValue = '' } })

const RAIL_ICONS = { select: 'pointer', sig: 'sig', text: 'type', edit: 'edit', comment: 'comment', region: 'region' }
for (const b of document.querySelectorAll('.rail [data-tool]')) {
  b.append(icon(RAIL_ICONS[b.dataset.tool]))
  b.addEventListener('click', () => {
    if (b.dataset.tool === 'sig' && S.tool === 'sig') return $('#sigFlyout').hidden ? openFlyout() : ($('#sigFlyout').hidden = true)
    setTool(b.dataset.tool)
  })
}
const orgBtn = document.querySelector('.rail [data-panel=organize]')
orgBtn.append(icon('pages'))
orgBtn.addEventListener('click', () => openOrganize())
const toolsBtn = document.querySelector('.rail [data-panel=tools]')
toolsBtn.append(icon('grid'))
toolsBtn.addEventListener('click', () => ($('#drawer').hidden || !toolsBtn.classList.contains('on') ? openTools() : closeDrawer()))
$('#prev').append(icon('left'))
$('#next').append(icon('right'))
$('#zout').append(icon('minus'))
$('#zin').append(icon('plus'))
$('#rotL').append(icon('rotL'))
$('#rotR').append(icon('rotR'))
$('#btnExplorer').append(icon('folder'))
$('#btnCopyPath').append(icon('copy'))
$('#btnComments').prepend(icon('comment'))
$('#prev').addEventListener('click', () => goTo(S.cur - 1))
$('#next').addEventListener('click', () => goTo(S.cur + 1))
$('#zout').addEventListener('click', () => stepZoom(-1))
$('#zin').addEventListener('click', () => stepZoom(1))
$('#rotL').addEventListener('click', e => rotate(-90, e.shiftKey))
$('#rotR').addEventListener('click', e => rotate(90, e.shiftKey))
$('#zpct').addEventListener('click', () => setZoom(1))
$('#btnSave').addEventListener('click', () => save())
$('#btnCert').addEventListener('click', () => openCertSign())
$('#btnPrint').append(icon('printer'))
$('#btnPrint').addEventListener('click', () => printDoc())
$('#btnSearch').append(icon('search'))
$('#btnSearch').addEventListener('click', () => openPalette())
$('#btnComments').addEventListener('click', () => ($('#drawer').hidden ? openCommentsList() : closeDrawer()))
$('#btnCopyPath').addEventListener('click', async () => {
  const p = S.doc?.path || PATH
  try { await navigator.clipboard.writeText(p); toast(`Calea e copiată: ${p}`) } catch (err) { toast(`Nu am putut copia calea: ${err.message}`, { err: true }) }
})
$('#btnExplorer').addEventListener('click', () => post('open', { path: PATH, how: 'explorer' }).catch(err => toast(err.message, { err: true })))
$('#btnOpen').append(icon('open'))
$('#btnOpen').addEventListener('click', () => openOther())
document.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'o') { e.preventDefault(); openOther() } })

// Alt PDF în aceeași fereastră, ales din fereastra Windows (serverul o deschide: pagina nu vede căile fișierelor).
async function openOther(force) {
  if (!force && changed().length) {
    return toast('Ai modificări nesalvate în PDF-ul ăsta.', { action: { label: 'Deschide alt PDF oricum', fn: () => openOther(true) } })
  }
  try {
    const r = await post('pick', { dir: S.doc?.dir || '' })
    if (!r.path) return
    if (!/\.pdf$/i.test(r.path)) return toast('Alege un fișier PDF.', { err: true })
    main.querySelector('.start')?.remove()
    if (!S.lib.length) await loadLib()
    await openDoc(r.path)
  } catch (err) {
    toast(err.message, { err: true })
  }
}

// Limba editorului (română / engleză), ținută minte în settings.json; schimbarea reîncarcă pagina.
function applyLang() {
  setLang(S.app.lang)
  document.body.dataset.lang = lang()
  for (const el of document.querySelectorAll('[title]')) el.title = tr(el.title)
  $('#btnSave').textContent = tr($('#btnSave').textContent)
  $('#btnCert').textContent = tr($('#btnCert').textContent)
  const b = $('#btnLang')
  b.textContent = lang() === 'en' ? 'RO' : 'EN'
  b.title = lang() === 'en' ? 'Treci pe română' : 'Switch to English'
}
$('#btnLang').addEventListener('click', async () => {
  await post('settings', { lang: lang() === 'en' ? 'ro' : 'en' }).catch(() => {})
  location.reload()
})

// Aplicația separată se oprește când se închide ultima ei fereastră: fiecare fereastră dă semn de viață.
function heartbeat() {
  const id = Math.random().toString(36).slice(2)
  const ping = () => post('ping', { id }).catch(() => {})
  ping()
  setInterval(ping, 20000)
  addEventListener('pagehide', () => navigator.sendBeacon(url('bye', {}), JSON.stringify({ id })))
}

;(async () => {
  if (TOKEN) S.app = { ...S.app, ...(await api('info').catch(() => ({}))) }
  applyLang()
  initAssist({ h, $, api, post, url, toast, icon, tr, openDrawer, closeDrawer, openUpload, state: S, path: () => S.doc?.path || PATH,
    reload: async msg => { if (!changed().length) { await openDoc(PATH, S.cur); toast(msg) } } })
  // Ghidul de la prima pornire (se poate sări; se redeschide din Ctrl+K → „Ghid de pornire”).
  if (TOKEN && !S.app.onboarded && Q.get('onboarding') !== '0') openOnboarding()
  if (S.app.standalone) { heartbeat(); applyAiName() }
  if (!TOKEN) {
    main.append(h('div', { class: 'empty' }, 'Lipsește fișierul. Deschide editorul din cardul PDF-ului din chat.'))
    return
  }
  if (!PATH) {
    // Ecranul de start: aplicația rămâne deschisă și când renunți la alegerea fișierului.
    main.append(h('div', { class: 'empty start' },
      h('div', { class: 'start-card' }, h('img', { src: '/editor/icon.png', alt: '' }), h('h1', {}, 'PDF Sign'),
        h('button', { class: 'primary big', onclick: () => openOther() }, 'Alege un PDF'), h('kbd', {}, 'Ctrl+O'),
        h('button', { class: 'linkbtn', type: 'button', onclick: () => openOnboarding() }, 'Ghid de pornire'))))
    loadLib().catch(() => {})
    if (Q.get('pick') && S.app.onboarded) openOther()
    return
  }
  try {
    await Promise.all([loadLib(), openDoc(PATH, +Q.get('page') || 1)])
  } catch (err) {
    main.append(h('div', { class: 'empty' }, `Nu am putut deschide PDF-ul: ${err.message}`))
    return
  }
  const sigFile = (Q.get('sig') || '').toLowerCase()
  const pre = S.lib.find(s => s.file.toLowerCase() === sigFile)
  if (pre) chooseSig(pre.file)
  const tool = Q.get('tool')
  setTool(pre ? 'sig' : ['sig', 'text', 'edit', 'comment', 'region'].includes(tool) ? tool : 'select')
  if (tool === 'tools') openTools()
  if (Q.get('upload')) openUpload()
})()
