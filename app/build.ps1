# Construiește versiunea portabilă (nu cere Python pe calculatorul contabilului):
#   dist\PDF Sign\           PDF Sign.exe + _internal\ + Instalare.cmd / Dezinstalare.cmd
#   dist\PDF-Sign-win64.zip  ce se pune la Releases pe GitHub
# Rulează în .venv-build (creat aici, cu requirements.txt + PyInstaller), la fel local și pe GitHub Actions.
#   powershell -ExecutionPolicy Bypass -File app\build.ps1
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$venv = Join-Path $root '.venv-build'
$py = Join-Path $venv 'Scripts\python.exe'
$dist = Join-Path $root 'dist'
$app = Join-Path $dist 'PDF Sign'
$zip = Join-Path $dist 'PDF-Sign-win64.zip'

function Run($exe) {
    & $exe @args
    if ($LASTEXITCODE) { throw "$exe $args a eșuat ($LASTEXITCODE)." }
}

if (-not (Test-Path $py)) { Run python -m venv $venv }
Run $py -m pip install --disable-pip-version-check -q -r (Join-Path $root 'requirements.txt') pyinstaller==6.16.0

if (Test-Path $dist) { Remove-Item $dist -Recurse -Force }
# --paths bin: desktop.py importă fx_sign, editor_server și signature_transparent din același folder.
Run $py -m PyInstaller --noconfirm --clean --windowed --name 'PDF Sign' `
    --icon (Join-Path $here 'pdf-sign.ico') `
    --paths (Join-Path $root 'bin') `
    --add-data "$(Join-Path $root 'editor');editor" `
    --hidden-import editor_server --hidden-import fx_sign --hidden-import signature_transparent --hidden-import certsign --hidden-import xfaview --hidden-import mdview `
    --hidden-import localtools --hidden-import winenv --hidden-import deps --hidden-import acp_chat --hidden-import anaf `
    --add-data "$(Join-Path $here 'tessdata');tessdata" `
    --collect-submodules pdf2docx --collect-data docx `
    --collect-data pyhanko --collect-submodules pyhanko.sign --collect-submodules pyhanko_certvalidator `
    --exclude-module pymupdf.layout --exclude-module pymupdf4llm `
    --distpath $dist --workpath (Join-Path $root 'build') --specpath (Join-Path $root 'build') `
    (Join-Path $root 'bin\desktop.py')

Copy-Item (Join-Path $here 'install.ps1'), (Join-Path $here 'Instalare.cmd'), (Join-Path $here 'Dezinstalare.cmd'), (Join-Path $root 'LICENSE') $app
$version = (Get-Content (Join-Path $root '.claude-plugin\plugin.json') -Raw -Encoding UTF8 | ConvertFrom-Json).version
Set-Content (Join-Path $app 'version.txt') $version -Encoding ASCII
Compress-Archive -Path $app -DestinationPath $zip -CompressionLevel Optimal
"Gata: $zip ($([math]::Round((Get-Item $zip).Length / 1MB, 1)) MB)"

# Un singur fișier de descărcat: PDF-Sign-Setup.exe are zip-ul în el, îl despachetează și rulează install.ps1.
# csc din .NET Framework 4 (vine cu Windows), ca la PdfSign.cs.
$setup = Join-Path $dist 'PDF-Sign-Setup.exe'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
Run $csc /nologo /target:winexe /optimize+ "/out:$setup" "/win32icon:$(Join-Path $here 'pdf-sign.ico')" `
    "/resource:$zip,app.zip" /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.IO.Compression.dll `
    /r:System.IO.Compression.FileSystem.dll (Join-Path $here 'Setup.cs')
"Gata: $setup ($([math]::Round((Get-Item $setup).Length / 1MB, 1)) MB)"
