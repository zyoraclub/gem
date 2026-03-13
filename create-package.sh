#!/bin/bash

# Create a clean distribution package for sharing
# This excludes unnecessary files like node_modules, venv, etc.

echo "📦 Creating distribution package..."

# Get current date for filename
DATE=$(date +%Y%m%d)
PACKAGE_NAME="gem-automation-${DATE}.zip"

# Create zip excluding unnecessary files
cd /Users/redfoxhotels

zip -r "${PACKAGE_NAME}" gem \
    -x "gem/backend/venv/*" \
    -x "gem/backend/__pycache__/*" \
    -x "gem/backend/app/__pycache__/*" \
    -x "gem/backend/app/**/__pycache__/*" \
    -x "gem/backend/*.db" \
    -x "gem/frontend/node_modules/*" \
    -x "gem/frontend/.next/*" \
    -x "gem/.git/*" \
    -x "gem/**/.DS_Store" \
    -x "*.pyc"

echo ""
echo "✅ Package created: ${PACKAGE_NAME}"
echo "📍 Location: /Users/redfoxhotels/${PACKAGE_NAME}"
echo ""
echo "Share this file with your client!"
