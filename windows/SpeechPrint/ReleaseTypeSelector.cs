using System;
using System.Drawing;
using System.Windows.Forms;

namespace SpeechPrint;

public class ReleaseTypeSelector : Form
{
    public ReleaseType? SelectedType { get; private set; }
    private RadioButton stableRadio;
    private RadioButton devRadio;

    public ReleaseTypeSelector()
    {
        InitializeUI();
    }

    private void InitializeUI()
    {
        Text = "SpeechPrint - Select Release Channel";
        Width = 500;
        Height = 380;
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;

        this.ApplyDarkTheme();

        var title = new Label
        {
            Text = "Select Release Channel",
            Font = new Font("Segoe UI", 14, FontStyle.Bold),
            Location = new Point(20, 15),
            AutoSize = true,
            ForeColor = ThemeColors.TextPrimary,
        };
        Controls.Add(title);

        stableRadio = new RadioButton
        {
            Text = "Stable Release (Recommended)",
            Location = new Point(30, 60),
            AutoSize = true,
            Checked = true,
            ForeColor = ThemeColors.TextPrimary,
            BackColor = ThemeColors.BackgroundDark,
            Font = new Font("Segoe UI", 10, FontStyle.Bold),
        };
        Controls.Add(stableRadio);

        var stableDesc = new Label
        {
            Text = "Production-ready release. Tested and stable.\nRecommended for general use and field-recording workflows.",
            Location = new Point(55, 85),
            AutoSize = false,
            Width = 410,
            Height = 40,
            ForeColor = ThemeColors.TextDim,
        };
        Controls.Add(stableDesc);

        devRadio = new RadioButton
        {
            Text = "Development Release",
            Location = new Point(30, 150),
            AutoSize = true,
            ForeColor = ThemeColors.TextPrimary,
            BackColor = ThemeColors.BackgroundDark,
            Font = new Font("Segoe UI", 10, FontStyle.Bold),
        };
        Controls.Add(devRadio);

        var devDesc = new Label
        {
            Text = "Latest features and improvements. May contain bugs.\nFor testing and early access to new functionality.",
            Location = new Point(55, 175),
            AutoSize = false,
            Width = 410,
            Height = 40,
            ForeColor = ThemeColors.TextDim,
        };
        Controls.Add(devDesc);

        var nextBtn = ThemeExtensions.MakePrimaryButton("Next");
        nextBtn.Location = new Point(340, 290);
        nextBtn.Width = 120;
        nextBtn.Height = 36;
        nextBtn.Click += (s, e) =>
        {
            SelectedType = stableRadio.Checked ? ReleaseType.Stable : ReleaseType.Dev;
            DialogResult = DialogResult.OK;
            Close();
        };
        Controls.Add(nextBtn);

        var cancelBtn = ThemeExtensions.MakeSecondaryButton("Cancel");
        cancelBtn.Location = new Point(210, 290);
        cancelBtn.Width = 120;
        cancelBtn.Height = 36;
        cancelBtn.Click += (s, e) =>
        {
            DialogResult = DialogResult.Cancel;
            Close();
        };
        Controls.Add(cancelBtn);
    }
}
