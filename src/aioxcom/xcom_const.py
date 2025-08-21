#! /usr/bin/env python3

##
# Definition of all parameters / constants used in the Xcom protocol
##

from dataclasses import dataclass
from enum import IntEnum, StrEnum

MULTI_INFO_REQ_MAX = 76

class VOLTAGE(StrEnum):
    AC120 = "120 Vac"
    AC240 = "240 Vac"

    @staticmethod
    def from_str(s: str, default: str|None = None):
        match s.upper():
            case '120 VAC' | '120_VAC': return VOLTAGE.AC120
            case '240 VAC' | '240_VAC': return VOLTAGE.AC240
            case _: 
                if default is not None:
                    return default
                else:
                    msg = f"Unknown voltage: '{s}'"
                    raise Exception(msg)


### data types
class LEVEL(IntEnum):
    INFO   = 0x0001
    VO     = 0x0000 # View Only. Used for param RCC 5012 (User Level)
    BASIC  = 0x0010
    EXPERT = 0x0020
    INST   = 0x0030 # Installer
    QSP    = 0x0040 # Qualified Service Person

    @staticmethod
    def from_str(s: str, default: int|None = None):
        match s.upper():
            case 'INFO': return LEVEL.INFO
            case 'VO' | 'V.O.': return LEVEL.VO
            case 'BASIC': return LEVEL.BASIC
            case 'EXPERT': return LEVEL.EXPERT
            case 'INST' | 'INST.': return LEVEL.INST
            case 'QSP': return LEVEL.QSP
            case _: 
                if default is not None:
                    return default
                else:
                    msg = f"Unknown level: '{s}'"
                    raise Exception(msg)

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return self.name

class FORMAT(StrEnum):
    BOOL       = "BOOL"         # 1 byte
    FORMAT     = "FORMAT"       # 2 bytes
    SHORT_ENUM = "SHORT ENUM"   # 2 bytes
    ERROR      = "ERROR"        # 2 bytes
    INT32      = "INT32"        # 4 bytes
    FLOAT      = "FLOAT"        # 4 bytes
    LONG_ENUM  = "LONG_ENUM"    # 4 bytes
    GUID       = "GUID"         # 16 bytes
    STRING     = "STRING"       # n bytes
    DYNAMIC    = "DYNAMIC"      # n bytes
    BYTES      = "BYTES"        # n bytes
    MENU       = "MENU"         # n.a.
    INVALID    = "INVALID"      # n.a.

    @staticmethod
    def from_str(s: str, default: str|None = None):
        match s.upper():
            case 'BOOL': return FORMAT.BOOL
            case 'FORMAT': return FORMAT.FORMAT
            case 'SHORT_ENUM' | 'SHORT ENUM': return FORMAT.SHORT_ENUM
            case 'ERROR': return FORMAT.ERROR
            case 'INT32': return FORMAT.INT32
            case 'FLOAT': return FORMAT.FLOAT
            case 'LONG_ENUM' | 'LONG ENUM': return FORMAT.LONG_ENUM
            case 'GUID': return FORMAT.GUID
            case 'STRING': return FORMAT.STRING
            case 'DYNAMIC': return FORMAT.DYNAMIC
            case 'BYTES': return FORMAT.BYTES
            case 'MENU' | 'ONLY_LEVEL' | 'ONLY LEVEL': return FORMAT.MENU
            case 'NOT SUPPORTED': return FORMAT.INVALID
            case _: 
                if default is not None:
                    return default
                else:
                    msg = f"Unknown format: '{s}'"
                    raise Exception(msg)

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return self.name

### object_type
class OBJ_TYPE(StrEnum):
    INFO       = "INFO"
    PARAMETER  = "PARAMETER"
    MESSAGE    = "MESSAGE"
    GUID       = "GUID"
    DATALOG    = "DATALOG"
    MULTI_INFO = "MULTI-INFO"

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return self.name

    @staticmethod
    def fromScomObjType(obj_type):
        match obj_type:
            case SCOM_OBJ_TYPE.INFO: return OBJ_TYPE.INFO
            case SCOM_OBJ_TYPE.PARAMETER: return OBJ_TYPE.PARAMETER
            case SCOM_OBJ_TYPE.MESSAGE: return OBJ_TYPE.MESSAGE
            case SCOM_OBJ_TYPE.GUID: return OBJ_TYPE.GUID
            case SCOM_OBJ_TYPE.DATALOG: return OBJ_TYPE.DATALOG
            case SCOM_OBJ_TYPE.MULTI_INFO: return OBJ_TYPE.MULTI_INFO
            case _: 
                msg = f"Unknown obj_type: '{obj_type}'"
                raise Exception(msg)

### object_type in Scom/Xcom
class SCOM_OBJ_TYPE:
    INFO       = 0x0001
    PARAMETER  = 0x0002
    MESSAGE    = 0x0003
    GUID       = 0x0004
    DATALOG    = 0x0005
    MULTI_INFO = 0x000A

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return self.name

    @staticmethod
    def fromObjType(obj_type):
        match obj_type:
            case OBJ_TYPE.INFO: return SCOM_OBJ_TYPE.INFO
            case OBJ_TYPE.PARAMETER: return SCOM_OBJ_TYPE.PARAMETER
            case OBJ_TYPE.MESSAGE: return SCOM_OBJ_TYPE.MESSAGE
            case OBJ_TYPE.GUID: return SCOM_OBJ_TYPE.GUID
            case OBJ_TYPE.DATALOG: return SCOM_OBJ_TYPE.DATALOG
            case OBJ_TYPE.MULTI_INFO: return SCOM_OBJ_TYPE.MULTI_INFO
            case _: 
                msg = f"Unknown obj_type: '{obj_type}'"
                raise Exception(msg)

### object_id
class SCOM_OBJ_ID:
    NONE        = 0x00000000
    MULTI_INFO  = 0x00000001


### service_flags
class SCOM_SERVICE:
    READ   = 0x01
    WRITE  = 0x02

### property_id
class SCOM_QSP_ID:
    NONE            = 0x0000
    MULTI_INFO      = 0x0001
    VALUE           = 0x0005
    MIN             = 0x0006
    MAX             = 0x0007
    LEVEL           = 0x0008
    UNSAVED_VALUE   = 0x000D

## values for QSP_LEVEL
class SCOM_QSP_LEVEL:
    VIEW_ONLY       = 0x0000
    BASIC           = 0x0010
    EXPERT          = 0x0020
    INSTALLER       = 0x0030
    QSP             = 0x0040

## values for aggregation_type
class SCOM_AGGREGATION_TYPE:
    MASTER          = 0x00
    DEVICE1         = 0x01
    DEVICE2         = 0x02
    DEVICE3         = 0x03
    DEVICE4         = 0x04
    DEVICE5         = 0x05
    DEVICE6         = 0x06
    DEVICE7         = 0x07
    DEVICE8         = 0x08
    DEVICE9         = 0x09
    DEVICE10        = 0x0A
    DEVICE11        = 0x0B
    DEVICE12        = 0x0C
    DEVICE13        = 0x0D
    DEVICE14        = 0x0E
    DEVICE15        = 0x0F
    AVERAGE         = 0xFD
    SUM             = 0xFE

# SCOM_ADDRESSES
SCOM_ADDR_BROADCAST = 0

### error codes
class SCOM_ERROR_CODES:
    NO_ERROR                                = 0x0000 
    INVALID_FRAME                           = 0x0001
    DEVICE_NOT_FOUND                        = 0x0002
    RESPONSE_TIMEOUT                        = 0x0003
    SERVICE_NOT_SUPPORTED                   = 0x0011
    INVALID_SERVICE_ARGUMENT                = 0x0012
    SCOM_ERROR_GATEWAY_BUSY                 = 0x0013
    TYPE_NOT_SUPPORTED                      = 0x0021
    OBJECT_ID_NOT_FOUND                     = 0x0022
    PROPERTY_NOT_SUPPORTED                  = 0x0023
    INVALID_DATA_LENGTH                     = 0x0024
    PROPERTY_IS_READ_ONLY                   = 0x0025 
    INVALID_DATA                            = 0x0026 
    DATA_TOO_SMALL                          = 0x0027 
    DATA_TOO_BIG                            = 0x0028 
    WRITE_PROPERTY_FAILED                   = 0x0029 
    READ_PROPERTY_FAILED                    = 0x002A 
    ACCESS_DENIED                           = 0x002B 
    SCOM_ERROR_OBJECT_NOT_SUPPORTED         = 0x002C 
    SCOM_ERROR_MULTICAST_READ_NOT_SUPPORTED = 0x002D 
    OBJECT_PROPERTY_INVALID                 = 0x002E 
    FILE_OR_DIR_NOT_PRESENT                 = 0x002F 
    FILE_CORRUPTED                          = 0x0030 
    INVALID_SHELL_ARG                       = 0x0081

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return self.name

    @staticmethod
    def getByError(error: int):
        for key,val in SCOM_ERROR_CODES.__dict__.items():
            if type(key) is str and type(val) is int and val==error:
                return key

        return f"unknown error '{error:04x}'"
