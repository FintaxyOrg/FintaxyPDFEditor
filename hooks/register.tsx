import { atom, read, update } from 'claude-code'
import type { EngineInterface as Engine, Register, RenderElement, RenderInput } from 'claude-code'

import type { Card, Menu, MenuItem } from '../types'
import { FLUENT } from './icons'

// Sub fiecare PDF pomenit în chat: previzualizarea paginii și butoanele Deschide în panou, Semnează,
// Explorer și More. Editorul (semnături, text, editarea textului, comentarii pentru Claude, uneltele
// Stirling PDF) e o pagină locală servită de bin/editor_server.py și se deschide în panoul browserului
// din aplicație; dacă panoul nu se poate deschide, într-o fereastră separată.
// Un card desenat în afara casetei mesajului e tăiat de desktop, deci meniurile stau în card.

// Biblioteca de semnături o alege helper-ul (settings.json sau Documente\Semnaturi PDF Sign), iar căile de pe
// calculatorul ăsta (jurnalul, helper-ul de meniu) le dă `fx_sign.py paths`: mod-ul merge la oricine îl instalează.
const BROWSER_SERVER = 'Claude_Browser'
const MAX_PDFS = 6

// Calea până la „.pdf”, cu spații; și ținta unui link markdown.
const ABSOLUTE = /(?:file:\/\/\/)?[A-Za-z]:[\\/][^\r\n<>"|?*`[\]]*?\.pdf\b/gi
const LINK = /\]\(<?([^)\r\n>]+?\.pdf)>?(?:#[^)]*)?\)/gi

export function normalize(raw: string): string {
  let s = raw.trim().replace(/^file:\/\/\//i, '')
  if (/%[0-9A-Fa-f]{2}/.test(s)) {
    try {
      s = decodeURIComponent(s)
    } catch {
      // rămâne cum era
    }
  }
  return s.replace(/\//g, '\\')
}

// Candidații din text, în ordine, fără dubluri.
export function candidates(text: string, cwd: string): string[] {
  const out: string[] = []
  const add = (p: string) => {
    if (p.length > 6 && !out.some(o => o.toLowerCase() === p.toLowerCase())) out.push(p)
  }
  for (const m of text.matchAll(ABSOLUTE)) {
    const whole = normalize(m[0])
    add(whole)
    const inner = whole.slice(3).search(/[A-Za-z]:\\/)
    if (inner >= 0) add(whole.slice(inner + 3))
  }
  if (cwd) {
    for (const m of text.matchAll(LINK)) {
      const target = m[1]!.trim()
      if (/^[a-z][a-z0-9+.-]*:/i.test(target) && !/^[A-Za-z]:[\\/]/.test(target)) continue
      if (target.startsWith('/mnt/')) continue
      add(/^[A-Za-z]:[\\/]/.test(target) ? normalize(target) : normalize(`${cwd.replace(/[\\/]+$/, '')}\\${target.replace(/^\.?[\\/]/, '')}`))
    }
  }
  return out
}

export function fileName(path: string): string {
  return path.split('\\').pop() || path
}

const mtimes = new Map<string, number>()

async function findPdfs($: Engine, text: string): Promise<string[]> {
  if (!/\.pdf/i.test(text)) return []
  let cwd = ''
  if (text.includes('](')) {
    try {
      cwd = await $.session.cwd()
    } catch {
      cwd = ''
    }
  }
  const found: string[] = []
  for (const p of candidates(text, cwd)) {
    if (found.length >= MAX_PDFS) break
    // stat la fiecare desen: data modificării intră în cheia previzualizării, ca un fișier schimbat pe disc să se redeseneze
    try {
      const st = await $.fs.stat(p)
      if (st.kind !== 'file') continue
      mtimes.set(p.toLowerCase(), st.mtimeMs)
      found.push(p)
    } catch {
      // nu există
    }
  }
  return found
}

// ---------- jurnal ----------

const logLines: string[] = []
async function log($: Engine, line: string) {
  logLines.push(`${new Date().toISOString()} ${line}`)
  if (logLines.length > 200) logLines.splice(0, logLines.length - 200)
  try {
    const { state } = await paths($)
    if (state) await $.fs.write(`${state}\\mod-log.txt`, logLines.join('\n') + '\n')
  } catch {
    // jurnalul nu e esențial
  }
}

type Paths = { state: string; library: string; local: string }
let pathsOnce: Promise<Paths> | undefined
function paths($: Engine): Promise<Paths> {
  pathsOnce ??= (helper($, ['paths']) as Promise<Paths>).catch(err => {
    pathsOnce = undefined
    throw err
  })
  return pathsOnce
}
// Helper-ul meniului de click dreapta, compilat de mod-ul path-buttons (bin/shellmenu.cs).
const shellmenu = async ($: Engine) => `${(await paths($)).local}\\fintaxy-path-buttons\\shellmenu.exe`

// ---------- helper-ul Python ----------

type Preview = { pages: number; page: number; width: number; height: number; svg: string; signed: boolean }
type Thumb = { name: string; file: string; svg: string; error?: string }
type Loading = { isLoading: true } | { error: string }

const cards = atom({ plugin: 'pdf-sign', key: 'cards' } as const, {} as Record<string, Card>)
const menus = atom({ plugin: 'pdf-sign', key: 'menus' } as const, {} as Record<string, Menu>)
// Previzualizările și miniaturile stau în memoria modulului; tick redesenează cardurile când sosesc.
const tick = atom({ plugin: 'pdf-sign', key: 'tick' } as const, 0)
const previews = new Map<string, Preview | Loading>()
let thumbs: Thumb[] | Loading | undefined
let thumbsSince = 0
const PER_PAGE = 6
export const ZOOMS = [0.6, 0.8, 1, 1.25, 1.5, 2]

const script = ($: Engine) => `${$.plugin.root}\\bin\\fx_sign.py`

async function helper($: Engine, args: string[], timeoutMs = 60000): Promise<unknown> {
  const r = await $.process.run(['python', script($), ...args], { timeoutMs, env: { PYTHONIOENCODING: 'utf-8' } })
  const line = r.stdout.trim().split(/\r?\n/).pop() || ''
  try {
    return JSON.parse(line)
  } catch {
    throw new Error(r.stderr.trim().split(/\r?\n/).pop() || line || `cod ${r.exitCode}`)
  }
}

const bump = ($: Engine) => update($, tick, n => n + 1)
const norm = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
const errText = (err: unknown) => String(err instanceof Error ? err.message : err)

function loadPreview($: Engine, path: string, page: number, zoom: number) {
  const key = `${path.toLowerCase()}|${mtimes.get(path.toLowerCase()) ?? 0}|${page}|${zoom}`
  if (previews.has(key)) return previews.get(key)!
  previews.set(key, { isLoading: true })
  void helper($, ['render', path, String(page), String(zoom)])
    .then(r => {
      const p = r as Preview & { error?: string }
      previews.set(key, p.svg ? p : { error: p.error || 'Nu am putut citi PDF-ul.' })
    })
    .catch(err => previews.set(key, { error: errText(err) }))
    .finally(() => bump($))
  return previews.get(key)!
}

function forget(path: string) {
  const k = `${path.toLowerCase()}|`
  for (const key of [...previews.keys()]) if (key.startsWith(k)) previews.delete(key)
}

function loadThumbs($: Engine, force = false): Thumb[] | Loading {
  const stuck = thumbs && 'isLoading' in thumbs && Date.now() - thumbsSince > 30000
  if (thumbs && !('error' in thumbs) && !stuck && !force) return thumbs
  thumbs = { isLoading: true }
  thumbsSince = Date.now()
  void helper($, ['thumbs', ''])
    .then(r => {
      thumbs = Array.isArray(r) ? (r as Thumb[]) : { error: 'Biblioteca de semnături nu a putut fi citită.' }
    })
    .catch(err => {
      thumbs = { error: errText(err) }
    })
    .finally(() => bump($))
  return thumbs
}

// ---------- serverul editorului ----------

type Server = { port: number; token: string }
type EditorEvent = { event: string; [key: string]: unknown }
let server: Promise<Server> | undefined

// Pornit o dată pe sesiune: bucla de mai jos ține procesul în viață și citește ce face omul în editor.
function ensureServer($: Engine): Promise<Server> {
  if (server) return server
  const started = new Promise<Server>((resolve, reject) => {
    void (async () => {
      let ready = false
      let buf = ''
      try {
        const child = $.process.spawn({ argv: ['python', '-u', script($), 'serve', ''], env: { PYTHONIOENCODING: 'utf-8' } })
        for await (const { stream, text } of child) {
          if (stream !== 'stdout') {
            if (!ready) await log($, `server stderr: ${text.slice(0, 300)}`)
            continue
          }
          buf += text
          for (let nl = buf.indexOf('\n'); nl >= 0; nl = buf.indexOf('\n')) {
            const line = buf.slice(0, nl).trim()
            buf = buf.slice(nl + 1)
            let ev: EditorEvent
            try {
              ev = JSON.parse(line) as EditorEvent
            } catch {
              continue
            }
            if (ev.event === 'ready') {
              ready = true
              await log($, `server ready on ${ev.port}`)
              resolve({ port: Number(ev.port), token: String(ev.token) })
            } else {
              void onEvent($, ev).catch(err => log($, `event ${ev.event} failed: ${errText(err)}`))
            }
          }
        }
      } catch (err) {
        await log($, `server failed: ${errText(err)}`)
        if (!ready) reject(err)
      }
      server = undefined // la următoarea deschidere pornește altul
      if (!ready) reject(new Error('Editorul nu a pornit.'))
    })()
  })
  // Dacă nu răspunde în 30 de secunde, renunțăm și încercăm din nou data viitoare.
  const timeout = $.clock.sleep(30000).then(
    () => {
      throw new Error('Editorul nu a pornit în 30 de secunde.')
    },
    () => new Promise<never>(() => {}), // fără ceas (teste): doar pornirea decide
  )
  timeout.catch(() => {})
  server = Promise.race([started, timeout]).catch(err => {
    server = undefined
    throw err
  })
  return server
}

type EditorOpts = { page?: number; sig?: string; tool?: string; upload?: boolean }

export function editorUrl(s: Server, path: string, opts: EditorOpts = {}) {
  const q = new URLSearchParams({ t: s.token, path })
  if (opts.page && opts.page > 1) q.set('page', String(opts.page))
  if (opts.sig) q.set('sig', opts.sig)
  if (opts.tool) q.set('tool', opts.tool)
  if (opts.upload) q.set('upload', '1')
  return `http://127.0.0.1:${s.port}/?${q}`
}

// Panoul browserului din aplicație; altfel o fereastră Edge separată.
async function openEditor($: Engine, path: string, opts: EditorOpts = {}) {
  const s = await ensureServer($)
  const url = editorUrl(s, path, opts)
  let blocked = false
  // În modul auto, apelul trece prin clasificatorul de permisiuni; când nu dă un verdict, se cere o a doua încercare.
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const r = await $.mcp.call(BROWSER_SERVER, 'preview_start', { url })
      if (r.isError) throw new Error(JSON.stringify(r.content).slice(0, 300))
      await log($, `opened in panel: ${fileName(path)} (attempt ${attempt})`)
      return 'panel'
    } catch (err) {
      blocked = /classifier|auto mode|permission|denied|refused/i.test(errText(err))
      await log($, `panel attempt ${attempt} failed: ${errText(err)}`)
      if (!blocked) break
    }
  }
  await helper($, ['window', url])
  $.ui.toast(blocked
    ? 'Modul auto nu a lăsat mod-ul să deschidă panoul, așa că editorul e într-o fereastră. Se rezolvă cu o regulă de permisiune pentru panou.'
    : 'Panoul din dreapta nu s-a putut deschide; am deschis editorul într-o fereastră.')
  return 'window'
}

// ---------- evenimentele editorului ----------

export function doneNote(sigs: string[], texts: number, edits = 0, rotated = 0): string {
  const parts: string[] = []
  if (sigs.length) parts.push(`Semnat cu ${sigs.map(s => `„${s}”`).join(', ')}`)
  if (texts) parts.push(texts === 1 ? '1 text adăugat' : `${texts} texte adăugate`)
  if (edits) parts.push(edits === 1 ? '1 rând editat' : `${edits} rânduri editate`)
  if (rotated) parts.push(rotated === 1 ? '1 pagină rotită' : `${rotated} pagini rotite`)
  return parts.join(' · ') || 'Salvat'
}

// Mesajul pentru Claude din comentariul pus în editor.
export function commentMessage(ev: EditorEvent): string {
  const lines = [`Comentariu în PDF (#${ev.number ?? '?'}, pagina ${ev.page}): ${String(ev.text ?? '').trim()}`, `Fișier: ${ev.path}`]
  const ctx = String(ev.context ?? '').trim()
  if (ev.kind === 'region') {
    if (ctx) lines.push(`Zona selectată conține: „${ctx}”`)
    if (ev.capture) lines.push(`Captura zonei: ${ev.capture}`)
  } else if (ctx) {
    lines.push(`Lângă textul: „${ctx}”`)
  }
  return lines.join('\n')
}

async function onEvent($: Engine, ev: EditorEvent) {
  await log($, `event ${ev.event}`)
  const all = await read($, cards)
  const owner = (p: unknown) => Object.keys(all).filter(k => all[k]!.current.toLowerCase() === String(p).toLowerCase())
  if (ev.event === 'saved') {
    const out = String(ev.out)
    forget(out)
    for (const key of owner(ev.source)) {
      await patch($, key, () => ({ current: out, signed: out, page: Number(ev.page) || 1, mode: 'view',
        note: doneNote((ev.sigs as string[]) ?? [], Number(ev.texts) || 0, Number(ev.edits) || 0, Number(ev.rotated) || 0), error: '' }))
    }
    await bump($)
  } else if (ev.event === 'undone') {
    forget(String(ev.path))
    for (const key of owner(ev.path)) {
      await patch($, key, c => (ev.removed ? { ...fresh(key), page: c.page, zoom: c.zoom } : { note: 'Ultima salvare a fost anulată', error: '' }))
    }
    await bump($)
  } else if (ev.event === 'comment') {
    const text = commentMessage(ev)
    let draft = ''
    try {
      draft = (await $.prompt.read()).text
    } catch {
      draft = ''
    }
    const filled = await $.prompt.fill({ text: (draft.trim() ? '\n\n' : '') + text, mode: 'append' }).catch(() => ({ isFilled: false }))
    if (filled.isFilled) {
      $.ui.toast(`Comentariul #${ev.number} e în căsuța de chat: apasă Enter ca să i-l trimiți lui Claude.`)
    } else {
      await $.prompt.submit({ text, asUser: true })
      $.ui.toast(`Comentariul #${ev.number} a fost trimis lui Claude.`)
    }
  } else if (ev.event === 'library') {
    thumbs = undefined // o semnătură nouă: lista din card se reîncarcă
    await bump($)
  } else if (ev.event === 'tool') {
    $.ui.toast(`${ev.tool}: ${fileName(String(ev.out))}`)
  }
}

// ---------- acțiuni din card ----------

const fresh = (path: string): Card => ({ current: path, page: 1, zoom: 1, pickPage: 0, query: '', preview: false, mode: 'view', note: '', error: '', signed: '' })

async function patch($: Engine, path: string, fn: (c: Card) => Partial<Card>) {
  await update($, cards, all => {
    const c = { ...fresh(path), ...all[path] }
    return { ...all, [path]: { ...c, ...fn(c) } }
  })
}

async function openPanel($: Engine, path: string, card: Card, opts: EditorOpts = {}) {
  await patch($, path, () => ({ mode: 'placing', note: 'Deschid editorul…', error: '' }))
  try {
    const where = await openEditor($, card.current, { page: card.page, ...opts })
    await patch($, path, () => ({ mode: 'view', note: where === 'panel' ? 'Editorul e deschis în panoul din dreapta' : 'Editorul e deschis într-o fereastră', error: '' }))
  } catch (err) {
    await patch($, path, () => ({ mode: 'view', note: '', error: errText(err) }))
  }
}

async function undo($: Engine, path: string, card: Card) {
  try {
    const r = (await helper($, ['undo', card.signed])) as { ok?: boolean; removed?: boolean; error?: string }
    if (!r.ok) throw new Error(r.error || 'Nu am putut anula.')
    forget(card.signed)
    await patch($, path, c => (r.removed ? { ...fresh(path), page: c.page, zoom: c.zoom } : { note: 'Ultima salvare a fost anulată', error: '' }))
  } catch (err) {
    await patch($, path, () => ({ error: errText(err) }))
  }
}

// Calea trece prin variabila FX_PATH, deci spațiile, & și apostrofurile nu strică comanda.
async function explorer($: Engine, path: string) {
  try {
    const cmd = `Start-Process explorer.exe -ArgumentList ('/select,"' + $env:FX_PATH + '"')`
    const r = await $.process.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', cmd], { env: { FX_PATH: path }, timeoutMs: 15000 })
    if (r.exitCode !== 0) $.ui.toast(r.stderr.trim() || `cod ${r.exitCode}`)
  } catch (err) {
    $.ui.toast(errText(err))
  }
}

// ---------- More: meniul de click dreapta din Windows (ca în mod-ul path-buttons) ----------

export function parseMenu(stdout: string): MenuItem[] {
  const items: MenuItem[] = []
  for (const line of stdout.split(/\r?\n/)) {
    const [depth, kind, key = '', text = '', icon = ''] = line.split('\t')
    if (kind !== 'cmd' && kind !== 'sub' && kind !== 'sep') continue
    items.push({ depth: Number(depth) || 0, kind, key, text, icon })
  }
  return items
}

const HIDDEN = new Set(['new', 'add to favorites', 'scan with microsoft defender', 'share', 'restore previous versions', 'create shortcut', 'properties'])

function fallbackIcon(item: MenuItem): string {
  const top = item.key.split(' › ')[0]!.replace(/#\d+$/, '').toLowerCase()
  const text = item.text.toLowerCase()
  if (top === '7-zip') return FLUENT.folder_zip!
  if (top === 'send to' && item.depth === 0) return FLUENT.send!
  if (top === 'open with' && item.depth === 0) return FLUENT.apps_list!
  if (item.depth > 0) return ''
  const byText: Record<string, string> = { open: 'open', print: 'print', cut: 'cut', copy: 'copy', delete: 'delete', 'copy as path': 'link' }
  return byText[text] ? FLUENT[byText[text]!]! : ''
}

export function tidy(items: readonly MenuItem[]): MenuItem[] {
  const blocks: MenuItem[][] = []
  for (const item of items) {
    if (item.depth === 0 || blocks.length === 0) blocks.push([item])
    else blocks[blocks.length - 1]!.push(item)
  }
  const kept = blocks.filter(b => !(b[0]!.kind !== 'sep' && HIDDEN.has(b[0]!.text.toLowerCase())))
  return kept.flat().map(item => (item.kind === 'sep' || item.icon ? item : { ...item, icon: fallbackIcon(item) }))
}

export function parentOf(key: string): string {
  const at = key.lastIndexOf(' › ')
  return at < 0 ? '' : key.slice(0, at)
}

export function panel(items: readonly MenuItem[], parent: string): { item: MenuItem; index: number }[] {
  const out: { item: MenuItem; index: number }[] = []
  const lastAt: string[] = []
  items.forEach((item, index) => {
    if (item.kind !== 'sep') {
      lastAt[item.depth] = item.key
      lastAt.length = item.depth + 1
      if (parentOf(item.key) === parent) out.push({ item, index })
      return
    }
    const owner = item.depth === 0 ? '' : lastAt[item.depth - 1] ?? ''
    const prev = out[out.length - 1]
    if (owner === parent && prev && prev.item.kind !== 'sep') out.push({ item, index })
  })
  while (out.length && out[out.length - 1]!.item.kind === 'sep') out.pop()
  return out
}

async function toggleMenu($: Engine, path: string) {
  let isOpen = false
  await update($, menus, m => {
    isOpen = Boolean(m[path])
    const next = { ...m }
    if (isOpen) delete next[path]
    else next[path] = { isLoading: true, items: [], expanded: [], error: '' }
    return next
  })
  if (isOpen) return
  let menu: Menu
  try {
    const r = await $.process.run([await shellmenu($), 'list', path], { timeoutMs: 60000 })
    menu = r.exitCode === 0
      ? { isLoading: false, items: tidy(parseMenu(r.stdout)), expanded: [], error: '' }
      : { isLoading: false, items: [], expanded: [], error: r.stderr.trim() || `cod ${r.exitCode}` }
  } catch (err) {
    menu = { isLoading: false, items: [], expanded: [], error: `Meniul nu a pornit (${errText(err)}). E instalat mod-ul path-buttons?` }
  }
  await update($, menus, m => (m[path] ? { ...m, [path]: menu } : m))
}

async function openSub($: Engine, path: string, key: string | null) {
  await update($, menus, m => {
    const menu = m[path]
    if (!menu) return m
    const expanded = key === null ? menu.expanded.slice(0, -1) : [...menu.expanded, key]
    return { ...m, [path]: { ...menu, expanded } }
  })
}

async function runItem($: Engine, path: string, item: MenuItem) {
  await update($, menus, m => {
    const next = { ...m }
    delete next[path]
    return next
  })
  $.ui.toast(`${item.text}…`)
  try {
    const r = await $.process.run([await shellmenu($), 'invoke', path, item.key], { timeoutMs: 120000 })
    if (r.exitCode !== 0) $.ui.toast(`${item.text}: ${r.stderr.trim() || `cod ${r.exitCode}`}`)
  } catch (err) {
    $.ui.toast(`${item.text}: ${errText(err)}`)
  }
}

// ---------- desenul ----------

type Site = RenderInput<'AssistantMessage' | 'UserMessage' | 'ToolUse'>
type SvgEl = (p: { source: string; alt: string; width?: number; height?: number }) => RenderElement

const BORDER = '#dfe3ea'
const HOVER = '#eef3ff'
const MENU_BG = '#f9f9f9'
const MENU_BORDER = '#d6d6d6'
const MENU_HOVER = '#e8e8e8'

async function draw<E extends Site>($: Engine, e: E, next: (e: E) => Promise<RenderElement>, text: string) {
  const found = await findPdfs($, text)
  if (found.length === 0) return next(e)
  const original = await next(e)
  await read($, tick) // redesenează când sosește o previzualizare
  const all = await read($, cards)
  const open = await read($, menus)
  const table = $.ui.resolve(e)
  const { Box, Text, Button } = table
  const Input = 'Input' in table ? table.Input : undefined
  // Svg există pe desktop (și pe mobil); terminalul n-are imagini vectoriale.
  const Svg = 'Svg' in table ? (table as unknown as { Svg: SvgEl }).Svg : undefined

  const separator = (key: string, width: number) => (
    <Box key={key} height={1} overflow="hidden" paddingX={1}>
      <Text color={MENU_BORDER} wrap="wrap">
        {'─'.repeat(width * 2)}
      </Text>
    </Box>
  )

  const drawMenu = (i: number, path: string, menu: Menu): RenderElement => {
    const parent = menu.expanded[menu.expanded.length - 1] ?? ''
    const rows = panel(menu.items, parent)
    const title = parent ? menu.items.find(it => it.key === parent)?.text ?? '' : ''
    const width = Math.min(60, Math.max(30, title.length + 8, ...rows.map(r => r.item.text.length + 9)))
    return (
      <Box key={`menu-${i}`} width={width} flexDirection="column" borderStyle="round" borderColor={MENU_BORDER} backgroundColor={MENU_BG}>
        {parent ? (
          <Box key={`back-${i}`} flexDirection="row" paddingX={1} hover={{ backgroundColor: MENU_HOVER }}>
            <Button key={`back-btn-${i}`} plain onPress={() => openSub($, path, null)}>
              ‹ <Text bold>{title}</Text>
            </Button>
          </Box>
        ) : null}
        {parent ? separator(`back-sep-${i}`, width) : null}
        {rows.map(({ item, index }) =>
          item.kind === 'sep' ? (
            separator(`sep-${i}-${index}`, width)
          ) : (
            <Box key={`row-${i}-${index}`} flexDirection="row" paddingX={1} hover={{ backgroundColor: MENU_HOVER }}>
              <Box key={`icon-${i}-${index}`} width={3}>
                {Svg && item.icon ? <Svg source={item.icon.startsWith('<svg') ? item.icon : `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><image href="data:image/png;base64,${item.icon}" width="16" height="16"/></svg>`} alt={item.text} width={16} height={16} /> : null}
              </Box>
              <Button key={`m-${i}-${index}`} plain onPress={() => (item.kind === 'sub' ? openSub($, path, item.key) : runItem($, path, item))}>
                {item.text}
              </Button>
              <Box flexGrow={1} />
              {item.kind === 'sub' ? <Text dimColor>›</Text> : null}
            </Box>
          ),
        )}
      </Box>
    )
  }

  const drawCard = (path: string, i: number): RenderElement => {
    const card = { ...fresh(path), ...all[path] }
    // Previzualizarea se face doar când omul apasă Preview.
    const pv = Svg && card.preview ? loadPreview($, card.current, card.page, card.zoom) : undefined
    const pages = pv && 'pages' in pv ? pv.pages : 0
    const go = (page: number) => patch($, path, () => ({ page }))
    const zi = ZOOMS.indexOf(card.zoom) < 0 ? 2 : ZOOMS.indexOf(card.zoom)
    const zoom = (k: number) => patch($, path, () => ({ zoom: ZOOMS[k]! }))
    const busy = card.mode === 'placing'
    const menu = open[card.current]

    const picker = (): RenderElement => {
      const loaded = loadThumbs($)
      const k = norm(card.query.trim())
      const list = Array.isArray(loaded) ? loaded.filter(t => !k || norm(t.name).includes(k)) : loaded
      const total = Array.isArray(list) ? Math.max(1, Math.ceil(list.length / PER_PAGE)) : 1
      const pp = Math.min(card.pickPage, total - 1)
      const shown = Array.isArray(list) ? list.slice(pp * PER_PAGE, pp * PER_PAGE + PER_PAGE) : []
      return (
        <Box key={`pick-${i}`} flexDirection="column" gap={1} borderStyle="round" borderColor={BORDER} paddingX={1} paddingY={1}>
          <Box flexDirection="row" columnGap={2} flexWrap="wrap" alignItems="center">
            <Text bold>Alege semnătura</Text>
            {Input ? (
              <Input key={`pick-search-${i}`} placeholder="Caută după nume" value={card.query} submitLabel="alege"
                onInput={v => patch($, path, () => ({ query: v, pickPage: 0 }))}
                onSubmit={() => (shown[0] ? openPanel($, path, card, { sig: shown[0].file }) : undefined)} />
            ) : null}
            <Button key={`pick-new-${i}`} label="+ Semnătură nouă" onPress={() => openPanel($, path, card, { upload: true })} />
            <Button key={`pick-refresh-${i}`} label="↻ Actualizează" onPress={() => { loadThumbs($, true); return bump($) }} />
            <Box flexGrow={1} />
            <Button key={`pick-close-${i}`} plain dimColor onPress={() => patch($, path, () => ({ mode: 'view' }))}>
              ✕
            </Button>
          </Box>
          {Array.isArray(list) && !list.length ? <Text dimColor>{k ? 'Nicio semnătură cu numele ăsta.' : 'Biblioteca e goală.'}</Text> : null}
          {!Array.isArray(list) && 'isLoading' in list ? (
            <Text dimColor>Se încarcă semnăturile…</Text>
          ) : !Array.isArray(list) && 'error' in list ? (
            <Box flexDirection="row" columnGap={2}>
              <Text color="error">{list.error}</Text>
              <Button key={`pick-retry-${i}`} label="Reîncearcă" onPress={() => { loadThumbs($, true); return bump($) }} />
            </Box>
          ) : (
            <Box flexDirection="row" flexWrap="wrap" columnGap={2} rowGap={1}>
              {shown.map((t, k) => ({ t, j: pp * PER_PAGE + k })).map(({ t, j }) => (
                // Imaginea nu se poate apăsa (Svg nu primește click), deci sub ea e un buton adevărat.
                <Box key={`tile-${i}-${j}`} flexDirection="column" alignItems="center" gap={1} hover={{ backgroundColor: HOVER }}>
                  {Svg && t.svg ? <Svg source={t.svg} alt={`Semnătura ${t.name}`} width={200} height={76} /> : null}
                  <Button key={`use-${i}-${j}`} label={`✍ ${t.name}`} onPress={() => openPanel($, path, card, { sig: t.file })} />
                </Box>
              ))}
            </Box>
          )}
          {total > 1 ? (
            <Box flexDirection="row" columnGap={1} alignItems="center">
              <Button key={`pick-prev-${i}`} label="‹" onPress={() => patch($, path, () => ({ pickPage: Math.max(0, pp - 1) }))} />
              <Text dimColor>
                {pp + 1} / {total}
              </Text>
              <Button key={`pick-next-${i}`} label="›" onPress={() => patch($, path, () => ({ pickPage: Math.min(total - 1, pp + 1) }))} />
            </Box>
          ) : null}
        </Box>
      )
    }

    const preview = (): RenderElement => (
      <Box key={`preview-${i}`} flexDirection="column" gap={1} borderStyle="round" borderColor={BORDER} paddingX={1} paddingY={1}>
        {!Svg || !pv || 'isLoading' in pv ? (
          <Text dimColor>Se pregătește previzualizarea…</Text>
        ) : 'error' in pv ? (
          <Text color="error">{pv.error}</Text>
        ) : (
          <Svg source={pv.svg} alt={`Pagina ${pv.page} din ${fileName(card.current)}`} width={pv.width} height={pv.height} />
        )}
        <Box flexDirection="row" columnGap={1} flexWrap="wrap" alignItems="center">
          {pages > 1 ? (
            <Box flexDirection="row" columnGap={1} alignItems="center">
              <Button key={`prev-${i}`} label="‹" onPress={() => go(Math.max(1, card.page - 1))} />
              <Text dimColor>
                {card.page} / {pages}
              </Text>
              <Button key={`next-${i}`} label="›" onPress={() => go(Math.min(pages, card.page + 1))} />
            </Box>
          ) : null}
          <Box flexDirection="row" columnGap={1} alignItems="center">
            <Button key={`zoom-out-${i}`} label="−" onPress={() => zoom(Math.max(0, zi - 1))} />
            <Button key={`zoom-reset-${i}`} plain dimColor label={`${Math.round(card.zoom * 100)}%`} onPress={() => zoom(2)} />
            <Button key={`zoom-in-${i}`} label="+" onPress={() => zoom(Math.min(ZOOMS.length - 1, zi + 1))} />
          </Box>
          {pv && 'signed' in pv && pv.signed ? <Text color="warning">are semnătură digitală</Text> : null}
        </Box>
      </Box>
    )

    return (
      <Box key={`pdf-${i}`} flexDirection="column" gap={1}>
        <Box flexDirection="row" columnGap={1} flexWrap="wrap" alignItems="center">
          <Text>📄 {fileName(card.current)}</Text>
          {Svg ? (
            <Button key={`preview-btn-${i}`} label={card.preview ? 'Ascunde preview' : 'Preview'} variant={card.preview ? 'secondary' : undefined}
              onPress={() => patch($, path, c => ({ preview: !c.preview }))} />
          ) : null}
          <Button key={`panel-${i}`} variant="primary" label={busy ? 'Se deschide…' : 'Deschide'} onPress={() => (busy ? undefined : openPanel($, path, card))} />
          <Button
            key={`sign-${i}`}
            label="✍ Semnează"
            onPress={() => {
              if (busy) return
              loadThumbs($)
              return patch($, path, c => ({ mode: c.mode === 'pick' ? 'view' : 'pick', error: '' }))
            }}
          />
          <Button key={`explorer-${i}`} label="Explorer" onPress={() => explorer($, card.current)} />
          <Button key={`more-${i}`} label="More" variant={menu ? 'secondary' : undefined} onPress={() => toggleMenu($, card.current)} />
          {card.signed && !busy ? <Button key={`undo-${i}`} label="↶ Anulează" onPress={() => undo($, path, card)} /> : null}
        </Box>
        {menu && (menu.isLoading || menu.error) ? (
          <Text dimColor={!menu.error} color={menu.error ? 'error' : undefined}>
            {menu.error || 'Se încarcă meniul…'}
          </Text>
        ) : null}
        {menu && !menu.isLoading && !menu.error ? drawMenu(i, card.current, menu) : null}
        {card.mode === 'pick' ? picker() : null}
        {Svg && card.preview ? preview() : null}
        {card.note ? (
          <Text color={busy ? undefined : 'success'} dimColor={busy}>
            {busy ? '' : '✓ '}
            {card.note}
          </Text>
        ) : null}
        {card.signed && !busy ? <Text dimColor>{card.signed}</Text> : null}
        {card.error ? <Text color="error">{card.error}</Text> : null}
      </Box>
    )
  }

  return (
    <Box flexDirection="column">
      {original}
      <Box flexDirection="column" marginTop={1} gap={1}>
        {found.map((p, i) => drawCard(p, i))}
      </Box>
    </Box>
  )
}

function isReply(tool: string): boolean {
  return /^mcp__.*hearthbot.*__reply$/.test(tool)
}

export const register: Register = on => {
  on('ui.render', { component: 'AssistantMessage' }, ($, e, next) => draw($, e, next, e.props.text))
  on('ui.render', { component: 'UserMessage' }, ($, e, next) => draw($, e, next, e.props.text))
  on('ui.render', { component: 'ToolUse' }, async ($, e, next) => {
    // Fișierele trimise în chat (SendUserFile) primesc și ele rândul de butoane.
    if (e.props.tool === 'SendUserFile') {
      const files = (e.props.input as { files?: unknown } | undefined)?.files
      if (!Array.isArray(files)) return next(e)
      let cwd = ''
      try {
        cwd = await $.session.cwd()
      } catch {
        cwd = ''
      }
      const abs = files.map(String).filter(f => /\.pdf$/i.test(f))
        .map(f => (/^[A-Za-z]:[\\/]/.test(f) || !cwd ? f : `${cwd.replace(/[\\/]+$/, '')}\\${f.replace(/^\.?[\\/]/, '')}`))
      return draw($, e, next, abs.join('\n'))
    }
    if (!isReply(e.props.tool)) return next(e)
    const input = e.props.input as { text?: unknown } | undefined
    return draw($, e, next, typeof input?.text === 'string' ? input.text : '')
  })
  // Butoanele apar doar sub căi întregi; îi spunem lui Claude să le scrie așa.
  on('prompt.compose', async ($, e, next) => {
    const r = await next(e)
    return {
      ...r,
      sections: [...r.sections, {
        id: 'pdf-sign:paths',
        scope: 'session',
        text: 'When you mention a PDF file to the user, write its full absolute path (for example I:\\Shared drives\\...\\file.pdf), one per line, not just the file name: the pdf-sign mod shows Preview / Open / Sign buttons under every full PDF path. This applies to lists of PDFs too.',
      }],
    }
  })
}
