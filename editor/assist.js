// Ce ajută omul în jurul editorului: chatul cu Claude (prin ACP, ca „Ask AI” din Fintaxy CRM), programele în plus
// (LibreOffice, Stirling, Node.js, instalate din aplicație fără terminal) și ghidul de la prima pornire.
// Textele sunt scrise aici direct în ambele limbi: T('română', 'English').
import { lang } from './i18n.js'

let X = null // ce primește de la editor.js: h, $, api, post, toast, openDrawer, closeDrawer, state, path(), openDoc...
const T = (ro, en) => (lang() === 'en' ? en : ro)
const SVG = {
  chat: '<path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9z"/><path d="M19 15l.8 1.9 1.9.8-1.9.8L19 20.4l-.8-1.9-1.9-.8 1.9-.8z"/><path d="M5 16l.6 1.4L7 18l-1.4.6L5 20l-.6-1.4L3 18l1.4-.6z"/>',
  plug: '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
  fresh: '<path d="M12 5v14"/><path d="M5 12h14"/>',
  send: '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
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
  return esc(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, '$1<i>$2</i>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
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
    if (hd) out.push(`<h4>${inline(hd[2])}</h4>`)
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

// ---------- programele în plus ----------
// Un rând pe program: nume, la ce folosește (în semnul „i”), stare, buton de instalare. Fără terminal, fără Enter.
function depRow(id, it, onChange) {
  const { h } = X
  const state = h('span', { class: 'dep-state' })
  const btn = h('button', { class: 'secondary', type: 'button' }, T('Instalează', 'Install'))
  const row = h('div', { class: 'dep' }, h('div', { class: 'dep-name' }, h('b', {}, it.name), info(`${T(USE[id][0], USE[id][1])} · ${it.size}`)), state, btn)
  const draw = () => {
    row.classList.toggle('ok', it.installed)
    state.replaceChildren(it.installed ? svg('check') : '', it.installed ? T('Instalat', 'Installed') : it.needed ? T('Lipsește', 'Missing') : T('Opțional', 'Optional'))
    btn.hidden = it.installed
  }
  const run = async () => {
    btn.disabled = true
    state.replaceChildren(h('span', { class: 'spin' }), T('Pornesc…', 'Starting…'))
    try {
      await X.post('deps/install', { id })
      const j = await follow(async () => (await X.api('deps')).items[id].job, line => state.replaceChildren(h('span', { class: 'spin' }), line.slice(0, 60)))
      if (j.state === 'error') throw new Error(j.line)
      it.installed = true
      X.toast(T(`${it.name} e instalat.`, `${it.name} is installed.`))
      onChange?.()
    } catch (err) {
      X.toast(err.message, { err: true, ms: 9000 })
    }
    btn.disabled = false
    draw()
  }
  btn.addEventListener('click', run)
  draw()
  if (it.job?.state === 'running') run()
  return row
}
const USE = {
  libreoffice: ['Word, Excel, PowerPoint → PDF, când nu ai Microsoft Office', 'Word, Excel, PowerPoint → PDF, when you have no Microsoft Office'],
  stirling: ['Unelte rare: OCR, redactare automată, conversii exotice', 'Rare tools: OCR, auto-redaction, exotic conversions'],
  node: ['Necesar pentru chatul cu Claude din editor', 'Needed for the Claude chat in the editor'],
}
async function depsBox(only) {
  const { h } = X
  const box = h('div', { class: 'deps' }, h('div', { class: 'muted' }, h('span', { class: 'spin' })))
  try {
    const d = await X.api('deps')
    const ids = Object.keys(d.items).filter(id => !only || only.includes(id))
    box.replaceChildren(...ids.map(id => depRow(id, d.items[id])))
    if (!d.winget) box.append(h('div', { class: 'warn' }, T('Calculatorul nu are winget (App Installer din Microsoft Store): programele se instalează de pe site-urile lor.',
      'This PC has no winget (App Installer from the Microsoft Store): install the programs from their websites.')))
  } catch (err) {
    box.replaceChildren(h('div', { class: 'result err' }, err.message))
  }
  return box
}
export async function openDeps() {
  const { h } = X
  const body = h('div', { class: 'db form' })
  X.openDrawer(T('Programe în plus', 'Extra programs'), body)
  body.append(h('p', { class: 'desc' }, T('Aplicația merge și fără ele. Se instalează singure, fără terminal.', 'The app works without them. They install by themselves, no terminal.')),
    await depsBox())
}

// ---------- chatul cu Claude ----------
const chats = new Map() // cale -> { seq, revs, nodes: Map(seq -> element), running }
let poll = 0 // schimbat la fiecare deschidere: bucla veche de citire se oprește singură

function chatState(path) {
  const k = path.toLowerCase()
  if (!chats.has(k)) chats.set(k, { seq: 0, revs: {}, events: new Map(), running: false })
  return chats.get(k)
}

function eventNode(e, path) {
  const { h } = X
  if (e.type === 'user') return h('div', { class: 'msg user' }, e.text)
  if (e.type === 'text') return h('div', { class: 'msg bot', html: markdown(e.text) })
  if (e.type === 'thought') return h('details', { class: 'msg thought' }, h('summary', {}, T('Gândire', 'Thinking')), h('div', {}, e.text))
  if (e.type === 'tool') {
    const st = e.status === 'completed' ? 'ok' : e.status === 'failed' ? 'bad' : 'run'
    return h('div', { class: `msg tool ${st}` }, st === 'run' ? h('span', { class: 'spin' }) : h('span', { class: 'tdot' }), h('span', {}, e.title))
  }
  if (e.type === 'perm') {
    const box = h('div', { class: `msg perm ${e.state}` }, h('b', {}, T('Claude vrea să:', 'Claude wants to:')), h('div', { class: 'ptitle' }, e.title),
      e.detail ? h('code', {}, e.detail) : null)
    if (e.state === 'ask') {
      const answer = choice => X.post('chat/permission', { path, id: e.id, choice }).catch(err => X.toast(err.message, { err: true }))
      box.append(h('div', { class: 'pbtns' },
        h('button', { class: 'primary', type: 'button', onclick: () => answer('allow') }, T('Permite', 'Allow')),
        h('button', { class: 'secondary', type: 'button', onclick: () => answer('always'), title: T('Nu mai întreabă pentru acest fel de acțiune, în conversația asta', 'Stops asking for this kind of action, in this conversation') }, T('Mereu', 'Always')),
        h('button', { class: 'secondary', type: 'button', onclick: () => answer('deny') }, T('Refuză', 'Deny'))))
    } else {
      box.append(h('div', { class: 'pstate' }, { allowed: T('Permis', 'Allowed'), denied: T('Refuzat', 'Denied'), cancelled: T('Anulat', 'Cancelled') }[e.state] || ''))
    }
    return box
  }
  if (e.type === 'error') {
    const box = h('div', { class: 'msg err' }, e.text)
    if (e.needLogin) box.append(h('div', { class: 'pbtns' }, h('button', { class: 'primary', type: 'button', onclick: () => X.post('chat/login', {}).catch(err => X.toast(err.message, { err: true })) }, T('Conectează Claude', 'Connect Claude'))))
    return box
  }
  return null
}

export async function openChat(prefill) {
  const { h } = X
  const path = X.path()
  if (!path) return X.toast(T('Deschide întâi un PDF.', 'Open a PDF first.'))
  const my = ++poll
  const list = h('div', { class: 'chat-list' })
  const input = h('textarea', { rows: '1', placeholder: T('Întreabă-l pe Claude despre document…', 'Ask Claude about the document…') })
  const send = h('button', { class: 'chat-send', type: 'button', title: T('Trimite (Enter)', 'Send (Enter)') }, svg('send'))
  const body = h('div', { class: 'chat' }, list, h('div', { class: 'chat-in' }, input, send))
  const d = X.openDrawer('Claude', body)
  d.dataset.kind = 'chat'
  const head = d.querySelector('.dh')
  head.querySelector('h2').append(info(T('Claude vede PDF-ul deschis și pagina pe care ești. Orice scriere de fișiere îți cere acordul.',
    'Claude sees the open PDF and the page you are on. Any file write asks for your approval.')))
  head.lastChild.before(
    h('button', { class: 'icon', type: 'button', title: T('Conversație nouă', 'New conversation'), onclick: () => reset() }, svg('fresh')),
    h('button', { class: 'icon', type: 'button', title: T('Conexiuni (CRM)', 'Connections (CRM)'), onclick: () => openConnections() }, svg('plug')))
  const st = chatState(path)

  const draw = e => {
    const old = list.querySelector(`[data-seq="${e.seq}"]`)
    const node = eventNode(e, path)
    if (!node) return old?.remove()
    node.dataset.seq = e.seq
    const stick = list.scrollHeight - list.scrollTop - list.clientHeight < 80
    if (old) old.replaceWith(node)
    else list.append(node)
    if (stick) list.scrollTop = list.scrollHeight
  }
  const setRunning = on => {
    st.running = on
    send.replaceChildren(svg(on ? 'stop' : 'send'))
    send.title = on ? T('Oprește', 'Stop') : T('Trimite (Enter)', 'Send (Enter)')
    send.classList.toggle('stop', on)
  }
  const empty = () => {
    if (list.children.length) return
    const tips = [[T('Rezumă documentul', 'Summarise the document'), T('Rezumă documentul în 5 rânduri.', 'Summarise the document in 5 lines.')],
      [T('Ce trebuie semnat?', 'What needs signing?'), T('Unde trebuie semnat documentul ăsta și de către cine?', 'Where does this document need to be signed, and by whom?')],
      [T('Verifică sumele și datele', 'Check amounts and dates'), T('Verifică sumele, datele și numele din document: sunt consecvente?', 'Check the amounts, dates and names in the document: are they consistent?')]]
    list.append(h('div', { class: 'chat-empty' }, h('div', { class: 'muted' }, T('Întreabă orice despre PDF-ul deschis.', 'Ask anything about the open PDF.')),
      ...tips.map(([label, text]) => h('button', { class: 'chip', type: 'button', onclick: () => { input.value = text; go() } }, label))))
  }
  const loop = async () => {
    while (my === poll && d.isConnected && !d.hidden && d.dataset.kind === 'chat') {
      try {
        const r = await X.api('chat/events', { path, since: st.seq, revs: JSON.stringify(st.revs), wait: 20 })
        if (my !== poll) return
        if (r.events.length) list.querySelector('.chat-empty')?.remove()
        for (const e of r.events) {
          st.events.set(e.seq, e)
          st.revs[e.seq] = e.rev || 0
          st.seq = Math.max(st.seq, e.seq)
          draw(e)
          if (e.type === 'done' && e.docChanged) X.reload(T('Claude a schimbat documentul: l-am reîncărcat.', 'Claude changed the document: reloaded.'))
        }
        if (r.last < st.seq) { st.seq = 0; st.revs = {}; st.events.clear(); list.replaceChildren(); empty() } // conversație nouă
        setRunning(r.running)
      } catch {
        await new Promise(r => setTimeout(r, 1500))
      }
    }
  }
  async function reset() {
    await X.post('chat/reset', { path }).catch(() => {})
    st.seq = 0; st.revs = {}; st.events.clear()
    list.replaceChildren()
    empty()
  }
  async function go() {
    if (st.running) return X.post('chat/cancel', { path }).catch(() => {})
    const text = input.value.trim()
    if (!text) return
    input.value = ''
    input.style.height = ''
    setRunning(true)
    try {
      await X.post('chat/send', { path, text, page: X.state.cur })
    } catch (err) {
      setRunning(false)
      input.value = text
      X.toast(err.message, { err: true })
    }
  }
  send.addEventListener('click', go)
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); go() } })
  input.addEventListener('input', () => { input.style.height = ''; input.style.height = `${Math.min(140, input.scrollHeight)}px` })

  // Ce lipsește ca să meargă chatul (Node.js, legătura cu Claude, conectarea): pașii apar în loc de conversație.
  let status
  try { status = await X.api('chat/status') } catch (err) { status = { available: false, step: 'error', error: err.message } }
  if (my !== poll) return
  if (!status.available) {
    list.append(await chatSetup(status, () => openChat(prefill)))
    input.disabled = send.disabled = true
    return
  }
  for (const e of st.events.values()) draw(e)
  empty()
  setRunning(st.running)
  loop()
  if (prefill) { input.value = prefill; input.dispatchEvent(new Event('input')) }
  input.focus()
}

// Pașii de pornire ai chatului: fiecare cu butonul lui; nimic de tastat într-un terminal, în afară de conectarea
// la contul Claude (o dată), care se face în browser.
async function chatSetup(status, done) {
  const { h } = X
  const box = h('div', { class: 'chat-setup' }, h('b', {}, T('Pornește chatul cu Claude', 'Set up the Claude chat')),
    info(T('O singură dată pe calculator (~350 MB). Chatul folosește abonamentul tău Claude, fără alte costuri.', 'Once per computer (~350 MB). The chat uses your Claude subscription, at no extra cost.')))
  const step = (n, label, ok, btnLabel, run) => {
    const state = h('span', { class: 'dep-state' }, ok ? svg('check') : '', ok ? T('Gata', 'Done') : '')
    const btn = h('button', { class: 'primary', type: 'button', hidden: ok || !run }, btnLabel)
    btn.addEventListener('click', async () => {
      btn.disabled = true
      try { await run(state) } catch (err) { X.toast(err.message, { err: true, ms: 9000 }) }
      btn.disabled = false
    })
    box.append(h('div', { class: `dep${ok ? ' ok' : ''}` }, h('div', { class: 'dep-name' }, h('b', {}, `${n}. ${label}`)), state, btn))
  }
  const cur = status.step
  step(1, 'Node.js', status.node, T('Instalează', 'Install'), cur === 'node' && (async state => {
    await X.post('deps/install', { id: 'node' })
    const j = await follow(async () => (await X.api('deps')).items.node.job, line => state.replaceChildren(h('span', { class: 'spin' }), line.slice(0, 50)))
    if (j.state === 'error') throw new Error(j.line)
    done()
  }))
  step(2, T('Legătura cu Claude', 'Claude link'), status.adapter, T('Instalează', 'Install'), cur === 'adapter' && (async state => {
    await X.post('chat/setup', {})
    const j = await follow(async () => (await X.api('chat/status')).setup, line => state.replaceChildren(h('span', { class: 'spin' }), line.slice(0, 50)))
    if (j.state === 'error') throw new Error(j.line)
    done()
  }))
  step(3, T('Contul Claude', 'Claude account'), status.loggedIn, T('Conectează', 'Connect'), cur === 'login' && (async state => {
    await X.post('chat/login', {})
    state.replaceChildren(h('span', { class: 'spin' }), T('Scrie /login în fereastra deschisă…', 'Type /login in the window that opened…'))
    for (let i = 0; i < 200; i++) { // până la ~10 minute: omul se conectează în browser
      await new Promise(r => setTimeout(r, 3000))
      if ((await X.api('chat/status')).loggedIn) return done()
    }
  }))
  if (cur === 'login') box.append(h('div', { class: 'muted small' }, T('Se deschide o fereastră: scrie /login, Enter, apoi urmezi pașii din browser.', 'A window opens: type /login, Enter, then follow the steps in the browser.')))
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
  X.openDrawer(T('Conexiuni', 'Connections'), body)
}

// ---------- ghidul de la prima pornire ----------
const MOD_PROMPT = () => T(`Instalează modul PDF Sign (Fintaxy) pentru Claude Code pe acest calculator:
1. Rulează: claude plugin marketplace add FintaxyOrg/FintaxyPDFEditor
2. Rulează: claude plugin install pdf-sign@fintaxy-pdf-sign
3. Verifică să existe Python 3.12; dacă lipsește, instalează-l cu winget (pe tăcute, cu acordurile acceptate). Apoi instalează pachetele din requirements.txt al modului (pip install -r requirements.txt, din folderul în care s-a instalat).
4. Spune-mi să dau /reload-plugins, apoi arată-mi pe un PDF de test că sub el apar butoanele Preview / Deschide / Semnează.
Dacă marketplace-ul nu se poate adăuga (repo privat), spune-mi ce cont GitHub trebuie să primească acces și oprește-te acolo.`,
`Install the PDF Sign (Fintaxy) mod for Claude Code on this computer:
1. Run: claude plugin marketplace add FintaxyOrg/FintaxyPDFEditor
2. Run: claude plugin install pdf-sign@fintaxy-pdf-sign
3. Make sure Python 3.12 exists; if it is missing, install it with winget (silently, agreements accepted). Then install the packages from the mod's requirements.txt (pip install -r requirements.txt, from the folder it was installed in).
4. Tell me to run /reload-plugins, then show me on a test PDF that the Preview / Open / Sign buttons appear under it.
If the marketplace cannot be added (private repo), tell me which GitHub account needs access and stop there.`)

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
    { title: T('Programe în plus', 'Extra programs'), tip: T('Opționale. Se instalează din aplicație, fără terminal; Windows poate cere o singură confirmare de administrator.', 'Optional. They install from the app, no terminal; Windows may ask for one administrator confirmation.'),
      body: () => depsBox(['libreoffice', 'stirling']) },
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
  const b = ctx.h('button', { 'data-panel': 'chat', title: T('Vorbește cu Claude (A)', 'Talk to Claude (A)') }, svg('chat'))
  b.addEventListener('click', () => {
    const d = ctx.$('#drawer')
    if (!d.hidden && d.dataset.kind === 'chat') ctx.closeDrawer()
    else openChat()
  })
  rail.append(ctx.h('span', { class: 'rail-sep' }), b)
  // Ghidul de pornire e mereu la îndemână: butonul „?” din bara de sus.
  const help = ctx.h('button', { class: 'icon', id: 'btnHelp', type: 'button', title: T('Ghid de pornire', 'Getting started') }, svg('help'))
  help.addEventListener('click', () => openOnboarding())
  document.querySelector('header.top .actions').prepend(help)
}
