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

from .xcom_const import (
    XcomFormat,
    ScomAddress,
    ScomErrorCode,
)
from .xcom_data import (
    XcomData,
    readFloat,
    writeFloat,
    readUInt32,
    writeUInt32,
    readUInt16,
    writeUInt16,
    readUInt8,
    writeUInt8,
    readSInt32,
    writeSInt32,
    readBytes,
    writeBytes,
)


_LOGGER = logging.getLogger(__name__)


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
            src_addr = ScomAddress.SOURCE,
            dst_addr = ScomAddress.BROADCAST):
        
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

