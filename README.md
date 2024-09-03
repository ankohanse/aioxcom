[![license](https://img.shields.io/github/license/toreamun/amshan-homeassistant?style=for-the-badge)](LICENSE)
[![buy_me_a_coffee](https://img.shields.io/badge/If%20you%20like%20it-Buy%20me%20a%20coffee-yellow.svg?style=for-the-badge)](https://www.buymeacoffee.com/ankohanse)


# aioxcom

Python library for retrieving sensor information from Studer-Innotec devices.
This component connects directly over the local network using the Studer xcom protocol.

The custom component was tested with:
- Xtender XTH 8000-48 (but should also work for other XTH, XTS and XTM)
- Xcom-CAN (BSP connection to a third party BMS)
- Xcom-LAN (which actually is a Xcom232i with a Moxy NPort 5110A)
- RCC-03

It should also be able to detect and handle
- Studer BMS
- VarioTrack
- VarioString
- RCC-02


# Prerequisites

This device depends on having a Studer Xcom-LAN (i.e. an Xcom-232i and a Moxa ethernet gateway) acting as a Xcom client and connecting to this integration. For older systems this will be a separate component, for future systems Studer have indicated that LAN connection will become part of the Xtender range.

The Studer Xcom-LAN will be able to simultaneously send data to the Studer online portal as well as sending data to this integration.

Configuration steps:

1. Download and install the Moxa DSU tool (Device Search Utility)
    - Open [www.moxa.com](https://www.moxa.com) in a browser
    - Select Support -> Software and Documentation
    - Choose NPort 5100A series (or whatever specific device you have)
    - Scroll down under 'Related Software, Firmware and Drivers' to find 'Device Search Utility'
    - Download and install the utility

2. Locate the Moxa NPort device on the local network
    - Run the Moxa Device Search Utility
    - Press the 'Search' button and wait until the search finishes
    - The utility should display the found NPort device
    - Double click on the found device to open its configuration page

      ![dsu_search_results](documentation/DSU_results.png)

3. Configure the Moxa NPort device
    - In the Main Menu, select 'Operating Settings' -> Port 1
    - Verify that 'Operation Mode' is set to 'TCP Client'
    - Add the ip-address or network name of your HomeAssistant as 'Destination IP address'
    - Press the 'Submit' button
    - Press 'Save/Restart'

      ![moxa_operating_settings](documentation/Moxa_operating_settings.png)


# Usage

To read an infos or param or write to a param:

```
from aioxcom import XcomApiTcp, XcomDataset, VOLTAGE

api = XcomApiTcp(4001)    # port number configured in Xcom-LAN/Moxa NPort
dataset = XcomDataset.create(VOLTAGE.AC240) # or use VOLTAGE.AC120
try:
    await api.start()

    # Retrieve info #3023 from the first Xtender (Output power)
    param = dataset.getByNr(3023, "xt")
    value = await api.requestValue(param, 101)    # xt address range is 101 to 109
    print f"XT1 3023: {value}"

    # Retrieve param #6001 from BSP (Nominal capacity)
    param = dataset.getByNr(6001, "bsp")
    value = await api.requestValue(param, 601)    # bsp address range is only 601
    print f"BSP 6001: {value}"

    # Update param 1107 on the first Xtender (Maximum current of AC source)
    param = dataset.getByNr(1107, "xt")
    value = 4.0    # 4 Ampere
    if await api.updateValue(param, value 101):
        print f"XT1 1107 updated to {value}

    # Retrieve menu structure
    items = dataset.getMenu(0, "xt)     # use 0 for root menu, or item.nr for lower menu's

finally:
    await api.stop()
```

A complete list of param and infos numbers can be found in the source of this library in file `src/aioxcom/xcom_datapoints_240v.json`  

A complete list of all available device families and their address range can be found in file `src/aioxcom/xcom_families.py`  


# Param writes to device RAM

When the value of a Studer param is changed via this library, these are written via Xcom to the affected device. 
Changes are stored in the device's RAM memory, not in its flash memory as you can only write to flash a limited number of time over its lifetime.

However, reading back the value from the entity will be from flash (querying RAM gives unreliable responses). As a result, the change to the entity value is not visible. You can only tell from the behavior of the PV system that the Studer param was indeed changed.  
After a restart/reboot of the PV system the system will revert to the value from Flash. So you may want to periodically repeat the write of changed param values via an automation.

**IMPORTANT**:

I will not take responsibility for damage to your PV system resulting from you choosing to change Studer params you are not supposed to change. Or setting a combination of param values that cause an invalid status.  
Be very carefull in changing params marked as having level Expert, Installer or even Qualified Service Person. If you do not know what the effect of a Studer param change is, then do not change it.


# Credits

Special thanks to the following people for providing the information this library is based on:
- [zocker-160](https://github.com/zocker-160/xcom-protocol)
- [Michael Jeffers](https://community.home-assistant.io/u/JeffersM)


