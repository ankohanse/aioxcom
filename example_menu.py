import asyncio
import logging
import sys

from aioxcom import XcomDataset, XcomVoltage, XcomFormat

# Setup logging to StdOut
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    # Print entire menu structure
    dataset = await XcomDataset.create(XcomVoltage.AC240) # or use XcomVoltage.AC120

    # Helper function to recursively print the entire menu
    async def printMenu(parent, indent=""):
        items = dataset.getMenuItems(parent)
        for item in items:
            logger.info(f"{indent}{item.nr}: {item.name}")

            if item.format == XcomFormat.MENU:
                await printMenu(item.nr, indent+"  ")

    await printMenu(0)
    dataset = None  # Release memory of the dataset


asyncio.run(main())  # main loop