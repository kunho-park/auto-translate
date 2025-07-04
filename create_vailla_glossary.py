import asyncio
import logging

from src.translators.vanilla_glossary_builder import create_vanilla_glossary

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_vanilla_glossary_async():
    vanilla_terms = await create_vanilla_glossary(
        output_path="src/assets/vanilla_glossary/ko_kr.json",
        force_rebuild=True,  # 새로 생성
        max_concurrent_requests=15,
        max_retries=5,
        max_entries_per_batch=100,
    )

    print(vanilla_terms)


asyncio.run(create_vanilla_glossary_async())
