#! /usr/bin/env python3

##
# Definition of all parameters / constants used in the Xcom protocol
##

import aiofiles
import json
import logging
import orjson
import struct

from dataclasses import dataclass

from .xcom_const import (
    LEVEL,
    FORMAT,
    OBJ_TYPE,
)


_LOGGER = logging.getLogger(__name__)


class XcomDatapointUnknownException(Exception):
    pass


@dataclass
class XcomDatapoint:
    family_id: str
    level: LEVEL
    parent: int | None
    nr: int
    name: str
    abbr: str   # abbreviated/coded name
    unit: str
    format: FORMAT
    default: float|str = None
    min: float|str = None
    max: float|str = None
    inc: float|str = None
    options: dict = None

    @staticmethod
    def from_dict(d):
        fam = d.get('fam', None)
        lvl = d.get('lvl', None)
        pnr = d.get('pnr', None)
        nr  = d.get('nr', None)
        name = d.get('name', None)
        abbr = d.get('short', None)
        unit = d.get('unit', None)
        fmt = d.get('fmt', None)
        dft = d.get('def', None)
        min = d.get('min', None)
        max = d.get('max', None)
        inc = d.get('inc', None)
        opt = d.get('opt', None)

        # Check and convert properties
        if not fam or not lvl or not nr or not name or not fmt:
            return None
        
        if type(pnr) is not int:
            return None

        if type(nr) is not int:
            return None

        lvl = LEVEL.from_str(lvl)
        fmt = FORMAT.from_str(fmt)
        
        name = str(name).strip()
        dft = float(dft) if (type(dft) is int or type(dft) is float) else "S" if (dft=="S") else None
        min = float(min) if (type(min) is int or type(min) is float) else "S" if (dft=="S") else None
        max = float(max) if (type(max) is int or type(max) is float) else "S" if (dft=="S") else None
        inc = float(inc) if (type(inc) is int or type(inc) is float) else "S" if (dft=="S") else None
            
        return XcomDatapoint(fam, lvl, pnr, nr, name, abbr, unit, fmt, dft, min, max, inc, opt)
        
    @property
    def obj_type(self):
        if self.level in [LEVEL.INFO]:
            return OBJ_TYPE.INFO

        if self.level in [LEVEL.BASIC, LEVEL.EXPERT, LEVEL.INST, LEVEL.QSP]:
            return OBJ_TYPE.PARAMETER
            
        _LOGGER.debug(f"Unknown obj_type for datapoint {self.nr} with level {self.level} and format {self.format}")
        return OBJ_TYPE.INFO


class XcomDataset:

    def __init__(self, datapoints: list[XcomDatapoint] | None = None):
        self._datapoints = datapoints
   

    @staticmethod
    async def create(voltage: str):
        """
        The actual XcomDataset list is kept in a separate json file to reduce the memory size needed to load the integration.
        The list is only loaded during config flow and during initial startup, and then released again.
        """
        path_120vac = __file__.replace('.py', '_120v.json')   # Override values for 120 Vac
        path_240vac = __file__.replace('.py', '_240v.json')   # Base values for both 120 Vac and 240 Vac

        async with aiofiles.open(path_120vac, "r", encoding="UTF-8") as file_120vac:
            text_120vac = await file_120vac.read()
        async with aiofiles.open(path_240vac, "r", encoding="UTF-8") as file_240vac:
            text_240vac = await file_240vac.read()
        
        values_120vac = orjson.loads(text_120vac)
        values_240vac = orjson.loads(text_240vac)

        datapoints_120vac = list(filter(None, [XcomDatapoint.from_dict(val) for val in values_120vac]))
        datapoints_240vac = list(filter(None, [XcomDatapoint.from_dict(val) for val in values_240vac]))

        # start with the 240v list as base
        datapoints = datapoints_240vac

        if voltage == "120 Vac":
            # Merge the 120v list into the 240v one by replacing duplicates. This maintains the order of menu items
            for dp120 in datapoints_120vac:
                # already in result?
                index = next( (idx for idx,dp240 in enumerate(datapoints) if dp120.nr == dp240.nr and dp120.family_id == dp240.family_id ), None)
                if index is not None:
                    datapoints[index] = dp120

            _LOGGER.info(f"Using {len(datapoints)} datapoints for 120 Vac")

        elif voltage == "240 Vac":
            _LOGGER.info(f"Using {len(datapoints)} datapoints for 240 Vac")

        else:
            raise Exception(f"Unknown voltage: '{voltage}'")

        return XcomDataset(datapoints)


    def getByNr(self, nr: int, family_id: str|None = None) -> XcomDatapoint:
        for point in self._datapoints:
            if point.nr == nr and (point.family_id == family_id or family_id is None):
                return point

        raise XcomDatapointUnknownException(nr, family_id)
    

    def getByName(self, name: str, family_id: str|None = None) -> XcomDatapoint:
        for point in self._datapoints:
            if point.name == name and (point.family_id == family_id or family_id is None):
                return point

        raise XcomDatapointUnknownException(name, family_id)
    

    def getMenuItems(self, parent: int = 0, family_id: str|None = None):
        datapoints = []
        for point in self._datapoints:
            if point.parent == parent and (point.family_id == family_id or family_id is None):
                datapoints.append(point)

        return datapoints

