from common.config import log  # noqa: F401
from common.utils.todo.work_dev import work_dev_from
import logging
logger = logging.getLogger(__name__)

async def main():
    result = await work_dev_from('cli')
    logger.info(result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
