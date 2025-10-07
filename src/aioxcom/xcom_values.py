##
## Class implementing Xcom protocol 
##
## See the studer document: "Technical Specification - Xtender serial protocol"
## Download from:
##   https://studer-innotec.com/downloads/ 
##   -> Downloads -> software + updates -> communication protocol xcom 232i
##


import asyncio
import binascii
from enum import IntEnum
import logging
import struct
from io import BufferedWriter, BufferedReader, BytesIO
from typing import Any, Iterable

from .xcom_const import (
    XcomAggregationType,
    XcomParamException,
)
from .xcom_data import (
    XcomData,
    XcomDataMultiInfoReq,
    XcomDataMultiInfoReqItem,
    XcomDataMultiInfoRsp,
    XcomDataMultiInfoRspItem,
)
from .xcom_datapoints import (
    XcomDatapoint,
    XcomDataset,
)
from .xcom_families import (
    XcomDeviceFamilies,
)


_LOGGER = logging.getLogger(__name__)


class XcomValuesItem():
    datapoint: XcomDatapoint                    # Both in request and response, for requestInfos and requestValues
    code: str|None                              # Both in request and response, for requestInfos and requestValues
    address: int|None                           # Both in request and response, for requestInfos and requestValues
    aggregation_type: XcomAggregationType|None  # Both in request and response, for requestInfos and requestValues
    value: Any                                  # Only in response from requestValues()
    error: str|None                             # Only in response from requestValues()

    def __init__(self, datapoint: XcomDatapoint, code:str|None=None, address:int|None=None, aggregation_type:XcomAggregationType|None=None, value:Any=None, error:str|None=None):

        # Convert from code, addr and aggr. Code trumps addr and aggr, while addr trumps aggr.
        if code is not None:
            code = code
            addr = XcomDeviceFamilies.getAddrByCode(code)
            aggr = XcomDeviceFamilies.getAggregationTypeByCode(code)
        
        elif address is not None:
            code = XcomDeviceFamilies.getCodeByAddr(address, datapoint.family_id)
            addr = address
            aggr = XcomDeviceFamilies.getAggregationTypeByAddr(address)

        elif aggregation_type is not None:
            code = XcomDeviceFamilies.getCodeByAggregationType(aggregation_type, datapoint.family_id)
            addr = XcomDeviceFamilies.getAddrByAggregationType(aggregation_type, datapoint.family_id)
            aggr = aggregation_type

        else:
            raise XcomParamException(f"One of code, addr or aggr must be passed into an XcomValuesItem")

        # Set properties
        self.datapoint = datapoint
        self.code = code
        self.address = addr
        self.aggregation_type = aggr
        self.value = value
        self.error = error


class XcomValues():
    items: Iterable[XcomValuesItem] # Both in request and response
    flags: int                      # Only in response from requestValues
    datetime: int                   # Only in response from requestValues

    def __init__(self, items: Iterable[XcomValuesItem], flags:int=None, datetime:int=None):
        self.items = items
        self.flags = flags
        self.datetime = datetime

    @staticmethod
    def unpackRequest(buf: bytes, dataset: XcomDataset):
        """Unpack request data; only used for unit-tests"""
        req = XcomDataMultiInfoReq.unpack(buf)

        # Resolve additional properties
        items = list()
        for item in req.items:
            items.append(XcomValuesItem(
                datapoint = dataset.getByNr(item.user_info_ref),
                aggregation_type = item.aggregation_type
            ))
        return XcomValues(items)

    @staticmethod
    def unpackResponse(buf: bytes, req: 'XcomValues'):
        """Unpack response data"""
        rsp = XcomDataMultiInfoRsp.unpack(buf)

        # Resolve additional properties
        items = list()
        for item in rsp.items:
            datapoint = next((i.datapoint for i in req.items if i.datapoint.nr==item.user_info_ref), None)
            aggregation_type = item.aggregation_type
            value = XcomData.cast(item.data, datapoint.format) if datapoint is not None else None

            items.append(XcomValuesItem(
                datapoint = datapoint,
                aggregation_type = aggregation_type,
                value = value
            ))

        return XcomValues(items, rsp.flags, rsp.datetime)

    def packRequest(self) -> bytes:
        """Pack a request"""
        req = XcomDataMultiInfoReq(
            items = [XcomDataMultiInfoReqItem(i.datapoint.nr, i.aggregation_type) for i in self.items]
        )
        return req.pack()
            
    def packResponse(self) -> bytes:
        """Pack a response; only used for unit-testing"""
        rsp = XcomDataMultiInfoRsp(
            flags = self.flags,
            datetime = self.datetime,
            items = [XcomDataMultiInfoRspItem(i.datapoint.nr, i.aggregation_type, float(i.value)) for i in self.items]
        )
        return rsp.pack()

