##
## Class implementing Xcom protocol 
##
## See the studer document: "Technical Specification - Xtender serial protocol"
## Download from:
##   https://studer-innotec.com/downloads/ 
##   -> Downloads -> software + updates -> communication protocol xcom 232i
##

import aiofiles
import logging
import orjson

from dataclasses import dataclass

from .xcom_const import (
    XcomLevel,
)
from .xcom_data import (
    XcomDataMessageRsp,
)



_LOGGER = logging.getLogger(__name__)


class XcomMessage(XcomDataMessageRsp):

    # Class variable
    _message_defs = None

    @staticmethod
    async def from_rsp(rsp: XcomDataMessageRsp):
        await XcomMessage._create_message_defs()
        return XcomMessage(
            message_total = rsp.message_total,
            message_number = rsp.message_number,
            source_address = rsp.source_address,
            timestamp = rsp.timestamp,
            value = rsp.value,
        )

    @classmethod
    async def _create_message_defs(cls):
        if not cls._message_defs:
           cls._message_defs = await XcomMessageSet.create()

    @property
    def message_string(self):
        try:
            return XcomMessage._message_defs.getStringByNr(self.message_number)
        except:
            return f"({self.message_number}): unknown message"
    

class XcomMessageUnknownException(Exception):
    pass


@dataclass
class XcomMessageDef:
    level: XcomLevel
    number: int
    string: str

    @staticmethod
    def from_dict(d):
        lvl = d.get('lvl', None)
        nr  = d.get('nr', None)
        msg = d.get('msg', None)

        # Check and convert properties
        if lvl is None or nr is None or msg is None:
            return None
        
        if type(nr) is not int:
            return None
        
        level = XcomLevel.from_str(str(lvl))
        number = int(nr)
        string = str(msg).strip()
            
        return XcomMessageDef(level, number, string)
        

class XcomMessageSet:

    def __init__(self, messages: list[XcomMessageDef] | None = None):
        self._messages = messages
   

    @staticmethod
    async def create(language: str = "en"):
        """
        The actual XcomMessage list is kept in a separate json file.
        """
        match language:
            case "en": path = __file__.replace('.py', '_en.json') # English
            case _:
                msg = f"Unknown language: '{language}'"
                raise Exception(msg)
        
        async with aiofiles.open(path, "r", encoding="UTF-8") as f:
            text = await f.read()
        
        values = orjson.loads(text)
        messages = list(filter(None, [XcomMessageDef.from_dict(val) for val in values]))

        return XcomMessageSet(messages)


    def getByNr(self, nr: int) -> XcomMessageDef:
        for msg in self._messages:
            if msg.number == nr:
                return msg

        raise XcomMessageUnknownException(nr)


    def getStringByNr(self, nr: int) -> str:
        msg = self.getByNr(nr)
        return msg.string
