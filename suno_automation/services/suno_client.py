import asyncio
from pathlib import Path
from typing import Optional
from playwright.async_api import BrowserContext, Page

from suno_automation.config import settings
from suno_automation.core.browser import human_pause, human_type
from suno_automation.models.prompt import PromptRow
from suno_automation.models.song import SongResult


class SunoClient:
    def __init__(self, context: BrowserContext, logger):
        self.context = context
        self.logger = logger
        self.page: Optional[Page] = None

    async def init(self) -> None:
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        self.page.set_default_timeout(settings.timeout_ms)

    async def login(self) -> None:
        assert self.page
        await self.page.goto(settings.login_url, wait_until="networkidle")
        if "create" in self.page.url:
            self.logger.info("Already logged in via persistent profile")
            return
        await human_type(self.page, 'input[type="email"]', settings.email)
        await human_pause()
        await human_type(self.page, 'input[type="password"]', settings.password)
        await human_pause()
        await self.page.click('button:has-text("Continue")')
        await self.page.wait_for_url("**/create", timeout=settings.timeout_ms)

    async def generate_song(self, prompt: PromptRow) -> SongResult:
        assert self.page
        await self.page.goto(settings.create_url, wait_until="domcontentloaded")
        await human_pause()
        await self.page.click('button:has-text("Custom Mode")')
        await human_type(self.page, 'textarea[placeholder*="Describe"]', prompt.lyrics)
        await human_type(self.page, 'input[placeholder*="Style"]', prompt.style)
        await self.page.click('button:has-text("Create")')

        result = SongResult(prompt_id=prompt.prompt_id, title=prompt.title, status="queued")
        await self._wait_for_completion(result)
        return result

    async def _wait_for_completion(self, result: SongResult) -> None:
        assert self.page
        for _ in range(120):
            status_locator = self.page.locator("[data-testid='generation-status']").first
            if await status_locator.count() > 0:
                status_text = (await status_locator.inner_text()).lower()
                if "complete" in status_text or "ready" in status_text:
                    result.status = "completed"
                    result.suno_track_id = await self.page.locator("[data-track-id]").first.get_attribute("data-track-id")
                    result.download_url = await self.page.locator("a[href*='download']").first.get_attribute("href")
                    return
                if "failed" in status_text:
                    result.status = "failed"
                    result.error = "generation failed from UI status"
                    return
            await asyncio.sleep(settings.poll_interval_seconds)
        result.status = "timeout"
        result.error = "generation timeout"

    async def download_audio(self, result: SongResult) -> SongResult:
        assert self.page
        if not result.download_url:
            result.status = "failed"
            result.error = "download url missing"
            return result

        target = settings.output_audio_dir / f"{result.prompt_id}_{result.suno_track_id or 'track'}.mp3"
        target.parent.mkdir(parents=True, exist_ok=True)

        async with self.page.expect_download() as download_info:
            await self.page.goto(result.download_url)
        download = await download_info.value
        await download.save_as(str(target))

        result.local_path = Path(target)
        return result
