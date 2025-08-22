import asyncio
import logging
import sys

from aioxcom import XcomApiTcp, XcomDataset, XcomDatapoint
from aioxcom import VOLTAGE, SCOM_AGGREGATION_TYPE
from aioxcom.xcom_protocol import XcomData

# Setup logging to StdOut
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    dataset = await XcomDataset.create(VOLTAGE.AC240) # or use VOLTAGE.AC120
    info_3021 = dataset.getByNr(3021, "xt")  # the "xt" part is optional but usefull for detecting mistakes
    info_3022 = dataset.getByNr(3022, "xt")
    info_3023 = dataset.getByNr(3023, "xt")
    info_7002 = dataset.getByNr(7002, "bsp")
    param_5012 = dataset.getByNr(5012, "rcc")
    param_1107 = dataset.getByNr(1107, "xt")

    api = XcomApiTcp(4001)    # port number configured in Xcom-LAN/Moxa NPort
    try:
        if not await api.start():
            logger.info(f"Did not connect to Xcom")
            return

        # Retrieve info #3023 from the first Xtender (Output power)
        value = await api.requestValue(info_3023, "XT1")    # xt address range is 101 to 109, or use "XT1" to "XT9"
        logger.info(f"XT1 {info_3023.nr}: {value} {info_3023.unit} ({info_3023.name})")

        # Retrieve info #7002 from BSP (State of Charge)
        value = await api.requestValue(info_7002, "BSP")    # bsp address range is only 601, or use "BSP"
        logger.info(f"BSP {info_7002.nr}: {value} {info_7002.unit} ({info_7002.name})")

        # Retrieve param #5012 from RCC (User Level)
        value = await api.requestValue(param_5012, "RCC")    # rcc address range is only 501, or use "RCC"
        logger.info(f"RCC {param_5012.nr}: {param_5012.enum_value(value)} ({param_5012.name})")

        # Retrieve multiple params in one call. Note this will fail for some older Xcom-232i firmware versions
        try:
            props: list[XcomDatapoint,str] = [
                (info_3021, SCOM_AGGREGATION_TYPE.MASTER),      # pass an aggregation_type constant
                (info_3022, "XT1"),                             # alternatively pass a device code
                (info_3023, 101),                               # alternatively pass a device address
            ]
            values = await api.requestValues(props)
            if values:
                for (info,aggr,val) in values:
                    logger.info(f"Multi-info {info.nr}: {val} {info.unit} ({info.name}), aggregate_type={aggr}")

        except Exception as ex:
            logger.warning(ex)

        # Retrieve and Update param 1107 on the first Xtender (Maximum current of AC source)
        value = await api.requestValue(param_1107, "XT1")
        logger.info(f"XT1 {param_1107.nr}: {value} {param_1107.unit} ({param_1107.name})")

        value = 3.0    # 4 Ampere
        if await api.updateValue(param_1107, value, "XT1"):
            logger.info(f"XT1 {param_1107.nr} updated to {value} {param_1107.unit} ({param_1107.name})")

        # Retrieve unique guid for this installation
        value = await api.requestGuid()
        logger.info(f"Installation Guid: {value}")

    except Exception as e:
        logger.info(f"Unexpected exception: {e}")

    finally:
        await api.stop()


asyncio.run(main())  # main loop