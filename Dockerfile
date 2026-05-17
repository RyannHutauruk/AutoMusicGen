FROM mcr.microsoft.com/playwright/python:v1.53.0-jammy

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN playwright install chromium

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "suno_automation.main"]
