import asyncio
import logging
import sys

from aioxcom import XcomApiTcp, XcomDataset, XcomDiscover, VOLTAGE

# Setup logging to StdOut
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    api     = XcomApiTcp(4001)    # port number configured in Xcom-LAN/Moxa NPort
    dataset = await XcomDataset.create(VOLTAGE.AC240) # or use VOLTAGE.AC120

    try:
        if not await api.start():
            logger.info(f"Did not connect to Xcom")
            return
        
        helper = XcomDiscover(api, dataset)
        devices = await helper.discoverDevices(getExtendedInfo=True)

        for device in devices:
            logger.info(f"Discovered {device}")

    finally:
        await api.stop()
        dataset = None


asyncio.run(main())  # main loop
