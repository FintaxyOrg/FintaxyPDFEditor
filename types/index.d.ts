// Starea unui card de PDF din chat, după calea PDF-ului găsit în mesaj.
export type Card = {
  // PDF-ul arătat acum: originalul sau, după salvare, copia _semnat.pdf / _editat.pdf
  current: string
  page: number
  // Mărimea previzualizării (1 = 100%) și pagina din lista de semnături
  zoom: number
  pickPage: number
  // Căutarea din lista de semnături a cardului
  query: string
  // Previzualizarea din chat apare doar după ce omul apasă Preview
  preview: boolean
  mode: 'view' | 'pick' | 'placing'
  note: string
  error: string
  // Fișierul scris la ultima salvare, pentru „Anulează”
  signed: string
}

// Meniul de click dreapta al unei căi (More), așa cum l-a citit shellmenu.exe.
export type MenuItem = {
  depth: number
  kind: 'cmd' | 'sub' | 'sep'
  key: string
  text: string
  icon: string
}

export type Menu = {
  isLoading: boolean
  items: MenuItem[]
  expanded: string[]
  error: string
}

declare module 'claude-code' {
  interface PluginState {
    'pdf-sign': { cards: Record<string, Card>; menus: Record<string, Menu>; tick: number }
  }
}
