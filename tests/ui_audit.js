// Auditul vizual al editorului, rulat în pagină (consola browserului sau un instrument de automatizare):
// deschide pe rând fiecare panou și fiecare formular de unealtă și caută greșelile pe care le vede omul:
// elemente care ies din panou, text tăiat fără „…”, panouri care nu se pot derula, butoane ieșite din ecran,
// texte rămase netraduse (în engleză). Întoarce lista problemelor găsite.
//   const r = await (await import('/editor/../tests-ui-audit')).run()   -> vezi tests/README sau lipește fișierul în consolă
(async () => {
  const wait = ms => new Promise(r => setTimeout(r, ms))
  const $ = (s, el = document) => el.querySelector(s)
  const $$ = (s, el = document) => [...el.querySelectorAll(s)]
  const found = []
  const en = document.documentElement.lang === 'en'
  const RO = /[ăâîșțĂÂÎȘȚ]/
  const vis = n => { const r = n.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(n).visibility !== 'hidden' }

  function check(where, root) {
    if (!root || !vis(root)) return found.push({ where, what: 'nu s-a deschis' })
    const box = root.getBoundingClientRect()
    const scroller = $('.db', root) || $('.chat-thread', root) || root
    for (const n of $$('*', root)) {
      if (!vis(n) || n.closest('svg')) continue
      const r = n.getBoundingClientRect()
      const cs = getComputedStyle(n)
      // iese în lateral din panou (în afara elementelor care se derulează singure)
      if ((r.right > box.right + 2 || r.left < box.left - 2) && !n.closest('pre, table, select, .blist, .ct-perm-input')) {
        found.push({ where, what: 'iese din panou', el: `${n.tagName}.${n.className}`.slice(0, 60), text: (n.textContent || '').trim().slice(0, 40) })
      }
      // conținut mai lat decât elementul, tăiat fără „…” și fără derulare
      const own = [...n.childNodes].some(c => c.nodeType === 3 && c.textContent.trim())
      if (own && n.scrollWidth > n.clientWidth + 2 && cs.overflowX === 'hidden' && cs.textOverflow !== 'ellipsis' && cs.webkitLineClamp === 'none') {
        found.push({ where, what: 'text tăiat', el: `${n.tagName}.${n.className}`.slice(0, 60), text: n.textContent.trim().slice(0, 40) })
      }
      // text tăiat pe verticală (înălțime fixă mai mică decât textul)
      if (own && n.scrollHeight > n.clientHeight + 3 && cs.overflowY === 'hidden' && cs.webkitLineClamp === 'none' && !/^(INPUT|TEXTAREA|SELECT)$/.test(n.tagName)) {
        found.push({ where, what: 'text tăiat pe înălțime', el: `${n.tagName}.${n.className}`.slice(0, 60), text: n.textContent.trim().slice(0, 40) })
      }
      // în engleză: text românesc rămas (în afara numelor de fișiere și a valorilor)
      if (en && own && n.children.length === 0 && RO.test(n.textContent) && !n.closest('.ct-q, .ct-a, .bn, pre, code, option[value]') && n.tagName !== 'OPTION') {
        found.push({ where, what: 'netradus', text: n.textContent.trim().slice(0, 70) })
      }
    }
    for (const n of $$('[title], [placeholder]', root)) {
      const t = n.getAttribute('title') || n.getAttribute('placeholder') || ''
      if (en && RO.test(t) && !n.closest('.bn, .ct-tool, .brow')) found.push({ where, what: 'netradus (indiciu)', text: t.slice(0, 70) })
    }
    // panoul trebuie să se poată derula dacă are mai mult conținut decât încape
    if (scroller.scrollHeight > scroller.clientHeight + 4 && !/(auto|scroll)/.test(getComputedStyle(scroller).overflowY)) {
      found.push({ where, what: 'nu se poate derula', el: scroller.className })
    }
    // ultimul buton trebuie să se poată aduce în vedere
    const btn = $$('button', root).filter(vis).pop()
    if (btn) {
      btn.scrollIntoView({ block: 'nearest' })
      const r = btn.getBoundingClientRect()
      if (r.bottom > innerHeight + 2 || r.right > innerWidth + 2) found.push({ where, what: 'buton în afara ecranului', text: btn.textContent.trim().slice(0, 30) })
    }
  }

  const drawer = $('#drawer')
  const closeAll = () => { $('.modal-back')?.remove(); $('#palette')?.remove(); if (!drawer.hidden) $('.dh button.icon:last-child', drawer)?.click() }

  // 1. panourile mari
  const panels = [
    ['semnătură electronică', () => $('#btnCert').click(), 2500],
    ['comentarii', () => $('#btnComments').click(), 600],
    ['chat', () => $('.rail [data-panel=chat]').click(), 1500],
    ['componente', async () => { $('#btnSearch').click(); await wait(300); const i = $('#palette input'); i.value = en ? 'Components' : 'Componente'; i.dispatchEvent(new Event('input')); await wait(300); i.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })) }, 1500],
    ['toate uneltele', () => $('.rail [data-panel=tools]').click(), 900],
  ]
  for (const [name, open, ms] of panels) {
    closeAll(); await wait(200)
    try { await open(); await wait(ms); check(name, drawer) } catch (err) { found.push({ where: name, what: 'eroare: ' + err.message }) }
  }
  // 2. paleta, semnătura nouă, ghidul
  closeAll(); $('#btnSearch').click(); await wait(400); check('căutare Ctrl+K', $('#palette') || $('.palette')); $('#palette')?.remove(); document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  $('#btnHelp').click(); await wait(500)
  for (let k = 0; k < 6 && $('#onboard'); k++) {
    await wait(k === 2 ? 3500 : 900)
    check(`ghid, pasul ${k + 1}`, $('#onboard .ob-card'))
    const next = $$('#onboard .ob-foot button.primary')[0]
    if (k < 5) next.click(); else $('#onboard .ob-head button.icon').click()
  }
  await wait(300); $('#onboard')?.remove()

  // 3. fiecare unealtă din listă: formularul ei
  closeAll(); await wait(200); $('.rail [data-panel=tools]').click(); await wait(900)
  const count = $$('#drawer .tool').length
  let opened = 0
  for (let i = 0; i < count; i++) {
    const row = $$('#drawer .tool')[i]
    if (!row) break
    const label = row.textContent.trim().slice(0, 40)
    row.click()
    await wait(350)
    if ($('.modal-back')) { check(`unealtă: ${label}`, $('.modal-back .modal')); $('.modal-back')?.remove() }
    else if ($('#organize, .organize')) { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); $('#organize, .organize')?.remove() }
    else {
      for (let k = 0; k < 12 && $('#drawer .spin') && !$('#drawer .form label, #drawer .form .result, #drawer .form .warn'); k++) await wait(250)
      check(`unealtă: ${label}`, drawer)
    }
    opened++
    // înapoi la listă
    const back = $$('#drawer .dh button.icon')[0]
    if (drawer.hidden || !$$('#drawer .tool').length) { if (back && $$('#drawer .dh button.icon').length > 1) back.click(); await wait(150) }
    if (drawer.hidden || !$$('#drawer .tool').length) { $('.rail [data-panel=tools]').click(); await wait(500); if (!$$('#drawer .tool').length) { $('.rail [data-panel=tools]').click(); await wait(500) } }
  }
  closeAll()
  const seen = new Set()
  const unique = found.filter(f => { const k = JSON.stringify(f); if (seen.has(k)) return false; seen.add(k); return true })
  return { limba: en ? 'en' : 'ro', fereastra: `${innerWidth}x${innerHeight}`, unelteDeschise: opened, probleme: unique.length, lista: unique.slice(0, 60) }
})()
