"""xcom_api_serial.py: communication api to Studer Xcom via serial port."""

import asyncio
import binascii
import logging
import serial_asyncio

from .xcom_api_base import (
    XcomApiBase,
    XcomApiReadException,
    XcomApiTimeoutException,
    XcomApiWriteException,
)
from .xcom_protocol import (
    XcomPackage,
)


_LOGGER = logging.getLogger(__name__)


DEFAULT_PORT = 'COM3'   # For Windows, or '/dev/ttyUSB0' for Linux
DEFAULT_BAUDRATE = 115200
DEFAULT_DATA_BITS = 8
DEFAULT_STOP_BITS = serial_asyncio.serial.STOPBITS_ONE
DEFAULT_PARITY = serial_asyncio.serial.PARITY_NONE
START_TIMEOUT = 30 # seconds
STOP_TIMEOUT = 5
REQ_TIMEOUT = 3

SERIAL_TERMINATOR = b'\x0D\x0A' # from Studer Xcom documentation


##
## Class implementing Xcom-RS232i serial protocol
##
class XcomApiSerial(XcomApiBase):

    def __init__(self, port=DEFAULT_PORT, baudrate=DEFAULT_BAUDRATE):
        """
        Initialize a new XcomApiSerial object.
        """
        super().__init__()

        self.localPort = port
        self.baudrate = baudrate
        self._serial = None
        self._reader = None
        self._writer = None
        self._started = False
        self._connected = False
        self._remote_ip = None

        self._sendPackageLock = asyncio.Lock() # to make sure _sendPackage is never called concurrently


    async def start(self, timeout=START_TIMEOUT, loop=None) -> bool:
        """
        Start the serial connection to the Xcom-RS232i client.
        """
        if not self._started:
            _LOGGER.info(f"Xcom-RS232i serial connection start via {self.localPort}")

            # Open serial connection. Maybe need to set parity, stopbits, etc as well...
            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                loop = loop,
                url=self.localPort, 
                baudrate=self.baudrate,
                bytesize = DEFAULT_DATA_BITS,
                stopbits = DEFAULT_STOP_BITS,
                parity = DEFAULT_PARITY
            )
            self._started = True

            # Seems to work better if we wait a short moment before we start communication
            await asyncio.sleep(1)
            self._connected = True
        else:
            _LOGGER.info(f"Xcom-RS232i serial connection already listening via {self.localPort}")
        
        return True


    async def stop(self):
        """
        Stop listening to the the Xcom Client and stop the Xcom Server.
        """
        _LOGGER.info(f"Stopping Xcom-RS232i serial connection")
        try:
            self._connected = False

            # Close the writer; we do not need to close the reader
            if self._writer:
                self._writer.close()
                await asyncio.sleep(1)
                #await self._writer.wait_closed()
    
        except Exception as e:
            _LOGGER.warning(f"Exception during closing of Xcom writer: {e}")

        self._reader = None
        self._writer = None
        self._started = False
        _LOGGER.info(f"Stopped Xcom-RS232i serial Connection")
    

    async def _sendPackage(self, request: XcomPackage, timeout=REQ_TIMEOUT, verbose=False) -> XcomPackage | None:
        """
        Send an Xcom package from Server to Client and wait for the response (or timeout).
        Throws:
            XcomApiWriteException
            XcomApiReadException
            XcomApiTimeoutException
        """
        if not self._connected:
            _LOGGER.warning(f"_sendPackage - not connected")
            return None
        
        async with self._sendPackageLock:
            # Send the request package to the Xcom client
            try:
                data = request.getBytes()
                if verbose:
                    _LOGGER.debug(f"send {len(data)} bytes ({binascii.hexlify(data).decode('ascii')}), decoded: {request}")

                self._writer.write(data)

            except Exception as e:
                msg = f"Exception while sending request package to Xcom client: {e}"
                raise XcomApiWriteException(msg) from None

            # Receive packages until we get the one we expect
            try:
                async with asyncio.timeout(timeout):
                    while True:
                        response,data = await XcomPackage.parse(self._reader, verbose=verbose)

                        if response.isResponse() and \
                        response.frame_data.service_id == request.frame_data.service_id and \
                        response.frame_data.service_data.object_id == request.frame_data.service_data.object_id and \
                        response.frame_data.service_data.property_id == request.frame_data.service_data.property_id:

                            # Yes, this is the answer to our request
                            if verbose:
                                _LOGGER.debug(f"recv {len(data)} bytes ({binascii.hexlify(data).decode('ascii')}), decoded: {response}")
                            return response
                        
                        else:
                            # No, not an answer to our request, continue loop for next answer (or timeout)
                            if verbose:
                                _LOGGER.debug(f"skip {len(data)} bytes ({binascii.hexlify(data).decode('ascii')}), decoded: {response}")

            except asyncio.TimeoutError as te:
                msg = f"Timeout while listening for response package from Xcom client"
                raise XcomApiTimeoutException(msg) from None

            except Exception as e:
                msg = f"Exception while listening for response package from Xcom client: {e}"
                raise XcomApiReadException() from None

