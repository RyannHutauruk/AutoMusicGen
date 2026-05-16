import asyncio
from typing import List

from suno_automation.config import settings
from suno_automation.core.browser import get_context
from suno_automation.models.song import SongResult
from suno_automation.services.csv_loader import CSVLoader
from suno_automation.services.metadata_store import MetadataStore
from suno_automation.services.suno_client import SunoClient
from suno_automation.utils.logger import setup_logger


async def process_prompt(client: SunoClient, prompt, logger) -> SongResult:
    attempt = 0
    last = SongResult(prompt_id=prompt.prompt_id, title=prompt.title, status="failed")
    while attempt < settings.max_retries:
        attempt += 1
        try:
            logger.info("Generating %s (attempt %s)", prompt.prompt_id, attempt)
            result = await client.generate_song(prompt)
            result.attempts = attempt
            if result.status != "completed":
                raise RuntimeError(result.error or result.status)
            result = await client.download_audio(result)
            if result.local_path:
                return result
            raise RuntimeError(result.error or "download failed")
        except Exception as exc:  # noqa: BLE001
            last = SongResult(
                prompt_id=prompt.prompt_id,
                title=prompt.title,
                status="failed",
                attempts=attempt,
                error=str(exc),
            )
            logger.warning("Prompt %s failed attempt %s: %s", prompt.prompt_id, attempt, exc)
            await asyncio.sleep(3)
    return last


async def run() -> None:
    logger = setup_logger()
    prompts = CSVLoader.load_prompts(settings.csv_path)
    logger.info("Loaded %s prompts", len(prompts))

    async with get_context() as context:
        client = SunoClient(context=context, logger=logger)
        await client.init()
        await client.login()

        semaphore = asyncio.Semaphore(settings.concurrency)
        results: List[SongResult] = []

        async def worker(prompt):
            async with semaphore:
                results.append(await process_prompt(client, prompt, logger))

        await asyncio.gather(*(worker(p) for p in prompts))

    metadata_file = MetadataStore.save_json(results, settings.output_metadata_dir)
    logger.info("Saved metadata to %s", metadata_file)


if __name__ == "__main__":
    asyncio.run(run())
