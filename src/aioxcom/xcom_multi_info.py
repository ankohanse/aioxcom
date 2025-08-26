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
    ScomObjType,
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


MULTI_INFO_REQ_MAX = 76

class XcomValuesItem():
    datapoint: XcomDatapoint                # Both in request and response
    aggregation_type: XcomAggregationType   # Both in request and response
    value: Any                              # Only in answer from requestValues()

    def __init__(self, datapoint: XcomDatapoint, aggregation_type: Any, value:Any=None):

        # Sanity check
        if datapoint.obj_type != ScomObjType.INFO:
                raise XcomParamException(f"Invalid datapoint passed to requestValues; must have obj_type INFO. Violated by datapoint '{datapoint.name}' ({datapoint.nr})")

        # Convert from enum, str, int, device code, or device addr into an aggregation_type
        aggr = XcomDeviceFamilies.getAggregationTypeByAny(aggregation_type) 

        # Set properties
        self.datapoint = datapoint
        self.aggregation_type = aggr
        self.value = value

    @property
    def addr(self):
        family = XcomDeviceFamilies.getById(self.datapoint.family_id)
        return XcomDeviceFamilies.getAddrByAggregationType(self.aggregation_type, family)

    @property
    def code(self):
        family = XcomDeviceFamilies.getById(self.datapoint.family_id)
        addr = XcomDeviceFamilies.getAddrByAggregationType(self.aggregation_type, family)
        if addr is not None:
            return family.getCode(addr)
        else:
            return str(self.aggregation_type)


class XcomValues():
    items: Iterable[XcomValuesItem] # Both in request and response
    flags: int                      # Only in response from requestValues
    datetime: int                   # Only in response from requestValues

    def __init__(self, items: Iterable[XcomValuesItem], flags:int=None, datetime:int=None):

        # Sanity check
        if len(items) < 1:
            raise XcomParamException("No values items passed")
        if len(items) > MULTI_INFO_REQ_MAX:
            raise XcomParamException(f"Too values items passed, maximum is {MULTI_INFO_REQ_MAX} in one request")
    
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
            value = XcomData.cast(item.data, datapoint.format)

            items.append(XcomValuesItem(
                datapoint,
                aggregation_type,
                value
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
