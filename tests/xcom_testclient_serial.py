"""xcom_api.py: communication api to Studer Xcom via LAN."""

import asyncio
import logging

import serial_asyncio

from aioxcom import  (
    XcomApiTimeoutException,
    XcomApiReadException,
    XcomApiWriteException,
    XcomPackage,
)

_LOGGER = logging.getLogger(__name__)


DEFAULT_PORT = 54001
DEFAULT_BAUDRATE = 115200
DEFAULT_DATA_BITS = 8
DEFAULT_STOP_BITS = serial_asyncio.serial.STOPBITS_ONE
DEFAULT_PARITY = serial_asyncio.serial.PARITY_NONE
START_TIMEOUT = 30 # seconds
STOP_TIMEOUT = 5
REQ_TIMEOUT = 2
REQ_RETRIES = 3


##
## Class implementing Xcom-RS232i network protocol
##
class XcomTestClientSerial:

    def __init__(self, port=DEFAULT_PORT):
        """
        Initialize the mock test client.
        """
        super().__init__()

        self.localPort = port
        self._reader = None
        self._writer = None
        self._started = False
        self._connected = False
        self._remote_ip = None

        self._receivePackageLock = asyncio.Lock() # to make sure receivePackage is never called concurrently
        self._sendPackageLock    = asyncio.Lock() # to make sure sendPackage is never called concurrently


    @property
    def connected(self):
        """Returns True if the Xcom client is connected, otherwise False"""
        return self._connected


    @property
    def remote_ip(self) -> str|None:
        """Returns the IP address of the connected Xcom client, otherwise None"""
        return self._remote_ip


    async def start(self, timeout=START_TIMEOUT, loop=None) -> bool:
        """
        Start the Xcom Client and listening to the Xcom server.
        """
        if not self._started:
            _LOGGER.info(f"Xcom Serial Test Client connect to port {self.localPort}")

            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                loop = loop,
                url = self.localPort, 
                baudrate = DEFAULT_BAUDRATE,
                bytesize = DEFAULT_DATA_BITS,
                stopbits = DEFAULT_STOP_BITS,
                parity = DEFAULT_PARITY
            )

            _LOGGER.info(f"Connected to Xcom server '{self._remote_ip}'")
            self._started = True

            # Seems to work better if we wait a short moment before we start communication
            await asyncio.sleep(1)
            self._connected = True
        else:
            _LOGGER.info(f"Xcom Serial Test Client already listening on port {self.localPort}")


    async def stop(self):
        """
        Stop listening to the the Xcom Server and stop the Xcom Serial Test Client
        """
        _LOGGER.info(f"Stopping Xcom Serial Test Client")
        try:
            self._connected = False

            # Close the writer; we do not need to close the reader
            if self._writer:
                self._writer.close()
                await asyncio.sleep(1)
                # await self._writer.wait_closed()
    
        except Exception as e:
            _LOGGER.warning(f"Exception during closing of Xcom writer: {e}")

        
        self._reader = None
        self._writer = None
        self._started = False
        _LOGGER.info(f"Stopped Xcom Serial Test Client")
    

    async def receivePackage(self, timeout=REQ_TIMEOUT) -> XcomPackage | None:
        """
        Receive an Xcom package from Server to Client
        Throws:
            XcomApiWriteException
            XcomApiReadException
            XcomApiTimeoutException
        """
        if not self._connected:
            _LOGGER.info(f"receivePackage - not connected")
            return None
        
        async with self._receivePackageLock:
            # Receive a package
            try:
                async with asyncio.timeout(timeout):
                    while True:
                        request, _ = await XcomPackage.parse(self._reader)

                        if request is not None:
                            _LOGGER.info(f"Xcom Serial Test Client received request package {request}")
                            return request

            except asyncio.TimeoutError as te:
                msg = f"Timeout while listening for request package from Xcom server"
                raise XcomApiTimeoutException(msg) from None

            except Exception as e:
                msg = f"Exception while listening for request package from Xcom server: {e}"
                raise XcomApiReadException(msg) from None


    async def sendPackage(self, package: XcomPackage, timeout=REQ_TIMEOUT):
        """
        Send an Xcom package from Client to Server
        Throws:
            XcomApiWriteException
            XcomApiReadException
            XcomApiTimeoutException
        """
        if not self._connected:
            _LOGGER.info(f"sendPackage - not connected")
            return None
        
        async with self._sendPackageLock:
            # Send the package to the Xcom server
            try:
                _LOGGER.info(f"Xcom Serial Test Client send response package {package}")
                self._writer.write(package.getBytes())
                await self._writer.drain()

            except Exception as e:
                msg = f"Exception while sending package to Xcom server: {e}"
                raise XcomApiWriteException(msg) from None
