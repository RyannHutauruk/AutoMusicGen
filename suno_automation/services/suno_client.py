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
            await self._type_reliably(google_page, email_selector, settings.google_email)
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
            await self._type_reliably(google_page, password_selector, settings.google_password)
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

    async def _type_reliably(self, page: Page, selector: str, text: str) -> None:
        locator = page.locator(selector).first
        await locator.wait_for(state="visible", timeout=settings.timeout_ms)
        await locator.click()
        await page.wait_for_timeout(250)
        await locator.press("Control+A")
        await locator.press("Backspace")
        await page.wait_for_timeout(150)
        await human_type(page, selector, text, click_first=False)

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

    async def _ensure_active_page(self) -> Page:
        if self.page is None or self.page.is_closed():
            open_pages = [p for p in self.context.pages if not p.is_closed()]
            self.page = open_pages[0] if open_pages else await self.context.new_page()
            self.page.set_default_timeout(settings.timeout_ms)
            self.logger.info("Recovered active browser page for continued login/session checks")
        return self.page

    @staticmethod
    def _is_handshake_url(url: str) -> bool:
        u = (url or "").lower()
        return any(token in u for token in ["clerk", "handshake", "sso-callback", "oauth", "accounts.google.com"])

    async def _manual_login_wait(self) -> None:
        assert self.page
        self.logger.warning(
            "Waiting for authenticated Suno session up to %s seconds.",
            settings.manual_login_timeout_seconds,
        )

        deadline = asyncio.get_event_loop().time() + settings.manual_login_timeout_seconds
        sleep_seconds = settings.login_poll_base_seconds

        while asyncio.get_event_loop().time() < deadline:
            page = await self._ensure_active_page()
            current_url = page.url
            if "/create" in current_url:
                return

            # During auth handshake, avoid aggressive reload loops.
            if self._is_handshake_url(current_url):
                self.logger.info("Auth handshake in progress at %s; waiting %.1fs", current_url, sleep_seconds)
                await asyncio.sleep(sleep_seconds)
                sleep_seconds = min(settings.login_poll_max_seconds, sleep_seconds + 1)
                continue

            try:
                await self._safe_goto(settings.create_url)
                if self.page and "/create" in self.page.url:
                    return
            except Exception:
                pass

            await asyncio.sleep(sleep_seconds)
            sleep_seconds = min(settings.login_poll_max_seconds, sleep_seconds + 1)

        raise TimeoutError("Login timeout: session did not reach /create.")

    async def _find_google_auth_page(self) -> Optional[Page]:
        for _ in range(40):
            for page in self.context.pages:
                if "accounts.google.com" in page.url:
                    return page
            await asyncio.sleep(0.5)
        return None

    async def _safe_goto(self, url: str) -> None:
        page = await self._ensure_active_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=settings.timeout_ms)
            await page.wait_for_load_state("load", timeout=min(settings.timeout_ms, 30000))
        except Exception as first_error:  # noqa: BLE001
            self.logger.warning("Primary navigation to %s failed: %s. Retrying with commit state.", url, first_error)
            page = await self._ensure_active_page()
            await page.goto(url, wait_until="commit", timeout=settings.timeout_ms)

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
        await self._safe_goto(settings.create_url)
        await human_pause()

        await self._try_click_any([
            'button:has-text("Custom Mode")',
            'button:has-text("Custom")',
        ])

        desc_selector = await self._first_visible([
            'textarea[placeholder*="Describe" i]',
            'textarea[placeholder*="song" i]',
            'textarea',
        ])
        if not desc_selector:
            raise RuntimeError("Song description input not found on create page")

        await self._type_reliably(self.page, desc_selector, prompt.lyrics)

        if prompt.style:
            style_selector = await self._first_visible([
                'input[placeholder*="Style" i]',
                'input[placeholder*="genre" i]',
            ])
            if style_selector:
                await self._type_reliably(self.page, style_selector, prompt.style)

        clicked_create = await self._click_create_button()
        if not clicked_create:
            raise RuntimeError("Create/Generate button not found or still disabled")

        result = SongResult(prompt_id=prompt.prompt_id, title=prompt.title, status="queued")
        await self._wait_for_completion(result)
        return result

    async def _click_create_button(self) -> bool:
        assert self.page
        candidates = [
            self.page.get_by_role("button", name="Create"),
            self.page.get_by_role("button", name="Generate"),
            self.page.locator('button:has-text("Create")'),
            self.page.locator('button:has-text("Generate")'),
            self.page.locator('button[type="submit"]'),
            self.page.locator('button span:has-text("Create")').locator('xpath=ancestor::button[1]'),
        ]

        # wait up to ~20s for button to appear and become enabled
        for _ in range(20):
            for locator in candidates:
                if await locator.count() == 0:
                    continue
                btn = locator.first
                if not await btn.is_visible():
                    continue
                disabled = await btn.get_attribute("disabled")
                aria_disabled = await btn.get_attribute("aria-disabled")
                if disabled is None and aria_disabled not in {"true", "1"}:
                    await btn.scroll_into_view_if_needed()
                    await btn.click()
                    return True
            await asyncio.sleep(1)

        return False

    async def _wait_for_completion(self, result: SongResult) -> None:
        assert self.page
        max_rounds = 180
        for _ in range(max_rounds):
            # Prefer explicit status labels when available
            status_locator = self.page.locator("[data-testid='generation-status'], [aria-live='polite']").first
            if await status_locator.count() > 0:
                status_text = (await status_locator.inner_text()).lower()
                if "failed" in status_text or "error" in status_text:
                    result.status = "failed"
                    result.error = f"generation failed: {status_text}"
                    return

            # Spinner/progress disappearance heuristic
            active_spinners = self.page.locator(
                "svg.animate-spin, [role='progressbar'], [data-testid*='loading'], [aria-busy='true']"
            )
            spinner_count = await active_spinners.count()

            download_links = self.page.locator("a[href*='download'], button:has-text('Download')")
            has_downloads = await download_links.count() > 0

            if spinner_count == 0 and has_downloads:
                result.status = "completed"
                result.suno_track_id = await self.page.locator("[data-track-id]").first.get_attribute("data-track-id")
                result.download_url = await self.page.locator("a[href*='download']").first.get_attribute("href")
                return

            await asyncio.sleep(settings.poll_interval_seconds)

        result.status = "timeout"
        result.error = "generation timeout (spinner/status did not resolve)"

    async def download_audio(self, result: SongResult) -> SongResult:
        assert self.page

        # Suno usually returns 2 songs per generation; download up to 2 links.
        anchors = self.page.locator("a[href*='download']")
        link_count = await anchors.count()

        if link_count == 0 and result.download_url:
            link_count = 1

        if link_count == 0:
            result.status = "failed"
            result.error = "download url missing"
            return result

        saved_any = False
        for idx in range(min(link_count, 2)):
            href = result.download_url if idx == 0 and result.download_url else await anchors.nth(idx).get_attribute("href")
            if not href:
                continue
            target = settings.output_audio_dir / f"{result.prompt_id}_{result.suno_track_id or 'track'}_{idx+1}.mp3"
            target.parent.mkdir(parents=True, exist_ok=True)

            async with self.page.expect_download() as download_info:
                await self.page.goto(href)
            download = await download_info.value
            await download.save_as(str(target))
            if not saved_any:
                result.local_path = Path(target)
                saved_any = True

        if not saved_any:
            result.status = "failed"
            result.error = "no downloadable files were saved"
        return result
