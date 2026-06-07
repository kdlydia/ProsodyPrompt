# SpeechPrint - Windows installer build script
# Builds a self-contained single-file SpeechPrint.exe via `dotnet publish`.

param(
    [string]$Version = "0.3.0",
    [string]$Configuration = "Release",
    [string]$Runtime = "win-x64"
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "  [err] $msg" -ForegroundColor Red }

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Resolve-Path (Join-Path $scriptDir "..\..")
$projDir   = Join-Path $repoRoot "windows\SpeechPrint"
$projFile  = Join-Path $projDir "SpeechPrint.csproj"
$buildDir  = Join-Path $repoRoot "build\windows"
$publishDir = Join-Path $buildDir "publish"

if (-not (Test-Path $projFile)) {
    Write-Err "Project not found: $projFile"
    exit 1
}

# ----------------------------------------------------------------------------
# Check prerequisites
# ----------------------------------------------------------------------------

Write-Step "Checking prerequisites..."
$dotnet = Get-Command dotnet -ErrorAction SilentlyContinue
if (-not $dotnet) {
    Write-Err "dotnet SDK 8.0+ is required. Install from https://dotnet.microsoft.com/download"
    exit 1
}
$dotnetVersion = & dotnet --version
Write-OK "dotnet $dotnetVersion"

# ----------------------------------------------------------------------------
# Clean previous build
# ----------------------------------------------------------------------------

Write-Step "Cleaning previous build..."
if (Test-Path $buildDir) {
    Remove-Item -Recurse -Force $buildDir
}
New-Item -ItemType Directory -Force -Path $publishDir | Out-Null
Write-OK "Build directory cleaned"

# ----------------------------------------------------------------------------
# Publish
# ----------------------------------------------------------------------------

Write-Step "Building SpeechPrint.exe (Configuration=$Configuration, Runtime=$Runtime)..."
& dotnet publish $projFile `
    -c $Configuration `
    -r $Runtime `
    --self-contained true `
    /p:PublishSingleFile=true `
    /p:IncludeNativeLibrariesForSelfExtract=true `
    /p:Version=$Version `
    -o $publishDir

if ($LASTEXITCODE -ne 0) {
    Write-Err "dotnet publish failed"
    exit $LASTEXITCODE
}
Write-OK "Build complete"

# ----------------------------------------------------------------------------
# Stage final output
# ----------------------------------------------------------------------------

$exe = Get-ChildItem -Path $publishDir -Filter "SpeechPrint.exe" -Recurse | Select-Object -First 1
if (-not $exe) {
    Write-Err "SpeechPrint.exe not found in publish output"
    exit 1
}

$finalName = "SpeechPrint-$Version.exe"
$finalPath = Join-Path $buildDir $finalName
Copy-Item -Force $exe.FullName $finalPath

$size = (Get-Item $finalPath).Length
$sizeMB = [math]::Round($size / 1MB, 2)

Write-Host ""
Write-Host "============================================="
Write-Host "  SpeechPrint Installer Built!" -ForegroundColor Green
Write-Host "============================================="
Write-Host ""
Write-Host "  File : $finalPath"
Write-Host "  Size : $sizeMB MB"
Write-Host ""
Write-Host "Hash (SHA-256):"
Get-FileHash -Algorithm SHA256 $finalPath | Select-Object -ExpandProperty Hash
Write-Host ""
Write-Host "To install on a target machine:"
Write-Host "  1. Copy $finalName"
Write-Host "  2. Right-click → Run as administrator"
Write-Host "  3. Follow the GUI prompts"
Write-Host ""

exit 0
