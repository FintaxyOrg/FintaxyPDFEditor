import { expect, test } from 'claude-code/testing'

import { candidates, fileName, normalize, shownFrom } from './register'

test('găsește căile PDF cu spații, două în aceeași frază', () => {
  const text = String.raw`Am salvat I:\Shared drives\FINTAXY HQ\01_Management\Acord X.pdf și C:\Temp\b.pdf, gata.`
  expect(candidates(text, '')).toEqual([
    String.raw`I:\Shared drives\FINTAXY HQ\01_Management\Acord X.pdf`,
    String.raw`C:\Temp\b.pdf`,
  ])
})

test('link markdown relativ și file:///', () => {
  const text = '[acord](docs/Acord%20nou.pdf) și file:///C:/Temp/Doc%20A.pdf'
  expect(candidates(text, String.raw`I:\Proiect`)).toEqual([String.raw`C:\Temp\Doc A.pdf`, String.raw`I:\Proiect\docs\Acord nou.pdf`])
})

test('ignoră ce nu e PDF', () => {
  expect(candidates(String.raw`C:\Temp\a.docx`, '')).toEqual([])
})

test('numele fișierului', () => {
  expect(fileName(normalize('C:/a/b c.pdf'))).toBe('b c.pdf')
})

test('răspunsul show_pane: arătat, fereastră proprie, ascuns', () => {
  const t = (text: string, isError = false) => shownFrom({ content: [{ type: 'text', text }], isError })
  expect(t('Showing the Browser pane.')).toBe('shown')
  // textul real al aplicației când sesiunea nu e pe ecran
  expect(t(`This session isn't open in any window right now, so its view was left alone. Tell the user what to look at instead.
{"views":[],"open_panes":[]}`)).toBe('hidden')
  expect(t('The preview pane is in a window of its own; it was left where it is.')).toBe('popped')
  expect(t('whatever', true)).toBe('hidden')
})
