##
# Definition of all known device families used in the Xcom protocol
##

import logging

from dataclasses import dataclass
from typing import Any

from .xcom_const import (
    XcomAggregationType,
    XcomParamException,
) 


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


    @staticmethod
    def getList() -> list[XcomDeviceFamily]:
        return [val for val in XcomDeviceFamilies.__dict__.values() if type(val) is XcomDeviceFamily]


    # Static variables to cache helper mappings
    _code_to_family_map: dict[str,XcomDeviceFamily] = None
    _code_to_addr_map: dict[str,int] = None
    _code_to_aggr_map: dict[int,XcomAggregationType] = None
    _addr_to_aggr_map: dict[str,int] = None

    @staticmethod
    def _buildStaticMaps():
        """Fill static variable once"""
        if XcomDeviceFamilies._code_to_family_map is None:

            XcomDeviceFamilies._code_to_family_map = {}
            XcomDeviceFamilies._code_to_addr_map = {}
            XcomDeviceFamilies._code_to_aggr_map = {}
            XcomDeviceFamilies._addr_to_aggr_map = {}
            # Note: no _addr_to_code_map because address range for BMS and BSP overlap

            for f in XcomDeviceFamilies.getList():
                has_aggr = f not in [XcomDeviceFamilies.L1, XcomDeviceFamilies.L2, XcomDeviceFamilies.L3]

                for addr in range(f.addrDevicesStart, f.addrDevicesEnd+1):
                    code = f.getCode(addr)
                    aggr = XcomAggregationType(addr - f.addrDevicesStart + 1) if has_aggr else None
                    
                    XcomDeviceFamilies._code_to_family_map[code] = f
                    XcomDeviceFamilies._code_to_addr_map[code] = addr # XT1-XT9 -> 101-109,  VT1-VT15 -> 301-315,  VS1-VS15 -> 701-715
                    XcomDeviceFamilies._code_to_aggr_map[code] = aggr # XT1-XT9 -> 1-9,      VT1-VT15 -> 1-15,     VS1-VS15 -> 1-15
                    XcomDeviceFamilies._addr_to_aggr_map[addr] = aggr # 101-109 -> 1-9,      301-315  -> 1-15,     701-715  -> 1-15


    @staticmethod
    def getByCode(code: str) -> XcomDeviceFamily:
        """
        Lookup the code to find the device family
        """
        XcomDeviceFamilies._buildStaticMaps()

        return  XcomDeviceFamilies._code_to_family_map.get(code, None)
    

    @staticmethod
    def getAddrByCode(code: str) -> int:
        """
        Lookup the code to find the addr
        """
        XcomDeviceFamilies._buildStaticMaps()

        return XcomDeviceFamilies._code_to_addr_map.get(code, None)


    @staticmethod
    def getAggregationTypeByCode(code: str) -> XcomAggregationType:
        """
        Lookup the code to find the aggregation_type
        """
        XcomDeviceFamilies._buildStaticMaps()
        
        return XcomDeviceFamilies._code_to_aggr_map.get(code, None)


    @staticmethod
    def getCodeByAddr(addr: int, family_id: str) -> int:
        """
        Lookup the addr to find the code.
        Family is passed as hint because BMS and BSP use same address range
        """
        for family in XcomDeviceFamilies.getList():
            if family.id == family_id or family.idForNr == family_id:
                try:
                    return family.getCode(addr)
                except:
                    pass
        
        return None


    @staticmethod
    def getAggregationTypeByAddr(addr: int) -> XcomAggregationType:
        """
        Lookup the device address to find the aggregation_type
        Note that addr 601 can either be BMS or BSP. However, both result in XcomAggregationType=1 so we don't care...
        """
        XcomDeviceFamilies._buildStaticMaps()
        
        return XcomDeviceFamilies._addr_to_aggr_map.get(addr, None)
    

    @staticmethod
    def getCodeByAggregationType(aggr: XcomAggregationType, family_id: str):
        """
        Reverse lookup an aggregation_type to find the corresponding device code within a family
        Note that some aggregation_types (AVERAGE,SUM) will result in a None response.
        """
        addr = XcomDeviceFamilies.getAddrByAggregationType(aggr, family_id)
        if addr is not None:
            return XcomDeviceFamilies.getCodeByAddr(addr, family_id)
        else:
            return None
        

    @staticmethod
    def getAddrByAggregationType(aggr: XcomAggregationType, family_id: str):
        """
        Reverse lookup an aggregation_type to find the corresponding device address within a family.
        Note that some aggregation_types (AVERAGE,SUM) will result in a None response.
        """
        XcomDeviceFamilies._buildStaticMaps()
        family = XcomDeviceFamilies.getById(family_id)

        for addr in range(family.addrDevicesStart, family.addrDevicesEnd+1):
            if XcomDeviceFamilies._addr_to_aggr_map.get(addr, None) == aggr:
                return addr
            
        return None
