"""xcom_api.py: communication api to Studer Xcom via LAN."""

import asyncio
import asyncudp
import logging
import socket

from aioxcom import  (
    XcomApiTimeoutException,
    XcomApiReadException,
    XcomApiWriteException,
    XcomPackage,
)

_LOGGER = logging.getLogger(__name__)


DEFAULT_LOCAL_PORT = 54001
START_TIMEOUT = 30 # seconds
STOP_TIMEOUT = 5
REQ_TIMEOUT = 2
REQ_RETRIES = 3


##
## Class implementing Xcom-LAN TCP network protocol
##
class XcomTestClientUdp:

    def __init__(self, remote_ip: str, remote_port: int, local_port=DEFAULT_LOCAL_PORT):
        """
        MOXA is connecting to the UCP Server we are creating here.
        Once it is connected we can send package requests.
        """
        super().__init__()

        self._remote_ip = remote_ip
        self._remote_port = remote_port
        self._local_port = local_port    
        self._socket = None    
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
        if not self._connected:
            _LOGGER.info(f"Xcom UDP Test Client start connect to port {self._local_port}")

            self._socket = await asyncudp.create_socket(local_addr=('0.0.0.0', self._local_port))
            self._connected = True
        else:
            _LOGGER.info(f"Xcom UDP Test Client already listening on port {self._local_port}") 

        return True      


    async def stop(self):
        """
        Stop listening to the the Xcom Server and stop the Xcom UDP Test Client
        """
        _LOGGER.info(f"Stopping Xcom UDP Test Client")
        try:
            self._connected = False

            # Close the writer; we do not need to close the reader
            if self._socket:
                self._socket.close()
                
        except Exception as e:
            _LOGGER.warning(f"Exception during closing of Xcom socket: {e}")

        self._connected = False
        self._socket = None
        _LOGGER.info(f"Stopped Xcom UDP Test Client")
    

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
                        data,addr = await self._socket.recvfrom()
                        request = await XcomPackage.parseBytes(data)

                        if self._remote_ip is None and self._remote_port is None:
                            self._remote_ip = addr[0]
                            self._remote_port = addr[1]

                        if request is not None:
                            _LOGGER.info(f"Xcom UDP Test Client received request package {request} from {addr}")
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
                _LOGGER.info(f"Xcom UDP Test Client send response package {package}")

                self._socket.sendto(package.getBytes(), addr=(self._remote_ip, self._remote_port))

            except Exception as e:
                msg = f"Exception while sending package to Xcom server: {e}"
                raise XcomApiWriteException(msg) from None
