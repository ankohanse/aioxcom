##
# Definition of all known device families used in the Xcom protocol
##

import logging
from dataclasses import dataclass


_LOGGER = logging.getLogger(__name__)


class XcomDeviceAddrUnknownException(Exception):
    pass

class XcomDeviceFamilyUnknownException(Exception):
    pass

class XcomDeviceCodeUnknownException(Exception):
    pass

    
@dataclass
class XcomDeviceFamily:
    id: str
    idForNr: str    # L1, L2 and L3 use xt numbers
    model: str
    addrMulticast: int
    addrDevicesStart: int
    addrDevicesEnd: int
    nrParamsStart: int
    nrParamsEnd: int
    nrInfosStart: int
    nrInfosEnd: int
    nrDiscover: int

    def getCode(self, addr):
        if addr == self.addrMulticast:
            return self.id.upper()
        
        if self.addrDevicesStart == addr == self.addrDevicesEnd:
            return self.id.upper()
        
        if self.addrDevicesStart <= addr <= self.addrDevicesEnd:
            idx = addr - self.addrDevicesStart + 1
            return f"{self.id.upper()}{idx}"
        
        msg = f"Addr {addr} is not in range for family {self.id} addresses ({self.addrDevicesStart}-{self.addrDevicesEnd})"
        raise XcomDeviceAddrUnknownException(msg)


class XcomDeviceFamilies:
    XTENDER = XcomDeviceFamily(
        "xt", "xt",
        "Xtender", 
        100,                   # addr multicast to all devices (write only)
        101, 109,              # addr devices,  start to end
        1000, 1999,            # nr for params, start to end
        3000, 3999,            # nr for infos,  start to end 
        3000,                  # nr for discovery
    )
    L1 = XcomDeviceFamily(
        "l1", "xt",
        "Phase L1", 
        191,                   # addr multicast to all devices (write only)
        191, 191,              # addr devices,  start to end
        1000, 1999,            # nr for params, start to end
        3000, 3999,            # nr for infos,  start to end   
        3000,                  # nr for discovery
    )
    L2 = XcomDeviceFamily(
        "l2", "xt",
        "Phase L2", 
        192,                   # addr multicast to all devices (write only)
        192, 192,              # addr devices,  start to end
        1000, 1999,            # nr for params, start to end
        3000, 3999,            # nr for infos,  start to end   
        3000,                  # nr for discovery
    )
    L3 = XcomDeviceFamily(
        "l3", "xt",
        "Phase L3", 
        193,                   # addr multicast to all devices (write only)
        193, 193,              # addr devices,  start to end
        1000, 1999,            # nr for params, start to end
        3000, 3999,            # nr for infos,  start to end   
        3000,                  # nr for discovery
    )
    RCC = XcomDeviceFamily(
        "rcc", "rcc",
        "RCC", 
        500,                   # addr multicast to all devices (write only)
        501, 501,              # addr devices,  start to end
        5000, 5999,            # nr for params, start to end
        0, 0,                  # nr for infos,  start to end
        5002,                  # nr for discovery
    )
    BSP = XcomDeviceFamily(
        "bsp", "bsp",
        "BSP", 
        600,                   # addr multicast to all devices (write only)
        601, 601,              # addr devices,  start to end
        6000, 6999,            # nr for params, start to end
        7000, 7999,            # nr for infos,  start to end
        7036,                  # nr for discovery
    )
    BMS = XcomDeviceFamily(
        "bms", "bms",
        "Xcom-CAN BMS", 
        600,                   # addr multicast to all devices (write only)
        601, 601,              # addr devices,  start to end
        6000, 6999,            # nr for params, start to end
        7000, 7999,            # nr for infos,  start to end
        7054,                  # nr for discovery
    )
    VARIOTRACK = XcomDeviceFamily(
        "vt", "vt",
        "VarioTrack", 
        300,                   # addr multicast to all devices (write only)
        301, 315,              # addr devices,  start to end
        10000, 10999,          # nr for params, start to end
        11000, 11999,          # nr for infos,  start to end
        11000,                 # nr for discovery
    )
    VARIOSTRING = XcomDeviceFamily(
        "vs", "vs",
        "VarioString", 
        700,                   # addr multicast to all devices (write only)
        701, 715,              # addr devices,  start to end
        14000, 14999,          # nr for params, start to end
        15000, 15999,          # nr for infos,  start to end
        15000,                 # nr for discovery
    )

    @staticmethod
    def getById(id: str) -> XcomDeviceFamily:
        for f in XcomDeviceFamilies.getList():
            if id == f.id:
                return f

        raise XcomDeviceFamilyUnknownException(id)
    

    # Static variable to cache helper mapping
    _addr_map = None

    @staticmethod
    def _buildAddrMap():
        """Fill static variable once"""
        if XcomDeviceFamilies._addr_map is None:
            XcomDeviceFamilies._addr_map = {}
            for f in XcomDeviceFamilies.getList():
                for addr in range(f.addrDevicesStart, f.addrDevicesEnd+1):
                    XcomDeviceFamilies._addr_map[f.getCode(addr)] = addr


    @staticmethod
    def getAddrByCode(code: str) -> int:
        """Lookup the code to find the addr"""
        XcomDeviceFamilies._buildAddrMap()
        addr = XcomDeviceFamilies._addr_map.get(code, None)
        if addr is not None:
            return addr
    
        raise XcomDeviceCodeUnknownException(str)


    @staticmethod
    def getList() -> list[XcomDeviceFamily]:
        return [val for val in XcomDeviceFamilies.__dict__.values() if type(val) is XcomDeviceFamily]
