import asyncio
import random
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, BrowserContext, Page

from suno_automation.config import settings

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


async def human_pause(min_seconds: float = 0.25, max_seconds: float = 1.5) -> None:
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


async def human_type(page: Page, selector: str, text: str, click_first: bool = True) -> None:
    if click_first:
        await page.click(selector)
    for ch in text:
        await page.keyboard.type(ch, delay=random.randint(35, 120))
    await human_pause(0.1, 0.4)


@asynccontextmanager
async def get_context() -> BrowserContext:
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(settings.user_data_dir),
            headless=settings.headless,
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": random.choice([1280, 1366, 1440]), "height": random.choice([768, 900, 960])},
            locale="en-US",
            timezone_id="America/New_York",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        try:
            yield context
        finally:
            await context.close()
