#!/bin/bash

# GEM Portal Automation - Setup Script
# Run this once to set up the project

echo "🚀 Setting up GEM Portal Automation..."
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 is not installed!${NC}"
    echo "Please install Python 3.11+ from https://www.python.org/downloads/"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed!${NC}"
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi

echo -e "${GREEN}✅ Python3 found: $(python3 --version)${NC}"
echo -e "${GREEN}✅ Node.js found: $(node --version)${NC}"
echo ""

# Setup Backend
echo -e "${YELLOW}📦 Setting up Backend...${NC}"
cd backend

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << EOF
# Gmail IMAP for OTP fetching
GMAIL_EMAIL=
GMAIL_APP_PASSWORD=

# Google OAuth (Sheets)
GOOGLE_CLIENT_ID=694469542353-lvcig3hqbpjv58274jqcsoht33uibuu0.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=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
GOOGLE_REDIRECT_URI=http://localhost:8000/api/oauth/callback
EOF
fi

cd ..

# Setup Frontend
echo ""
echo -e "${YELLOW}📦 Setting up Frontend...${NC}"
cd frontend

# Install Node dependencies
echo "Installing Node.js dependencies..."
npm install

cd ..

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "To start the application, run:"
echo -e "${YELLOW}  ./start.sh${NC}"
echo ""
echo "Or manually:"
echo "  Terminal 1: cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo "  Terminal 2: cd frontend && npm run dev"
echo ""
echo "Then open http://localhost:3000 in your browser"
