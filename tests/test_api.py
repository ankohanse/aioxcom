import asyncio
import copy
import pytest
import pytest_asyncio

from aioxcom import XcomApiTcp, XcomDataset, XcomData, XcomPackage
from aioxcom import XcomApiTimeoutException, XcomApiResponseIsError
from aioxcom import VOLTAGE, FORMAT, SCOM_SERVICE, SCOM_OBJ_TYPE, SCOM_QSP_ID, SCOM_ERROR_CODES
from . import XcomTestClientTcp


class TestContext:
    def __init__(self):
        self.server = None
        self.client = None

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
            await self.client.stop()
        self.client = None


@pytest_asyncio.fixture
async def context():
    # Prepare
    ctx = TestContext()

    # pass objects to tests
    yield ctx

    # cleanup
    await ctx.stop_client()
    await ctx.stop_server()


@pytest.mark.asyncio
@pytest.mark.usefixtures("context", "unused_tcp_port")
@pytest.mark.parametrize(
    "name, start_server, start_client, wait_server, exp_server_conn, exp_client_conn, exp_server_ip, exp_client_ip",
    [
        ("connect no start", False, False, False, False, False, None, None),
        ("connect no wait",  True,  False, False, False, False, None, None),
        ("connect timeout",  True,  False, True,  False, False, None, None),
        ("connect ok",       True,  True,  True,  True,  True,  "127.0.0.1", "127.0.0.1"),
    ]
)
async def test_connect(name, start_server, start_client, wait_server, exp_server_conn, exp_client_conn, exp_server_ip, exp_client_ip, request):

    context = request.getfixturevalue("context")
    port    = request.getfixturevalue("unused_tcp_port")

    assert context.server is None
    assert context.client is None

    if start_server:
        await context.start_server(port)

        assert context.server is not None
        assert context.server.connected == False

    if start_client:
        await context.start_client(port)

        assert context.client is not None

    if wait_server:
        await context.server._waitConnected(5)

        assert context.server is not None

    assert context.server is None or context.server.connected == exp_server_conn
    assert context.client is None or context.client.connected == exp_client_conn

    assert context.server is None or context.server.remote_ip == exp_server_ip
    assert context.client is None or context.client.remote_ip == exp_client_ip


@pytest.mark.asyncio
@pytest.mark.usefixtures("context", "unused_tcp_port")
@pytest.mark.parametrize(
    "name, test_nr, test_dest, test_value_update, exp_dst_addr, exp_svc_id, exp_obj_type, exp_obj_id, exp_prop_id, rsp_flags, rsp_data, exp_value, exp_except",
    [
        ("request info ok",      3000, 100, None, 100, SCOM_SERVICE.READ, SCOM_OBJ_TYPE.INFO, 3000, SCOM_QSP_ID.VALUE, 0x02, XcomData.pack(1234.0, FORMAT.FLOAT), 1234.0, None),
        ("request info err",     3000, 100, None, 100, SCOM_SERVICE.READ, SCOM_OBJ_TYPE.INFO, 3000, SCOM_QSP_ID.VALUE, 0x03, XcomData.pack(SCOM_ERROR_CODES.READ_PROPERTY_FAILED, FORMAT.ERROR), None, XcomApiResponseIsError),
        ("request info timeout", 3000, 100, None, 100, SCOM_SERVICE.READ, SCOM_OBJ_TYPE.INFO, 3000, SCOM_QSP_ID.VALUE, 0x00, XcomData.pack(1234.0, FORMAT.FLOAT), None, XcomApiTimeoutException),
        ("request param ok",     1107, 100, None, 100, SCOM_SERVICE.READ, SCOM_OBJ_TYPE.PARAMETER, 1107, SCOM_QSP_ID.UNSAVED_VALUE, 0x02, XcomData.pack(1234.0, FORMAT.FLOAT), 1234.0, None),
        ("update param ok",      1107, 100, 4.0,  100, SCOM_SERVICE.WRITE, SCOM_OBJ_TYPE.PARAMETER, 1107, SCOM_QSP_ID.UNSAVED_VALUE, 0x02, b'', True, None),
        ("update param err",     1107, 100, 4.0,  100, SCOM_SERVICE.WRITE, SCOM_OBJ_TYPE.PARAMETER, 1107, SCOM_QSP_ID.UNSAVED_VALUE, 0x03, XcomData.pack(SCOM_ERROR_CODES.WRITE_PROPERTY_FAILED, FORMAT.ERROR), None, XcomApiResponseIsError),
        ("update param timeout", 1107, 100, 4.0,  100, SCOM_SERVICE.WRITE, SCOM_OBJ_TYPE.PARAMETER, 1107, SCOM_QSP_ID.UNSAVED_VALUE, 0x00, b'', True, XcomApiTimeoutException),
        ("request param vo",     5012, 501, None, 501, SCOM_SERVICE.READ, SCOM_OBJ_TYPE.PARAMETER, 5012, SCOM_QSP_ID.UNSAVED_VALUE, 0x02, XcomData.pack(32, FORMAT.INT32), 32, None),
        ("update param vo",      5012, 501, 32,   501, SCOM_SERVICE.WRITE, SCOM_OBJ_TYPE.PARAMETER, 5012, SCOM_QSP_ID.UNSAVED_VALUE, 0x03, XcomData.pack(SCOM_ERROR_CODES.ACCESS_DENIED, FORMAT.ERROR), None, XcomApiResponseIsError),
    ]
)
async def test_request(name, test_nr, test_dest, test_value_update, exp_dst_addr, exp_svc_id, exp_obj_type, exp_obj_id, exp_prop_id, rsp_flags, rsp_data, exp_value, exp_except, request):
    context = request.getfixturevalue("context")
    port    = request.getfixturevalue("unused_tcp_port")

    # The order of start is important, first server, then client.
    await context.start_server(port)
    await context.start_client(port)

    await context.server._waitConnected(5)
    assert context.server.connected == True
    assert context.client.connected == True

    dataset = await XcomDataset.create(VOLTAGE.AC240)
    param = dataset.getByNr(test_nr)

    # Helper function for client to handle a request and submit a response
    async def clientHandler():
    
        # Receive the request from the server
        req: XcomPackage = await context.client.receivePackage()

        # Make a deep copy of the request and turn it into a response
        rsp = copy.deepcopy(req)
        rsp.frame_data.service_flags = rsp_flags
        rsp.frame_data.service_data.property_data = rsp_data
        rsp.header.data_length = len(rsp.frame_data)

        # Send the response back to the server
        await context.client.sendPackage(rsp)
        return req,rsp

    # Start 2 parallel tasks, for server and for client
    if test_value_update:
        task_server = asyncio.create_task(context.server.updateValue(param, test_value_update, test_dest, retries=1, timeout=5))
    else:
        task_server = asyncio.create_task(context.server.requestValue(param, test_dest, retries=1, timeout=5))

    task_client = asyncio.create_task(clientHandler())

    # Wait for client to finish and check the received request
    req, rsp = await task_client

    assert req.header.dst_addr == exp_dst_addr
    assert req.frame_data.service_id == exp_svc_id
    assert req.frame_data.service_data.object_type == exp_obj_type
    assert req.frame_data.service_data.object_id == exp_obj_id
    assert req.frame_data.service_data.property_id == exp_prop_id

    # Wait for server to finish and check the handling of the received response
    if exp_except == None:
        value = await task_server
        assert value == exp_value
    else:
        with pytest.raises(exp_except):
            await task_server
