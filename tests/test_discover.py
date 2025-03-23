import asyncio
import copy
import threading
import pytest
import pytest_asyncio

from aioxcom import XcomDiscover, XcomApiTcp, XcomDataset, XcomData, XcomPackage
from aioxcom import XcomApiTimeoutException, XcomApiResponseIsError
from aioxcom import VOLTAGE, FORMAT, SCOM_SERVICE, SCOM_OBJ_TYPE, SCOM_QSP_ID, SCOM_ERROR_CODES
from . import XcomTestClientTcp


class TestContext:
    def __init__(self):
        self.discover = None
        self.server = None
        self.client = None
        self.client_stop = threading.Event()

    async def start_discover(self, dataset):
        self.discover = XcomDiscover(self.server, dataset)

    async def stop_discover(self):
        self.discover = None

    async def start_server(self, port):
        if not self.server:
            self.server = XcomApiTcp(port)

        await self.server.start(wait_for_connect = False)

    async def stop_server(self):
        if self.server:
            await self.server.stop()
        self.server = None

    async def start_client(self, port):
        if not self.client:
            self.client = XcomTestClientTcp(port)

        await self.client.start()

    async def stop_client(self):
        if self.client:
            if not self.client_stop.is_set():
                self.client_stop.set()
                await asyncio.sleep(5)

            await self.client.stop()
        self.client = None

    # Helper function for client to handle a request and submit a response
    async def clientHandler(self, rsp_dest, rsp_dict):
        while not self.client_stop.is_set():
            # Receive the request from the server
            try:
                req: XcomPackage = await self.client.receivePackage()
                if req:
                    # Make a deep copy of the request and turn it into a response
                    if req.header.dst_addr not in rsp_dest:
                       flags = 0x03
                       data = SCOM_ERROR_CODES.DEVICE_NOT_FOUND

                    elif str(req.frame_data.service_data.object_id) not in rsp_dict:
                        flags = 0x03
                        data = SCOM_ERROR_CODES.READ_PROPERTY_FAILED

                    else:
                        flags = 0x02
                        data = rsp_dict[str(req.frame_data.service_data.object_id)]

                    rsp = copy.deepcopy(req)
                    rsp.frame_data.service_flags = flags
                    rsp.frame_data.service_data.property_data = data
                    rsp.header.data_length = len(rsp.frame_data)

                    # Send the response back to the server
                    await self.client.sendPackage(rsp)
            except XcomApiTimeoutException:
                pass


@pytest_asyncio.fixture
async def context():
    # Prepare
    ctx = TestContext()

    # pass objects to tests
    yield ctx

    # cleanup
    await ctx.stop_discover()
    await ctx.stop_client()
    await ctx.stop_server()


@pytest.mark.asyncio
@pytest.mark.usefixtures("context", "unused_tcp_port")
@pytest.mark.parametrize(
    "name, rsp_dest, rsp_dict, exp_devices",
    [
        ("none",        [],             { "3000": XcomData.pack(1234.0, FORMAT.FLOAT) },  []),
        ("xt1",         [101],          { "3000": XcomData.pack(1234.0, FORMAT.FLOAT) },  ["XT1"]),
        ("xt1,xt2,xt3", [101,102,103],  { "3000": XcomData.pack(1234.0, FORMAT.FLOAT) },  ["XT1", "XT2", "XT3"]),
        ("l1",          [191],          { "3000": XcomData.pack(1234.0, FORMAT.FLOAT) },  ["L1"]),
        ("l1,l2,l3",    [191,192,193],  { "3000": XcomData.pack(1234.0, FORMAT.FLOAT) },  ["L1", "L2", "L3"]),
        ("rcc",         [501],          { "5002": XcomData.pack(1234.0, FORMAT.FLOAT) },  ["RCC"]),
        ("bsp",         [601],          { "7036": XcomData.pack(1234.0, FORMAT.FLOAT) },  ["BSP"]),
        ("bms",         [601],          { "7054": XcomData.pack(1234.0, FORMAT.FLOAT) },  ["BMS"]),
        ("vt1",         [301],          { "11000": XcomData.pack(1234.0, FORMAT.FLOAT) }, ["VT1"]),
        ("vt1,vt2",     [301,302],      { "11000": XcomData.pack(1234.0, FORMAT.FLOAT) }, ["VT1", "VT2"]),
        ("vs1",         [701],          { "15000": XcomData.pack(1234.0, FORMAT.FLOAT) }, ["VS1"]),
        ("vs1,vs2",     [701,702],      { "15000": XcomData.pack(1234.0, FORMAT.FLOAT) }, ["VS1", "VS2"]),
    ]
)
async def test_discover_devices(name, rsp_dest, rsp_dict, exp_devices, request):
    context = request.getfixturevalue("context")
    port    = request.getfixturevalue("unused_tcp_port")

    # The order of start is important, first discover server, then client
    await context.start_server(port)
    await context.start_client(port)
    
    await context.server._waitConnected(5)
    assert context.server.connected == True
    assert context.client.connected == True

    # Once the server is started, we can use it to create the discovery helper
    dataset = await XcomDataset.create(VOLTAGE.AC240)
    discover = XcomDiscover(api=context.server, dataset=dataset)

    # Start 2 parallel tasks, for server and for client
    task_discover = asyncio.create_task(discover.discoverDevices(getExtendedInfo=False))
    task_client = asyncio.create_task(context.clientHandler(rsp_dest, rsp_dict))

    # wait for discover to finish
    devices = await task_discover
    discover = None
    dataset = None

    # Wait for client to finish
    context.client_stop.set()
    await asyncio.sleep(5)
    await task_client

    # Check discovered devices
    assert len(devices) == len(exp_devices)
    for device in devices:
        assert device.code in exp_devices
        assert device.addr in rsp_dest
        assert device.family_id is not None
        assert device.family_model is not None
        
        assert device.device_model is None
        assert device.fid is None
        assert device.hw_version is None
        assert device.sw_version is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("context", "unused_tcp_port")
@pytest.mark.parametrize(
    "name, rsp_dest, rsp_dict, exp_code, exp_model, exp_hw_version, exp_sw_version, exp_fid",
    [
        ("xt1 none",    [101], {
                            "3000": XcomData.pack(1234.0, FORMAT.FLOAT)  # detect
                        }, "XT1", None, None, None, None),
        ("xt1 ext",     [101], {
                            "3000": XcomData.pack(1234.0, FORMAT.FLOAT), # detect
                            "3124": XcomData.pack(0x01, FORMAT.FLOAT),   # device_model
                            "3129": XcomData.pack(0x0203, FORMAT.FLOAT), # hw_version
                            "3132": XcomData.pack(0x0405, FORMAT.FLOAT), # hw_version
                            "3130": XcomData.pack(0x0607, FORMAT.FLOAT), # sw_version
                            "3131": XcomData.pack(0x0809, FORMAT.FLOAT), # sw_version
                            "3156": XcomData.pack(0x0908, FORMAT.FLOAT), # fid
                            "3157": XcomData.pack(0x0706, FORMAT.FLOAT), # fid
                        }, "XT1", "XTH", "2.3 / 4.5", "6.8.9", "09080706"),
        ("bsp ext",     [601], {
                            "7036": XcomData.pack(1.0, FORMAT.FLOAT),    # detect
                            "7034": XcomData.pack(10241, FORMAT.FLOAT),  # device_model
                            "7036": XcomData.pack(0X0102, FORMAT.FLOAT), # hw_version
                            "7037": XcomData.pack(0X0304, FORMAT.FLOAT), # sw_version      
                            "7038": XcomData.pack(0X0506, FORMAT.FLOAT), # sw_version
                            "7048": XcomData.pack(0x0708, FORMAT.FLOAT), # fid
                            "7049": XcomData.pack(0x0901, FORMAT.FLOAT), # fid
                        }, "BSP", None, "1.2", "3.5.6", "07080901"),
        ("vt1 ext",     [301], {
                            "11000": XcomData.pack(1234.0, FORMAT.FLOAT), #detect
                            "11047": XcomData.pack(9079, FORMAT.FLOAT),   # device_model
                            "11049": XcomData.pack(0X0102, FORMAT.FLOAT), # hw_version
                            "11050": XcomData.pack(0X0304, FORMAT.FLOAT), # sw_version
                            "11051": XcomData.pack(0X0506, FORMAT.FLOAT), # sw_version
                            "11067": XcomData.pack(0x0708, FORMAT.FLOAT), # fid
                            "11068": XcomData.pack(0x0901, FORMAT.FLOAT), # fid
                        }, "VT1", None, "1.2", "3.5.6", "07080901"),
        ("vs1 ext",     [701], {
                            "15000": XcomData.pack(1234.0, FORMAT.FLOAT), # detect
                            "15074": XcomData.pack(12801, FORMAT.FLOAT),  # device_model
                            "15076": XcomData.pack(0X0102, FORMAT.FLOAT), # hw_version
                            "15077": XcomData.pack(0X0304, FORMAT.FLOAT), # sw_version
                            "15078": XcomData.pack(0X0506, FORMAT.FLOAT), # sw_version
                            "15102": XcomData.pack(0x0708, FORMAT.FLOAT), # fid 
                            "15103": XcomData.pack(0x0901, FORMAT.FLOAT), # fid  
                        }, "VS1", "VS120", "1.2", "3.5.6", "07080901"),
    ]
)
async def test_discover_extendedinfo(name, rsp_dest, rsp_dict, exp_code, exp_model, exp_hw_version, exp_sw_version, exp_fid, request):
    context = request.getfixturevalue("context")
    port    = request.getfixturevalue("unused_tcp_port")

    # The order of start is important, first discover server, then client
    await context.start_server(port)
    await context.start_client(port)

    await context.server._waitConnected(5)
    assert context.server.connected == True
    assert context.client.connected == True

    # Once the server is started, we can use it to create the discovery helper
    dataset = await XcomDataset.create(VOLTAGE.AC240)
    discover = XcomDiscover(api=context.server, dataset=dataset)

    # Start 2 parallel tasks, for server and for client
    task_discover = asyncio.create_task(discover.discoverDevices(getExtendedInfo=True))
    task_client = asyncio.create_task(context.clientHandler(rsp_dest, rsp_dict))

    # wait for discover to finish
    devices = await task_discover
    discover = None
    dataset = None

    # Wait for client to finish
    context.client_stop.set()
    await asyncio.sleep(5)
    await task_client

    # Check discovered devices
    assert len(devices) == 1
    device = devices[0]

    assert device.code in exp_code
    assert device.device_model == exp_model
    assert device.hw_version == exp_hw_version
    assert device.sw_version == exp_sw_version
    assert device.fid == exp_fid


@pytest.mark.asyncio
@pytest.mark.usefixtures("context", "unused_tcp_port")
@pytest.mark.parametrize(
    "name, rsp_dest, rsp_dict",
    [
        ("localhost", [], {}),
    ]
)
async def test_clientinfo(name, rsp_dest, rsp_dict, request):
    context = request.getfixturevalue("context")
    port    = request.getfixturevalue("unused_tcp_port")

    # The order of start is important, first discover server, then client
    await context.start_server(port)
    await context.start_client(port)

    await context.server._waitConnected(5)
    assert context.server.connected == True
    assert context.client.connected == True

    # Once the server is started, we can use it to create the discovery helper
    dataset = await XcomDataset.create(VOLTAGE.AC240)
    discover = XcomDiscover(api=context.server, dataset=dataset)

    # Start task for discover
    client_info = await discover.discoverClientInfo()
    discover = None
    dataset = None

    # Check discovered info
    assert client_info is not None
    assert client_info.ip == "127.0.0.1"
    assert client_info.mac == "00:00:00:00:00:00"
