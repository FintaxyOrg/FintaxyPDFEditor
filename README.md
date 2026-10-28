# PDF Sign (Fintaxy)

Aplicație Windows pentru semnat și editat PDF-uri:

- **semnătură olografă**: imagine transparentă pusă cu mouse-ul;
- **semnătură electronică (calificată)** cu certificatul din Windows: buletinul electronic, un token sau stick-ul din birou prin **FintaxySign**; și **mai multe PDF-uri deodată**, cu un singur PIN;
- **formulare**: completezi câmpurile direct pe pagină;
- **PDF-uri ANAF** (formulare XFA cu XML atașat): le citești, deschizi XML-ul și le semnezi în câmpul „Semnătura”;
- text nou sau corectat, rotire, comentarii pentru un AI și, dacă e instalat Stirling PDF, uneltele PDF (comprimare, OCR, unire, împărțire etc.).

## Pentru contabili: instalare

1. Deschide [Releases](https://github.com/FintaxyOrg/FintaxyPDFEditor/releases/latest) și descarcă **PDF-Sign-win64.zip**.
2. Clic dreapta pe zip → **Extract All / Extrage tot**.
3. În folderul `PDF Sign` dă dublu clic pe **Instalare.cmd**.
   Dacă Windows arată „Windows protected your PC”: **More info → Run anyway** (aplicația nu e semnată digital de un furnizor).
4. Gata: ai **PDF Sign** pe Desktop și în Start, iar pe orice PDF ai **Deschide cu → PDF Sign** și, la clic dreapta, „Semnează cu Fintaxy PDF Sign”. Folderul descărcat se poate șterge.

Nu trebuie Python sau altceva instalat. Fereastra editorului se deschide în Microsoft Edge (vine cu Windows).

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
2. În editor apasă **Semnătură electronică** (sus, dreapta), alege certificatul și locul semnăturii:
   - în câmpul de semnătură al documentului (declarațiile ANAF, formularele);
   - într-un dreptunghi tras pe pagină;
   - invizibilă.
3. **Semnează**: Windows cere PIN-ul. Rezultatul e `<nume>_semnat.pdf`, lângă original.

**Mai multe PDF-uri deodată**: Unelte → **Semnează mai multe PDF-uri**, adaugi fișierele, un singur PIN. Cu stick-ul din birou, apasă întâi „Reserve 2 min” în FintaxySign, ca să nu-l ia un coleg între fișiere.

Un PDF deja semnat (de exemplu o declarație semnată de alt administrator) primește semnătura ta după cea existentă, fără s-o strice.

### Formulare și PDF-uri ANAF

- **Formular cu câmpuri**: câmpurile apar evidențiate pe pagină; le completezi și apeși **Salvează** (`<nume>_editat.pdf`).
- **Declarații ANAF** (D100, D112, D300 etc., formulare XFA): se văd ca în Adobe; deasupra apare XML-ul atașat, cu **Deschide** și **Arată în folder** (se salvează în `<nume> - atasamente`). Datele se completează în programul ANAF (Soft J / DUKIntegrator) sau în Adobe Reader; aici le citești și le semnezi.

### Unelte PDF (opțional)

Instalează [Stirling PDF](https://www.stirlingpdf.com/) pentru Windows (sau `winget install --id StirlingTools.StirlingPDF -e`). PDF Sign îl pornește singur, în fundal. Semnătura electronică nu are nevoie de Stirling.

### Actualizare și dezinstalare

- Actualizare: descarci zip-ul nou și rulezi din nou **Instalare.cmd**. Semnăturile și setările rămân.
- Dezinstalare: **Setări → Aplicații → PDF Sign (Fintaxy) → Dezinstalare**, sau **Dezinstalare.cmd** din zip.

## Pentru cine modifică aplicația

### Structura

| Folder | Ce e |
|---|---|
| `bin/` | aplicația, în Python: `desktop.py` (pornirea, ferestrele, AI), `editor_server.py` (serverul local al editorului, Stirling), `fx_sign.py` (scrierea în PDF cu PyMuPDF, formulare), `certsign.py` (semnătura electronică: pyHanko + cheia din Windows prin PowerShell), `signature_transparent.py` (fundal transparent la semnături) |
| `editor/` | interfața (HTML, CSS, JS), servită de `editor_server.py` pe 127.0.0.1 cu token |
| `app/` | `build.ps1` (versiunea portabilă), `install.ps1` + `Instalare.cmd` / `Dezinstalare.cmd`, iconița |
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

### Mod-ul pentru Claude Code

Sub fiecare PDF pomenit în chat apar Preview / Deschide / Semnează, iar editorul se deschide în panoul lui Claude. Are nevoie de Python cu pachetele de mai sus (`pip install -r requirements.txt`). Se instalează din Claude Code (repo-ul e privat: contul tău GitHub trebuie să aibă acces):

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

GitHub Actions construiește `PDF-Sign-win64.zip` și creează release-ul (~5 minute, tab-ul **Actions**). Local, același build: `powershell -ExecutionPolicy Bypass -File app\build.ps1` → `dist\PDF-Sign-win64.zip`.
