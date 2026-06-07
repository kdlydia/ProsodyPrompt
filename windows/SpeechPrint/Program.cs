using System;
using System.Windows.Forms;

namespace SpeechPrint;

static class Program
{
    [STAThread]
    static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        var modeSelector = new ModeSelector();
        if (modeSelector.ShowDialog() != DialogResult.OK || modeSelector.SelectedMode == null)
        {
            Application.Exit();
            return;
        }

        var mode = modeSelector.SelectedMode.Value;
        ReleaseType releaseType = ReleaseType.Stable;
        string[] languages = new[] { "en" };

        if (mode == SpeechPrintMode.Installation)
        {
            var releaseSelector = new ReleaseTypeSelector();
            if (releaseSelector.ShowDialog() != DialogResult.OK || releaseSelector.SelectedType == null)
            {
                Application.Exit();
                return;
            }
            releaseType = releaseSelector.SelectedType.Value;

            var langSelector = new LanguageSelector();
            if (langSelector.ShowDialog() != DialogResult.OK || langSelector.SelectedLanguages.Count == 0)
            {
                Application.Exit();
                return;
            }
            languages = langSelector.SelectedLanguages.ToArray();
        }

        var mainWindow = new MainWindow(mode, releaseType, languages);
        Application.Run(mainWindow);
    }
}

public enum SpeechPrintMode { Installation, CorpusCreation }
public enum ReleaseType { Stable, Dev }
