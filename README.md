# PDF Sign (Fintaxy)

Aplicație Windows pentru semnat și editat PDF-uri:

- **semnătură olografă**: imagine transparentă pusă cu mouse-ul;
- **semnătură electronică (calificată)** cu certificatul din Windows: buletinul electronic, un token sau stick-ul din birou prin **FintaxySign**; și **mai multe PDF-uri deodată**, cu un singur PIN;
- **formulare**: completezi câmpurile direct pe pagină;
- **PDF-uri ANAF** (formulare XFA cu XML atașat): le citești, deschizi XML-ul și le semnezi în câmpul „Semnătura”; și formularele „inteligente” nesalvate din Adobe (D300, D394, D101…), care în alte programe arată doar „Please wait…”;
- **organizarea paginilor**: miniaturi pe care le tragi în altă ordine, le ștergi sau le rotești (tasta **P**);
- **unelte PDF direct în aplicație**: unire, împărțire, extragere și ștergere de pagini, comprimare, PDF → Word / Excel / imagini / text, imagini → PDF, Word / Excel → PDF (cu Microsoft Office), parolă, watermark, numere de pagină, aplatizare, validarea semnăturii, reparare;
- **validare și semnare declarații**: XML-ul unei declarații (D100, D112, D300, D390, D394…) e verificat cu validatorul oficial al ANAF, adus și ținut la zi de aplicație; se face PDF-ul și îl semnezi cu certificatul din Windows;
- **căutare globală Ctrl+K**: orice unealtă sau acțiune, scrisă cu sau fără diacritice;
- **printare** (butonul cu imprimanta sau **Ctrl+P**): doar paginile documentului, câte una pe foaie, întregi pe hârtia aleasă, cu semnăturile puse și nesalvate încă, fără bara editorului și fără data sau adresa browserului;
- **OCR** (text căutabil peste scanări, română + engleză), **redactare** (textul e scos din PDF) și **caută și înlocuiește**, toate fără nimic instalat;
- **chat cu Claude în editor** (butonul cu steluțe din stânga sau tasta **A**): Claude vede PDF-ul deschis și pagina pe care ești; orice scriere de fișiere îți cere acordul. Merge prin ACP (Agent Client Protocol), ca „Ask AI” din Fintaxy CRM, pe abonamentul tău Claude;
- text nou sau corectat, comentarii pentru Claude și, dacă e instalat Stirling PDF, încă ~50 de unelte rare.

## Pentru contabili: instalare

1. Descarcă **PDF-Sign-Setup.exe** (din [Releases](https://github.com/FintaxyOrg/FintaxyPDFEditor/releases/latest) sau de la linkul primit) și dă dublu clic pe el.
   Dacă Windows arată „Windows protected your PC”: **More info → Run anyway** (aplicația nu e semnată digital de un furnizor).
2. Gata: se instalează singur (fără drepturi de administrator, fără terminal) și pornește. Ai **PDF Sign** pe Desktop și în Start, iar pe orice PDF ai **Deschide cu → PDF Sign** și, la clic dreapta, „Semnează cu Fintaxy PDF Sign”.

La prima pornire apare un **ghid scurt** (se poate sări; se redeschide din Ctrl+K → „Ghid de pornire”): semnătura ta, semnătura electronică, Claude, programele în plus.

Nu trebuie Python sau altceva instalat. Fereastra editorului se deschide în Microsoft Edge (vine cu Windows). Varianta veche rămâne: **PDF-Sign-win64.zip** + `Instalare.cmd`. Pentru IT: `PDF-Sign-Setup.exe /silent`.

### Semnăturile

- Stau în **Documente\Semnaturi PDF Sign**, câte un PNG transparent pe persoană (`Semnatura Ion Popescu.png`, numele de după „Semnatura” apare în listă).
- Semnătură nouă: în editor **Semnătură → + Nouă**, încarci o poză sau un scan cu semnătura pe hârtie albă, aplicația scoate fundalul și o salvează în folder.
- Butonul **Folder** din lista de semnături deschide folderul.

### Ce scrie aplicația

- PDF-ul original rămâne neatins: salvarea face `<nume>_semnat.pdf` (sau `_editat.pdf`) lângă el.
- Un PDF care are deja semnătură digitală nu se modifică (s-ar invalida semnătura).

### Semnătura electronică (certificat)

1. Certificatul trebuie să fie în Windows:
   - **buletinul electronic** sau un **token**: în cititor, cu driverul lui instalat;
   - **stick-ul din birou**: pornește **FintaxySign** și verifică să scrie „connected” și „Driver installed”.
2. În editor apasă **Semnătură electronică** (sus, dreapta), alege certificatul și locul semnăturii. Lista spune de unde vine fiecare certificat (**Buletin electronic**, **Stick birou (FintaxySign)**, **Token / card**), ce PIN cere și, dedesubt, dacă FintaxySign e pornit și are stick-ul conectat:
   - în câmpul de semnătură al documentului (declarațiile ANAF, formularele);
   - într-un dreptunghi tras pe pagină;
   - invizibilă.
3. **Semnează**: Windows cere PIN-ul în fereastra lui („Windows Security”), care apare peste editor; editorul îți spune în ce fază e (se deschide cheia, așteaptă PIN-ul, semnează) și are **Anulează**. Rezultatul e `<nume>_semnat.pdf`, lângă original.

**PIN-ul buletinului**: pentru semnat e PIN-ul de **semnare (6 cifre)**, nu cel de 4 cifre. După **3 PIN-uri greșite** buletinul se blochează (se deblochează cu PUK). La PIN greșit aplicația se oprește și nu mai încearcă singură.

**Mai multe PDF-uri deodată**: Unelte → **Semnează mai multe PDF-uri**, adaugi fișierele, un singur PIN. Cu stick-ul din birou, apasă întâi „Reserve 2 min” în FintaxySign, ca să nu-l ia un coleg între fișiere.

Un PDF deja semnat (de exemplu o declarație semnată de alt administrator) primește semnătura ta după cea existentă, fără s-o strice.

### Formulare și PDF-uri ANAF

- **Formular cu câmpuri**: câmpurile apar evidențiate pe pagină; le completezi și apeși **Salvează** (`<nume>_editat.pdf`).
- **Declarații ANAF** (D100, D112, D300 etc., formulare XFA): se văd ca în Adobe; deasupra apare XML-ul atașat, cu **Deschide** și **Arată în folder** (se salvează în `<nume> - atasamente`). Datele se completează în programul ANAF (Soft J / DUKIntegrator) sau în Adobe Reader; aici le citești și le semnezi.
- **Formulare „inteligente” dinamice** (cele care în alte programe arată doar „Please wait…”): fișierul conține doar acea pagină, iar formularul adevărat e desenat de aplicație (pdf.js + Edge, câteva secunde la prima deschidere), ca în Adobe: numerele cu separatorii românești (27.525,55), CIF-ul pe căsuțe, bifele pătrate cu X, tabelele cu toate coloanele, sigla ANAF, caseta „Semnătura”, câmpurile completabile pe fundalul albastru deschis al Adobe, cu chenar roșu la cele obligatorii. Dacă pe calculator e Acrobat sau Adobe Reader, se folosesc și fonturile lui (Myriad Pro, Minion Pro); altfel un font asemănător. Le citești, le printezi și le semnezi electronic: semnătura se pune în caseta „Semnătura” a formularului, ca în Acrobat (câmpul cu numele pe care îl dă și Acrobat, aspectul „Digitally signed by … / Date”), pe fișierul original; un formular fără casetă se semnează invizibil. Nu se pot edita aici.

### Validare și semnare declarații

Unelte → **Validare și semnare declarații** (sau butonul **Validează** de lângă XML-ul atașat unui PDF ANAF).

1. Alegi XML-ul declarației, exportat din programul de contabilitate, sau PDF-ul ANAF care îl are atașat. Tipul (D300, D112…) e recunoscut din fișier.
2. **Validează**: fișierul e verificat cu validatorul oficial al ANAF (cel din DUKIntegrator, „soft J”). Erorile apar cu explicația lor și cu mesajul ANAF dedesubt.
3. Dacă nu are erori, lângă XML apare PDF-ul declarației (cu XML-ul atașat), iar dedesubt alegi certificatul și apeși **Semnează**: rezultatul e `<nume>_semnat.pdf`, pe care îl depui în SPV.

**D300 scos din SAGA Web** (formular inteligent „FORMULAR NEVALIDAT”, fără XML): deschis în PDF Sign, bara de sus arată **Validează formularul**. Aplicația face ce face butonul cu același nume din Adobe: scrie XML-ul din formular (după scriptul formularului), îl verifică cu validatorul ANAF și, dacă trece, face `<nume>_validat.pdf` — formularul colorat, validat, cu `D300.xml` atașat — pe care îl semnezi în caseta „Semnatura”. Dacă validatorul găsește erori (de exemplu adresa sau CAEN-ul firmei goale în programul de contabilitate), nu se face nimic: corectezi acolo și generezi din nou declarația.

Validatoarele nu sunt în kit: aplicația le ia singură de pe site-ul ANAF (`static.anaf.ro`), în folderul ei, doar pentru declarațiile pe care le folosești, și verifică o dată pe zi dacă ANAF a publicat o versiune nouă. Java, de care au nevoie, e cel adus cu Stirling PDF (sau, dacă lipsește, unul mic adus atunci). Fără internet merg validatoarele deja aduse.

După semnare, validatorul ANAF verifică și PDF-ul semnat. La certificatele cu cheie RSA (tokenurile calificate obișnuite) confirmă semnătura; la buletinul electronic (cheie ECDSA) nu o poate verifica, fiindcă programul ANAF e vechi. În ambele cazuri, dacă serverul ANAF primește declarația se vede abia la depunere, din recipisă.

### Unelte PDF

Butonul cu pătrățele din stânga (sau **Ctrl+K**) arată toate uneltele. Cele obișnuite merg direct, fără nimic instalat; rezultatul apare lângă PDF, cu un sufix (`_unit`, `_comprimat`, `_word.docx` etc.). Word / Excel → PDF are nevoie de Microsoft Office.

Word / Excel → PDF merge cu Microsoft Office sau, fără el, cu **LibreOffice** (pornit fără nicio fereastră). Uneltele marcate **Stirling** sunt conversii și verificări rare.

### Componente

LibreOffice, Stirling PDF, Node.js și legătura cu Claude **fac parte din PDF Sign**: nu instalezi nimic. La prima pornire aplicația le aduce singură, în fundal, de la sursa lor oficială, în folderul ei (`%LOCALAPPDATA%\fintaxy-pdf-sign\components`), fără drepturi de administrator și fără terminal (~750 MB de descărcat, ~2 GB pe disc; poți lucra între timp). Ce e deja instalat pe calculator e folosit de acolo și nu se mai descarcă. Starea lor: **Ctrl+K → „Componente”**; un buton „Reîncearcă” apare doar dacă ceva n-a reușit (de exemplu fără internet).

De ce nu sunt în kit: Claude Code nu poate fi redistribuit de noi, iar pentru celelalte rămânem curați cu licențele; kitul rămâne de ~105 MB în loc de peste 1 GB.

### Claude în editor

Făcut după „Ask AI” din Fintaxy CRM, prin ACP (Agent Client Protocol), pe abonamentul tău Claude.

- Butonul cu semnul Claude din stânga (tasta **A** sau **Ctrl+J**) deschide chatul. Singurul lucru pe care îl faci tu, o dată: **Conectează** (o fereastră în care scrii `/login`).
- Claude vede PDF-ul deschis și pagina pe care ești. Fiecare unealtă folosită apare ca un rând („Citește contract.pdf”, „Rulează o comandă: …”).
- **Manual / Auto** (în compozitor): în Manual, orice schimbare îți cere acordul într-un card cu detaliul acțiunii (**Permite**, **Mereu în acest chat**, **Refuză**; o cerere fără răspuns e refuzată după 3 minute). În Auto, Claude decide singur la acțiunile de rutină.
- Sub ultimul răspuns: **sugestii de continuare**, copiere și, după o eroare sau o oprire, **Reîncearcă**. Conversația fiecărui PDF se păstrează între porniri.
- **Conexiuni** (iconița cu ștecher): servere MCP prin care Claude ajunge la alte sisteme. Pentru Fintaxy CRM: în CRM, Setări → Conectare Claude, copiezi adresa și jetonul.
- Comentariile (tasta **C**) și capturile de zonă (**R**) merg la **Claude · panou** sau la **Claude Desktop** (două butoane în fereastra comentariului); celelalte aplicații sunt la „Altele”.

### Scurtături

| Tastă | Ce face |
|---|---|
| Ctrl+K | caută orice unealtă |
| P | organizează paginile |
| S / T / E | semnătură olografă / text / editează textul |
| A / Ctrl+J | chatul cu Claude |
| C / R | comentariu / captură de zonă pentru Claude |
| Ctrl+S / Ctrl+O | salvează / deschide alt PDF |
| Ctrl+P | printează documentul |

### Actualizare și dezinstalare

- Actualizare: descarci **PDF-Sign-Setup.exe** nou și îl rulezi. Semnăturile și setările rămân.
- Dezinstalare: **Setări → Aplicații → PDF Sign (Fintaxy) → Dezinstalare**, sau **Dezinstalare.cmd** din zip.

## Pentru cine modifică aplicația

### Structura

| Folder | Ce e |
|---|---|
| `bin/` | aplicația, în Python: `desktop.py` (pornirea, ferestrele, AI), `editor_server.py` (serverul local al editorului, Stirling), `fx_sign.py` (scrierea în PDF cu PyMuPDF, formulare), `certsign.py` (semnătura electronică: pyHanko + cheia din Windows prin PowerShell), `winenv.py` (ce află de la Windows: fereastra de PIN, cititoare, FintaxySign, unde stă cheia fiecărui certificat), `localtools.py` (uneltele PDF fără Stirling, OCR, redactare), `xfaview.py` (formularele XFA dinamice: PDF de vizualizare făcut cu pdf.js din `editor/xfa` și tipărit cu Edge), `deps.py` (programele în plus și instalarea lor), `anaf.py` (validare și semnare declarații: validatoarele ANAF aduse din `versiuni.xml`, rulate cu Java în linie de comandă), `acp_chat.py` (chatul cu Claude prin ACP), `signature_transparent.py` (fundal transparent la semnături) |
| `editor/` | interfața (HTML, CSS, JS), servită de `editor_server.py` pe 127.0.0.1 cu token; `assist.js` = chatul, programele în plus, ghidul de pornire |
| `app/` | `build.ps1` (versiunea portabilă + `PDF-Sign-Setup.exe`), `Setup.cs` (fișierul unic de instalare), `install.ps1` + `Instalare.cmd` / `Dezinstalare.cmd`, iconița, `tessdata/` (limbile OCR) |
| `tools/patch_pdfjs_xfa.py` | face `editor/xfa` din pdfjs-dist 4.10.38, cu corecturile pentru formularele ANAF (coloane de tabel cu lățime 0, numere după limbă, căsuțe comb, bife, semnătură, sigla BMP, marginile câmpurilor); fiecare corectură e comentată acolo |
| `tests/` | testele aplicației (vezi mai jos) |
| `hooks/`, `types/`, `.claude-plugin/` | mod-ul pentru Claude Code (cardul de sub PDF-uri din chat); nu e necesar pentru aplicație. `.claude-plugin/marketplace.json` face din repo un marketplace |
| `.github/workflows/release.yml` | construiește zip-ul și îl pune la Releases la fiecare tag `v*` |

### Rulare din cod

Python 3.12 pe Windows:

```powershell
pip install -r requirements.txt
pythonw bin\desktop.py              # alegi un PDF
pythonw bin\desktop.py "C:\cale\document.pdf"
```

Opțional, `powershell -ExecutionPolicy Bypass -File app\install.ps1` pune scurtăturile și meniul PDF care pornesc codul din folderul ăsta.

Jurnale și setări: `%LOCALAPPDATA%\fintaxy-pdf-sign` (`app-log.txt`, `settings.json`). În `settings.json`, `"library"` schimbă folderul cu semnături.

### Teste

Toate rulează cu Python-ul din `.venv-build`, pe documente făcute pe loc, într-un folder de stare separat (`FX_STATE`): nu ating setările, semnăturile sau certificatele din Windows.

```powershell
.venv-build\Scripts\python.exe tests\test_sign.py                 # semnătura electronică cap-coadă (RSA și P-384, din .pfx de test)
.venv-build\Scripts\python.exe tests\test_chat.py                 # chatul prin ACP, cu un agent simulat
.venv-build\Scripts\python.exe tests\test_xfa.py                  # formularele XFA dinamice (ANAF): desenare, editor, semnare
.venv-build\Scripts\python.exe tests\test_anaf.py C:\tmp\a          # validare și semnare declarații, cu un „site ANAF” și un validator simulate
.venv-build\Scripts\python.exe tests\test_anaf.py C:\tmp\a --live   # la fel, cu validatoarele adevărate de la ANAF (--clean: își aduce și Java)
.venv-build\Scripts\python.exe tests\dev_server.py C:\tmp\t 8765   # serverul de test (lasă-l pornit), apoi:
.venv-build\Scripts\python.exe tests\test_tools.py C:\tmp\t 8765   # editorul + toate uneltele locale + toate uneltele Stirling
.venv-build\Scripts\python.exe tests\test_chat_live.py            # chatul pe viu (folosește abonamentul Claude al calculatorului)
.venv-build\Scripts\python.exe tests\test_components.py C:\tmp\c  # componentele aduse ca pe un calculator curat (~750 MB, ~8 min)
.venv-build\Scripts\python.exe tests\test_packaged.py             # aplicația construită (dist\PDF Sign), cap-coadă
```

`tests\ui_audit.js` se lipește în consola editorului (sau se rulează cu un instrument de automatizare): deschide fiecare panou și fiecare formular de unealtă și caută elemente ieșite din panou, text tăiat, panouri care nu se derulează și texte netraduse.

Ce nu pot verifica testele: PIN-ul adevărat al unui card (îl scrie doar omul, în fereastra Windows), instalarea pe un calculator curat și primirea unei declarații de către serverul ANAF (se vede doar la o depunere adevărată în SPV).

### Mod-ul pentru Claude Code

Sub fiecare PDF pomenit în chat apar Preview / Deschide / Semnează, iar editorul se deschide în panoul lui Claude. Are nevoie de Python cu pachetele de mai sus (`pip install -r requirements.txt`). Se instalează din Claude Code:

```
/plugin install pdf-sign --marketplace FintaxyOrg/FintaxyPDFEditor
```

Sau din terminal: `claude plugin marketplace add FintaxyOrg/FintaxyPDFEditor`, apoi `claude plugin install pdf-sign@fintaxy-pdf-sign`. Teste: `claude plugin test .`

### Versiune nouă

1. Faci modificările și le testezi din cod.
2. Crești `version` în `.claude-plugin/plugin.json`.
3. Commit, apoi tag și push:

```powershell
git tag v0.12.1
git push origin master --tags
```

Build local: `powershell -ExecutionPolicy Bypass -File app\build.ps1` → `dist\PDF-Sign-win64.zip` și `dist\PDF-Sign-Setup.exe` (~5 minute), apoi `gh release create vX.Y.Z dist\PDF-Sign-Setup.exe dist\PDF-Sign-win64.zip`. (GitHub Actions dă `startup_failure` din noiembrie 2026; până e reparat, release-ul se face local.)

## Licență

PDF Sign e software liber, sub **GNU Affero General Public License v3.0** (fișierul `LICENSE`). Copyright © 2026 Fintaxy.

Poți folosi, modifica și da mai departe aplicația, cu condiția să dai mai departe și codul sursă al variantei tale, sub aceeași licență. Kitul de instalare e construit din acest depozit (`app\build.ps1`).

Licența e AGPL fiindcă aplicația scrie în PDF cu PyMuPDF (MuPDF), care e AGPL-3.0. Pachetele puse în kit, fiecare sub licența ei:

| Pachet | Licență |
|---|---|
| PyMuPDF (MuPDF) | AGPL-3.0 |
| pyHanko, pyhanko-certvalidator, asn1crypto, oscrypto, uritools, tzlocal | MIT |
| pdf2docx, python-docx, openpyxl, et_xmlfile, fonttools, PyYAML, termcolor | MIT |
| urllib3, charset-normalizer, cffi (MIT-0) | MIT |
| Pillow | MIT-CMU |
| NumPy, lxml, idna, pycparser | BSD-3-Clause |
| OpenCV (opencv-python-headless), requests, fire, tzdata | Apache-2.0 |
| cryptography | Apache-2.0 sau BSD-3-Clause |
| certifi | MPL-2.0 |
| typing_extensions, Python | PSF-2.0 |
| PyInstaller (programul de pornire din kit) | GPL-2.0 cu excepție pentru aplicațiile împachetate |
| Tesseract tessdata (`ron`, `eng`) | Apache-2.0 |
| iconițe Fluent UI | MIT |
| pdf.js (`editor/xfa`, desenarea formularelor XFA; `pdf.worker.mjs` are corecturile din `tools/patch_pdfjs_xfa.py`) | Apache-2.0 |
| fonturile standard pdf.js (`editor/xfa/standard_fonts`: Foxit, Liberation) | BSD (Foxit), SIL OFL 1.1 (Liberation); licențele sunt în folder |

LibreOffice, Stirling PDF, Node.js și adaptorul Claude nu sunt în kit: aplicația le descarcă de la sursa lor oficială, fiecare sub licența ei.
