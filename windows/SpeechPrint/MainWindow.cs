using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace SpeechPrint;

public class MainWindow : Form
{
    private readonly SpeechPrintMode mode;
    private readonly ReleaseType releaseType;
    private readonly string[] languages;
    private TextBox? logBox;
    private Label? statusLabel;
    private ProgressBar? progressBar;

    public MainWindow(SpeechPrintMode mode, ReleaseType releaseType, string[] languages)
    {
        this.mode = mode;
        this.releaseType = releaseType;
        this.languages = languages;

        Text = mode == SpeechPrintMode.Installation
            ? "SpeechPrint - Install Toolchain"
            : "SpeechPrint - Create Corpus";
        Width = 720;
        Height = 600;
        StartPosition = FormStartPosition.CenterScreen;
        this.ApplyDarkTheme();

        if (mode == SpeechPrintMode.Installation)
            BuildInstallUI();
        else
            BuildCorpusUI();
    }

    // ========================================================================
    // INSTALL UI
    // ========================================================================

    private void BuildInstallUI()
    {
        var title = new Label
        {
            Text = $"Installing SpeechPrint ({releaseType})",
            Font = new Font("Segoe UI", 14, FontStyle.Bold),
            Location = new Point(20, 15),
            AutoSize = true,
            ForeColor = ThemeColors.TextPrimary,
        };
        Controls.Add(title);

        var langLine = new Label
        {
            Text = "Language modules: " + string.Join(", ", languages),
            Location = new Point(20, 50),
            AutoSize = true,
            ForeColor = ThemeColors.TextDim,
        };
        Controls.Add(langLine);

        statusLabel = new Label
        {
            Text = "Preparing…",
            Location = new Point(20, 80),
            AutoSize = true,
            ForeColor = ThemeColors.TextPrimary,
        };
        Controls.Add(statusLabel);

        progressBar = new ProgressBar
        {
            Location = new Point(20, 105),
            Width = 660,
            Height = 18,
            Style = ProgressBarStyle.Marquee,
            MarqueeAnimationSpeed = 30,
        };
        Controls.Add(progressBar);

        logBox = new TextBox
        {
            Location = new Point(20, 140),
            Width = 660,
            Height = 360,
            Multiline = true,
            ScrollBars = ScrollBars.Vertical,
            ReadOnly = true,
            Font = new Font("Consolas", 9),
            BackColor = ThemeColors.BackgroundMid,
            ForeColor = ThemeColors.TextPrimary,
        };
        Controls.Add(logBox);

        var closeBtn = ThemeExtensions.MakeSecondaryButton("Close");
        closeBtn.Location = new Point(580, 510);
        closeBtn.Width = 100;
        closeBtn.Height = 36;
        closeBtn.Click += (s, e) => Close();
        Controls.Add(closeBtn);

        Load += async (s, e) => await RunInstaller();
    }

    private async Task RunInstaller()
    {
        Append("[SpeechPrint] Starting installation…");

        // 1. Extract install_package.ps1 + packages.psd1 from embedded resources
        var tempDir = Path.Combine(Path.GetTempPath(), "speechprint_install");
        Directory.CreateDirectory(tempDir);
        ExtractResource("install_package.ps1", tempDir);
        ExtractResource("packages.psd1", tempDir);
        ExtractTemplates(tempDir);

        var ps1 = Path.Combine(tempDir, "install_package.ps1");
        if (!File.Exists(ps1))
        {
            Append("✗ install_package.ps1 not found in bundle");
            SetStatus("Installation failed");
            return;
        }

        var langArg = string.Join(",", languages);
        var releaseArg = releaseType == ReleaseType.Dev ? "dev" : "stable";

        var psi = new ProcessStartInfo
        {
            FileName = "powershell.exe",
            Arguments = $"-ExecutionPolicy Bypass -NoProfile -File \"{ps1}\" -Release {releaseArg} -Languages {langArg}",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            WorkingDirectory = tempDir,
        };

        try
        {
            using var proc = Process.Start(psi)!;
            proc.OutputDataReceived += (s, e) => { if (e.Data != null) Append(e.Data); };
            proc.ErrorDataReceived  += (s, e) => { if (e.Data != null) Append(e.Data); };
            proc.BeginOutputReadLine();
            proc.BeginErrorReadLine();
            await proc.WaitForExitAsync();

            if (proc.ExitCode == 0)
            {
                Append("");
                Append("✓ Installation complete.");
                Append("");
                Append("Next steps:");
                Append("  1. Restart PowerShell/CMD");
                Append("  2. speechprint new MyCorpus C:\\Corpora\\");
                Append("  3. speechprint annotate data\\recording.wav --language " + languages[0]);
                SetStatus("✓ Installation complete");
            }
            else
            {
                Append($"⚠ install_package.ps1 exited with code {proc.ExitCode}");
                SetStatus("⚠ Completed with warnings");
            }
        }
        catch (Exception ex)
        {
            Append("✗ " + ex.Message);
            SetStatus("✗ Installation failed");
        }

        if (progressBar != null) progressBar.Style = ProgressBarStyle.Blocks;
    }

    // ========================================================================
    // CORPUS UI
    // ========================================================================

    private TextBox? nameBox;
    private TextBox? locationBox;
    private ComboBox? languagePicker;
    private CheckBox? autoEnsembleCheck;
    private CheckBox? vscodeCheck;
    private Label? previewLabel;

    private void BuildCorpusUI()
    {
        var title = new Label
        {
            Text = "New Corpus",
            Font = new Font("Segoe UI", 14, FontStyle.Bold),
            Location = new Point(20, 15),
            AutoSize = true,
            ForeColor = ThemeColors.TextPrimary,
        };
        Controls.Add(title);

        // Name
        Controls.Add(new Label
        {
            Text = "Corpus Name:",
            Location = new Point(20, 60),
            AutoSize = true,
            ForeColor = ThemeColors.TextPrimary,
        });
        nameBox = new TextBox
        {
            Location = new Point(20, 85),
            Width = 660,
            Text = "MyCorpus",
            BackColor = ThemeColors.BackgroundMid,
            ForeColor = ThemeColors.TextPrimary,
            BorderStyle = BorderStyle.FixedSingle,
        };
        nameBox.TextChanged += (s, e) => UpdatePreview();
        Controls.Add(nameBox);

        // Location
        Controls.Add(new Label
        {
            Text = "Location:",
            Location = new Point(20, 120),
            AutoSize = true,
            ForeColor = ThemeColors.TextPrimary,
        });
        locationBox = new TextBox
        {
            Location = new Point(20, 145),
            Width = 530,
            Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Corpora"),
            BackColor = ThemeColors.BackgroundMid,
            ForeColor = ThemeColors.TextPrimary,
            BorderStyle = BorderStyle.FixedSingle,
        };
        locationBox.TextChanged += (s, e) => UpdatePreview();
        Controls.Add(locationBox);

        var browseBtn = ThemeExtensions.MakeSecondaryButton("Browse…");
        browseBtn.Location = new Point(560, 144);
        browseBtn.Width = 120;
        browseBtn.Height = 26;
        browseBtn.Click += (s, e) =>
        {
            using var dlg = new FolderBrowserDialog();
            if (Directory.Exists(locationBox!.Text)) dlg.SelectedPath = locationBox.Text;
            if (dlg.ShowDialog() == DialogResult.OK)
            {
                locationBox.Text = dlg.SelectedPath;
            }
        };
        Controls.Add(browseBtn);

        // Language picker
        Controls.Add(new Label
        {
            Text = "Default Language:",
            Location = new Point(20, 180),
            AutoSize = true,
            ForeColor = ThemeColors.TextPrimary,
        });
        languagePicker = new ComboBox
        {
            Location = new Point(20, 205),
            Width = 250,
            DropDownStyle = ComboBoxStyle.DropDownList,
            BackColor = ThemeColors.BackgroundMid,
            ForeColor = ThemeColors.TextPrimary,
        };
        languagePicker.Items.AddRange(new object[]
        {
            "English (en)", "German (de)", "Italian (it)",
            "Spanish (es)", "French (fr)", "Czech (cs)"
        });
        languagePicker.SelectedIndex = 0;
        Controls.Add(languagePicker);

        autoEnsembleCheck = new CheckBox
        {
            Text = "Auto-ensemble (run aggregation after each annotate)",
            Location = new Point(20, 245),
            AutoSize = true,
            ForeColor = ThemeColors.TextPrimary,
            BackColor = ThemeColors.BackgroundDark,
        };
        Controls.Add(autoEnsembleCheck);

        vscodeCheck = new CheckBox
        {
            Text = "Include VS Code configuration",
            Location = new Point(20, 275),
            AutoSize = true,
            Checked = true,
            ForeColor = ThemeColors.TextPrimary,
            BackColor = ThemeColors.BackgroundDark,
        };
        Controls.Add(vscodeCheck);

        Controls.Add(new Label
        {
            Text = "Corpus will be created at:",
            Location = new Point(20, 320),
            AutoSize = true,
            ForeColor = ThemeColors.TextDim,
        });
        previewLabel = new Label
        {
            Location = new Point(20, 345),
            AutoSize = true,
            Font = new Font("Consolas", 10),
            ForeColor = ThemeColors.TextPrimary,
        };
        Controls.Add(previewLabel);
        UpdatePreview();

        var createBtn = ThemeExtensions.MakePrimaryButton("Create Corpus");
        createBtn.Location = new Point(540, 510);
        createBtn.Width = 140;
        createBtn.Height = 40;
        createBtn.Click += async (s, e) => await CreateCorpus();
        Controls.Add(createBtn);

        var cancelBtn = ThemeExtensions.MakeSecondaryButton("Cancel");
        cancelBtn.Location = new Point(410, 510);
        cancelBtn.Width = 120;
        cancelBtn.Height = 40;
        cancelBtn.Click += (s, e) => Close();
        Controls.Add(cancelBtn);
    }

    private string SelectedLanguageCode()
    {
        return languagePicker?.SelectedIndex switch
        {
            0 => "en", 1 => "de", 2 => "it",
            3 => "es", 4 => "fr", 5 => "cs",
            _ => "en"
        };
    }

    private void UpdatePreview()
    {
        if (nameBox == null || locationBox == null || previewLabel == null) return;
        var safe = string.IsNullOrWhiteSpace(nameBox.Text)
            ? "MyCorpus"
            : new string(nameBox.Text.Select(c => char.IsLetterOrDigit(c) || c == '-' || c == '_' ? c : '_').ToArray());
        previewLabel.Text = Path.Combine(locationBox.Text, safe);
    }

    private async Task CreateCorpus()
    {
        if (nameBox == null || locationBox == null) return;
        var name = nameBox.Text.Trim();
        var loc  = locationBox.Text.Trim();
        if (string.IsNullOrEmpty(name) || string.IsNullOrEmpty(loc))
        {
            MessageBox.Show("Corpus name and location are required.", "SpeechPrint",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        Directory.CreateDirectory(loc);
        var target = Path.Combine(loc, name);
        if (Directory.Exists(target))
        {
            MessageBox.Show("Corpus already exists at:\n" + target, "SpeechPrint",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        var lang = SelectedLanguageCode();
        var auto = autoEnsembleCheck?.Checked == true;
        var vscode = vscodeCheck?.Checked == true;

        // Try `speechprint new` from PATH first
        var psi = new ProcessStartInfo
        {
            FileName = "speechprint",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        psi.ArgumentList.Add("new");
        psi.ArgumentList.Add(name);
        psi.ArgumentList.Add(loc);
        psi.ArgumentList.Add("--language");
        psi.ArgumentList.Add(lang);
        if (auto)   psi.ArgumentList.Add("--auto-ensemble");
        if (!vscode) psi.ArgumentList.Add("--no-vscode");

        try
        {
            using var proc = Process.Start(psi)!;
            var stdout = await proc.StandardOutput.ReadToEndAsync();
            var stderr = await proc.StandardError.ReadToEndAsync();
            await proc.WaitForExitAsync();
            if (proc.ExitCode == 0)
            {
                MessageBox.Show(
                    "Corpus created successfully!\n\n" + target +
                    "\n\nNext steps:\n  cd " + target +
                    "\n  drop WAVs in data\\" +
                    "\n  speechprint annotate data\\<file>.wav --language " + lang,
                    "SpeechPrint", MessageBoxButtons.OK, MessageBoxIcon.Information);
                Close();
            }
            else
            {
                MessageBox.Show("Failed to create corpus:\n" + (stderr.Length > 0 ? stderr : stdout),
                    "SpeechPrint", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                "Could not run `speechprint` — is the installer finished?\n\n" + ex.Message,
                "SpeechPrint", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    // ========================================================================
    // HELPERS
    // ========================================================================

    private void Append(string text)
    {
        if (logBox == null) return;
        if (logBox.InvokeRequired)
        {
            logBox.Invoke(() => Append(text));
            return;
        }
        logBox.AppendText(text + Environment.NewLine);
    }

    private void SetStatus(string text)
    {
        if (statusLabel == null) return;
        if (statusLabel.InvokeRequired)
        {
            statusLabel.Invoke(() => SetStatus(text));
            return;
        }
        statusLabel.Text = text;
    }

    private static void ExtractResource(string resourceFilename, string destDir)
    {
        var asm = Assembly.GetExecutingAssembly();
        var match = asm.GetManifestResourceNames()
            .FirstOrDefault(n => n.EndsWith(resourceFilename, StringComparison.OrdinalIgnoreCase));
        if (match == null) return;
        using var s = asm.GetManifestResourceStream(match);
        if (s == null) return;
        var dest = Path.Combine(destDir, resourceFilename);
        using var fs = File.Create(dest);
        s.CopyTo(fs);
    }

    private static void ExtractTemplates(string destDir)
    {
        var asm = Assembly.GetExecutingAssembly();
        var templatesDir = Path.Combine(destDir, "templates");
        Directory.CreateDirectory(templatesDir);
        foreach (var name in asm.GetManifestResourceNames())
        {
            var idx = name.IndexOf("templates", StringComparison.OrdinalIgnoreCase);
            if (idx < 0) continue;
            var relative = name.Substring(idx + "templates".Length).TrimStart('.');
            // Embedded resource names look like "SpeechPrint.Resources.templates.corpus.toml"
            // We split into segments and re-join with path separators, except the last "." (extension).
            var segments = relative.Split('.');
            string outPath;
            if (segments.Length <= 1)
                outPath = Path.Combine(templatesDir, relative);
            else
            {
                var ext = segments[^1];
                var parts = segments[..^1];
                outPath = Path.Combine(new[] { templatesDir }.Concat(parts).ToArray()) + "." + ext;
            }
            Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
            using var s = asm.GetManifestResourceStream(name);
            if (s == null) continue;
            using var fs = File.Create(outPath);
            s.CopyTo(fs);
        }
    }
}
