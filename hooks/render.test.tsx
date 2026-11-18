import { expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const PDF = String.raw`I:\Shared drives\FINTAXY HQ\01_Management\06_De Semnat\Acord nou.pdf`
const SIGNED = String.raw`I:\Shared drives\FINTAXY HQ\01_Management\06_De Semnat\Acord nou_semnat.pdf`
const SIG = String.raw`C:\s\Semnatura Denis Bradu.png`
const SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'

type Seen = { runs: (readonly string[])[]; urls: string[]; fills: string[]; submits: string[]; spawned: number; panes: string[]; paneText: string }

// Evenimentele pe care serverul editorului le scrie pe stdout după ce pornește.
function stubs(on: On, seen: Seen, events: object[] = [], panelOk = true, keepAlive = false) {
  on('ui.render', async ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>reply</Text>
  })
  on('fs.stat', async ($, e) => (e.path === PDF ? { value: { kind: 'file', size: 1, mtimeMs: 0, isLink: false } } : { deny: 'ENOENT' }))
  on('fs.write', async () => ({ value: undefined }))
  on('process.run', async ($, e) => {
    seen.runs.push(e.argv)
    const cmd = e.argv[2]
    const value =
      cmd === 'render' ? { pages: 3, page: Number(e.argv[4]), width: 420, height: 594, svg: SVG, signed: false }
      : cmd === 'thumbs' ? [
          { name: 'Denis Bradu', file: SIG, svg: SVG },
          { name: 'Andrei', file: 'C:\\s\\Semnatura Andrei.png', svg: SVG },
        ]
      : { ok: true }
    return { value: { exitCode: 0, stdout: JSON.stringify(value), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('process.spawn', async function* () {
    seen.spawned++
    yield { stream: 'stdout', text: '{"event": "ready", "port": 47811, "token": "tok"}\n' }
    for (const ev of events) yield { stream: 'stdout', text: JSON.stringify(ev) + '\n' }
    if (keepAlive) await new Promise(() => {}) // serverul adevărat rămâne pornit cât ține sesiunea
    return { value: { code: 0, signal: null } }
  })
  on('mcp.call', async ($, e) => {
    if (e.server === 'ccd_view') {
      seen.panes.push(`${e.tool}:${String(e.args?.pane)}`)
      return { value: { content: [{ type: 'text', text: seen.paneText }], isError: false } }
    }
    seen.urls.push(String((e.args as { url?: string })?.url))
    return { value: { content: [{ type: 'text', text: 'ok' }], isError: !panelOk } }
  })
  on('prompt.read', async () => ({ value: { text: '', cursor: 0 } }))
  on('prompt.fill', async ($, e) => {
    seen.fills.push(e.text)
    return { isFilled: true }
  })
  on('prompt.submit', async ($, e) => {
    seen.submits.push(e.text)
    return { text: e.text }
  })
}
const fresh = (paneText = 'Showing the Browser pane.'): Seen => ({ runs: [], urls: [], fills: [], submits: [], spawned: 0, panes: [], paneText })

test('desktop: preview doar la cerere, zoom, Deschide, alegerea semnăturii', async ($, on) => {
  const seen = fresh()
  stubs(on, seen, [], true, true)
  const ui = await $.ui.mount({
    plugin: 'pdf-sign', surface: 'desktop', component: 'AssistantMessage',
    props: { text: `Am pregătit ${PDF} pentru semnat.`, isFirstOfReply: true },
  })
  // Fără preview până nu apasă omul butonul.
  expect(await ui.find({ type: 'Svg' })).toBeUndefined()
  expect(seen.runs.some(r => r[2] === 'render')).toBe(false)
  expect((await ui.findAll({ type: 'Button' })).map(b => b.key)).toEqual(['preview-btn-0', 'panel-0', 'sign-0', 'explorer-0', 'more-0'])
  await ui.press({ key: 'preview-btn-0' })
  expect(await ui.find({ type: 'Button', text: 'Ascunde preview' })).toBeDefined()
  await ui.press({ key: 'next-0' })
  expect(seen.runs.some(r => r[2] === 'render' && r[4] === '2')).toBe(true)
  await ui.press({ key: 'zoom-in-0' })
  expect(seen.runs.some(r => r[2] === 'render' && r[4] === '2' && r[5] === '1.25')).toBe(true)
  expect(await ui.find({ type: 'Svg' })).toBeDefined()

  // Deschide în panou: pornește serverul o dată și cere panoul browserului cu URL-ul editorului.
  await ui.press({ key: 'panel-0' })
  expect(seen.spawned).toBe(1)
  expect(seen.urls[0]).toContain('http://127.0.0.1:47811/?t=tok&path=')
  const q = new URL(seen.urls[0]!).searchParams
  expect(q.get('path')).toBe(PDF)
  expect(q.get('page')).toBe('2')
  expect(await ui.find({ type: 'Text', text: /panoul din dreapta/ })).toBeDefined()
  expect(seen.panes).toEqual(['show_pane:preview']) // panoul e adus în față, nu rămâne ascuns
  expect(seen.runs.some(r => r[2] === 'window')).toBe(false)

  // Semnează: lista din card, apoi editorul cu semnătura aleasă.
  await ui.press({ key: 'sign-0' })
  expect(await ui.find({ key: 'use-0-1' })).toBeDefined()
  await ui.press({ key: 'use-0-0' })
  expect(seen.spawned).toBe(1) // același server
  expect(new URL(seen.urls[1]!).searchParams.get('sig')).toBe(SIG)
  expect(await ui.find({ key: 'use-0-0' })).toBeUndefined()

  // Ascunde preview: imaginea dispare.
  await ui.press({ key: 'preview-btn-0' })
  expect(await ui.find({ type: 'Svg' })).toBeUndefined()
  await ui.unmount()
})


test('căutarea în semnături și semnătura nouă', async ($, on) => {
  const seen = fresh()
  stubs(on, seen, [], true, true)
  const ui = await $.ui.mount({
    plugin: 'pdf-sign', surface: 'desktop', component: 'AssistantMessage',
    props: { text: `Vezi ${PDF}`, isFirstOfReply: true },
  })
  await ui.press({ key: 'sign-0' })
  expect(await ui.find({ key: 'use-0-1' })).toBeDefined()
  await ui.input({ key: 'pick-search-0', text: 'andrei', kind: 'change' })
  expect(await ui.find({ type: 'Button', text: '✍ Andrei' })).toBeDefined()
  expect(await ui.find({ type: 'Button', text: '✍ Denis Bradu' })).toBeUndefined()
  await ui.input({ key: 'pick-search-0', text: 'zzz', kind: 'change' })
  expect(await ui.find({ type: 'Text', text: /Nicio semnătură/ })).toBeDefined()
  const before = seen.runs.filter(r => r[2] === 'thumbs').length
  await ui.press({ key: 'pick-refresh-0' })
  expect(seen.runs.filter(r => r[2] === 'thumbs').length).toBe(before + 1)
  await ui.press({ key: 'pick-new-0' })
  expect(new URL(seen.urls[0]!).searchParams.get('upload')).toBe('1')
  await ui.unmount()
})

test('salvarea din editor schimbă cardul pe fișierul semnat', async ($, on) => {
  const seen = fresh()
  stubs(on, seen, [{ event: 'saved', source: PDF, out: SIGNED, sigs: ['Denis Bradu'], texts: 1, edits: 0, page: 3 }])
  const ui = await $.ui.mount({
    plugin: 'pdf-sign', surface: 'desktop', component: 'AssistantMessage',
    props: { text: `Vezi ${PDF}`, isFirstOfReply: true },
  })
  await ui.press({ key: 'panel-0' })
  expect(await ui.find({ type: 'Text', text: SIGNED })).toBeDefined()
  expect(await ui.find({ key: 'undo-0' })).toBeDefined()
  await ui.press({ key: 'preview-btn-0' })
  expect(seen.runs.some(r => r[2] === 'render' && r[3] === SIGNED && r[4] === '3')).toBe(true)
  await ui.press({ key: 'undo-0' })
  expect(seen.runs.find(r => r[2] === 'undo')!.slice(3)).toEqual([SIGNED])
})

test('comentariul din editor ajunge în căsuța de chat', async ($, on) => {
  const seen = fresh()
  stubs(on, seen, [{ event: 'comment', path: PDF, page: 2, number: 3, kind: 'region', text: 'Rezumă zona', context: 'Art. 4 Plata',
    capture: 'C:\\cap\\a.png', send: true }])
  const ui = await $.ui.mount({
    plugin: 'pdf-sign', surface: 'desktop', component: 'AssistantMessage',
    props: { text: `Vezi ${PDF}`, isFirstOfReply: true },
  })
  await ui.press({ key: 'panel-0' })
  expect(seen.fills).toHaveLength(1)
  expect(seen.fills[0]).toContain('Comentariu în PDF (#3, pagina 2): Rezumă zona')
  expect(seen.fills[0]).toContain('Captura zonei: C:\\cap\\a.png')
  expect(seen.fills[0]).toContain('„Art. 4 Plata”')
  expect(seen.submits).toHaveLength(0)
})

test('fără panou se deschide fereastra de rezervă', async ($, on) => {
  const seen = fresh()
  stubs(on, seen, [], false)
  const ui = await $.ui.mount({
    plugin: 'pdf-sign', surface: 'desktop', component: 'AssistantMessage',
    props: { text: `Vezi ${PDF}`, isFirstOfReply: true },
  })
  await ui.press({ key: 'panel-0' })
  const win = seen.runs.find(r => r[2] === 'window')!
  expect(win[3]).toContain('http://127.0.0.1:47811/?t=tok')
  expect(await ui.find({ type: 'Text', text: /într-o fereastră/ })).toBeDefined()
})

test('panoul rămas ascuns: editorul se deschide și într-o fereastră', async ($, on) => {
  const seen = fresh("This session isn't open in any window right now, so its view was left alone.")
  stubs(on, seen)
  const ui = await $.ui.mount({
    plugin: 'pdf-sign', surface: 'desktop', component: 'AssistantMessage',
    props: { text: `Vezi ${PDF}`, isFirstOfReply: true },
  })
  await ui.press({ key: 'panel-0' })
  expect(seen.panes).toEqual(['show_pane:preview'])
  expect(seen.runs.find(r => r[2] === 'window')?.[3]).toContain('http://127.0.0.1:47811/?t=tok')
  expect(await ui.find({ type: 'Text', text: /fereastră separată/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /panoul din dreapta/ })).toBeUndefined()
})

test('panoul Browser într-o fereastră a lui: cardul spune unde e', async ($, on) => {
  const seen = fresh('The preview pane is in a window of its own; it was left where it is.')
  stubs(on, seen)
  const ui = await $.ui.mount({
    plugin: 'pdf-sign', surface: 'desktop', component: 'AssistantMessage',
    props: { text: `Vezi ${PDF}`, isFirstOfReply: true },
  })
  await ui.press({ key: 'panel-0' })
  expect(seen.runs.some(r => r[2] === 'window')).toBe(false)
  expect(await ui.find({ type: 'Text', text: /fereastra separată a panoului Browser/ })).toBeDefined()
})

test('fișierele trimise în chat primesc butoanele', async ($, on) => {
  stubs(on, fresh())
  const ui = await $.ui.mount({
    plugin: 'pdf-sign', surface: 'desktop', component: 'ToolUse',
    props: { tool_use_id: 'u1', tool: 'SendUserFile', input: { files: [PDF, 'C:\\x\\poza.png'], status: 'normal' }, isRunning: false, isErrored: false, isInterrupted: false },
  })
  expect(await ui.find({ key: 'panel-0' })).toBeDefined()
  expect(await ui.find({ key: 'panel-1' })).toBeUndefined()
})

test('terminal: fără imagini, dar cu butoanele', async ($, on) => {
  stubs(on, fresh())
  const ui = await $.ui.mount({
    plugin: 'pdf-sign', surface: 'terminal', component: 'AssistantMessage',
    props: { text: `Vezi ${PDF}`, isFirstOfReply: true },
  })
  expect(await ui.find({ key: 'sign-0' })).toBeDefined()
  expect(await ui.find({ key: 'more-0' })).toBeDefined()
})

test('fără PDF existent nu apare nimic', async ($, on) => {
  stubs(on, fresh())
  const ui = await $.ui.mount({
    plugin: 'pdf-sign', surface: 'desktop', component: 'AssistantMessage',
    props: { text: String.raw`Vezi C:\nu\exista.pdf`, isFirstOfReply: true },
  })
  expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
})
