# Stride — Strava Running Dashboard

A beautiful local dashboard for your Strava running data.
Runs entirely on your Mac — no cloud, no subscription, no data sharing.

---

## What it shows

- **At a Glance** — kilometers and runs this week, month, year, and all time
- **Streaks** — current daily run streak and your longest ever
- **Personal Records** — longest run, fastest 5K pace, fastest 10K pace
- **Trend Charts** — weekly mileage bars + monthly mileage line chart
- **Recent Runs** — your last 10 runs with pace, time, and elevation

---

## Setup (one-time, ~5 minutes)

### Step 1 — Create a Strava API app

1. Go to https://www.strava.com/settings/api (you must be logged in)
2. Fill in the form:
   - Application Name: Stride Dashboard (or anything you like)
   - Category: Data Importer
   - Website: http://localhost:5000
   - Authorization Callback Domain: localhost
3. Click Create
4. Copy your Client ID and Client Secret

### Step 2 — Add your credentials

Open the .env file in this folder (use TextEdit) and replace the placeholders:

    STRAVA_CLIENT_ID=123456
    STRAVA_CLIENT_SECRET=abc123...

Save the file.

### Step 3 — Make the start script executable (first time only)

Open Terminal, navigate to this folder, and run:

    chmod +x start.sh

---

## Running the dashboard

Every time you want to use it, open Terminal and run:

    cd /path/to/strava-dashboard
    ./start.sh

Your browser opens automatically. Click "Connect with Strava", authorize, and your dashboard loads.

To stop: press Ctrl+C in the Terminal window.

---

## Troubleshooting

"Missing Strava credentials" — check your .env file for typos or extra spaces.

"This app isn't verified" on Strava — normal for personal apps. Click Authorize anyway.

Port already in use — run: lsof -i :5000  then: kill -9 <PID>

pip3 not found — install Python from https://python.org or: brew install python

---

## Files

    strava-dashboard/
    ├── app.py      — the main application
    ├── start.sh    — launch script
    ├── .env        — your credentials (keep this private)
    └── README.md   — this file
