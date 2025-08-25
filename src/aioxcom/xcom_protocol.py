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
    XcomFormat,
    MULTI_INFO_REQ_MAX,
    ScomObjType,
    XcomAggregationType,
    ScomErrorCode,
    XcomParamException,
)
from .xcom_datapoints import (
    XcomDatapoint,
)
from .xcom_families import (
    XcomDeviceFamilies,
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
            case XcomFormat.GUID: return value.hex(sep=':')                     # 16 bytes
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
            case XcomFormat.GUID: return bytes.fromhex(value.replace(':',''))  # 16 bytes
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


class XcomDataMultiInfoReqItem():
    datapoint: XcomDatapoint
    aggregation_type: XcomAggregationType

    def __init__(self, datapoint: XcomDatapoint, aggregation_type: Any):

        if datapoint.obj_type != ScomObjType.INFO:
                raise XcomParamException(f"Invalid datapoint passed to requestValues; must have obj_type INFO. Violated by datapoint '{datapoint.name}' ({datapoint.nr})")

        self.datapoint = datapoint
        self.aggregation_type = XcomDeviceFamilies.getAggregationTypeByAny(aggregation_type) 

    def __str__(self) -> str:
        return f"MultiInfoReqItem(datapoint={self.datapoint.nr}, aggregation_type={self.aggregation_type})"


class XcomDataMultiInfoReq:
    items: list[XcomDataMultiInfoReqItem]

    def __init__(self, items: Iterable[XcomDataMultiInfoReqItem]):
        if len(items) < 1:
            raise XcomParamException("No multi-info request items passed")
        if len(items) > MULTI_INFO_REQ_MAX:
            raise XcomParamException(f"Too many multi-info request items passed, maximum is {MULTI_INFO_REQ_MAX} in one request")
    
        self.items = items

    def pack(self) -> bytes:
        f = BytesIO()
        for item in self.items:
            writeUInt16(f, item.datapoint.nr)
            writeUInt8(f, item.aggregation_type)
        return f.getvalue()

    def __len__(self) -> int:
        return 3 * len(self.items)

    def __str__(self) -> str:
        return f"(len={len(self.items)})"


class XcomDataMultiInfoRspItem():
    datapoint: XcomDatapoint
    aggregation_type: XcomAggregationType
    value: Any

    def __init__(self, datapoint: XcomDatapoint, aggregation_type: XcomAggregationType, value: Any):
        self.datapoint = datapoint
        self.aggregation_type = aggregation_type
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

    def __str__(self) -> str:
        return f"MultiInfoRspItem(datapoint={self.datapoint.nr}, aggregation_type={self.aggregation_type}, value={self.value})"


class XcomDataMultiInfoRsp:
    flags: int
    datetime: int
    items: list[XcomDataMultiInfoRspItem]

    def __init__(self, flags, datetime, items):
        self.flags = flags
        self.datetime = datetime
        self.items = items

    @staticmethod
    def unpack(buf: bytes, req_data: XcomDataMultiInfoReq):
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

            datapoint = next((item.datapoint for item in req_data.items if item.datapoint.nr==user_info_ref), None)
            aggregation_type = XcomAggregationType(aggr)
            value = XcomData.unpack(data, XcomFormat.FLOAT)
            val = XcomData.cast(value, datapoint.format)

            items.append(XcomDataMultiInfoRspItem(
                datapoint,
                aggregation_type,
                val
            ))

        return XcomDataMultiInfoRsp(flags, datetime, items)

    def pack(self) -> bytes:
        f = BytesIO()
        writeUInt32(f, self.flags)
        writeUInt32(f, self.datetime)
        for item in self.items:
            data = XcomData.pack(item.value, XcomFormat.FLOAT)
            writeUInt16(f, item.datapoint.nr)
            writeUInt8(f, item.aggregation_type)
            writeBytes(f, data)

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


class XcomService:

    object_type: int
    object_id: int
    property_id: int
    property_data: bytes

    @staticmethod
    def parse(f: BufferedReader):
        return XcomService(
            object_type   = readUInt16(f),
            object_id     = readUInt32(f),
            property_id   = readUInt16(f),
            property_data = readBytes(f, -1),
        )

    def __init__(self, 
            object_type: int, object_id: int, 
            property_id: int, property_data: bytes):

        self.object_type = object_type
        self.object_id = object_id
        self.property_id = property_id
        self.property_data = property_data

    def assemble(self, f: BufferedWriter):
        writeUInt16(f, self.object_type)
        writeUInt32(f, self.object_id)
        writeUInt16(f, self.property_id)
        writeBytes(f, self.property_data)

    def __len__(self) -> int:
        return 2*2 + 4 + len(self.property_data)

    def __str__(self) -> str:
        return f"Service(obj_type={self.object_type:04X}, obj_id={self.object_id}, property_id={self.property_id:02X}, property_data={self.property_data.hex(' ',1)})"


class XcomFrame:

    service_flags: int
    service_id: int
    service_data: XcomService

    @staticmethod
    def parse(f: BufferedReader):
        return XcomFrame(
            service_flags = readUInt8(f),
            service_id = readUInt8(f),
            service_data = XcomService.parse(f)
        )

    @staticmethod
    def parseBytes(buf: bytes):
        return XcomFrame.parse(BytesIO(buf))

    def __init__(self, service_id: bytes, service_data: XcomService, service_flags=0):
        self.service_flags = service_flags
        self.service_id = service_id
        self.service_data = service_data

    def assemble(self, f: BufferedWriter):
        writeUInt8(f, self.service_flags)
        writeUInt8(f, self.service_id)
        self.service_data.assemble(f)

    def getBytes(self) -> bytes:
        buf = BytesIO()
        self.assemble(buf)
        return buf.getvalue()

    def __len__(self) -> int:
        return 2*1 + len(self.service_data)

    def __str__(self) -> str:
        return f"Frame(flags={self.service_flags:01X}, id={self.service_id:01X}, service={self.service_data})"


class XcomHeader:

    frame_flags: int
    src_addr: int
    dst_addr: int
    data_length: int

    length: int = 1 + 4 + 4 + 2

    @staticmethod
    def parse(f: BufferedReader):
        return XcomHeader(
            frame_flags = readUInt8(f),
            src_addr = readUInt32(f),
            dst_addr = readUInt32(f),
            data_length = readUInt16(f)
        )

    @staticmethod
    def parseBytes(buf: bytes):
        return XcomHeader.parse(BytesIO(buf))

    def __init__(self, src_addr: int, dst_addr: int, data_length: int, frame_flags=0):
        assert frame_flags >= 0, "frame_flags must not be negative"

        self.frame_flags = frame_flags
        self.src_addr = src_addr
        self.dst_addr = dst_addr
        self.data_length = data_length

    def assemble(self, f: BufferedWriter):
        writeUInt8(f, self.frame_flags)
        writeUInt32(f, self.src_addr)
        writeUInt32(f, self.dst_addr)
        writeUInt16(f, self.data_length)

    def getBytes(self) -> bytes:
        buf = BytesIO()
        self.assemble(buf)
        return buf.getvalue()

    def __len__(self) -> int:
        return self.length

    def __str__(self) -> str:
        return f"Header(flags={self.frame_flags}, src={self.src_addr}, dst={self.dst_addr}, data_length={self.data_length})"


class XcomPackage:

    start_byte: bytes = b'\xAA'
    delimeters: bytes = b'\x0D\x0A'
    header: XcomHeader
    frame_data: XcomFrame

    @staticmethod
    async def parse(f: asyncio.StreamReader, verbose=False):
        # package sometimes starts with 0xff
        skipped = bytearray(b'')
        while True:
            sb = await readBytes(f, 1)
            if sb == XcomPackage.start_byte:
                break

            skipped.extend(sb)

        if verbose and len(skipped) > 0:
            _LOGGER.debug(f"skip {len(skipped)} bytes until start-byte ({binascii.hexlify(skipped).decode('ascii')})")

        h_raw = await readBytes(f, XcomHeader.length)
        h_chk = await readBytes(f, 2)
        assert checksum(h_raw) == h_chk
        header = XcomHeader.parseBytes(h_raw)

        f_raw = await readBytes(f, header.data_length)
        f_chk = await readBytes(f, 2)
        assert checksum(f_raw) == f_chk
        frame = XcomFrame.parseBytes(f_raw)

        package = XcomPackage(header, frame)

        if verbose:
            data = bytearray(b'')
            data.extend(sb)
            data.extend(h_raw)
            data.extend(h_chk)
            data.extend(f_raw)
            data.extend(f_chk)
            _LOGGER.debug(f"recv {len(data)} bytes ({binascii.hexlify(data).decode('ascii')}), decoded: {package}")

        return package

    @staticmethod
    async def parseBytes(buf: bytes):
        reader = asyncio.StreamReader()
        reader.feed_data(buf)

        return await XcomPackage.parse(reader)
    
    @staticmethod
    def genPackage(
            service_id: int,
            object_type: int,
            object_id: int,
            property_id: int,
            property_data: bytes,
            src_addr = 1,
            dst_addr = 0):
        
        service = XcomService(object_type, object_id, property_id, property_data)
        frame = XcomFrame(service_id, service)
        header = XcomHeader(src_addr, dst_addr, len(frame))

        return XcomPackage(header, frame)

    def __init__(self, header: XcomHeader, frame_data: XcomFrame):
        self.header = header
        self.frame_data = frame_data

    def assemble(self, f: BufferedWriter):
        writeBytes(f, self.start_byte)

        header = self.header.getBytes()
        writeBytes(f, header)
        writeBytes(f, checksum(header))

        data = self.frame_data.getBytes()
        writeBytes(f, data)
        writeBytes(f, checksum(data))

        # Don't write delimeter, seems not needed as we send the package in one whole chunk
        #writeBytes(f, self.delimeters)

    def getBytes(self) -> bytes:
        buf = BytesIO()
        self.assemble(buf)
        return buf.getvalue()

    def isResponse(self) -> bool:
        return (self.frame_data.service_flags & 2) >> 1 == 1

    def isError(self) -> bool:
        return self.frame_data.service_flags & 1 == 1

    def getError(self) -> str:
        if self.isError():
            error = XcomData.unpack(self.frame_data.service_data.property_data, XcomFormat.ERROR)
            return ScomErrorCode.getByError(error)
        return None
 
    def __str__(self) -> str:
        return f"Package(header={self.header}, frame={self.frame_data})"

##

def checksum(data: bytes) -> bytes:
    """Function to calculate the checksum needed for the header and the data"""
    A = 0xFF
    B = 0x00

    for d in data:
        A = (A + d) % 0x100
        B = (B + A) % 0x100

    A = struct.pack("<B", A)
    B = struct.pack("<B", B)

    return A + B

##

def readFloat(f: BufferedReader) -> float:
    return float.from_bytes(f.read(4), byteorder="little", signed=True)


def readUInt32(f: BufferedReader) -> int:
    return int.from_bytes(f.read(4), byteorder="little", signed=False)

def writeUInt32(f: BufferedWriter, value: int) -> int:
    return f.write(value.to_bytes(4, byteorder="little", signed=False))

def readSInt32(f: BufferedReader) -> int:
    return int.from_bytes(f.read(4), byteorder="little", signed=True)

def writeSInt32(f: BufferedWriter, value: int) -> int:
    return f.write(value.to_bytes(4, byteorder="little", signed=True))


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
