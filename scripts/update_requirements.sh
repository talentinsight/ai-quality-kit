#!/bin/bash

# Script to update requirements.txt with current virtual environment packages
# Usage: ./scripts/update_requirements.sh

set -e

echo "🔄 Updating requirements.txt..."

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "❌ Virtual environment not activated. Please activate .venv first."
    echo "   Run: source .venv/bin/activate"
    exit 1
fi

# Check if we're in the right directory
if [[ ! -f "requirements.txt" ]]; then
    echo "❌ requirements.txt not found. Please run this script from the project root."
    exit 1
fi

# Create backup of current requirements.txt
cp requirements.txt requirements.txt.backup.$(date +%Y%m%d_%H%M%S)
echo "📋 Created backup of current requirements.txt"

# Generate new requirements.txt with pip freeze
echo "📦 Running pip freeze..."
pip freeze > requirements.txt

echo "✅ requirements.txt updated successfully!"
echo "📊 Total packages: $(wc -l < requirements.txt)"

# Optional: Clean up old backup files (keep last 5)
echo "🧹 Cleaning up old backup files..."
ls -t requirements.txt.backup.* | tail -n +6 | xargs -r rm

echo "🎉 Done! requirements.txt has been updated with current package versions."
echo "💡 Tip: Review the file and remove any packages that aren't needed for production."
