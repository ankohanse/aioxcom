"""xcom_api.py: communication api to Studer Xcom via LAN."""

import aiohttp
import asyncio
import ipaddress
import logging
import os
import struct

from dataclasses import dataclass

from .xcom_api import (
    XcomApiBase,
)
from .xcom_datapoints import (
    XcomDatapoint,
    XcomDataset,
    XcomDatapointUnknownException,
)
from .xcom_families import (
    XcomDeviceFamilies
)

_LOGGER = logging.getLogger(__name__)
logging.getLogger("aiohttp").setLevel(logging.WARNING)


@dataclass
class XcomDiscoveredDevice:
    # Base info
    code: str
    addr: int
    family_id: str
    family_model: str

    # Extended info
    device_model: str = None
    hw_version: str = None
    sw_version: str = None
    fid: str = None


class XcomDiscover:

    def __init__(self, api: XcomApiBase, dataset: XcomDataset):
        """
        MOXA is connecting to the TCP Server we are creating here.
        Once it is connected we can send package requests.
        """
        self._api = api
        self._dataset = dataset


    async def discoverDevices(self, getExtendedInfo = False, verbose = False) -> list[XcomDiscoveredDevice]:
        """
        Discover which Studer devices can be reached via the Xcom client
        """
        devices: list[XcomDiscoveredDevice] = []

        for family in XcomDeviceFamilies.getList():

            _LOGGER.info(f"Trying family {family.id} ({family.model})")

            # Get value for the specific discovery nr, or otherwise the first info nr or first param nr
            nr = family.nrDiscover or family.nrInfosStart or family.nrParamsStart or None
            if not nr:
                continue

            # Iterate all addresses in the family, up to the first address that is not found
            for device_addr in range(family.addrDevicesStart, family.addrDevicesEnd+1):

                device_code = family.getCode(device_addr)

                # Send the test request to the device. This will return None in case:
                # - the device does not exist (DEVICE_NOT_FOUND)
                # - the device does not support the param (INVALID_DATA), used to distinguish BSP from BMS
                try:
                    param = self._dataset.getByNr(nr, family.idForNr)

                    _LOGGER.info(f"Trying device {device_code} on {device_addr} for nr {nr}")
                    value = await self._api.requestValue(param, device_addr, verbose=verbose)
                    if value is not None:
                        _LOGGER.info(f"  Found device {device_code} via {nr}:{device_addr}")

                        device = XcomDiscoveredDevice(device_code, device_addr, family.id, family.model)
                        if getExtendedInfo:
                            device = await self.getExtendedDeviceInfo(device, verbose=verbose)
                        
                        devices.append(device)

                    else:
                        _LOGGER.info(f"  No device {device_code}; no value returned from Xcom client: {e}")

                except Exception as e:
                    _LOGGER.info(f"  No device {device_code}; no test value returned from Xcom client: {e}")

                    # Do not test further device addresses in this family
                    break

        return devices


    async def getExtendedDeviceInfo(self, device: XcomDiscoveredDevice, verbose=False) -> XcomDiscoveredDevice:
        # ID type
        # ID HW
        # ID HW PWR
        # ID SOFT msb/lsb
        # ID SID
        # ID FID msb/lsb
        try:
            _LOGGER.info(f"Trying to get extended device info for device {device.code})")
            family = XcomDeviceFamilies.getById(device.family_id)

            id_type    = await self._requestValueByName("ID type",     family.id, device.addr, verbose=verbose)
            id_hw      = await self._requestValueByName("ID HW",       family.id, device.addr, verbose=verbose)
            id_hw_pwr  = await self._requestValueByName("ID HW PWR",   family.id, device.addr, verbose=verbose)
            id_sw_msb  = await self._requestValueByName("ID SOFT msb", family.id, device.addr, verbose=verbose)
            id_sw_lsb  = await self._requestValueByName("ID SOFT lsb", family.id, device.addr, verbose=verbose)
            id_fid_msb = await self._requestValueByName("ID FID msb",  family.id, device.addr, verbose=verbose)
            id_fid_lsb = await self._requestValueByName("ID FID lsb",  family.id, device.addr, verbose=verbose)

            device.device_model = self._decodeType(id_type, "ID type", family.idForNr)
            device.hw_version   = self._decodeIdHW(id_hw, id_hw_pwr)
            device.sw_version   = self._decodeIdSW(id_sw_msb, id_sw_lsb)
            device.fid          = self._decodeFID(id_fid_msb, id_fid_lsb)

            _LOGGER.info(f"  Found extended device info: model: {device.device_model}, hw_version: {device.hw_version}, sw_version: {device.sw_version}, fid: {device.fid})")

        except Exception as e:
            _LOGGER.warning(f"  Exception in getExtendedDeviceInfo: {e}")

        return device


    async def _requestValueByName(self, param_name, family_id, device_addr, verbose=False):
        try:
            param = self._dataset.getByName(param_name, family_id)
            return await self._api.requestValue(param, device_addr, verbose=verbose)
        except:
            # Not all devices have these IDs
            return None
        

    def _decodeType(self, val, param_name, family_id):
        if val is None:
            return None

        param = self._dataset.getByName(param_name, family_id)
        return param.options.get(str(int(val)), None) if param.options else None


    def _decodeIdHW(self, cmd, pwr):
        if cmd is None:
            return None
        
        bytes_cmd = struct.pack(">H", int(cmd))
        if pwr is None:
            return f"{int(bytes_cmd[0])}.{int(bytes_cmd[1])}"
        else:
            bytes_pwr = struct.pack(">H", int(pwr))
            return f"{int(bytes_cmd[0])}.{int(bytes_cmd[1])} / {int(bytes_pwr[0])}.{int(bytes_pwr[1])}"


    def _decodeIdSW(self, msb, lsb):
        if msb is None or lsb is None:
            return None
        
        bytes = struct.pack(">H", int(msb)) + struct.pack(">H", int(lsb))
        return f"{int(bytes[0])}.{int(bytes[2])}.{int(bytes[3])}"


    def _decodeFID(self, msb, lsb):
        if msb is None or lsb is None:
            return None
        
        bytes = struct.pack(">H", int(msb)) + struct.pack(">H", int(lsb))
        return bytes.hex(' ',4).upper()


    @staticmethod
    async def discoverMoxaWebConfig(hint: str = None) -> str:
        """
        Discover if Moxa Web Config page can be found on the local network
        """

        # Find all device IP addresses to check
        urls: list[str] = [hint] if hint else []
        urls.append("http://192.168.127.254")   # default if using static address

        for line in os.popen('arp -a'):     # arp seems to be available on Linux, Windows and Pi
            try:
                device = line.strip('?').split()[0].strip('()')
                ip = ipaddress.ip_address(device)
                urls.append(f"http://{str(ip)}")
            except:
                pass

        # Define helper function to check for Moxa Web Config page
        async def check_url(session, url:str) -> str|None:
            _LOGGER.info(f"Trying {url}")
            async with session.get(url) as rsp:
                if rsp and rsp.ok and rsp.headers.get("Server", "").startswith("Moxa"):
                    return url
                else:
                    return None

        # Parallel check for Moxa Web Config page on all found device url's
        # No need to SSL verify plain HTTP GET calls, this also keeps Home Assistant happy
        async with aiohttp.ClientSession(
            connector = aiohttp.TCPConnector(ssl = False) 
        ) as session:  
            tasks = [asyncio.create_task(check_url(session, url)) for url in urls]
            for task in asyncio.as_completed(tasks):
                try:
                    url = await task
                    if url is not None:
                        # Cleanup remaining tasks and return found url
                        for other_task in tasks:
                            other_task.cancel()

                        _LOGGER.info(f"Found Moxa Web Config url: {url}")
                        return url
                except:
                    pass
                
        return None
        