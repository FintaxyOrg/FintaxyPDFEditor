import { expect, test } from 'claude-code/testing'

import { candidates, fileName, normalize } from './register'

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
