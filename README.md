# Suno AI Browser Automation (Python + Playwright)

Production-oriented async browser automation framework for Suno song generation workflows.

## Features
- Async orchestration with retries
- Persistent Playwright browser session
- CSV prompt ingestion
- Song generation polling
- Audio download and metadata export
- Human-like typing and random delays
- Anti-detection hardening basics
- Dockerized and Ubuntu VPS friendly

## Project Structure
```text
.
├── Dockerfile
├── README.md
├── requirements.txt
└── suno_automation
    ├── config.py
    ├── main.py
    ├── core
    │   └── browser.py
    ├── data
    │   └── prompts.csv
    ├── logs
    ├── models
    │   ├── prompt.py
    │   └── song.py
    ├── output
    │   ├── audio
    │   └── metadata
    ├── services
    │   ├── csv_loader.py
    │   ├── metadata_store.py
    │   └── suno_client.py
    └── utils
        └── logger.py
```

## Setup (Ubuntu/VPS)
```bash
sudo apt update
sudo apt install -y python3 python3-pip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Environment
Create `.env` in project root:
```env
SUNO_LOGIN_METHOD=google
SUNO_EMAIL=you@example.com
SUNO_PASSWORD=supersecret
SUNO_GOOGLE_EMAIL=you@gmail.com
SUNO_GOOGLE_PASSWORD=app_or_account_password
HEADLESS=false
MAX_RETRIES=3
CONCURRENCY=2
POLL_INTERVAL_SECONDS=8
TIMEOUT_MS=90000
MANUAL_LOGIN_TIMEOUT_SECONDS=180
```

## Run
```bash
python -m suno_automation.main
```

## Docker
```bash
docker build -t suno-automation .
docker run --rm -it \
  -v $(pwd)/suno_profile:/app/suno_profile \
  -v $(pwd)/suno_automation/output:/app/suno_automation/output \
  --env-file .env \
  suno-automation
```

## Login flow note
Default login mode is Google (`SUNO_LOGIN_METHOD=google`). The client clicks `Continue with Google`, completes Google email/password steps in the auth window, and then returns to Suno.

If Google auth UI changes (or prompts 2FA/captcha), automation falls back to manual login wait mode until `/create` is reached.

Set `SUNO_LOGIN_METHOD=email` to use the direct email/password flow.

## Notes on selectors
Suno UI can change. Update selectors in `suno_automation/services/suno_client.py` as needed.


## Troubleshooting
- If `Page.goto` to Suno times out, the client now uses resilient navigation (`domcontentloaded` then `commit` retry) instead of strict `networkidle`.
- If your network is slow, increase `TIMEOUT_MS` (for example `TIMEOUT_MS=180000`).

## Compliance and safety
Use only on accounts you own and in compliance with Suno's Terms of Service.
