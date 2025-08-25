"""xcom_api.py: communication api to Studer Xcom via LAN."""

import asyncio
import binascii
import logging
import socket

from datetime import datetime, timedelta
from typing import Iterable

from .xcom_const import (
    XcomLevel,
    XcomFormat,
    ScomObjType,
    XcomAggregationType,
    ScomObjType,
    ScomObjId,
    ScomService,
    ScomQspId,
    ScomErrorCode,
)
from .xcom_protocol import (
    XcomPackage,
)
from .xcom_data import (
    XcomData,
    XcomDataMessageRsp,
)
from .xcom_multi_info import (
    XcomMultiInfoReq,
    XcomMultiInfoReqItem,
    XcomMultiInfoRsp,
    XcomMultiInfoRspItem,
)
from .xcom_datapoints import (
    XcomDatapoint,
)
from .xcom_families import (
    XcomDeviceFamilies
)

_LOGGER = logging.getLogger(__name__)


DEFAULT_PORT = 4001
START_TIMEOUT = 30 # seconds
STOP_TIMEOUT = 5
REQ_TIMEOUT = 3
REQ_RETRIES = 3


class XcomApiWriteException(Exception):
    """Exception to indicate failure while writing data to the xcom client"""
    
class XcomApiReadException(Exception):
    """Exception to indicate failure while reading data from the xcom client"""
    
class XcomApiTimeoutException(Exception):
    """Exception to indicate a timeout while reading from the xcom client"""

class XcomApiUnpackException(Exception):
    """Exception to indicate faulure to unpack a response package from the xcom client"""

class XcomApiResponseIsError(Exception):
    """Exception to indicate an error message was received back from the xcom client"""



##
## Base cass abstracting Xcom Api
##
class XcomApiBase:

    def __init__(self):
        """
        MOXA is connecting to the TCP Server we are creating here.
        Once it is connected we can send package requests.
        """
        self._started = False
        self._connected = False
        self._remote_ip = None
        self._request_id = 0

        # Diagnostics gathering
        self._diag_retries = {}
        self._diag_durations = {}


    async def start(self, timeout=START_TIMEOUT) -> bool:
        """
        Start the Xcom Server and listening to the Xcom client.
        """
        raise NotImplementedError()


    async def stop(self):
        """
        Stop listening to the the Xcom Client and stop the Xcom Server.
        """
        raise NotImplementedError()
    

    @property
    def connected(self) -> bool:
        """Returns True if the Xcom client is connected, otherwise False"""
        return self._connected


    @property
    def remote_ip(self) -> str|None:
        """Returns the IP address of the connected Xcom client, otherwise None"""
        return self._remote_ip
    

    async def _waitConnected(self, timeout) -> bool:
        """Wait for Xcom client to connect. Or timout."""
        try:
            for i in range(timeout):
                if self._connected:
                    return True
                
                await asyncio.sleep(1)

        except Exception as e:
            _LOGGER.warning(f"Exception while checking connection to Xcom client: {e}")

        return False


    async def requestGuid(self, retries = None, timeout = None, verbose=False):
        """
        Request the GUID that is used for remotely identifying the installation.
        This function is only for the Modem or Ethernet mode

        Returns None if not connected, otherwise returns the requested value
        Throws
            XcomApiWriteException
            XcomApiReadException
            XcomApiTimeoutException
            XcomApiResponseIsError
        """

        # Compose the request and send it
        request: XcomPackage = XcomPackage.genPackage(
            service_id = ScomService.READ,
            object_type = ScomObjType.GUID,
            object_id = ScomObjId.NONE,
            property_id = ScomQspId.NONE,
            property_data = XcomData.NONE,
            dst_addr = XcomDeviceFamilies.RCC.addrDevicesStart
        )

        response = await self._sendRequest(request, retries=retries, timeout=timeout, verbose=verbose)
        if response is not None:
            # Unpack the response value
            try:
                return XcomData.unpack(response.frame_data.service_data.property_data, XcomFormat.GUID)

            except Exception as e:
                msg = f"Failed to unpack response package for GUID:{request.header.dst_addr}, data={response.frame_data.service_data.property_data.hex()}: {e}"
                raise XcomApiUnpackException(msg) from None

                                         
    async def requestValue(self, parameter: XcomDatapoint, dstAddr = 100, retries = None, timeout = None, verbose=False):
        """
        Request a param or info.
        Returns None if not connected, otherwise returns the requested value
        Throws
            XcomApiWriteException
            XcomApiReadException
            XcomApiTimeoutException
            XcomApiResponseIsError
        """

        # Check/convert input parameters        
        if type(dstAddr) is str:
            dstAddr = XcomDeviceFamilies.getAddrByCode(dstAddr)

        # Compose the request and send it
        request: XcomPackage = XcomPackage.genPackage(
            service_id = ScomService.READ,
            object_type = parameter.obj_type,
            object_id = parameter.nr,
            property_id = ScomQspId.UNSAVED_VALUE if parameter.obj_type == ScomObjType.PARAMETER else ScomQspId.VALUE,
            property_data = XcomData.NONE,
            dst_addr = dstAddr
        )

        response = await self._sendRequest(request, retries=retries, timeout=timeout, verbose=verbose)
        if response is not None:
            # Unpack the response value
            try:
                return XcomData.unpack(response.frame_data.service_data.property_data, parameter.format)

            except Exception as e:
                msg = f"Failed to unpack response package for {parameter.nr}:{dstAddr}, data={response.frame_data.service_data.property_data.hex()}: {e}"
                raise XcomApiUnpackException(msg) from None

                                         
    async def requestValues(self, multi_info_req_data: XcomMultiInfoReq, retries = None, timeout = None, verbose=False) -> XcomMultiInfoRsp:
        """
        Request multiple infos in one call.
        Returns None if not connected, otherwise returns the list of requested values
        Throws
            XcomApiWriteException
            XcomApiReadException
            XcomApiTimeoutException
            XcomApiResponseIsError

        Note: this requires at least firmware version 1.6.74 on your Xcom-232/Xcom-LAN.
              On older versions it results in a 'Service not supported' response from the Xcom client
        """

        # Compose the request and send it
        request: XcomPackage = XcomPackage.genPackage(
            service_id = ScomService.READ,
            object_type = ScomObjType.MULTI_INFO,
            object_id = ScomObjId.MULTI_INFO,
            property_id = self._getNextRequestId() & 0xffff,
            property_data = multi_info_req_data.pack(),
            dst_addr = XcomDeviceFamilies.RCC.addrDevicesStart
        )

        response = await self._sendRequest(request, retries=retries, timeout=timeout, verbose=verbose)
        if response is not None:
            try:
                # Unpack the response value
                return XcomMultiInfoRsp.unpack(response.frame_data.service_data.property_data, multi_info_req_data)

            except Exception as e:
                msg = f"Failed to unpack response package for multi-info request, data={response.frame_data.service_data.property_data.hex()}: {e}"
                raise XcomApiUnpackException(msg) from None


    async def updateValue(self, parameter: XcomDatapoint, value, dstAddr = 100, retries = None, timeout = None, verbose=False):
        """
        Update a param
        Returns None if not connected, otherwise returns True on success
        Throws
            XcomApiWriteException
            XcomApiReadException
            XcomApiTimeoutException
            XcomApiResponseIsError
        """
        # Sanity check: the parameter/datapoint must have obj_type == ScomObjType.PARAMETER
        if parameter.obj_type != ScomObjType.PARAMETER:
            _LOGGER.warn(f"Ignoring attempt to update readonly infos value {parameter}")
            return None

        if type(dstAddr) is str:
            dstAddr = XcomDeviceFamilies.getAddrByCode(dstAddr)

        _LOGGER.debug(f"Update value {parameter} on addr {dstAddr}")

        # Compose the request and send it
        request: XcomPackage = XcomPackage.genPackage(
            service_id = ScomService.WRITE,
            object_type = ScomObjType.PARAMETER,
            object_id = parameter.nr,
            property_id = ScomQspId.UNSAVED_VALUE,
            property_data = XcomData.pack(value, parameter.format),
            dst_addr = dstAddr
        )

        response = await self._sendRequest(request, retries=retries, timeout=timeout, verbose=verbose)
        if response is not None:
            # No need to unpack the response value
            return True
        
        return False
    

    async def _sendRequest(self, request: XcomPackage, retries = None, timeout = None, verbose=False):
    
        # Sometimes the Xcom client does not seem to pickup a request
        # so retry if needed
        last_exception = None
        retries = retries or REQ_RETRIES
        timeout = timeout or REQ_TIMEOUT

        for retry in range(retries):
            try:
                ts_start = datetime.now()

                response = await self._sendPackage(request, timeout=timeout, verbose=verbose)

                # Update diagnostics
                ts_end = datetime.now()
                await self._addDiagnostics(retries = retry, duration = ts_end-ts_start)

                # Check the response
                if response is None:
                    return None

                if response.isError():
                    message = response.getError()
                    msg = f"Response package for {request.frame_data.service_data.object_id}:{request.header.dst_addr} contains message: '{message}'"
                    raise XcomApiResponseIsError(msg)
                
                # Success
                return response
                    
            except Exception as e:
                last_exception = e

        # Update diagnostics in case of timeout of each retry
        await self._addDiagnostics(retries = retry)

        if last_exception:
            raise last_exception from None


    async def _sendPackage(self, request: XcomPackage, timeout=REQ_TIMEOUT) -> XcomPackage | None:
        """Implemented in derived classes"""
        raise NotImplementedError()
    

    def _getNextRequestId(self) -> int:
        self._request_id += 1
        return self._request_id


    async def _addDiagnostics(self, retries: int = None, duration: timedelta = None):
        if retries is not None:
            if retries not in self._diag_retries:
                self._diag_retries[retries] = 1
            else:
                self._diag_retries[retries] += 1

        if duration is not None:
            duration = round(duration.total_seconds(), 1)
            if duration not in self._diag_durations:
                self._diag_durations[duration] = 1
            else:
                self._diag_durations[duration] += 1


    async def getDiagnostics(self):
        return {
            "statistics": {
                "retries": dict(sorted(self._diag_retries.items())),
                "durations": dict(sorted(self._diag_durations.items())),
            }
        }


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
                        response = await XcomPackage.parse(self._reader, verbose=verbose)

                        if response.isResponse() and \
                        response.frame_data.service_id == request.frame_data.service_id and \
                        response.frame_data.service_data.object_id == request.frame_data.service_data.object_id and \
                        response.frame_data.service_data.property_id == request.frame_data.service_data.property_id:

                            # Yes, this is the answer to our request
                            #_LOGGER.debug(f"recv {response}")
                            return response
                        
                        else:
                            # No, not an answer to our request, continue loop for next answer (or timeout)
                            pass

            except asyncio.TimeoutError as te:
                msg = f"Timeout while listening for response package from Xcom client"
                raise XcomApiTimeoutException(msg) from None

            except Exception as e:
                msg = f"Exception while listening for response package from Xcom client: {e}"
                raise XcomApiReadException() from None


##
## Class implementing Xcom-LAN UDP network protocol
##
class XcomApiUdp(XcomApiBase):

    def __init__(self, port=DEFAULT_PORT):
        """
        MOXA is connecting to the TCP Server we are creating here.
        Once it is connected we can send package requests.
        """
        super().__init__()

        raise NotImplementedError()


    async def start(self, timeout=START_TIMEOUT) -> bool:
        """
        Start the Xcom Server and listening to the Xcom client.
        """
        raise NotImplementedError()


    async def stop(self):
        """
        Stop listening to the the Xcom Client and stop the Xcom Server.
        """
        raise NotImplementedError()


    async def _sendPackage(self, request: XcomPackage, timeout=REQ_TIMEOUT) -> XcomPackage | None:
        """
        Send an Xcom package from Server to Client and wait for the response (or timeout).
        Throws:
            XcomApiWriteException
            XcomApiReadException
            XcomApiTimeoutException
        """
        raise NotImplementedError()
