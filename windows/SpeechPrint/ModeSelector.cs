using System;
using System.Drawing;
using System.Windows.Forms;

namespace SpeechPrint;

public class ModeSelector : Form
{
    public SpeechPrintMode? SelectedMode { get; private set; }

    public ModeSelector()
    {
        InitializeUI();
    }

    private void InitializeUI()
    {
        Text = "SpeechPrint - Select Mode";
        Width = 500;
        Height = 300;
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        Icon = SystemIcons.Application;
        ShowInTaskbar = true;

        this.ApplyDarkTheme();

        var titleLabel = new Label
        {
            Text = "What would you like to do?",
            Font = new Font("Segoe UI", 14, FontStyle.Bold),
            Location = new Point(20, 20),
            AutoSize = true,
            BackColor = ThemeColors.BackgroundDark,
            ForeColor = ThemeColors.TextPrimary
        };
        Controls.Add(titleLabel);

        var installButton = ThemeExtensions.MakePrimaryButton("Install SpeechPrint");
        installButton.Location = new Point(50, 70);
        installButton.Width = 380;
        installButton.Height = 80;
        installButton.Click += (s, e) =>
        {
            SelectedMode = SpeechPrintMode.Installation;
            DialogResult = DialogResult.OK;
            Close();
        };
        Controls.Add(installButton);

        var corpusButton = ThemeExtensions.MakePrimaryButton("Create Corpus");
        corpusButton.BackColor = ThemeColors.ButtonSuccess;
        corpusButton.Location = new Point(50, 160);
        corpusButton.Width = 380;
        corpusButton.Height = 80;
        corpusButton.Click += (s, e) =>
        {
            SelectedMode = SpeechPrintMode.CorpusCreation;
            DialogResult = DialogResult.OK;
            Close();
        };
        Controls.Add(corpusButton);
    }
}
