import asyncio
import logging
import sys

from aioxcom import XcomDataset, VOLTAGE, FORMAT

# Setup logging to StdOut
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    # Print entire menu structure
    dataset = await XcomDataset.create(VOLTAGE.AC240) # or use VOLTAGE.AC120

    # Helper function to recursively print the entire menu
    async def printMenu(parent, indent=""):
        items = dataset.getMenuItems(parent)
        for item in items:
            logger.info(f"{indent}{item.nr}: {item.name}")

            if item.format == FORMAT.MENU:
                await printMenu(item.nr, indent+"  ")

    await printMenu(0)
    dataset = None  # Release memory of the dataset


asyncio.run(main())  # main loop