import asyncio
import logging
import sys

from aioxcom import XcomApiTcp, XcomDeviceFamilies, XcomDataset, VOLTAGE

# Setup logging to StdOut
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    dataset = XcomDataset.create(VOLTAGE.AC240) # or use VOLTAGE.AC120
    api     = XcomApiTcp(4001)    # port number configured in Xcom-LAN/Moxa NPort

    try:
        if not await api.start():
            logger.info(f"Did not connect to Xcom")
            return

        for family in XcomDeviceFamilies.getList():
            logger.info(f"Discover devices for family {family.id} ({family.model})")

            # Get value for the specific discovery nr, or otherwise the first info nr or first param nr
            nr = family.nrDiscover or family.nrInfosStart or family.nrParamsStart or None
            if not nr:
                continue

            # Iterate all addresses in the family, up to the first address that is not found
            for device_addr in range(family.addrDevicesStart, family.addrDevicesEnd+1):

                device_code = family.getCode(device_addr)

                # Send the test request to the device. This will return False in case:
                # - the device does not exist (DEVICE_NOT_FOUND)
                # - the device does not support the param (INVALID_DATA), used to distinguish BSP from BMS
                try:
                    param = dataset.getByNr(nr, family.idForNr)

                    value = await api.requestValue(param, device_addr)
                    if value is not None:
                        logger.info(f"Found device {device_code} via {nr}:{device_addr}")

                except Exception as e:
                    logger.debug(f"No device {device_code}; no test value returned from Xcom client: {e}")

                    # Do not test further device addresses in this family
                    break

    finally:
        await api.stop()
        dataset = None


asyncio.run(main())  # main loop
