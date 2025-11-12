"""xcom_api.py: communication api to Studer Xcom via LAN."""

import asyncio
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


DEFAULT_PORT = 4001


##
## Class implementing Xcom-LAN TCP network protocol
##
class XcomApiTcp(XcomApiBase):

    def __init__(self, port=DEFAULT_PORT):
        """
        MOXA is connecting to the TCP Server we are creating here.
        Once it is connected we can send package requests.
        """
        super().__init__()

        self.localPort = port
        self._server = None
        self._reader = None
        self._writer = None
        self._started = False
        self._connected = False
        self._remote_ip = None

        self._sendPackageLock = asyncio.Lock() # to make sure _sendPackage is never called concurrently


    async def start(self, timeout=START_TIMEOUT, wait_for_connect=True) -> bool:
        """
        Start the Xcom Server and listening to the Xcom client.
        """
        if not self._started:
            _LOGGER.info(f"Xcom TCP server start listening on port {self.localPort}")

            self._server = await asyncio.start_server(self._client_connected_callback, "0.0.0.0", self.localPort, limit=1000, family=socket.AF_INET)
            self._server._start_serving()
            self._started = True
        else:
            _LOGGER.info(f"Xcom TCP server already listening on port {self.localPort}")

        if wait_for_connect:
            _LOGGER.info("Waiting for Xcom TCP client to connect...")
            return await self._waitConnected(timeout)
        
        return True


    async def stop(self):
        """
        Stop listening to the the Xcom Client and stop the Xcom Server.
        """
        _LOGGER.info(f"Stopping Xcom TCP server")
        try:
            self._connected = False

            # Close the writer; we do not need to close the reader
            if self._writer:
                self._writer.close()
                await self._writer.wait_closed()
    
        except Exception as e:
            _LOGGER.warning(f"Exception during closing of Xcom writer: {e}")

        # Close the server
        try:
            async with asyncio.timeout(STOP_TIMEOUT):
                if self._server:
                    self._server.close()
                    await self._server.wait_closed()
    
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            _LOGGER.warning(f"Exception during closing of Xcom server: {e}")

        self._started = False
        _LOGGER.info(f"Stopped Xcom TCP server")
    

    async def _client_connected_callback(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Callback called once the Xcom Client connects to our Server
        """
        self._reader: asyncio.StreamReader = reader
        self._writer: asyncio.StreamWriter = writer
        self._connected = True

        # Gather some info about remote server
        (self._remote_ip,_) = self._writer.get_extra_info("peername")

        _LOGGER.info(f"Connected to Xcom client '{self._remote_ip}'")


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

