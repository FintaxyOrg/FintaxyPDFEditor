# Instalează PDF Sign ca aplicație pe calculator, doar pentru utilizatorul curent (fără drepturi de admin).
#   powershell -ExecutionPolicy Bypass -File install.ps1              -> instalează / actualizează
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall   -> scoate tot ce a pus (semnăturile rămân)
# Două feluri:
#   portabil  install.ps1 stă lângă PDF Sign.exe (zip-ul din Releases): copiază folderul în Programs și îl înregistrează;
#   din cod   install.ps1 stă în app\ din repo: compilează un PDF Sign.exe mic care pornește bin\desktop.py cu pythonw.
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$portable = Test-Path -LiteralPath (Join-Path $here 'PDF Sign.exe')
$dest = Join-Path $env:LOCALAPPDATA 'Programs\Fintaxy PDF Sign'
$exe = Join-Path $dest 'PDF Sign.exe'
$ico = Join-Path $dest 'pdf-sign.ico'
$links = @((Join-Path ([Environment]::GetFolderPath('Desktop')) 'PDF Sign.lnk'),
           (Join-Path ([Environment]::GetFolderPath('Programs')) 'PDF Sign.lnk'))
$classes = 'HKCU:\Software\Classes'
$verb = "$classes\SystemFileAssociations\.pdf\shell\FintaxyPdfSign"
$progId = "$classes\Fintaxy.PdfSign"
$appKey = "$classes\Applications\PDF Sign.exe"
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\FintaxyPdfSign'

Add-Type -Namespace Fx -Name Shell -MemberDefinition '[DllImport("shell32.dll")] public static extern void SHChangeNotify(int e, int f, IntPtr a, IntPtr b);'

function Stop-App {
    # Aplicația portabilă e chiar serverul editorului: o oprim ca să putem scrie peste fișierele ei.
    Get-Process -Name 'PDF Sign' -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$dest\*" } | Stop-Process -Force
    Start-Sleep -Milliseconds 500
}

# Pe lângă PDF, aplicația deschide (prin PDF-ul lor de citit, bin/mdview.py) fișierele Markdown și documentele Word.
$docExt = '.md', '.markdown', '.docx', '.doc', '.docm', '.dotx', '.dot', '.rtf', '.odt'

if ($Uninstall) {
    Stop-App
    foreach ($k in $verb, $progId, $appKey, $uninstallKey) { if (Test-Path -LiteralPath $k) { Remove-Item -LiteralPath $k -Recurse -Force } }
    foreach ($e in @('.pdf') + $docExt) { Remove-ItemProperty -LiteralPath "$classes\$e\OpenWithProgids" -Name 'Fintaxy.PdfSign' -ErrorAction SilentlyContinue }
    foreach ($l in $links) { Remove-Item -LiteralPath $l -Force -ErrorAction SilentlyContinue }
    if ($here.TrimEnd('\') -eq $dest.TrimEnd('\')) {
        # Scriptul rulează chiar din folderul de șters: îl ștergem după ce se termină.
        Start-Process cmd.exe -ArgumentList "/c timeout /t 3 /nobreak >nul & rmdir /s /q `"$dest`"" -WindowStyle Hidden -WorkingDirectory $env:TEMP
    } else {
        Remove-Item -LiteralPath $dest -Recurse -Force -ErrorAction SilentlyContinue
    }
    [Fx.Shell]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)
    'PDF Sign a fost dezinstalat. Semnăturile din Documente\Semnaturi PDF Sign au rămas.'
    exit 0
}

if ($portable) {
    Stop-App
    # Fișierele dintr-un zip descărcat au „Mark of the Web”: fără Unblock, Windows întreabă la fiecare pornire.
    Get-ChildItem -LiteralPath $here -Recurse -File | Unblock-File
    if ($here.TrimEnd('\') -ne $dest.TrimEnd('\')) {
        if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
        New-Item -ItemType Directory -Force $dest | Out-Null
        Copy-Item -Path (Join-Path $here '*') -Destination $dest -Recurse -Force
    }
    $icon = "`"$exe`",0"
    $version = ''
    $vf = Join-Path $dest 'version.txt'
    if (Test-Path -LiteralPath $vf) { $version = (Get-Content -LiteralPath $vf -Raw).Trim() }
    # Apare în Setări > Aplicații, de unde se poate dezinstala.
    New-Item -Path $uninstallKey -Force | Out-Null
    foreach ($p in @{ DisplayName = 'PDF Sign (Fintaxy)'; Publisher = 'Fintaxy'; DisplayVersion = $version
                      DisplayIcon = $icon; InstallLocation = $dest
                      UninstallString = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$dest\install.ps1`" -Uninstall" }.GetEnumerator()) {
        New-ItemProperty -LiteralPath $uninstallKey -Name $p.Key -Value $p.Value -PropertyType String -Force | Out-Null
    }
    New-ItemProperty -LiteralPath $uninstallKey -Name NoModify -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -LiteralPath $uninstallKey -Name NoRepair -Value 1 -PropertyType DWord -Force | Out-Null
} else {
    # Python-ul care are PyMuPDF (cel folosit și de mod).
    $python = (& python -W ignore -c "import sys, fitz, PIL, numpy; print(sys.executable)" | Select-Object -Last 1)
    if (-not $python -or -not (Test-Path $python)) { throw 'Nu găsesc Python cu pachetele aplicației (pip install -r requirements.txt).' }
    $pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
    if (-not (Test-Path $pythonw)) { throw "Nu găsesc $pythonw" }

    New-Item -ItemType Directory -Force $dest | Out-Null
    & $python (Join-Path $here 'make_icon.py')
    if ($LASTEXITCODE) { throw 'make_icon.py a eșuat.' }
    Copy-Item -LiteralPath (Join-Path $here 'pdf-sign.ico') -Destination $ico -Force

    # PDF Sign.exe, compilat cu csc din .NET Framework (vine cu Windows).
    $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    $src = [IO.File]::ReadAllText((Join-Path $here 'PdfSign.cs'), [Text.Encoding]::UTF8)
    $src = $src.Replace('__PYTHONW__', $pythonw).Replace('__SCRIPT__', (Join-Path $root 'bin\desktop.py'))
    $tmp = Join-Path $env:TEMP 'PdfSign.cs'
    [IO.File]::WriteAllText($tmp, $src, (New-Object Text.UTF8Encoding $true))
    & $csc /nologo /target:winexe "/out:$exe" "/win32icon:$ico" /r:System.Windows.Forms.dll $tmp
    if ($LASTEXITCODE) { throw 'Compilarea PDF Sign.exe a eșuat.' }
    Remove-Item $tmp -Force
}

function Set-Key($path, $default, $values = @{}) {
    New-Item -Path $path -Force | Out-Null
    if ($null -ne $default) { Set-Item -LiteralPath $path -Value $default }
    foreach ($n in $values.Keys) { New-ItemProperty -LiteralPath $path -Name $n -Value $values[$n] -PropertyType String -Force | Out-Null }
}
$cmd = "`"$exe`" `"%1`""

# Clic dreapta pe PDF (în Windows 11: „Afișați mai multe opțiuni”).
Set-Key $verb 'Semnează cu Fintaxy PDF Sign' @{ Icon = "`"$exe`",0" }
Set-Key "$verb\command" $cmd
# „Deschide cu” (apare și în meniul scurt din Windows 11); nu schimbă aplicația implicită pentru PDF.
Set-Key $progId 'Document PDF'
Set-Key "$progId\Application" $null @{ ApplicationName = 'PDF Sign'; ApplicationIcon = "`"$exe`",0"; ApplicationCompany = 'Fintaxy' }
Set-Key "$progId\DefaultIcon" "`"$exe`",0"
Set-Key "$progId\shell\open" $null @{ FriendlyAppName = 'PDF Sign' }
Set-Key "$progId\shell\open\command" $cmd
Set-Key "$classes\.pdf\OpenWithProgids" $null @{ 'Fintaxy.PdfSign' = '' }
Set-Key $appKey $null @{ FriendlyAppName = 'PDF Sign' }
$types = @{ '.pdf' = '' }; foreach ($e in $docExt) { $types[$e] = '' }
Set-Key "$appKey\SupportedTypes" $null $types
# Fișierele Markdown și Word: PDF Sign apare la „Deschide cu” (nu devine programul implicit)
foreach ($e in $docExt) { Set-Key "$classes\$e\OpenWithProgids" $null @{ 'Fintaxy.PdfSign' = '' } }
Set-Key "$appKey\shell\open\command" $cmd

# Scurtături pe Desktop și în meniul Start (tragi un PDF peste ele ca să-l deschizi).
$ws = New-Object -ComObject WScript.Shell
foreach ($l in $links) {
    $s = $ws.CreateShortcut($l)
    $s.TargetPath = $exe
    $s.WorkingDirectory = $dest
    $s.IconLocation = "$exe,0"
    $s.Description = 'Semnează și editează PDF-uri (Fintaxy)'
    $s.Save()
}
[Fx.Shell]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)
"Instalat: $exe"
