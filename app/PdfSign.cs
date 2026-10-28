// PDF Sign.exe: pornește editorul PDF (bin\desktop.py) cu pythonw, fără fereastră de consolă.
// install.ps1 înlocuiește __PYTHONW__ și __SCRIPT__ înainte de compilare (csc din .NET Framework, C# 5).
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

static class Program
{
    const string PythonW = @"__PYTHONW__";
    const string Script = @"__SCRIPT__";

    [STAThread]
    static int Main(string[] args)
    {
        var line = new StringBuilder(Quote(Script));
        foreach (var a in args) line.Append(' ').Append(Quote(a));
        try
        {
            if (!File.Exists(Script)) throw new FileNotFoundException("Nu găsesc editorul: " + Script + "\n(Google Drive e pornit?)");
            var psi = new ProcessStartInfo(PythonW, line.ToString());
            psi.UseShellExecute = false;
            psi.WorkingDirectory = Path.GetDirectoryName(Script);
            Process.Start(psi);
            return 0;
        }
        catch (Exception e)
        {
            MessageBox.Show(e.Message, "PDF Sign", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    static string Quote(string s)
    {
        return "\"" + s.TrimEnd('\\') + "\"";
    }
}
