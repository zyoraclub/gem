# GEM Portal Automation System

Automated product scraping and management for Government e-Marketplace (GEM).

## Features
- 🔍 Search and scrape products from GEM portal
- 📊 Auto-sync to Google Sheets with price tracking
- 📧 Gmail IMAP integration for OTP reading
- 📈 Statistics dashboard with real-time tracking
- 🔄 Smart upsert - updates existing products, inserts new ones

---

## Quick Setup (For Non-Technical Users)

### Step 1: Install Required Software

**On Mac:**
1. Open Terminal (Press `Cmd + Space`, type "Terminal", press Enter)
2. Copy and paste this command:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
3. Then install Python and Node.js:
```bash
brew install python@3.11 node
```

**On Windows:**
1. Download and install [Python 3.11](https://www.python.org/downloads/) - ✅ Check "Add to PATH" during install
2. Download and install [Node.js](https://nodejs.org/) (LTS version)

---

### Step 2: Run Setup Script

**On Mac/Linux:**
```bash
cd gem
chmod +x setup.sh
./setup.sh
```

**On Windows:**
```cmd
cd gem
setup.bat
```

---

### Step 3: Start the Application

**On Mac/Linux:**
```bash
./start.sh
```

**On Windows:**
```cmd
start.bat
```

Then open your browser and go to: **http://localhost:3000**

---

## Manual Setup (If Scripts Don't Work)

### Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # Mac/Linux
# OR: venv\Scripts\activate   # Windows

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup (in new terminal)
```bash
cd frontend
npm install
npm run dev
```

---

## Configuration

### 1. Google Sheets Integration
1. Open http://localhost:3000/integrations
2. Click "Connect" under Google Sheets
3. Sign in with your Google account
4. Allow permissions

### 2. Gmail IMAP (for OTP reading)
1. Enable 2-Step Verification in your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Create an App Password for "Mail"
4. In the app, go to Integrations → Gmail IMAP
5. Enter your email and the App Password

---

## Usage

### Dashboard (Home Page)
1. **Search** for product categories (e.g., "laptop", "safety shoes")
2. **Add** categories to your scrape list
3. **Select** a Google Sheet to save to
4. **Click Scrape** - products automatically save to sheet

### Automation Page
1. **Select** a sheet with products
2. Data loads automatically
3. Shows price changes and new products

---

## Troubleshooting

### "Command not found" errors
- Make sure Python and Node.js are installed
- Restart your terminal after installation

### "Port already in use"
```bash
# Kill existing processes
pkill -f "uvicorn"
pkill -f "node"
```

### Google Sheets not connecting
- Make sure you're logged into the correct Google account
- Check if the OAuth consent screen is set up in Google Cloud Console

---

## Support
For issues, contact: [your-email@example.com]
