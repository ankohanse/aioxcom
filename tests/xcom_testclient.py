"""xcom_api.py: communication api to Studer Xcom via LAN."""

import asyncio

import contextlib
import logging
import socket

from concurrent.futures import ThreadPoolExecutor
from io import BufferedWriter, BytesIO

from aioxcom import  (
    XcomApiTimeoutException,
    XcomApiReadException,
    XcomApiWriteException,
    XcomPackage,
)

_LOGGER = logging.getLogger(__name__)


DEFAULT_PORT = 54001
START_TIMEOUT = 30 # seconds
STOP_TIMEOUT = 5
REQ_TIMEOUT = 2
REQ_RETRIES = 3


##
## Class implementing Xcom-LAN TCP network protocol
##
class XcomTestClientTcp:

    def __init__(self, port=DEFAULT_PORT):
        """
        MOXA is connecting to the TCP Server we are creating here.
        Once it is connected we can send package requests.
        """
        super().__init__()

        self.localPort = port
        self._reader = None
        self._writer = None
        self._started = False
        self._connected = False

        self._receivePackageLock = asyncio.Lock() # to make sure receivePackage is never called concurrently
        self._sendPackageLock    = asyncio.Lock() # to make sure sendPackage is never called concurrently


    @property
    def connected(self):
        """Returns True if the Xcom client is connected, otherwise False"""
        return self._connected


    async def start(self, timeout=START_TIMEOUT) -> bool:
        """
        Start the Xcom Client and listening to the Xcom server.
        """
        if not self._started:
            _LOGGER.info(f"Xcom TCP Test Client connect to port {self.localPort}")

            self._reader, self._writer = await asyncio.open_connection("127.0.0.1", self.localPort, limit=1000, family=socket.AF_INET)

            peername = self._writer.get_extra_info("peername")
            _LOGGER.info(f"Connected to Xcom server '{peername}'")

            self._started = True
            self._connected = True
        else:
            _LOGGER.info(f"Xcom TCP Test Client already listening on port {self.localPort}")


    async def stop(self):
        """
        Stop listening to the the Xcom Server and stop the Xcom TCP Test Client
        """
        _LOGGER.info(f"Stopping Xcom TCP Test Client")
        try:
            self._connected = False

            # Close the writer; we do not need to close the reader
            if self._writer:
                self._writer.close()
    
        except Exception as e:
            _LOGGER.warning(f"Exception during closing of Xcom writer: {e}")

        self._started = False
        _LOGGER.info(f"Stopped Xcom TCP Test Client")
    

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
                        request = await XcomPackage.parse(self._reader)

                        if request is not None:
                            _LOGGER.info(f"Xcom TCP Test Client received request package {request}")
                            return request

            except asyncio.TimeoutError as te:
                raise XcomApiTimeoutException(f"Timeout while listening for request package from Xcom server") from None

            except Exception as e:
                raise XcomApiReadException(f"Exception while listening for request package from Xcom server: {e}") from None


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
                _LOGGER.info(f"Xcom TCP Test Client send response package {package}")
                self._writer.write(package.getBytes())
                self._writer.write(b'\x0A\x0D')
                await self._writer.drain()

            except Exception as e:
                raise XcomApiWriteException(f"Exception while sending package to Xcom server: {e}") from None


    async def requestHandle(self,
            expected_dst_addr,
            expected_service_id,
            expected_object_type,
            expected_object_id,
            expected_property_id,
            response_flags,
            response_data):
        
        p: XcomPackage = await self.receivePackage()

        assert p.header.dst_addr == expected_dst_addr
        assert p.frame_data.service_id == expected_service_id
        assert p.frame_data.service_data.object_type == expected_object_type
        assert p.frame_data.service_data.object_id == expected_object_id
        assert p.frame_data.service_data.property_id == expected_property_id

        p.frame_data.service_flags = response_flags
        p.frame_data.service_data.property_data = response_data
        p.header.data_length = len(p.frame_data)

        await self.sendPackage(p)