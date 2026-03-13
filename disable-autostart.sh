#!/bin/bash

# GEM Portal Automation - Disable Auto-Start on Mac
# This removes the LaunchAgent

echo "Disabling auto-start for GEM Portal Automation..."
echo ""

PLIST_NAME="com.gem.automation"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

if [ -f "$PLIST_PATH" ]; then
    # Unload the LaunchAgent
    launchctl unload "$PLIST_PATH" 2>/dev/null
    
    # Remove the plist file
    rm "$PLIST_PATH"
    
    echo "✅ Auto-start disabled!"
    echo ""
    echo "The application will no longer start automatically."
else
    echo "Auto-start was not enabled."
fi

echo ""
