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
SUNO_EMAIL=you@example.com
SUNO_PASSWORD=supersecret
HEADLESS=false
MAX_RETRIES=3
CONCURRENCY=2
POLL_INTERVAL_SECONDS=8
TIMEOUT_MS=90000
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

## Notes on selectors
Suno UI can change. Update selectors in `suno_automation/services/suno_client.py` as needed.

## Compliance and safety
Use only on accounts you own and in compliance with Suno's Terms of Service.
