# PDF Sign (Fintaxy)

Aplicație Windows pentru semnat și editat PDF-uri: pui semnătura olografă (imagine transparentă) cu mouse-ul, adaugi sau corectezi text, rotești pagini, lași comentarii pentru un AI și, dacă e instalat Stirling PDF, semnezi cu certificat (CEI, token) și ai uneltele PDF (comprimare, OCR, unire, împărțire etc.).

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

### Semnare cu certificat și unelte PDF (opțional)

Instalează [Stirling PDF](https://www.stirlingpdf.com/) pentru Windows (sau `winget install --id StirlingTools.StirlingPDF -e`). PDF Sign îl pornește singur, în fundal. Certificatul (CEI, token) trebuie să fie în Windows (Certificate Store).

### Actualizare și dezinstalare

- Actualizare: descarci zip-ul nou și rulezi din nou **Instalare.cmd**. Semnăturile și setările rămân.
- Dezinstalare: **Setări → Aplicații → PDF Sign (Fintaxy) → Dezinstalare**, sau **Dezinstalare.cmd** din zip.

## Pentru cine modifică aplicația

### Structura

| Folder | Ce e |
|---|---|
| `bin/` | aplicația, în Python: `desktop.py` (pornirea, ferestrele, AI), `editor_server.py` (serverul local al editorului, Stirling), `fx_sign.py` (scrierea în PDF cu PyMuPDF), `signature_transparent.py` (fundal transparent la semnături) |
| `editor/` | interfața (HTML, CSS, JS), servită de `editor_server.py` pe 127.0.0.1 cu token |
| `app/` | `build.ps1` (versiunea portabilă), `install.ps1` + `Instalare.cmd` / `Dezinstalare.cmd`, iconița |
| `hooks/`, `types/`, `.claude-plugin/` | mod-ul pentru Claude Code (cardul de sub PDF-uri din chat); nu e necesar pentru aplicație |
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

### Versiune nouă

1. Faci modificările și le testezi din cod.
2. Crești `version` în `.claude-plugin/plugin.json`.
3. Commit, apoi tag și push:

```powershell
git tag v0.11.1
git push origin master --tags
```

GitHub Actions construiește `PDF-Sign-win64.zip` și creează release-ul (~5 minute, tab-ul **Actions**). Local, același build: `powershell -ExecutionPolicy Bypass -File app\build.ps1` → `dist\PDF-Sign-win64.zip`.
