"""xcom_api.py: communication api to Studer Xcom via LAN."""

import asyncio
import binascii
import logging
import socket

from datetime import datetime, timedelta
from typing import Iterable

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

_LOGGER = logging.getLogger(__name__)


DEFAULT_PORT = 4001
START_TIMEOUT = 30 # seconds
STOP_TIMEOUT = 5
REQ_TIMEOUT = 3
REQ_RETRIES = 3
REQ_BURST_SIZE = 10 # do 10 requests, then wait a second, then the next 10 requests


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
            dst_addr = ScomAddress.RCC
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
            object_type = ScomObjType.PARAMETER if parameter.category == XcomCategory.PARAMETER else ScomObjType.INFO,
            object_id = parameter.nr,
            property_id = ScomQspId.UNSAVED_VALUE if parameter.category == XcomCategory.PARAMETER else ScomQspId.VALUE,
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

                                         
    async def requestInfos(self, request_data: XcomValues, retries = None, timeout = None, verbose=False) -> XcomValues:
        """
        Request multiple infos in one call.
        Per info you can indicate what device to get it from, or to get Average or Sum of multiple devices

        Returns None if not connected, otherwise returns the list of requested values
        Throws
            XcomApiWriteException
            XcomApiReadException
            XcomApiTimeoutException
            XcomApiResponseIsError

        Note: this requires at least firmware version 1.6.74 on your Xcom-232i/Xcom-LAN.
              On older versions it results in a 'Service not supported' response from the Xcom client
        """

        # Sanity check
        for item in request_data.items:
            if item.datapoint.category != XcomCategory.INFO:
                raise XcomParamException(f"Invalid datapoint passed to requestInfos; must have type INFO. Violated by datapoint '{item.datapoint.name}' ({item.datapoint.nr})")
            
            if item.aggregation_type not in XcomAggregationType:
                raise XcomParamException(f"Invalid aggregation_type passed to requestInfos; violated by '{item.aggregation_type}'")                

        # Compose the request and send it
        request: XcomPackage = XcomPackage.genPackage(
            service_id = ScomService.READ,
            object_type = ScomObjType.MULTI_INFO,
            object_id = ScomObjId.MULTI_INFO,
            property_id = self._getNextRequestId() & 0xffff,
            property_data = request_data.packRequest(),
            dst_addr = ScomAddress.RCC
        )

        response = await self._sendRequest(request, retries=retries, timeout=timeout, verbose=verbose)
        if response is not None:
            try:
                # Unpack the response value
                return XcomValues.unpackResponse(response.frame_data.service_data.property_data, request_data)

            except Exception as e:
                msg = f"Failed to unpack response package for multi-info request, data={response.frame_data.service_data.property_data.hex()}: {e}"
                raise XcomApiUnpackException(msg) from None


    async def requestValues(self, request_data: XcomValues, retries = None, timeout = None, verbose=False) -> XcomValues:
        """
        Request multiple infos and params in one call.
        Can only retrieve actual device values, NOT the average or sum over multiple devices.

        The function will try to be as efficient as possible and combine retrieval of multiple infos in one call.
        When the xcom-client does not support multiple-infos in one call, they are retried one by one. 
        Requested params are always retrieved one by one, so the function can take a while to finish.        

        Returns None if not connected, otherwise returns the list of requested values
        Throws
            XcomApiWriteException
            XcomApiReadException
            XcomApiTimeoutException
            XcomApiResponseIsError
        """

        # Sort out which XcomValues can be done via multi requestValues and which must be done via single requestValue
        req_singles: list[XcomValuesItem] = []
        req_multi_items: list[XcomValuesItem] = []
        req_multis: list[XcomValues] = []
        idx_last = safe_len(request_data.items)-1

        for idx,item in enumerate(request_data.items):
            
            match item.datapoint.category:
                case XcomCategory.INFO:
                    if item.aggregation_type is not None and item.aggregation_type in range(XcomAggregationType.DEVICE1, XcomAggregationType.DEVICE15+1):
                        # Can be combined with other infos in a requestValues call
                        req_multi_items.append(item)

                    elif item.address is not None:
                        # Any others need to be done via an individual requestValue cal
                        req_singles.append(item)

                    else:
                        raise XcomParamException(f"Invalid XcomValuesItem passed to requestValues; violated by code='{item.code}', address={item.address}, aggregation_type={item.aggregation_type}")

                case XcomCategory.PARAMETER:
                    if item.address is not None:
                        # Needs to be done via an individual requestValue call
                        req_singles.append(item)

                    else:
                        raise XcomParamException(f"Invalid XcomValuesItem passed to requestValues; violated by code='{item.code}', address={item.address}, aggregation_type={item.aggregation_type}")
            
            if (len(req_multi_items) == MULTI_INFO_REQ_MAX) or \
               (len(req_multi_items) > 0 and idx == idx_last):

                # Start a new multi-items if current one if full or on last item of enumerate
                req_multis.append( XcomValues(items=req_multi_items) )
                req_multi_items = []

        # Now perform all the multi requestValues requests
        result_items: list[XcomValues] = []
        req_idx = 0

        for req_multi in req_multis:
            try:
                rsp_multi = await self.requestInfos(req_multi, retries=retries, timeout=timeout, verbose=verbose)

                # Success; gather the returned response items
                result_items.extend(rsp_multi.items)
            
            except XcomApiTimeoutException as tex:
                _LOGGER.debug(f"Failed to retrieve infos via single call. {tex}")

                # Fail; do not retry as single requestValue also expected to give timeout
                value = None
                error = str(tex)
                result_items.extend( [XcomValuesItem(req.datapoint, code=req.code, address=req.address, aggregation_type=req.aggregation_type, value=value, error=error) for req in req_multi.items] )
            
            except Exception as ex:
                _LOGGER.debug(f"Failed to retrieve infos via single call; will retry retrieve one-by-one. {ex}")

                # Fail; retry all items as single requestValue
                req_singles.extend(req_multi.items)

            # Periodically wait for a second. This will make sure we do not block Xcom-LAN with
            # too many requests at once and prevent it from uploading data to the Studer portal.
            req_idx += 1
            if req_idx % REQ_BURST_SIZE == 0:
                await asyncio.sleep(1)

        # Next perform all the single requestValue requests
        for req_single in req_singles:
            try:
                error = None
                value = await self.requestValue(req_single.datapoint, req_single.address, retries=retries, timeout=timeout, verbose=verbose)
            
            except Exception as ex:
                value = None
                error = str(ex)

            if error is not None:
                _LOGGER.debug(f"Failed to retrieve info or param {req_single.datapoint.nr}:{req_single.address}; {error}")

            # Add to results
            rsp_single = XcomValuesItem(
                datapoint = req_single.datapoint, 
                code = req_single.code,
                address = req_single.address,
                aggregation_type=req_single.aggregation_type, 
                value = value,
                error = error,
            )
            result_items.append(rsp_single)

            # Periodically wait for a second. This will make sure we do not block Xcom-LAN with
            # too many requests at once and prevent it from uploading data to the Studer portal.
            req_idx += 1
            if req_idx % REQ_BURST_SIZE == 0:
                await asyncio.sleep(1)

        # Return all reponse items as one XcomValues object
        return XcomValues(result_items)


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
        # Sanity check: the parameter/datapoint must have category == XcomDatapointType.PARAMETER
        if parameter.category != XcomCategory.PARAMETER:
            _LOGGER.warning(f"Ignoring attempt to update readonly infos value {parameter}")
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
                    raise XcomApiResponseIsError(response.getError())
                
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
                            if verbose:
                                _LOGGER.debug(f"recv {response}")
                            return response
                        
                        else:
                            # No, not an answer to our request, continue loop for next answer (or timeout)
                            if verbose:
                                _LOGGER.debug(f"skip {response}")

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
