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
)
from .xcom_families import (
    XcomDeviceFamilies,
)


_LOGGER = logging.getLogger(__name__)


MULTI_INFO_REQ_MAX = 76


class XcomMultiInfoReqItem(XcomDataMultiInfoReqItem):
    datapoint: XcomDatapoint

    # From base class:
    # - user_info_ref: int
    # - aggregation_type: XcomAggregationType

    def __init__(self, datapoint: XcomDatapoint, aggregation_type: Any):

        # Sanity check
        if datapoint.obj_type != ScomObjType.INFO:
                raise XcomParamException(f"Invalid datapoint passed to requestValues; must have obj_type INFO. Violated by datapoint '{datapoint.name}' ({datapoint.nr})")

        # Convert from enum, str, int, device code, or device addr into an aggregation_type
        aggr = XcomDeviceFamilies.getAggregationTypeByAny(aggregation_type) 

        # Set properties
        self.datapoint = datapoint
        super().__init__(datapoint.nr, aggr)


class XcomMultiInfoReq(XcomDataMultiInfoReq):

    # From base class:
    # - items: Iterable[XcomDataMultiInfoReqItem]

    def __init__(self, items: Iterable[XcomMultiInfoReqItem]):

        # Sanity check
        if len(items) < 1:
            raise XcomParamException("No multi-info request items passed")
        if len(items) > MULTI_INFO_REQ_MAX:
            raise XcomParamException(f"Too many multi-info request items passed, maximum is {MULTI_INFO_REQ_MAX} in one request")
    
        # Set properties
        super().__init__(items)

    # From base class:
    # -  def pack(self) -> bytes:


class XcomMultiInfoRspItem(XcomDataMultiInfoRspItem):
    datapoint: XcomDatapoint
    value: Any

    # From base class:
    # - user_info_ref: int
    # - aggregation_type: XcomAggregationType
    # - data: float

    def __init__(self, datapoint: XcomDatapoint, aggregation_type: XcomAggregationType, value: Any):
        self.datapoint = datapoint
        self.value = value

        super().__init__(datapoint.nr, aggregation_type, float(value))

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


class XcomMultiInfoRsp(XcomDataMultiInfoRsp):

    # From base class:
    # - flags: int
    # - datetime: int
    # - items: list[XcomDataMultiInfoRspItem]

    def __init__(self, flags, datetime, items):
        super().__init__(flags, datetime, items)

    # From base class:
    # - def pack(self) -> bytes:
    # - def unpack(buf: bytes) -> XcomDataMultiInfoRsp:

    @staticmethod
    def unpack(buf: bytes, req_data: XcomMultiInfoReq):
        # Unpack the data
        rsp = XcomDataMultiInfoRsp.unpack(buf)

        # Resolve additional properties
        items = list()
        for item in rsp.items:
            datapoint = next((i.datapoint for i in req_data.items if i.datapoint.nr==item.user_info_ref), None)
            aggregation_type = item.aggregation_type
            value = XcomData.cast(item.data, datapoint.format)

            items.append(XcomMultiInfoRspItem(
                datapoint,
                aggregation_type,
                value
            ))

        return XcomMultiInfoRsp(rsp.flags, rsp.datetime, items)


