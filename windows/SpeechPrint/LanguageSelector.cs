using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;

namespace SpeechPrint;

public class LanguageSelector : Form
{
    public List<string> SelectedLanguages { get; private set; } = new();

    private static readonly (string code, string name)[] Languages =
    {
        ("en", "English"),
        ("de", "German"),
        ("it", "Italian"),
        ("es", "Spanish"),
        ("fr", "French"),
        ("cs", "Czech"),
    };

    private readonly Dictionary<string, CheckBox> checkboxes = new();
    private readonly Label summary;

    public LanguageSelector()
    {
        Text = "SpeechPrint - Select Language Modules";
        Width = 500;
        Height = 460;
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;

        this.ApplyDarkTheme();

        var title = new Label
        {
            Text = "Select Language Modules",
            Font = new Font("Segoe UI", 14, FontStyle.Bold),
            Location = new Point(20, 15),
            AutoSize = true,
            ForeColor = ThemeColors.TextPrimary,
        };
        Controls.Add(title);

        var sub = new Label
        {
            Text = "Each language adds an MFA acoustic model + dictionary (~300 MB).\n"
                 + "You can add more later with `mfa model download`.",
            Location = new Point(20, 50),
            AutoSize = false,
            Width = 450,
            Height = 36,
            ForeColor = ThemeColors.TextDim,
        };
        Controls.Add(sub);

        int y = 100;
        foreach (var (code, name) in Languages)
        {
            var cb = new CheckBox
            {
                Text = $"{name} ({code})",
                Location = new Point(40, y),
                AutoSize = true,
                ForeColor = ThemeColors.TextPrimary,
                BackColor = ThemeColors.BackgroundDark,
                Checked = code == "en",
            };
            cb.CheckedChanged += (s, e) => UpdateSummary();
            checkboxes[code] = cb;
            Controls.Add(cb);
            y += 28;
        }

        summary = new Label
        {
            Location = new Point(20, y + 10),
            AutoSize = false,
            Width = 450,
            Height = 24,
            ForeColor = ThemeColors.TextDim,
        };
        Controls.Add(summary);
        UpdateSummary();

        var nextBtn = ThemeExtensions.MakePrimaryButton("Install");
        nextBtn.Location = new Point(340, y + 60);
        nextBtn.Width = 120;
        nextBtn.Height = 36;
        nextBtn.Click += (s, e) =>
        {
            SelectedLanguages = checkboxes
                .Where(kv => kv.Value.Checked)
                .Select(kv => kv.Key)
                .ToList();
            if (SelectedLanguages.Count == 0)
            {
                MessageBox.Show("Select at least one language.", "SpeechPrint",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            DialogResult = DialogResult.OK;
            Close();
        };
        Controls.Add(nextBtn);

        var cancelBtn = ThemeExtensions.MakeSecondaryButton("Cancel");
        cancelBtn.Location = new Point(210, y + 60);
        cancelBtn.Width = 120;
        cancelBtn.Height = 36;
        cancelBtn.Click += (s, e) =>
        {
            DialogResult = DialogResult.Cancel;
            Close();
        };
        Controls.Add(cancelBtn);
    }

    private void UpdateSummary()
    {
        int n = checkboxes.Count(kv => kv.Value.Checked);
        if (n == 0)
            summary.Text = "Select at least one language.";
        else
            summary.Text = $"{n} module(s) selected · approx. {n * 300} MB acoustic models";
    }
}
