#!/usr/bin/env bash
set -e

# Change to the script's directory (repo root)
cd "$(dirname "$0")/.."

if [ -z "$1" ]; then
    echo "Usage: ./commit.sh \"<commit_message>\""
    exit 1
fi

echo "🔍 Validating backend Release build..."
if [ -f *.sln ] || [ -f *.slnx ]; then
    dotnet build --configuration Release
fi

echo "🔄 Running automated version bump..."
if [ -f scripts/bump_version.py ]; then
    python3 scripts/bump_version.py "$1"
fi

echo "💾 Creating atomic commit: '$1'..."
git add -u
git commit -m "$1"
echo "✅ Commit created successfully."
