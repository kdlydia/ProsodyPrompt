@{
    # SpeechPrint Windows package manifest
    # Used by install_package.ps1 to resolve winget IDs and MFA model names.

    Version = '0.3.0'

    # winget package IDs installed by install_package.ps1
    WingetPackages = @(
        @{ Id = 'Python.Python.3.11'; Name = 'Python 3.11';  Required = $true }
        @{ Id = 'Gyan.FFmpeg';        Name = 'ffmpeg';       Required = $true }
        @{ Id = 'Praat.Praat';        Name = 'Praat';        Required = $true }
        @{ Id = 'Git.Git';            Name = 'Git';          Required = $true }
    )

    # Python packages installed into the SpeechPrint venv
    PythonPackages = @(
        'torch>=2.1'
        'whisperx'
        'montreal-forced-aligner'
        'praat-parselmouth'
        'librosa'
        'scipy'
        'numpy'
        'pandas'
        'matplotlib'
        'pympi-ling'
        'textgrid'
        'soundfile'
    )

    # Language code → MFA acoustic model + dictionary name
    LanguageModels = @{
        en = 'english_mfa'
        de = 'german_mfa'
        it = 'italian_mfa'
        es = 'spanish_mfa'
        fr = 'french_mfa'
        cs = 'czech_mfa'
    }

    # Default install locations
    Paths = @{
        Root      = 'C:\SpeechPrint'
        Python    = 'C:\Python311'
        Venv      = 'C:\SpeechPrint\.venv'
        Bin       = 'C:\SpeechPrint\bin'
        MfaRoot   = 'C:\SpeechPrint\mfa'
        Templates = 'C:\SpeechPrint\share\speechprint\templates'
    }

    # Machine-scope environment variables set by the installer
    EnvironmentVariables = @{
        SPEECHPRINT_ROOT         = 'C:\SpeechPrint'
        MFA_ROOT_DIR             = 'C:\SpeechPrint\mfa'
        WHISPERX_MODEL           = 'large-v3'
        SPEECHPRINT_TEMPLATE_DIR = 'C:\SpeechPrint\share\speechprint\templates'
    }
}
