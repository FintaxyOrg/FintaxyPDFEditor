// Engleza editorului. Textele rămân scrise în română în cod; tr() le traduce când limba e engleza.
// h() și toast() trec totul prin tr(), deci intră și uneltele, câmpurile și mesajele venite de la server.
// Un text nou în română care nu e aici rămâne în română și în engleză: adaugă-l în EN sau în PATTERNS.
let LANG = 'ro'
export const lang = () => LANG
export function setLang(l) {
  LANG = l === 'en' ? 'en' : 'ro'
  document.documentElement.lang = LANG
}

const EN = {
  // bara de sus și uneltele din stânga (index.html)
  'Arată în Explorer': 'Show in Explorer', 'Copiază calea fișierului': 'Copy file path', 'Deschide alt PDF (Ctrl+O)': 'Open another PDF (Ctrl+O)',
  'Pagina anterioară': 'Previous page', 'Pagina următoare': 'Next page', 'Micșorează': 'Zoom out', 'Potrivește lățimea': 'Fit width',
  'Mărește': 'Zoom in', 'Rotește pagina spre stânga · Shift = toate paginile': 'Rotate page left · Shift = all pages',
  'Rotește pagina spre dreapta · Shift = toate paginile': 'Rotate page right · Shift = all pages', 'Comentariile': 'Comments',
  'Selectează și mută (V)': 'Select and move (V)', 'Semnătură (S)': 'Signature (S)', 'Adaugă text (T)': 'Add text (T)',
  'Editează textul din PDF (E)': 'Edit PDF text (E)', 'Toate uneltele PDF': 'All PDF tools', 'Salvează': 'Save', 'Se salvează…': 'Saving…',

  // editorul
  'Aplicația AI care primește comentariul (rămâne ținută minte)': 'AI app that receives the comment (remembered)',
  'PDF-ul are semnătură digitală: îl poți citi și comenta, dar orice modificare ar strica semnătura.':
    'This PDF has a digital signature: you can read and comment on it, but any change would break the signature.',
  'Trage de semnături și texte ca să le muți · Delete le șterge': 'Drag signatures and text to move them · Delete removes them',
  'Click pe pagină pune semnătura · Ctrl+rotiță sau glisorul = mărimea': 'Click the page to place the signature · Ctrl+wheel or the slider = size',
  'Click pe pagină și scrie · trage de ✥ ca să muți textul': 'Click the page and type · drag ✥ to move the text',
  'Click pe orice rând din PDF și rescrie-l · Enter = gata · Esc = renunți': 'Click any line in the PDF and rewrite it · Enter = done · Esc = cancel',
  'Caută după nume': 'Search by name', 'Nicio semnătură cu numele ăsta.': 'No signature with that name.', 'Biblioteca e goală.': 'The library is empty.',
  'Alege semnătura': 'Choose a signature', 'Recitește folderul Semnaturi': 'Reload the Semnaturi folder', '↻ Actualizează': '↻ Refresh', '+ Nouă': '+ New',
  'PDF-ul are semnătură digitală; nu-l modific.': "The PDF has a digital signature; I won't modify it.",
  'Trimite (Enter)': 'Send (Enter)', 'Trimite la': 'Send to', 'Trimite lui Claude': 'Send to Claude', 'Trimite': 'Send', 'Trimite din nou': 'Send again',
  'Trimis lui Claude: îl găsești în chat.': "Sent to Claude: you'll find it in the chat.", 'Trimis lui Claude.': 'Sent to Claude.',
  'Comentariu salvat.': 'Comment saved.', 'Captura zonei': 'Area capture', 'Șterge': 'Delete',
  'Schimbă semnătura': 'Change signature', 'Mărime': 'Size', 'Mai mic': 'Smaller', 'Mai mare': 'Larger',
  'Negru': 'Black', 'Albastru': 'Blue', 'Roșu': 'Red', 'Anulează': 'Undo',
  'PDF-ul are semnătură digitală; rotirea ar strica-o.': 'The PDF has a digital signature; rotating would break it.',
  'Am anulat ultima salvare.': 'Undid the last save.', 'Închide': 'Close',
  'Nu ai comentarii pe acest PDF. Alege 💬 sau ⬚ din stânga și dă click pe pagină.': 'No comments on this PDF. Pick 💬 or ⬚ on the left and click the page.',
  'Caută o unealtă (ex. comprimă, parolă, word)': 'Search for a tool (e.g. compress, password, word)',
  'Uneltele Stirling se încarcă când deschizi una (pornesc Stirling PDF dacă e nevoie).': 'Stirling tools load when you open one (Stirling PDF starts if needed).',
  'Unelte PDF': 'PDF tools', 'Înapoi la unelte': 'Back to tools', 'Încarc unealta din Stirling PDF…': 'Loading the tool from Stirling PDF…',
  'Unealta nu există în versiunea ta de Stirling PDF.': "This tool doesn't exist in your Stirling PDF version.",
  'Ai modificări nesalvate. Unealta lucrează pe fișierul salvat; apasă întâi Salvează dacă vrei să le includă.':
    'You have unsaved changes. The tool works on the saved file; press Save first if you want them included.',
  'PDF-ul are deja o semnătură digitală.': 'The PDF already has a digital signature.', 'Alte fișiere (după cel deschis)': 'Other files (after the open one)',
  'Semnează': 'Sign', 'Rulează': 'Run', 'Alege fișierul de convertit.': 'Choose the file to convert.',
  'Scrie PIN-ul de semnare în fereastra IDEMIA…': 'Type the signing PIN in the IDEMIA window…', 'Rulez unealta…': 'Running the tool…',
  'câte unul pe rând': 'one per line',
  'Alege certificatul care se termină cu (Semnare), nu (Autentificare). După „Semnează” apare fereastra IDEMIA: scrie acolo PIN-ul de semnare (6 cifre). După semnare fișierul nu mai poate fi modificat.':
    'Choose the certificate ending in (Semnare) – signing – not (Autentificare) – authentication. After “Sign” the IDEMIA window appears: type the signing PIN there (6 digits). Once signed, the file can no longer be modified.',
  'Se încarcă certificatele…': 'Loading certificates…', 'Nu văd niciun certificat: e buletinul în cititor?': "I don't see any certificate: is the ID card in the reader?",
  'Semnătură vizibilă pe pagină': 'Visible signature on the page', 'Pagina ștampilei': 'Stamp page',
  '✓ Gata': '✓ Done', 'Copiază': 'Copy', 'Copiat.': 'Copied.', 'Deschide aici': 'Open here', 'Deschide folderul': 'Open folder', 'Deschide': 'Open',
  'Trage aici poza semnăturii': 'Drop the signature photo here', 'sau ': 'or ', 'alege un fișier': 'choose a file', ', ori lipește cu Ctrl+V': ', or paste with Ctrl+V',
  'Merge și o poză făcută cu telefonul pe hârtie albă: fundalul se scoate singur.': 'A phone photo on white paper works too: the background is removed automatically.',
  'Semnătura cu fundal transparent': 'Signature with transparent background', 'Ca în poză': 'As in the photo',
  'Al cui e semnătura (ex. Ion Popescu)': 'Whose signature it is (e.g. John Smith)', 'Salvează în bibliotecă': 'Save to library',
  'Curățare': 'Cleanup', 'mai curat': 'cleaner', 'păstrează mai mult': 'keep more', 'Culoarea cernelii': 'Ink color', 'Nume': 'Name',
  'Semnătură nouă': 'New signature', 'Renunță': 'Cancel', 'Alege o imagine (PNG, JPG, HEIC salvat ca JPG).': 'Choose an image (PNG, JPG, HEIC saved as JPG).',
  'Scot fundalul…': 'Removing the background…', 'Înlocuiește': 'Replace', ' (cea veche merge în Semnaturi\\_Arhiva)': ' (the old one goes to Semnaturi\\_Arhiva)',
  'Ai modificări nesalvate în PDF-ul ăsta.': 'You have unsaved changes in this PDF.', 'Deschide alt PDF oricum': 'Open another PDF anyway',
  'Alege un fișier PDF.': 'Choose a PDF file.', 'Lipsește fișierul. Deschide editorul din cardul PDF-ului din chat.': 'No file. Open the editor from the PDF card in the chat.',
  'Alege un PDF': 'Choose a PDF', ' sau Ctrl+O': ' or Ctrl+O', 'Scrie aici': 'Type here',

  // aplicațiile AI (desktop.py)
  'aplicația Claude; captura e în clipboard (Ctrl+V)': 'Claude app; the capture is in the clipboard (Ctrl+V)',
  'terminal în folderul PDF-ului; vede PDF-ul și captura': "terminal in the PDF's folder; it sees the PDF and the capture",
  'chatgpt.com; captura e în clipboard (Ctrl+V)': 'chatgpt.com; the capture is in the clipboard (Ctrl+V)',
  'textul e în clipboard: lipește-l cu Ctrl+V': 'the text is in the clipboard: paste it with Ctrl+V',
  'doar copiază textul (și captura), lipești unde vrei': 'only copies the text (and capture); paste it anywhere',
  'Am deschis Claude Code în folderul PDF-ului, cu comentariul ca prim mesaj.': "Opened Claude Code in the PDF's folder with the comment as the first message.",
  'Comentariul și captura sunt în clipboard.': 'The comment and the capture are in the clipboard.', 'Comentariul e în clipboard.': 'The comment is in the clipboard.',

  // mesaje de la server
  'Stirling PDF nu e instalat pe calculator (winget install --id StirlingTools.StirlingPDF -e).': 'Stirling PDF is not installed (winget install --id StirlingTools.StirlingPDF -e).',
  'Am pornit Stirling PDF, dar nu a răspuns în timp util.': 'Stirling PDF was started but did not respond in time.',
  'Nu găsesc scriptul signature_transparent.py din skill-ul semnare-pdf.': "Can't find signature_transparent.py from the semnare-pdf skill.",
  'Nu am găsit cerneală în poză. Mută „Curățare” spre „păstrează mai mult”.': 'No ink found in the photo. Move “Cleanup” towards “keep more”.',
  'Încarcă întâi poza semnăturii.': 'Upload the signature photo first.', 'Scrie numele semnăturii (al cui e).': "Type the signature's name (whose it is).",
  'PDF-ul are deja o semnătură digitală; orice modificare acum o invalidează.': 'The PDF already has a digital signature; any change now would invalidate it.',
  'Nu am ce anula.': 'Nothing to undo.', 'token greșit': 'wrong token',
  'Scrie adresa completă a paginii (cu https://).': 'Type the full page address (with https://).',
  'Unealta e dezactivată în Stirling: îi lipsește un program extern (PDF → CBR cere WinRAR).': 'This tool is disabled in Stirling: an external program is missing (PDF → CBR needs WinRAR).',
  'Edge nu a putut tipări pagina.':'Edge could not print the page.', 'Calibre nu a putut citi cartea.': 'Calibre could not read the book.',

  // grupurile și uneltele (tools.js)
  'Recomandate': 'Recommended', 'Semnare': 'Signing', 'Securitate': 'Security', 'Verificare': 'Inspect', 'Revizuire': 'Review',
  'Pagini și formatare': 'Pages and layout', 'Extragere': 'Extract', 'Eliminare': 'Remove', 'Din PDF în alt format': 'From PDF to another format',
  'Din alt format în PDF': 'From another format to PDF', 'Formulare': 'Forms', 'Avansat': 'Advanced',
  'Editează text': 'Edit text', 'Click pe orice rând din PDF și îl rescrii direct pe pagină.': 'Click any line in the PDF and rewrite it right on the page.',
  'Unește PDF-uri': 'Merge PDFs', 'Lipește alte PDF-uri după cel deschis.': 'Appends other PDFs after the open one.', 'Comprimă': 'Compress',
  'Micșorează fișierul.': 'Makes the file smaller.',
  'Recunoaște textul din scanări, ca să-l poți căuta și copia.': 'Recognizes the text in scans so you can search and copy it.','OCR (text căutabil)': 'OCR (searchable text)', 'Redactează text': 'Redact text',
  'Acoperă definitiv textele date (ex. CNP, IBAN).': 'Permanently covers the given text (e.g. ID numbers, IBAN).',
  'Caută și înlocuiește': 'Find and replace', 'Înlocuiește un text peste tot în document.': 'Replaces a text everywhere in the document.',
  'Semnătură olografă': 'Handwritten signature', 'Pune o semnătură din biblioteca ta pe pagină.': 'Places a signature from your library on the page.',
  'Semnează cu certificat (CEI)': 'Sign with certificate (eID)',
  'Semnătură digitală cu certificatul din Windows (buletinul electronic). PIN-ul îl scrii în fereastra IDEMIA.': 'Digital signature with a Windows certificate (electronic ID card). You type the PIN in the IDEMIA window.',
  'Marcă temporală': 'Timestamp', 'Adaugă o marcă temporală RFC 3161.': 'Adds an RFC 3161 timestamp.', 'Elimină semnătura digitală': 'Remove digital signature',
  'Validează semnătura digitală': 'Validate digital signature', 'Cine a semnat și dacă fișierul e intact.': 'Who signed and whether the file is intact.',
  'Adaugă parolă': 'Add password', 'Schimbă permisiunile': 'Change permissions',
  'Ce poate face cine deschide PDF-ul (tipărire, copiere, editare).': 'What people opening the PDF can do (print, copy, edit).',
  'Elimină parola': 'Remove password', 'Watermark': 'Watermark', 'Ștampilă text / imagine': 'Text / image stamp', 'Curăță (sanitize)': 'Sanitize',
  'Scoate JavaScript, linkuri, fișiere încorporate, metadate.': 'Removes JavaScript, links, embedded files, metadata.', 'Aplatizează': 'Flatten',
  'Formularele și adnotările devin parte din pagină.': 'Forms and annotations become part of the page.', 'Deblochează formularele': 'Unlock forms',
  'Redactează zone sau pagini': 'Redact areas or pages', 'Toate informațiile despre PDF': 'All PDF information', 'Verifică standardele PDF': 'Check PDF standards',
  'Verifică PDF/A': 'Check PDF/A', 'Informații de bază': 'Basic info', 'Proprietățile documentului': 'Document properties', 'Fonturile folosite': 'Fonts used',
  'Criptare și permisiuni': 'Encryption and permissions', 'Dimensiunile paginilor': 'Page dimensions', 'Adnotările din PDF': 'PDF annotations',
  'Schimbă metadatele': 'Change metadata', 'Editează cuprinsul (bookmark-uri)': 'Edit table of contents (bookmarks)', 'Note lipite în PDF': 'Sticky notes in the PDF',
  'Note galbene (sticky notes) scrise chiar în PDF, vizibile oricui.': 'Yellow sticky notes written into the PDF, visible to anyone.',
  'Numere de pagină': 'Page numbers', 'Rotește': 'Rotate', 'Rotire automată': 'Auto-rotate', 'Decupează': 'Crop', 'Reordonează paginile': 'Reorder pages',
  'Împarte după pagini': 'Split by pages', 'Împarte după mărime sau număr': 'Split by size or count', 'Împarte pe capitole': 'Split by chapters',
  'Împarte paginile în bucăți': 'Split pages into sections', 'Împarte automat': 'Auto-split', 'Schimbă mărimea paginilor': 'Resize pages',
  'Mai multe pagini pe o foaie': 'Multiple pages per sheet', 'Broșură': 'Booklet', 'O singură pagină lungă': 'One long page',
  'Împarte pentru tipar poster': 'Split for poster printing', 'Suprapune PDF-uri': 'Overlay PDFs', 'Extrage imaginile': 'Extract images',
  'Extrage scanările': 'Extract scans', 'Extrage atașamentele': 'Extract attachments', 'Listează atașamentele': 'List attachments',
  'Extrage bookmark-urile': 'Extract bookmarks', 'Arată JavaScript-ul din PDF': 'Show the PDF JavaScript', 'Titlu din antet': 'Title from header',
  'Șterge pagini': 'Delete pages', 'Șterge paginile goale': 'Delete blank pages', 'Elimină imaginile': 'Remove images', 'Șterge un atașament': 'Delete an attachment',
  'PDF → Imagini': 'PDF → Images', 'PDF → CSV (tabele)': 'PDF → CSV (tables)', 'PDF → PDF/A (arhivare)': 'PDF → PDF/A (archiving)',
  'Word, Excel, orice fișier → PDF': 'Word, Excel, any file → PDF', 'Imagini → PDF': 'Images → PDF', 'Pagină web (URL) → PDF': 'Web page (URL) → PDF',
  'Vezi câmpurile': 'View fields', 'Completează câmpurile': 'Fill fields', 'Câmpurile în CSV': 'Fields to CSV', 'Câmpurile în Excel': 'Fields to Excel',
  'Adaugă câmpuri': 'Add fields', 'Șterge câmpuri': 'Delete fields', 'Repară PDF': 'Repair PDF', 'Inversează culorile': 'Invert colors',
  'Efect de scanare': 'Scanner effect', 'Adaugă o imagine': 'Add an image', 'Adaugă atașamente': 'Add attachments', 'Decomprimă': 'Decompress',
  'Portofoliu PDF': 'PDF portfolio',

  // câmpurile formularelor (FIELD_LABELS)
  'Pagini (ex. 1,3,5-9 sau all)': 'Pages (e.g. 1,3,5-9 or all)', 'Pagina': 'Page', 'Unghi': 'Angle', 'Parolă': 'Password',
  'Parola proprietarului': 'Owner password', 'Lungimea cheii': 'Key length', 'Tip': 'Type', 'Alfabet': 'Alphabet', 'Mărime font': 'Font size',
  'Rotire': 'Rotation', 'Opacitate (0-1)': 'Opacity (0-1)', 'Spațiu orizontal': 'Horizontal spacing', 'Spațiu vertical': 'Vertical spacing',
  'Culoare': 'Color', 'Transformă paginile în imagini': 'Convert pages to images', 'Nivel de comprimare': 'Compression level',
  'Mărimea dorită (ex. 2MB)': 'Target size (e.g. 2MB)', 'Alb-negru': 'Grayscale', 'Limbi': 'Languages', 'Tip OCR': 'OCR type', 'Randare': 'Rendering',
  'Format imagine': 'Image format', 'O imagine sau mai multe': 'Single or multiple images', 'Culori': 'Colors', 'Mod': 'Mode',
  'Ordinea paginilor': 'Page order', 'Titlu': 'Title', 'Autor': 'Author', 'Subiect': 'Subject', 'Cuvinte cheie': 'Keywords', 'Producător': 'Producer',
  'Data creării': 'Creation date', 'Data modificării': 'Modification date', 'Șterge toate metadatele': 'Delete all metadata', 'Poziție': 'Position',
  'Tip ștampilă': 'Stamp type', 'Margine': 'Margin', 'Primul număr': 'Starting number', 'Pagini de numerotat': 'Pages to number',
  'Text (ex. Pagina {n} din {total})': 'Text (e.g. Page {n} of {total})', 'Texte de acoperit (câte unul pe rând)': 'Texts to cover (one per line)',
  'Expresii regulate': 'Regular expressions', 'Doar cuvinte întregi': 'Whole words only', 'Tăieturi orizontale': 'Horizontal cuts',
  'Tăieturi verticale': 'Vertical cuts', 'Unește la loc într-un PDF': 'Merge back into one PDF', 'Cum împart': 'How to split', 'Valoare': 'Value',
  'Ordinea fișierelor': 'File order', 'Elimină semnăturile digitale': 'Remove digital signatures', 'Pagini pe foaie': 'Pages per sheet',
  'Chenar': 'Border', 'Factor': 'Factor', 'Mărimea paginii': 'Page size', 'Fișiere': 'Files', 'Adresa paginii': 'Page address', 'Motiv': 'Reason',
  'Locul': 'Location', 'Certificat': 'Certificate', 'Caută': 'Find', 'Înlocuiește cu': 'Replace with', 'Lățime (pt)': 'Width (pt)',
  'Înălțime (pt)': 'Height (pt)', 'PDF-uri de suprapus': 'PDFs to overlay', 'Imagine': 'Image', 'Fișiere de atașat': 'Files to attach',
  'Cum încape imaginea': 'Image fit', 'Include atașamentele': 'Include attachments', 'Scoate JavaScript': 'Remove JavaScript',
  'Scoate fișierele încorporate': 'Remove embedded files', 'Scoate metadatele XMP': 'Remove XMP metadata',
  'Scoate informațiile documentului': 'Remove document info', 'Scoate linkurile': 'Remove links', 'Scoate fonturile': 'Remove fonts',
  'Doar formularele': 'Forms only', 'Interzice asamblarea': 'Prevent assembly', 'Interzice copierea': 'Prevent copying',
  'Interzice extragerea pentru accesibilitate': 'Prevent extraction for accessibility', 'Interzice completarea': 'Prevent form filling',
  'Interzice modificarea': 'Prevent modifying', 'Interzice adnotările': 'Prevent annotations', 'Interzice tipărirea': 'Prevent printing',
  'Interzice tipărirea fidelă': 'Prevent faithful printing', 'Convertește în PDF/A': 'Convert to PDF/A', 'Prag': 'Threshold',
  'Procent alb': 'White percentage', 'Nume fișier': 'File name',
  // semnătura electronică, semnarea în bloc, formulare, atașamente
  'Semnătură electronică': 'Electronic signature', 'Semnătură electronică (certificat)': 'Electronic signature (certificate)',
  'Semnătură digitală cu certificat: buletin electronic, token, FintaxySign': 'Digital signature with a certificate: eID card, token, FintaxySign',
  'Semnătură digitală calificată cu certificatul din Windows: buletinul electronic, un token sau stick-ul din birou (FintaxySign).':
    'Qualified digital signature with a Windows certificate: the eID card, a token or the office stick (FintaxySign).',
  'Semnătură digitală calificată cu un certificat din Windows: buletinul electronic, un token sau stick-ul din birou (FintaxySign). Windows îți cere PIN-ul.':
    'Qualified digital signature with a Windows certificate: the eID card, a token or the office stick (FintaxySign). Windows asks for your PIN.',
  'Semnează mai multe PDF-uri': 'Sign several PDFs', 'Semnătură electronică pe mai multe PDF-uri deodată, cu un singur PIN.': 'Electronic signature on several PDFs at once, with a single PIN.',
  'Semnătură electronică pe mai multe PDF-uri deodată, cu un singur PIN. Fiecare PDF e semnat în câmpul lui de semnătură gol (declarațiile ANAF, formularele) sau, dacă nu are, invizibil. Lângă fiecare apare <nume>_semnat.pdf.':
    'Electronic signature on several PDFs at once, with a single PIN. Each PDF is signed in its empty signature field (ANAF returns, forms) or, if it has none, invisibly. A <name>_semnat.pdf appears next to each.',
  'Certificat': 'Certificate', '↻ Reîncarcă': '↻ Reload', 'Se încarcă certificatele…': 'Loading certificates…',
  'Niciun certificat de semnare în Windows': 'No signing certificate in Windows',
  'Buletinul electronic: e în cititor? Stick-ul din birou: pornește FintaxySign și verifică să scrie „connected” și „Driver installed”, apoi apasă Reîncarcă.':
    'eID card: is it in the reader? Office stick: start FintaxySign and check it says “connected” and “Driver installed”, then press Reload.',
  'Unde apare semnătura': 'Where the signature appears', 'Aleg locul pe pagină (trag un dreptunghi)': 'I choose the spot on the page (drag a rectangle)',
  'Invizibilă (se vede în panoul de semnături)': 'Invisible (shown in the signatures panel)', 'Alege alt loc': 'Choose another spot',
  'Trage un dreptunghi pe pagină unde vrei semnătura.': 'Drag a rectangle on the page where you want the signature.',
  'Trage un dreptunghi unde vrei semnătura electronică · Esc = renunți': 'Drag a rectangle where you want the electronic signature · Esc = cancel',
  'Motiv (opțional)': 'Reason (optional)', 'Locul (opțional)': 'Location (optional)', 'ex. București': 'e.g. Bucharest', 'Semnează': 'Sign',
  'Alege certificatul.': 'Choose the certificate.', 'Semnarea nu a reușit.': 'Signing failed.',
  'Ai modificări nesalvate. Semnătura se pune pe fișierul salvat: apasă întâi Salvează.': 'You have unsaved changes. The signature goes on the saved file: press Save first.',
  'PDF-ul are deja o semnătură; a ta se adaugă după ea, fără s-o strice.': 'The PDF is already signed; yours is added after it, without breaking it.',
  'Scrie PIN-ul în fereastra Windows… Cu stick-ul din birou (FintaxySign), dacă e la un coleg, aștepți câteva secunde rândul.':
    'Type the PIN in the Windows window… With the office stick (FintaxySign), if a colleague has it, you wait a few seconds for your turn.',
  '+ Adaugă PDF-uri…': '+ Add PDFs…', 'Fișiere': 'Files', 'Scoate': 'Remove', 'Adaugă PDF-urile de semnat.': 'Add the PDFs to sign.', 'Semnează toate': 'Sign all',
  'Cu stick-ul din birou (FintaxySign): apasă întâi „Reserve 2 min” în FintaxySign, ca să nu-l ia un coleg între fișiere (altfel PIN-ul se cere din nou).':
    'With the office stick (FintaxySign): first press “Reserve 2 min” in FintaxySign, so a colleague does not take it between files (otherwise the PIN is asked again).',
  'Formular inteligent (XFA)': 'Smart form (XFA)',
  'ca declarațiile ANAF. Îl poți citi și semna electronic aici; datele se completează în programul ANAF sau în Adobe Reader.':
    'like ANAF tax returns. You can read and e-sign it here; the data is filled in the ANAF program or in Adobe Reader.',
  'completează-le direct pe pagină, apoi Salvează.': 'fill them in right on the page, then Save.', 'Atașat:': 'Attached:',
  'Deschide': 'Open', 'Arată în folder': 'Show in folder', 'Câmp de semnătură gol': 'Empty signature field', 'Semnează electronic': 'Sign electronically',
  'Folder': 'Folder',
}

// Texte cu valori în ele: [tipar, înlocuire]. Tiparele sunt cât mai precise, ca să nu prindă textul scris de om.
const PATTERNS = [
  [/^Click pe pagină unde vrei să-i spui ceva lui (.+)$/, 'Click the page where you want to tell $1 something'],
  [/^Trage un dreptunghi peste zona pe care vrei s-o trimiți lui (.+)$/, 'Drag a rectangle over the area you want to send to $1'],
  [/^Comentariu pentru (.+) \(C\)$/, 'Comment for $1 (C)'],
  [/^Captură zonă pentru (.+) \(R\)$/, 'Area capture for $1 (R)'],
  [/^Ce vrei să facă (.+) cu zona asta\?$/, 'What should $1 do with this area?'],
  [/^Ce vrei să-i spui lui (.+) aici\?$/, 'What do you want to tell $1 here?'],
  [/^Lista e la zi: (\d+) semnături\.$/, 'The list is up to date: $1 signatures.'],
  [/^Salvează \((\d+)\)$/, 'Save ($1)'],
  [/^Nu am putut citi textul paginii (\d+): /, "Couldn't read the text of page $1: "],
  [/^Pagina (\d+)( › zonă selectată)?( › „.*”)?( · trimis)?$/s, (m, n, zone, ctx, sent) => `Page ${n}${zone ? ' › selected area' : ''}${ctx || ''}${sent ? ' · sent' : ''}`],
  [/^Trimis la (.+) · /, 'Sent to $1 · '],
  [/^Trimis lui Claude · /, 'Sent to Claude · '],
  [/^Doar notă · /, 'Note only · '],
  [/^Rotit și salvat: /, 'Rotated and saved: '],
  [/^Salvat: /, 'Saved: '],
  [/^Comentarii \((\d+)\)$/, 'Comments ($1)'],
  [/^Toate uneltele Stirling ?/, 'All Stirling tools '],
  [/^Stirling PDF nu răspunde: /, 'Stirling PDF is not responding: '],
  [/^(.*) · până la (\d{4}-\d\d-\d\d)( · EXPIRAT)?$/, (m, a, d, exp) => `${a} · valid until ${d}${exp ? ' · EXPIRED' : ''}`],
  [/^Eroare: /, 'Error: '],
  [/^✓ Gata: /, '✓ Done: '],
  [/^Am adăugat „(.+)” în bibliotecă\.$/, 'Added “$1” to the library.'],
  [/^Există deja o semnătură „(.+)”\.$/, 'A signature “$1” already exists.'],
  [/^Calea e copiată: /, 'Path copied: '],
  [/^Nu am putut copia calea: /, "Couldn't copy the path: "],
  [/^Nu am putut deschide PDF-ul: /, "Couldn't open the PDF: "],
  [/^Nu am putut trimite: /, "Couldn't send: "],
  [/^Unealta (.+) nu există în Stirling\.$/, 'The tool $1 does not exist in Stirling.'],
  [/^Stirling a răspuns (\d+): /, 'Stirling responded $1: '],
  [/^Stirling a răspuns (\d+) la pagina (\d+): /, 'Stirling responded $1 on page $2: '],
  [/^Semnătura nu mai e în bibliotecă: /, 'The signature is no longer in the library: '],
  [/^Am deschis (.+) cu comentariul\.( Captura e în clipboard: lipește-o cu Ctrl\+V\.)?$/,
    (m, app, cap) => `Opened ${app} with the comment.${cap ? ' The capture is in the clipboard: paste it with Ctrl+V.' : ''}`],
  [/^În câmpul de semnătură de pe pagina (\d+)$/, 'In the signature field on page $1'],
  [/^Pe pagina (\d+)\.$/, 'On page $1.'],
  [/^pe pagina (\d+)\.$/, 'on page $1.'],
  [/^Formular cu (\d+) câmpuri$/, 'Form with $1 fields'],
  [/^Semnat electronic: /, 'Signed electronically: '],
  [/^(\d+) din (\d+) semnate/, '$1 of $2 signed'],
  [/^Nu am putut citi câmpurile de pe pagina (\d+): /, "Couldn't read the fields on page $1: "],
  [/^Am deschis Gemini; comentariul e în clipboard: lipește-l cu Ctrl\+V\.( Captura: )?/,
    (m, cap) => `Opened Gemini; the comment is in the clipboard: paste it with Ctrl+V.${cap ? ' Capture: ' : ''}`],
]

export function tr(s) {
  if (LANG === 'ro' || typeof s !== 'string' || !s.trim()) return s
  const hit = EN[s]
  if (hit != null) return hit
  if (s.endsWith(' *') && EN[s.slice(0, -2)]) return `${EN[s.slice(0, -2)]} *`
  for (const [re, rep] of PATTERNS) if (re.test(s)) return s.replace(re, rep)
  return s
}
