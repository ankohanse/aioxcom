import asyncio
import logging
import sys

from aioxcom import XcomDiscover

# Setup logging to StdOut
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    # Discover IP address of Xcom-LAN / Moxa
    # Can be usefull to open the Moxa NPort Web Config
    url = await XcomDiscover.discoverMoxaWebConfig()
    if url:
        logger.info(f"Moxa NPort Web Config found at: {url}")
    else:
        logger.info(f"Moxa NPort Web Config not found")


asyncio.run(main())  # main loop
