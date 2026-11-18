// PDF-Sign-Setup.exe: un singur fișier de descărcat. Are în el aplicația portabilă (zip, ca resursă), o despachetează
// într-un folder temporar și rulează install.ps1 din ea (copiere în %LOCALAPPDATA%\Programs, scurtături, „Deschide cu”),
// apoi pornește PDF Sign. Fără drepturi de administrator, fără terminal, fără întrebări.
//   PDF-Sign-Setup.exe            instalează (sau actualizează) și pornește aplicația
//   PDF-Sign-Setup.exe /silent    la fel, fără fereastră și fără să pornească aplicația (pentru IT)
// Compilat de build.ps1 cu csc din .NET Framework 4 (vine cu Windows), C# 5.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Threading;
using System.Windows.Forms;

static class Setup
{
    static Form form;
    static Label status;
    static ProgressBar bar;

    [STAThread]
    static int Main(string[] args)
    {
        bool silent = Array.Exists(args, a => a.Equals("/silent", StringComparison.OrdinalIgnoreCase) || a.Equals("-silent", StringComparison.OrdinalIgnoreCase));
        if (silent)
        {
            try { Install(null); return 0; }
            catch (Exception e) { Console.Error.WriteLine(e.Message); return 1; }
        }
        Application.EnableVisualStyles();
        form = new Form();
        form.Text = "PDF Sign (Fintaxy)";
        form.ClientSize = new Size(420, 120);
        form.FormBorderStyle = FormBorderStyle.FixedDialog;
        form.MaximizeBox = false;
        form.MinimizeBox = false;
        form.StartPosition = FormStartPosition.CenterScreen;
        form.Font = new Font("Segoe UI", 9.5f);
        try { form.Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
        status = new Label();
        status.Text = "Se instalează PDF Sign…";
        status.SetBounds(20, 22, 380, 24);
        bar = new ProgressBar();
        bar.SetBounds(20, 56, 380, 18);
        bar.Maximum = 100;
        form.Controls.Add(status);
        form.Controls.Add(bar);
        Exception error = null;
        string exe = null;
        var worker = new Thread(() =>
        {
            try { exe = Install(p => form.BeginInvoke((Action)(() => { bar.Value = Math.Min(100, p); }))); }
            catch (Exception e) { error = e; }
            form.BeginInvoke((Action)(() => form.Close()));
        });
        form.Shown += (s, e) => worker.Start();
        // Cât se instalează, fereastra nu se închide: o instalare întreruptă lasă aplicația pe jumătate.
        form.FormClosing += (s, e) => { if (worker.IsAlive) e.Cancel = true; };
        Application.Run(form);
        if (error != null)
        {
            MessageBox.Show("Instalarea nu a reușit:\n\n" + error.Message, "PDF Sign", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        if (exe != null && File.Exists(exe)) Process.Start(new ProcessStartInfo(exe) { WorkingDirectory = Path.GetDirectoryName(exe) });
        return 0;
    }

    // Despachetează aplicația și rulează install.ps1; întoarce calea aplicației instalate.
    static string Install(Action<int> progress)
    {
        string temp = Path.Combine(Path.GetTempPath(), "PDFSignSetup-" + Guid.NewGuid().ToString("N").Substring(0, 8));
        Directory.CreateDirectory(temp);
        try
        {
            using (Stream zip = Assembly.GetExecutingAssembly().GetManifestResourceStream("app.zip"))
            {
                if (zip == null) throw new InvalidOperationException("Fișierul de instalare e incomplet (lipsește aplicația din el). Descarcă-l din nou.");
                using (var archive = new ZipArchive(zip, ZipArchiveMode.Read))
                {
                    int n = 0, total = Math.Max(1, archive.Entries.Count);
                    string root = Path.GetFullPath(temp) + Path.DirectorySeparatorChar;
                    foreach (ZipArchiveEntry entry in archive.Entries)
                    {
                        string target = Path.GetFullPath(Path.Combine(temp, entry.FullName));
                        if (!target.StartsWith(root, StringComparison.OrdinalIgnoreCase)) continue; // nimic în afara folderului
                        if (entry.FullName.EndsWith("/") || entry.FullName.EndsWith("\\")) Directory.CreateDirectory(target);
                        else
                        {
                            Directory.CreateDirectory(Path.GetDirectoryName(target));
                            entry.ExtractToFile(target, true);
                        }
                        if (progress != null && (++n % 25 == 0)) progress(n * 85 / total);
                    }
                }
            }
            string script = Path.Combine(temp, "PDF Sign", "install.ps1");
            if (!File.Exists(script)) throw new FileNotFoundException("Lipsește install.ps1 din pachet.");
            var psi = new ProcessStartInfo("powershell.exe", "-NoProfile -ExecutionPolicy Bypass -File \"" + script + "\"");
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.RedirectStandardError = true;
            psi.RedirectStandardOutput = true;
            using (Process p = Process.Start(psi))
            {
                string output = p.StandardOutput.ReadToEnd();
                string err = p.StandardError.ReadToEnd();
                p.WaitForExit();
                if (p.ExitCode != 0) throw new InvalidOperationException((err + "\n" + output).Trim());
            }
            if (progress != null) progress(100);
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Fintaxy PDF Sign", "PDF Sign.exe");
        }
        finally
        {
            try { Directory.Delete(temp, true); } catch { }
        }
    }
}
