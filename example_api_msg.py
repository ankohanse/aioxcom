import asyncio
from datetime import datetime
import logging
import sys

from aioxcom import XcomApiTcp, XcomData, XcomValues, XcomValuesItem
from aioxcom import XcomVoltage, XcomAggregationType, XcomFormat

# Setup logging to StdOut
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():

    api = XcomApiTcp(4001)    # port number configured in Xcom-LAN/Moxa NPort
    try:
        if not await api.start():
            logger.info(f"Did not connect to Xcom")
            return

        # Retrieve unique guid for this installation
        logger.info(f"")
        logger.info(f"Retrieve unique guid of this installation")

        value = await api.requestGuid()
        logger.info(f"Installation Guid: {value}")

        # Retrieve messages
        logger.info(f"")
        logger.info(f"Retrieve messages")

        # Retrieving message #0 returns the last saved message. 
        # But be aware that it will also erase the flag that there are new messages
        idx = 0
        for idx in range(0, 0xFFFFFFFF):
            msg = await api.requestMessage(idx)
            logger.info(f"msg #{idx} from {msg.source_address} at {datetime.fromtimestamp(msg.timestamp)}: {msg.message_string}")

            if msg.message_total <= 1:
                break

    except Exception as e:
        logger.info(f"Unexpected exception: {e}")

    finally:
        logger.info(f"")
        await api.stop()


asyncio.run(main())  # main loop