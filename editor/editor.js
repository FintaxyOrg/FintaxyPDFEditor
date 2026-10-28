// Editorul PDF din panoul lui Claude: pagini, semnături, text nou, editarea textului existent,
// comentarii și capturi pentru Claude, plus toate uneltele Stirling PDF.
// Toate pozițiile sunt în puncte PDF (pt), în pagina așa cum se vede; pe ecran = pt × scale.
import { FIELD_LABELS, GROUPS, TOOLS } from './tools.js'
import { lang, setLang, tr } from './i18n.js'
import { toolIconSvg } from './tool-icons.js'

const Q = new URLSearchParams(location.search)
const TOKEN = Q.get('t') || ''
let PATH = Q.get('path') || ''

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
}

// ---------- starea ----------
const S = {
  doc: null, pages: [], scale: 1, zoom: 1, tool: 'select', lib: [], sig: '', sigW: 113, fs: 11, color: '#141720', bold: false,
  items: [], sel: null, comments: [], runs: {}, uid: 0, pop: null, cur: 1, spec: null, sigQuery: '',
  app: { standalone: false, apps: [], ai: '' }, // aplicația separată (desktop.py): comentariile merg la o aplicație AI
}

// În panoul lui Claude comentariile ajung la Claude; în aplicația separată, la aplicația AI aleasă.
const aiName = () => (!S.app.standalone ? 'Claude' : S.app.ai === 'copy' ? 'AI' : S.app.apps.find(a => a.id === S.app.ai)?.name || 'AI')
function applyAiName() {
  const n = aiName()
  HINTS.comment = `Click pe pagină unde vrei să-i spui ceva lui ${n}`
  HINTS.region = `Trage un dreptunghi peste zona pe care vrei s-o trimiți lui ${n}`
  $('.rail [data-tool=comment]').title = tr(`Comentariu pentru ${n} (C)`)
  $('.rail [data-tool=region]').title = tr(`Captură zonă pentru ${n} (R)`)
  if (HINTS[S.tool]) $('#hint').textContent = tr(HINTS[S.tool])
}
function aiPicker(onChange) {
  const sel = h('select', { class: 'aipick', title: 'Aplicația AI care primește comentariul (rămâne ținută minte)' },
    ...S.app.apps.map(a => h('option', { value: a.id, title: a.hint, selected: a.id === S.app.ai }, a.name)))
  sel.addEventListener('change', () => {
    S.app.ai = sel.value
    post('settings', { ai: sel.value }).catch(() => {})
    applyAiName()
    onChange?.()
  })
  return sel
}
function sentToast(r, fallback) {
  if (r.sendError) toast(r.sendError, { err: true, ms: 8000 })
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
  buildPages()
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
}
function setTool(t) {
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
  fly.replaceChildren(
    h('div', { class: 'flyhead' }, h('h3', {}, 'Alege semnătura'),
      h('span', {}, h('button', { class: 'linkbtn', title: 'Recitește folderul Semnaturi', onclick: async () => {
        await loadLib()
        renderFlyout()
        toast(`Lista e la zi: ${S.lib.length} semnături.`)
      } }, '↻ Actualizează'), ' · ', h('button', { class: 'linkbtn', onclick: () => openUpload() }, '+ Nouă'),
      S.app.library ? [' · ', h('button', { class: 'linkbtn', title: S.app.library,
        onclick: () => post('open', { path: S.app.library, how: 'explorer' }).catch(e => toast(e.message)) }, 'Folder')] : null)),
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
  return S.items.filter(it => (it.type === 'sig') || (it.type === 'text' && it.text.trim()) || (it.type === 'edit' && it.text !== it.orig))
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
  if (e.target.closest('.item, .pin, .editbox, .run')) return
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
  if (S.tool !== 'region' || e.button !== 0 || e.target.closest('.pin')) return
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

// ---------- sertarul din dreapta ----------
function openDrawer(title, ...content) {
  const d = $('#drawer')
  d.hidden = false
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
    if (!spec) return list.append(h('div', { class: 'empty' }, 'Uneltele Stirling se încarcă când deschizi una (pornesc Stirling PDF dacă e nevoie).'))
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
    ic.content.firstChild, h('span', { class: 'tl' }, t.label))
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

async function openToolForm(t) {
  const body = h('div', { class: 'db' })
  const d = openDrawer(t.label, body)
  d.querySelector('.dh').prepend(h('button', { class: 'icon', title: 'Înapoi la unelte', onclick: () => openTools() }, icon('back')))
  body.append(h('div', { class: 'form' }, h('p', { class: 'desc' }, h('span', { class: 'spin' }), 'Încarc unealta din Stirling PDF…')))
  let spec
  try {
    // Semnarea cu certificat are formularul ei: nu așteaptă lista de unelte (Stirling poate încă porni).
    spec = t.custom === 'certsign' ? { fields: [] } : (await loadSpec()).tools[t.endpoint]
  } catch (err) {
    return body.replaceChildren(h('div', { class: 'form' }, h('div', { class: 'result err' }, `Stirling PDF nu răspunde: ${err.message}`)))
  }
  if (!spec) return body.replaceChildren(h('div', { class: 'form' }, h('div', { class: 'result err' }, 'Unealta nu există în versiunea ta de Stirling PDF.')))
  const form = h('div', { class: 'form' })
  body.replaceChildren(form)
  form.append(h('p', { class: 'desc' }, t.desc || spec.description || spec.summary))
  if (changed().length && !t.noDoc) form.append(h('div', { class: 'warn' }, 'Ai modificări nesalvate. Unealta lucrează pe fișierul salvat; apasă întâi Salvează dacă vrei să le includă.'))
  if (S.doc.signed && t.suffix && !['validatesign', 'removesign'].includes(t.id) && !t.noDoc && t.endpoint.includes('security/cert-sign')) {
    form.append(h('div', { class: 'warn' }, 'PDF-ul are deja o semnătură digitală.'))
  }
  const controls = []
  const mainName = spec.fields.find(f => f.name === 'fileInput' || f.name === 'file')?.name
  const extra = {}
  if (t.custom === 'certsign') await certFields(form, controls)
  else {
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
  const go = h('button', { class: 'primary' }, t.custom === 'certsign' ? 'Semnează' : 'Rulează')
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
    result.replaceChildren(h('div', { class: 'result' }, h('span', { class: 'spin' }), t.custom === 'certsign' ? 'Scrie PIN-ul de semnare în fereastra IDEMIA…' : 'Rulez unealta…'))
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

async function certFields(form, controls) {
  form.append(h('div', { class: 'warn' }, 'Alege certificatul care se termină cu (Semnare), nu (Autentificare). După „Semnează” apare fereastra IDEMIA: scrie acolo PIN-ul de semnare (6 cifre). După semnare fișierul nu mai poate fi modificat.'))
  const sel = h('select', {}, h('option', { value: '' }, 'Se încarcă certificatele…'))
  form.append(h('label', { class: 'field' }, h('span', {}, 'Certificat *'), sel))
  // Întâi lista citită direct din Windows (instant), apoi cea a lui Stirling, care semnează (aceleași nume).
  const fill = list => {
    const keep = sel.value
    sel.replaceChildren(...(list.length ? list : [{ alias: '', label: 'Nu văd niciun certificat: e buletinul în cititor?' }]).map(c =>
      h('option', { value: c.alias, selected: keep ? c.alias === keep : /\(semnare\)/i.test(c.alias || '') }, c.label || `${c.alias}${c.notAfter ? ` · până la ${String(c.notAfter).slice(0, 10)}` : ''}${c.expired ? ' · EXPIRAT' : ''}`)))
  }
  let real = false
  api('stirling/certs', { quick: 1 }).then(list => { if (!real) fill(list) }).catch(() => {})
  api('stirling/certs').then(list => { real = true; fill(list) })
    .catch(err => { if (!sel.options.length || !sel.value) sel.replaceChildren(h('option', { value: '' }, `Eroare: ${err.message}`)) })
  controls.push({ name: 'alias', read: () => sel.value }, { name: 'certType', read: () => 'WINDOWS_STORE' }, { name: 'showLogo', read: () => false })
  const vis = h('input', { type: 'checkbox', checked: true })
  form.append(h('label', { class: 'field' }, h('span', { class: 'check' }, vis, 'Semnătură vizibilă pe pagină')))
  controls.push({ name: 'showSignature', read: () => vis.checked })
  const page = h('input', { type: 'number', min: 1, max: S.pages.length, value: S.pages.length })
  form.append(h('label', { class: 'field' }, h('span', {}, 'Pagina ștampilei'), page))
  controls.push({ name: 'pageNumber', read: () => (vis.checked ? page.value : undefined) })
  for (const [name, label] of [['reason', 'Motiv'], ['location', 'Locul']]) {
    const inp = h('input', { type: 'text' })
    form.append(h('label', { class: 'field' }, h('span', {}, label), inp))
    controls.push({ name, read: () => inp.value })
  }
}

function showResult(r) {
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
    r.files ? h('div', { style: { fontSize: '12px', marginTop: '6px' } }, r.files.join(', ')) : null, rb)
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

// ---------- tastatură, butoane, pornire ----------
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); return }
  if (e.key === 'Escape') {
    if (S.pop) return closePop()
    if (!$('#sigFlyout').hidden) { $('#sigFlyout').hidden = true; return }
    if (!$('#drawer').hidden) return closeDrawer()
    if (typing()) return document.activeElement.blur()
    return setTool('select')
  }
  if (typing()) return
  if ((e.key === 'Delete' || e.key === 'Backspace') && S.sel && S.sel.type !== 'edit') return removeItem(S.sel)
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
  if (S.app.standalone) { heartbeat(); applyAiName() }
  if (!TOKEN) {
    main.append(h('div', { class: 'empty' }, 'Lipsește fișierul. Deschide editorul din cardul PDF-ului din chat.'))
    return
  }
  if (!PATH) {
    main.append(h('div', { class: 'empty start' }, h('button', { class: 'primary', onclick: () => openOther() }, 'Alege un PDF'), ' sau Ctrl+O'))
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
