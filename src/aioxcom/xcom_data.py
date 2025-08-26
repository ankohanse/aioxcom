##
## Class implementing Xcom protocol data objects
##
## See the studer document: "Technical Specification - Xtender serial protocol"
## Download from:
##   https://studer-innotec.com/downloads/ 
##   -> Downloads -> software + updates -> communication protocol xcom 232i
##


import logging
import struct
import uuid

from io import BufferedWriter, BufferedReader, BytesIO
from typing import Any, Iterable

from .xcom_const import (
    XcomFormat,
    XcomAggregationType,
)

_LOGGER = logging.getLogger(__name__)

class XcomData:
    NONE = b''

    @staticmethod
    def unpack(value: bytes, format):
        match format:
            case XcomFormat.BOOL: return struct.unpack("<?", value)[0]          # 1 byte, little endian, bool
            case XcomFormat.ERROR: return struct.unpack("<H", value)[0]         # 2 bytes, little endian, unsigned short/int16
            case XcomFormat.FORMAT: return struct.unpack("<H", value)[0]        # 2 bytes, little endian, unsigned short/int16
            case XcomFormat.SHORT_ENUM: return struct.unpack("<H", value)[0]    # 2 bytes, little endian, unsigned short/int16
            case XcomFormat.FLOAT: return struct.unpack("<f", value)[0]         # 4 bytes, little endian, float
            case XcomFormat.INT32: return struct.unpack("<i", value)[0]         # 4 bytes, little endian, signed long/int32
            case XcomFormat.LONG_ENUM: return struct.unpack("<I", value)[0]     # 4 bytes, little endian, unsigned long/int32
            case XcomFormat.GUID: return XcomData._bytes_to_guid(value)         # 16 bytes, little endian
            case XcomFormat.STRING: return value.decode('iso-8859-15')          # n bytes, ISO_8859-15 string of 8 bit characters
            case _: 
                msg = "Unknown data format '{format}"
                raise TypeError(msg)

    @staticmethod
    def pack(value, format) -> bytes:
        match format:
            case XcomFormat.BOOL: return struct.pack("<?", int(value))         # 1 byte, little endian, bool
            case XcomFormat.ERROR: return struct.pack("<H", int(value))        # 2 bytes, little endian, unsigned short/int16
            case XcomFormat.SHORT_ENUM: return struct.pack("<H", int(value))   # 2 bytes, little endian, unsigned short/int16
            case XcomFormat.FLOAT: return struct.pack("<f", float(value))      # 4 bytes, little endian, float
            case XcomFormat.INT32: return struct.pack("<i", int(value))        # 4 bytes, little endian, signed long/int32
            case XcomFormat.LONG_ENUM: return struct.pack("<I", int(value))    # 4 bytes, little endian, unsigned long/int32
            case XcomFormat.GUID: return XcomData._guid_to_bytes(value)        # 16 bytes, little endian
            case XcomFormat.STRING: return value.encode('iso-8859-15')         # n bytes, ISO_8859-15 string of 8 bit characters
            case _: 
                msg = "Unknown data format '{format}"
                raise TypeError(msg)

    @staticmethod
    def cast(value: float, format):
        match format:
            case XcomFormat.BOOL: return bool(value)
            case XcomFormat.ERROR: return int(value)
            case XcomFormat.FORMAT: return int(value)
            case XcomFormat.SHORT_ENUM: return int(value)
            case XcomFormat.FLOAT: return value
            case XcomFormat.INT32: return int(value)
            case XcomFormat.LONG_ENUM: return int(value)
            case XcomFormat.STRING: return value.decode('iso-8859-15') 
            case _: 
                msg = f"Unknown data format '{format}"
                raise TypeError(msg)

    @staticmethod      
    def _bytes_to_guid(value: bytes) -> str:
        guid_obj = uuid.UUID(int=int.from_bytes(value, byteorder='little'))
        return str(guid_obj)
    
    @staticmethod      
    def _guid_to_bytes(value: str) -> bytes:
        guid_obj = uuid.UUID(hex=value)
        guid_int = guid_obj.int
        return guid_int.to_bytes(16, byteorder='little')


class XcomDataMultiInfoReqItem():
    user_info_ref: int
    aggregation_type: XcomAggregationType

    def __init__(self, user_info_ref: int, aggregation_type: Any):

        self.user_info_ref = user_info_ref
        self.aggregation_type = aggregation_type 

    def __str__(self) -> str:
        return f"Item(user_info_ref={self.user_info_ref}, aggregation_type={self.aggregation_type})"


class XcomDataMultiInfoReq:
    items: Iterable[XcomDataMultiInfoReqItem]

    def __init__(self, items: Iterable[XcomDataMultiInfoReqItem]):
        self.items = items

    @staticmethod
    def unpack(buf: bytes) -> 'XcomDataMultiInfoReq':
        f = BytesIO(buf)
        f_len = f.getbuffer().nbytes
        items = list()

        while f_len >= 3:
            user_info_ref = readUInt16(f)
            aggr = readUInt8(f)
            f_len -= 3

            items.append(XcomDataMultiInfoReqItem(
                user_info_ref,
                XcomAggregationType(aggr),
            ))

        return XcomDataMultiInfoReq(items)

    def pack(self) -> bytes:
        f = BytesIO()
        for item in self.items:
            writeUInt16(f, item.user_info_ref)
            writeUInt8(f, item.aggregation_type)
        return f.getvalue()

    def __len__(self) -> int:
        return 3 * len(self.items)

    def __str__(self) -> str:
        return f"(len={len(self.items)})"


class XcomDataMultiInfoRspItem():
    user_info_ref: int
    aggregation_type: XcomAggregationType
    data: float

    def __init__(self, user_info_ref: int, aggregation_type: XcomAggregationType, data: float):
        self.user_info_ref = user_info_ref
        self.aggregation_type = aggregation_type
        self.data = data

    def __str__(self) -> str:
        return f"Item(user_info_ref={self.user_info_ref}, aggregation_type={self.aggregation_type}, value={self.value})"


class XcomDataMultiInfoRsp:
    flags: int
    datetime: int
    items: list[XcomDataMultiInfoRspItem]

    def __init__(self, flags, datetime, items):
        self.flags = flags
        self.datetime = datetime
        self.items = items

    @staticmethod
    def unpack(buf: bytes) -> 'XcomDataMultiInfoRsp':
        f = BytesIO(buf)
        f_len = f.getbuffer().nbytes

        flags = readUInt32(f)
        datetime= readUInt32(f)
        items = list()
        f_len -= 8

        while f_len >= 7:
            user_info_ref = readUInt16(f)
            aggr = readUInt8(f)
            data = readBytes(f, 4)
            f_len -= 7

            items.append(XcomDataMultiInfoRspItem(
                user_info_ref,
                XcomAggregationType(aggr),
                XcomData.unpack(data, XcomFormat.FLOAT)
            ))

        return XcomDataMultiInfoRsp(flags, datetime, items)

    def pack(self) -> bytes:
        f = BytesIO()
        writeUInt32(f, self.flags)
        writeUInt32(f, self.datetime)
        for item in self.items:
            writeUInt16(f, item.user_info_ref)
            writeUInt8(f, item.aggregation_type)
            writeBytes(f, XcomData.pack(item.data, XcomFormat.FLOAT))

        return f.getvalue()
    
    def __len__(self) -> int:
        return 2*4 + len(self.items)*(2+1+4)

    def __str__(self) -> str:
        return f"(flags={self.flags}, datetime={self.datetime}, len={len(self.items)})"


class XcomDataMessageRsp:
    msg_total: int      # 4 bytes
    msg_type: int       # 2 bytes
    src: int            # 4 bytes
    timestamp: int      # 4 bytes
    value: bytes        # 4 bytes

    @staticmethod
    def parse(f: BufferedReader):
        msg_total = readUInt32(f)
        msg_type= readUInt16(f)
        src = readUInt32(f)
        timestamp = readUInt32(f)
        value = readBytes(f, 4)

        return XcomDataMessageRsp(msg_total, msg_type, src, timestamp, value)
    
    @staticmethod
    def parseBytes(buf: bytes):
        return XcomDataMessageRsp.parse(BytesIO(buf))  
        
    def __init__(self, msg_total, msg_type, src, timestamp, value):
        self.msg_total = msg_total
        self.msg_type = msg_type
        self.src = src
        self.timestamp = timestamp
        self.value = value

    def __len__(self) -> int:
        return 2*4 + len(self.items)*(2+1+4)

    def __str__(self) -> str:
        return f"(flags={self.flags}, datetime={self.datetime}, len={len(self.items)})"


##

def readFloat(f: BufferedReader) -> float:
    return float.from_bytes(f.read(4), byteorder="little", signed=True)

def writeFloat(f: BufferedReader, value: float) -> int:
    return f.write(value.to_bytes(4, byteorder="little", signed=True))


def readSInt32(f: BufferedReader) -> int:
    return int.from_bytes(f.read(4), byteorder="little", signed=True)

def writeSInt32(f: BufferedWriter, value: int) -> int:
    return f.write(value.to_bytes(4, byteorder="little", signed=True))


def readUInt32(f: BufferedReader) -> int:
    return int.from_bytes(f.read(4), byteorder="little", signed=False)

def writeUInt32(f: BufferedWriter, value: int) -> int:
    return f.write(value.to_bytes(4, byteorder="little", signed=False))

def readUInt16(f: BufferedReader) -> int:
    return int.from_bytes(f.read(2), byteorder="little", signed=False)

def writeUInt16(f: BufferedWriter, value: int) -> int:
    return f.write(value.to_bytes(2, byteorder="little", signed=False))


def readUInt8(f: BufferedReader) -> int:
    return int.from_bytes(f.read(1), byteorder="little", signed=False)

def writeUInt8(f: BufferedWriter, value: int) -> int:
    return f.write(value.to_bytes(1, byteorder="little", signed=False))


def readBytes(f: BufferedReader, length: int) -> int:
    return f.read(length)

def writeBytes(f: BufferedWriter, value: bytes) -> int:
    return f.write(value)
