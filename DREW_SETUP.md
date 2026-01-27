# Drew's Setup Guide

Quick setup guide to get MatchForge running on your PC.

---

## Step 1: Install WSL (Windows Subsystem for Linux)

Open **PowerShell as Administrator** and run:

```powershell
wsl --install
```

Restart your PC when prompted. After restart, Ubuntu will open and ask you to create a username/password.

---

## Step 2: Install Required Tools in WSL

Open WSL (type `wsl` in Windows search) and run these commands:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install python3 python3-pip python3-venv git -y

# Install Node.js (needed for Claude Code)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install nodejs -y

# Install Claude Code
npm install -g @anthropic-ai/claude-code
```

---

## Step 3: Clone the Project

```bash
# Go to home directory
cd ~

# Clone the repo
git clone https://github.com/jerm71279/matchforge.git

# Enter project folder
cd matchforge
```

---

## Step 4: Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Step 5: Run the App

```bash
# Make sure venv is activated
source venv/bin/activate

# Run the app (no database needed)
SKIP_DB=true uvicorn app.main:app --port 8001 --reload
```

Open your browser to: **http://localhost:8001/demo**

Login: `demo@matchforge.com` / `DemoPass123`

---

## Step 6: Start Claude Code (for AI assistance)

Open a **new WSL terminal** (keep the app running in the first one):

```bash
cd ~/matchforge
claude
```

Claude can help you:
- Understand the code
- Make changes
- Fix bugs
- Add features

To resume a previous Claude session:
```bash
claude -r
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Open WSL | Type `wsl` in Windows search |
| Go to project | `cd ~/matchforge` |
| Activate Python env | `source venv/bin/activate` |
| Run app | `SKIP_DB=true uvicorn app.main:app --port 8001 --reload` |
| Stop app | Press `Ctrl+C` |
| Start Claude | `claude` |
| Resume Claude session | `claude -r` |

---

## Project Structure (Key Files)

```
matchforge/
├── demo.html              # Main demo UI (edit this for frontend changes)
├── app/
│   ├── api/
│   │   ├── jobs.py        # Job search, matching, skill gaps
│   │   ├── coaching.py    # AI coach, chat
│   │   └── auth.py        # Login, profile
│   └── services/
│       ├── job_matcher.py        # Matching algorithm
│       ├── skill_gap_analyzer.py # Skill gap analysis
│       └── coach_assistant.py    # AI coach logic
├── business_plan/
│   ├── MatchForge_Business_Plan_Verified.docx
│   └── MatchForge_Presentation.pptx
└── README.md              # Full documentation
```

---

## Making Changes

1. Edit files using Claude or any text editor
2. Save your changes
3. If the app is running with `--reload`, changes auto-refresh
4. Test in browser at http://localhost:8001/demo

To commit your changes:

```bash
git add .
git commit -m "Description of what you changed"
git push
```

---

## Need Help?

Just ask Claude! Start with:
```bash
cd ~/matchforge
claude
```

Then describe what you want to do, like:
- "Show me how the job matching works"
- "Add a new field to the profile form"
- "Fix the bug where..."

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `command not found: uvicorn` | Run `source venv/bin/activate` first |
| Port 8001 already in use | Kill other process or use `--port 8002` |
| Can't push to GitHub | Make sure you're added as collaborator |
| Module not found | Run `pip install -r requirements.txt` |

