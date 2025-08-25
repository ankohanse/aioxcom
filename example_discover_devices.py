import asyncio
from dataclasses import asdict
import logging
import sys

from aioxcom import XcomApiTcp, XcomDataset, XcomDiscover, XcomVoltage

# Setup logging to StdOut
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    # Discover all Xcom devices
    api     = XcomApiTcp(4001)    # port number configured in Xcom-LAN/Moxa NPort
    dataset = await XcomDataset.create(XcomVoltage.AC240) # or use XcomVoltage.AC120

    try:
        if not await api.start():
            logger.info(f"Did not connect to Xcom")
            return
        
        helper = XcomDiscover(api, dataset)

        # Discover Xcom client info
        client_info = await helper.discoverClientInfo()

        logger.info(f"\n\n")
        logger.info(f"Discovered {client_info}")

        # Discover Xcom devices
        devices = await helper.discoverDevices(getExtendedInfo=True, verbose=False)

        logger.info(f"\n\n")
        for device in devices:
            logger.info(f"Discovered {device}")

        # Log diagnostic information
        diag = await api.getDiagnostics()
        logger.info(f"Diagnostics: {diag}")

    finally:
        await api.stop()
        dataset = None


asyncio.run(main())  # main loop
