#!/bin/bash
# CLEANUP_AND_PUSH.sh
# Removes large files from git history and pushes clean code to GitHub
#
# Usage:
#   chmod +x CLEANUP_AND_PUSH.sh
#   ./CLEANUP_AND_PUSH.sh

set -e

echo "========================================================================"
echo "Git History Cleanup & Push"
echo "========================================================================"
echo ""
echo "This script will:"
echo "  1. Verify git-filter-repo is installed"
echo "  2. Remove large files from git history (356 MB WAV, 173 MB PPTX)"
echo "  3. Force-push cleaned history to GitHub"
echo "  4. Push feature/appendix-d-e-complete branch"
echo ""
echo "⚠️  This rewrites git history (safe with --force-with-lease)"
echo ""

# Check if git-filter-repo is installed
if ! command -v git-filter-repo &> /dev/null; then
    echo "❌ git-filter-repo not found"
    echo ""
    echo "Install with:"
    echo "  Arch Linux: sudo pacman -S git-filter-repo"
    echo "  macOS: brew install git-filter-repo"
    echo "  Ubuntu/Debian: sudo apt install git-filter-repo"
    echo "  Other: pip install git-filter-repo"
    exit 1
fi

echo "✓ git-filter-repo installed"
echo ""

# Create backup branch just in case
BACKUP_BRANCH="backup/before-cleanup-$(date +%s)"
echo "Creating safety backup: $BACKUP_BRANCH"
git branch "$BACKUP_BRANCH"
echo "✓ Backup created (you can delete this after successful push)"
echo ""

# Step 1: Remove large files from history
echo "========================================================================"
echo "Step 1: Removing large files from history"
echo "========================================================================"

echo ""
echo "Removing: meetingwithsupervisor/Sound record*.wav (356 MB)"
git filter-repo --path "meetingwithsupervisor/Sound record*.wav" --invert-paths --force

echo ""
echo "Removing: defense_slides_2026-06-02/*.pptx (173 MB total)"
git filter-repo --path "defense_slides_2026-06-02/*.pptx" --invert-paths --force

echo ""
echo "✓ Large files removed from history"
echo ""

# Step 2: Force push main branch
echo "========================================================================"
echo "Step 2: Force-pushing cleaned main branch"
echo "========================================================================"
echo ""

git push --force-with-lease origin main
if [ $? -eq 0 ]; then
    echo "✓ main branch pushed"
else
    echo "❌ Failed to push main branch"
    echo ""
    echo "Troubleshooting:"
    echo "  - Check your GitHub authentication (SSH key or token)"
    echo "  - Verify you have push permission"
    exit 1
fi

echo ""

# Step 3: Push feature branch
echo "========================================================================"
echo "Step 3: Pushing feature/appendix-d-e-complete branch"
echo "========================================================================"
echo ""

git push -u origin feature/appendix-d-e-complete
if [ $? -eq 0 ]; then
    echo "✓ feature branch pushed"
else
    echo "❌ Failed to push feature branch"
    echo "Retrying..."
    git push origin feature/appendix-d-e-complete --force-with-lease
fi

echo ""
echo "========================================================================"
echo "✅ CLEANUP COMPLETE"
echo "========================================================================"
echo ""
echo "Summary:"
echo "  ✓ Removed 356 MB WAV file from history"
echo "  ✓ Removed 173 MB PPTX files from history"
echo "  ✓ Force-pushed cleaned main branch"
echo "  ✓ Pushed feature/appendix-d-e-complete"
echo ""
echo "Your code is now on GitHub!"
echo ""
echo "Optional cleanup (after verifying GitHub looks good):"
echo "  git branch -d $BACKUP_BRANCH"
echo ""
echo "View on GitHub:"
echo "  https://github.com/kdlydia/ProsodyPrompt/tree/feature/appendix-d-e-complete"
echo ""
