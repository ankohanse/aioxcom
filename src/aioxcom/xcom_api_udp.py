"""xcom_api.py: communication api to Studer Xcom via LAN."""

import asyncio
import asyncudp
import binascii
import logging
import socket

from datetime import datetime, timedelta
from typing import Iterable


from .xcom_api_base import (
    XcomApiBase,
    XcomApiWriteException,
    XcomApiReadException,
    XcomApiTimeoutException,
    XcomApiUnpackException,
    XcomApiResponseIsError,
    START_TIMEOUT,
    STOP_TIMEOUT,
    REQ_TIMEOUT,
)
from .xcom_const import (
    ScomAddress,
    XcomLevel,
    XcomFormat,
    XcomCategory,
    XcomAggregationType,
    ScomObjType,
    ScomObjId,
    ScomService,
    ScomQspId,
    ScomErrorCode,
    XcomParamException,
    safe_len,
)
from .xcom_protocol import (
    XcomPackage,
)
from .xcom_data import (
    XcomData,
    XcomDataMessageRsp,
    MULTI_INFO_REQ_MAX,
)
from .xcom_values import (
    XcomValues,
    XcomValuesItem,
)
from .xcom_datapoints import (
    XcomDatapoint,
)
from .xcom_families import (
    XcomDeviceFamilies
)
from .xcom_messages import (
    XcomMessage,
)


_LOGGER = logging.getLogger(__name__)


DEFAULT_LOCAL_PORT = 4001
DEFAULT_REMOTE_PORT = 4001


##
## Class implementing Xcom-LAN UDP network protocol
##
class XcomApiUdp(XcomApiBase):

    def __init__(self, remote_ip: str, remote_port=DEFAULT_REMOTE_PORT, local_port=DEFAULT_LOCAL_PORT):
        """
        We connect to the Moxa using the Udp server we are creating here.
        Once it is started we can send package requests. 
        """
        super().__init__()

        self._remote_ip = remote_ip
        self._remote_port = remote_port
        self._local_port = local_port
        self._socket = None
        self._connected = False

        self._sendPackageLock = asyncio.Lock() # to make sure _sendPackage is never called concurrently


    async def start(self, timeout=START_TIMEOUT) -> bool:
        """
        Start the Xcom Server and listening to the Xcom client.
        """
        if not self._connected:
            _LOGGER.info(f"Xcom UDP server start listening on port {self._local_port}")

            self._socket = await asyncudp.create_socket(local_addr=('0.0.0.0', self._local_port), packets_queue_max_size=100)
            self._connected = True
        else:
            _LOGGER.info(f"Xcom UDP server already listening on port {self._local_port}")

        return True


    async def stop(self):
        """
        Stop listening to the the Xcom Client and stop the Xcom Server.
        """
        _LOGGER.info(f"Stopping Xcom UDP server")
        try:
            self._connected = False

            # Close the writer; we do not need to close the reader
            if self._socket:
                self._socket.close()
                
        except Exception as e:
            _LOGGER.warning(f"Exception during closing of Xcom socket: {e}")

        self._connected = False
        self._socket = None
        _LOGGER.info(f"Stopped Xcom UDP server")


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

                self._socket.sendto(data, addr=(self._remote_ip, self._remote_port) )
                
            except Exception as e:
                msg = f"Exception while sending request package to Xcom client: {e}"
                raise XcomApiWriteException(msg) from None

            # Receive packages until we get the one we expect
            try:
                async with asyncio.timeout(timeout):
                    while True:
                        data,addr = await self._socket.recvfrom()
                        response = await XcomPackage.parseBytes(data, verbose)

                        if response.isResponse() and \
                        response.frame_data.service_id == request.frame_data.service_id and \
                        response.frame_data.service_data.object_id == request.frame_data.service_data.object_id and \
                        response.frame_data.service_data.property_id == request.frame_data.service_data.property_id:

                            # Yes, this is the answer to our request
                            if verbose:
                                _LOGGER.debug(f"recv {len(data)} bytes ({binascii.hexlify(data).decode('ascii')}) from {addr}, decoded: {response}")
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


