import asyncio
import logging
import sys

from aioxcom import XcomApiTcp, XcomDataset, VOLTAGE

# Setup logging to StdOut
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    dataset = XcomDataset.create(VOLTAGE.AC240) # or use VOLTAGE.AC120
    info_3023 = dataset.getByNr(3023, "xt")  # the "xt" part is optional but usefull for detecting mistakes
    info_6001 = dataset.getByNr(6001, "bsp")
    param_1107 = dataset.getByNr(1107, "xt")
    dataset = None  # Release memory of the dataset

    api = XcomApiTcp(4001)    # port number configured in Xcom-LAN/Moxa NPort
    try:
        if not await api.start():
            logger.info(f"Did not connect to Xcom")
            return

        # Retrieve info #3023 from the first Xtender (Output power)
        value = await api.requestValue(info_3023, "XT1")    # xt address range is 101 to 109, or use "XT1" to "XT9"
        logger.info(f"XT1 3023: {value} {info_3023.unit} ({info_3023.name})")

        # Retrieve param #6001 from BSP (Nominal capacity)
        value = await api.requestValue(info_6001, "BSP")    # bsp address range is only 601, or use "BSP"
        logger.info(f"BSP 6001: {value} {info_6001.unit} ({info_6001.name})")

        # Update param 1107 on the first Xtender (Maximum current of AC source)
        value = 4.0    # 4 Ampere
        if await api.updateValue(param_1107, value, "XT1"):
            logger.info(f"XT1 1107 updated to {value} {param_1107.unit} ({param_1107.name})")

    finally:
        await api.stop()


asyncio.run(main())  # main loop