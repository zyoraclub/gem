#!/bin/bash

# GEM Portal Automation - Enable Auto-Start on Mac
# This creates a LaunchAgent to start on login

echo "Setting up auto-start for GEM Portal Automation..."
echo ""

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.gem.automation"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$HOME/Library/LaunchAgents"

# Create the plist file
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${SCRIPT_DIR}/start.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>StandardOutPath</key>
    <string>${SCRIPT_DIR}/logs/autostart.log</string>
    <key>StandardErrorPath</key>
    <string>${SCRIPT_DIR}/logs/autostart-error.log</string>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
EOF

# Create logs directory
mkdir -p "$SCRIPT_DIR/logs"

# Load the LaunchAgent
launchctl load "$PLIST_PATH" 2>/dev/null

echo ""
echo "✅ Auto-start enabled!"
echo ""
echo "The application will now start automatically when you log in to Mac."
echo ""
echo "To disable auto-start, run: ./disable-autostart.sh"
echo ""
