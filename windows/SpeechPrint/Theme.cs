using System.Drawing;
using System.Windows.Forms;

namespace SpeechPrint;

public static class ThemeColors
{
    public static readonly Color BackgroundDark = Color.FromArgb(30, 30, 30);
    public static readonly Color BackgroundMid  = Color.FromArgb(42, 42, 42);
    public static readonly Color TextPrimary    = Color.FromArgb(224, 224, 224);
    public static readonly Color TextDim        = Color.FromArgb(160, 160, 160);
    public static readonly Color ButtonPrimary  = Color.FromArgb(59, 130, 246);
    public static readonly Color ButtonHover    = Color.FromArgb(37, 99, 235);
    public static readonly Color ButtonSuccess  = Color.FromArgb(34, 197, 94);
    public static readonly Color ButtonNeutral  = Color.FromArgb(64, 64, 64);
    public static readonly Color Accent         = Color.FromArgb(59, 130, 246);
    public static readonly Color BorderDim      = Color.FromArgb(68, 68, 68);
}

public static class ThemeExtensions
{
    public static void ApplyDarkTheme(this Form f)
    {
        f.BackColor = ThemeColors.BackgroundDark;
        f.ForeColor = ThemeColors.TextPrimary;
        f.Font = new Font("Segoe UI", 9F);
    }

    public static Button MakePrimaryButton(string text)
    {
        return new Button
        {
            Text = text,
            BackColor = ThemeColors.ButtonPrimary,
            ForeColor = Color.White,
            Font = new Font("Segoe UI", 11, FontStyle.Bold),
            FlatStyle = FlatStyle.Flat,
            TextAlign = ContentAlignment.MiddleCenter,
        };
    }

    public static Button MakeSecondaryButton(string text)
    {
        return new Button
        {
            Text = text,
            BackColor = ThemeColors.ButtonNeutral,
            ForeColor = ThemeColors.TextPrimary,
            Font = new Font("Segoe UI", 10),
            FlatStyle = FlatStyle.Flat,
            TextAlign = ContentAlignment.MiddleCenter,
        };
    }
}
