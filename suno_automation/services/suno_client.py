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
        await self._safe_goto(settings.login_url)
        if await self._is_logged_in():
            self.logger.info("Already logged in via persistent profile")
            return

        if settings.login_method == "google":
            await self._safe_goto(settings.login_url)
            await self._login_with_google()
        else:
            await self._login_with_email()

        await self._manual_login_wait()

    async def _login_with_google(self) -> None:
        assert self.page
        clicked_google = await self._click_google_login_entry()
        if not clicked_google:
            raise RuntimeError("Required login step missing: could not click 'Continue with Google' on /sign-in")

        await human_pause(1.0, 2.0)

        google_page = await self._find_google_auth_page()
        if not google_page:
            # Same-tab Google flow is common on some browsers/settings.
            if "accounts.google.com" in self.page.url or await self._first_visible_on_page(
                self.page,
                ['input[type="email"]', 'input[name="identifier"]', 'input[autocomplete="username"]'],
            ):
                self.logger.info("Google auth is running in same tab; continuing on primary page.")
                google_page = self.page
            else:
                self.logger.info("Google auth popup not detected. Flow may be already authorized.")
                return

        email_selector = await self._first_visible_on_page(
            google_page,
            [
                'input[type="email"]',
                'input[name="identifier"]',
                'input[autocomplete="username"]',
            ],
        )
        if email_selector:
            await human_type(google_page, email_selector, settings.google_email)
            await self._try_click_any_on_page(google_page, ['button:has-text("Next")', '#identifierNext'])
            await human_pause(1.0, 2.2)

        password_selector = await self._first_visible_on_page(
            google_page,
            [
                'input[type="password"]',
                'input[name="Passwd"]',
                'input[autocomplete="current-password"]',
            ],
        )
        if password_selector:
            await human_type(google_page, password_selector, settings.google_password)
            await self._try_click_any_on_page(google_page, ['button:has-text("Next")', '#passwordNext'])
            await human_pause(1.0, 2.0)

    async def _click_google_login_entry(self) -> bool:
        assert self.page

        if self.page.is_closed():
            self.logger.warning("Login page was closed unexpectedly; reopening sign-in page.")
            self.page = await self.context.new_page()
            self.page.set_default_timeout(settings.timeout_ms)
            await self._safe_goto(settings.login_url)

        # Give client-rendered auth buttons time to mount.
        await self.page.wait_for_timeout(2500)

        role_candidates = [
            self.page.get_by_role("button", name="Continue with Google"),
            self.page.get_by_role("button", name="Sign in with Google"),
            self.page.get_by_role("button", name="Google"),
            self.page.get_by_role("link", name="Continue with Google"),
            self.page.get_by_role("link", name="Sign in with Google"),
        ]
        for locator in role_candidates:
            if await locator.count() > 0 and await locator.first.is_visible():
                text = await locator.first.inner_text()
                self.logger.info("Clicking Google entry by role: %s", text.strip())
                await locator.first.click()
                return True


        text_candidates = [
            self.page.locator("button", has_text="Continue with Google"),
            self.page.locator("button", has_text="Google"),
            self.page.locator("a", has_text="Continue with Google"),
            self.page.locator("span", has_text="Continue with Google"),
        ]
        for locator in text_candidates:
            if await locator.count() > 0 and await locator.first.is_visible():
                self.logger.info("Clicking Google entry by text locator")
                await locator.first.click()
                return True

        # Strict fallback: only selectors that contain Google text.
        fallback_clicked = await self._try_click_any([
            'button:has-text("Continue with Google")',
            'button:has-text("Sign in with Google")',
            'button:has-text("Google")',
            'a:has-text("Continue with Google")',
            'a:has-text("Sign in with Google")',
            'a:has-text("Google")',
            'span:has-text("Continue with Google")',
        ])
        if fallback_clicked:
            return True

        # Helpful diagnostics for runtime debugging.
        try:
            html = await self.page.content()
            Path("suno_automation/logs").mkdir(parents=True, exist_ok=True)
            Path("suno_automation/logs/login_debug.html").write_text(html, encoding="utf-8")
            await self.page.screenshot(path="suno_automation/logs/login_debug.png", full_page=True)
            self.logger.warning("Saved login debug artifacts: suno_automation/logs/login_debug.html and .png")
        except Exception as debug_error:  # noqa: BLE001
            self.logger.warning("Failed to capture login debug artifacts: %s", debug_error)

        return False

    async def _login_with_email(self) -> None:
        assert self.page
        email_inputs = [
            'input[type="email"]',
            'input[name="email"]',
            'input[placeholder*="email" i]',
        ]

        await self._try_click_any([
            'button:has-text("Continue with email")',
            'button:has-text("Continue with Email")',
            'button:has-text("Sign in with email")',
            'button:has-text("Use email")',
            'a:has-text("Continue with email")',
            'a:has-text("Sign in with email")',
        ])
        await human_pause(0.5, 1.4)

        email_selector = await self._first_visible(email_inputs)
        if not email_selector:
            return

        await human_type(self.page, email_selector, settings.email)
        await human_pause()

        await self._try_click_any([
            'button:has-text("Continue")',
            'button:has-text("Next")',
            'button:has-text("Sign in")',
            'button[type="submit"]',
        ])
        await human_pause(0.8, 1.8)

        password_selector = await self._first_visible([
            'input[type="password"]',
            'input[name="password"]',
            'input[placeholder*="password" i]',
        ])

        if password_selector:
            await human_type(self.page, password_selector, settings.password)
            await human_pause()
            await self._try_click_any([
                'button:has-text("Continue")',
                'button:has-text("Sign in")',
                'button[type="submit"]',
            ])

    async def _manual_login_wait(self) -> None:
        assert self.page
        self.logger.warning(
            "Waiting for authenticated Suno session up to %s seconds.",
            settings.manual_login_timeout_seconds,
        )

        deadline = asyncio.get_event_loop().time() + settings.manual_login_timeout_seconds
        while asyncio.get_event_loop().time() < deadline:
            if "/create" in self.page.url:
                return
            try:
                await self._safe_goto(settings.create_url)
                if "/create" in self.page.url:
                    return
            except Exception:
                pass
            await asyncio.sleep(2)

        raise TimeoutError("Login timeout: session did not reach /create.")

    async def _find_google_auth_page(self) -> Optional[Page]:
        for _ in range(40):
            for page in self.context.pages:
                if "accounts.google.com" in page.url:
                    return page
            await asyncio.sleep(0.5)
        return None

    async def _safe_goto(self, url: str) -> None:
        assert self.page
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=settings.timeout_ms)
            await self.page.wait_for_load_state("load", timeout=min(settings.timeout_ms, 30000))
        except Exception as first_error:  # noqa: BLE001
            self.logger.warning("Primary navigation to %s failed: %s. Retrying with commit state.", url, first_error)
            await self.page.goto(url, wait_until="commit", timeout=settings.timeout_ms)

    async def _is_logged_in(self) -> bool:
        assert self.page
        if "/create" in self.page.url:
            return True
        try:
            await self._safe_goto(settings.create_url)
            return "/create" in self.page.url
        except Exception:  # noqa: BLE001
            return False

    async def _try_click_any(self, selectors: list[str]) -> bool:
        assert self.page
        return await self._try_click_any_on_page(self.page, selectors)

    async def _try_click_any_on_page(self, page: Page, selectors: list[str]) -> bool:
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() > 0 and await locator.is_visible():
                await locator.click()
                return True
        return False

    async def _first_visible(self, selectors: list[str]) -> Optional[str]:
        assert self.page
        return await self._first_visible_on_page(self.page, selectors)

    async def _first_visible_on_page(self, page: Page, selectors: list[str]) -> Optional[str]:
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() > 0 and await locator.is_visible():
                return selector
        return None

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
