#!/bin/bash
# SpeechPrint - macOS .app bundle builder
# Builds a universal SpeechPrint.app from SpeechPrintGUI.swift

set -euo pipefail

VERSION="${1:-0.3.0}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MACOS_DIR="$REPO_ROOT/macos"
BUILD_DIR="$REPO_ROOT/build/macos"
APP_DIR="$BUILD_DIR/SpeechPrint.app"

echo "Building SpeechPrint.app v$VERSION..."
echo ""

rm -rf "$BUILD_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# ============================================================================
# Info.plist
# ============================================================================

cat > "$APP_DIR/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>SpeechPrint</string>
    <key>CFBundleIdentifier</key>
    <string>org.speechprint.installer</string>
    <key>CFBundleName</key>
    <string>SpeechPrint</string>
    <key>CFBundleDisplayName</key>
    <string>SpeechPrint</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# ============================================================================
# Compile SwiftUI app (universal binary)
# ============================================================================

echo "Compiling SwiftUI app (arm64 + x86_64)..."
swiftc \
    -O \
    -target arm64-apple-macos14.0 \
    -emit-executable \
    -o "$BUILD_DIR/SpeechPrint-arm64" \
    "$MACOS_DIR/SpeechPrintGUI.swift"

swiftc \
    -O \
    -target x86_64-apple-macos14.0 \
    -emit-executable \
    -o "$BUILD_DIR/SpeechPrint-x86_64" \
    "$MACOS_DIR/SpeechPrintGUI.swift"

lipo -create \
    "$BUILD_DIR/SpeechPrint-arm64" \
    "$BUILD_DIR/SpeechPrint-x86_64" \
    -output "$APP_DIR/Contents/MacOS/SpeechPrint"

chmod +x "$APP_DIR/Contents/MacOS/SpeechPrint"

# Verify universal
echo "Verifying binary architectures..."
lipo -info "$APP_DIR/Contents/MacOS/SpeechPrint"

# ============================================================================
# Bundle scripts and templates as Resources
# ============================================================================

echo "Bundling install scripts and templates..."
cp "$REPO_ROOT/linux/scripts/install_deps.sh" "$APP_DIR/Contents/Resources/install_deps.sh"
cp "$REPO_ROOT/linux/scripts/create_corpus.sh" "$APP_DIR/Contents/Resources/create_corpus.sh"
cp -r "$REPO_ROOT/templates" "$APP_DIR/Contents/Resources/templates"
chmod +x "$APP_DIR/Contents/Resources/"*.sh

# ============================================================================
# Done
# ============================================================================

echo ""
echo "✓ Built $APP_DIR"
echo ""
echo "To create a DMG:"
echo "  hdiutil create -volname SpeechPrint -srcfolder $APP_DIR -ov -format UDZO $BUILD_DIR/SpeechPrint-$VERSION.dmg"
