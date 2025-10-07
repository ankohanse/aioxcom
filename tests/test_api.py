import asyncio
import copy
from datetime import datetime
import pytest
import pytest_asyncio

from aioxcom import XcomApiTcp, XcomDataset, XcomData, XcomPackage
from aioxcom import XcomApiTimeoutException, XcomApiResponseIsError, XcomParamException
from aioxcom import XcomValues, XcomValuesItem
from aioxcom import XcomVoltage, XcomFormat, XcomAggregationType, ScomService, ScomObjType, ScomObjId, ScomQspId, ScomAddress, ScomErrorCode
from aioxcom import XcomDataMessageRsp
from . import XcomTestClientTcp


class TestContext:
    __test__ = False  # Prevent pytest from collecting this class

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
    "name, test_nr, test_dest, exp_dst_addr, exp_svc_id, exp_obj_type, exp_obj_id, exp_prop_id, rsp_flags, rsp_data, exp_value, exp_except",
    [
        ("request info ok",      3000, 100, 100, ScomService.READ, ScomObjType.INFO, 3000, ScomQspId.VALUE, 0x02, XcomData.pack(1234.0, XcomFormat.FLOAT), 1234.0, None),
        ("request info err",     3000, 100, 100, ScomService.READ, ScomObjType.INFO, 3000, ScomQspId.VALUE, 0x03, XcomData.pack(ScomErrorCode.READ_PROPERTY_FAILED, XcomFormat.ERROR), None, XcomApiResponseIsError),
        ("request info timeout", 3000, 100, 100, ScomService.READ, ScomObjType.INFO, 3000, ScomQspId.VALUE, 0x00, XcomData.pack(1234.0, XcomFormat.FLOAT), None, XcomApiTimeoutException),
        ("request param ok",     1107, 100, 100, ScomService.READ, ScomObjType.PARAMETER, 1107, ScomQspId.UNSAVED_VALUE, 0x02, XcomData.pack(1234.0, XcomFormat.FLOAT), 1234.0, None),
        ("request param vo",     5012, 501, 501, ScomService.READ, ScomObjType.PARAMETER, 5012, ScomQspId.UNSAVED_VALUE, 0x02, XcomData.pack(32, XcomFormat.INT32), 32, None),
    ]
)
async def test_requestValue(name, test_nr, test_dest, exp_dst_addr, exp_svc_id, exp_obj_type, exp_obj_id, exp_prop_id, rsp_flags, rsp_data, exp_value, exp_except, request):
    context = request.getfixturevalue("context")
    port    = request.getfixturevalue("unused_tcp_port")

    # The order of start is important, first server, then client.
    await context.start_server(port)
    await context.start_client(port)

    await context.server._waitConnected(5)
    assert context.server.connected == True
    assert context.client.connected == True

    dataset = await XcomDataset.create(XcomVoltage.AC240)
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


@pytest.mark.asyncio
@pytest.mark.usefixtures("context", "unused_tcp_port")
@pytest.mark.parametrize(
    "name, test_nr, test_dest, test_value_update, exp_dst_addr, exp_svc_id, exp_obj_type, exp_obj_id, exp_prop_id, rsp_flags, rsp_data, exp_value, exp_except",
    [
        ("update param ok",      1107, 100, 4.0,  100, ScomService.WRITE, ScomObjType.PARAMETER, 1107, ScomQspId.UNSAVED_VALUE, 0x02, b'', True, None),
        ("update param err",     1107, 100, 4.0,  100, ScomService.WRITE, ScomObjType.PARAMETER, 1107, ScomQspId.UNSAVED_VALUE, 0x03, XcomData.pack(ScomErrorCode.WRITE_PROPERTY_FAILED, XcomFormat.ERROR), None, XcomApiResponseIsError),
        ("update param timeout", 1107, 100, 4.0,  100, ScomService.WRITE, ScomObjType.PARAMETER, 1107, ScomQspId.UNSAVED_VALUE, 0x00, b'', True, XcomApiTimeoutException),
        ("update param vo",      5012, 501, 32,   501, ScomService.WRITE, ScomObjType.PARAMETER, 5012, ScomQspId.UNSAVED_VALUE, 0x03, XcomData.pack(ScomErrorCode.ACCESS_DENIED, XcomFormat.ERROR), None, XcomApiResponseIsError),
    ]
)
async def test_updateValue(name, test_nr, test_dest, test_value_update, exp_dst_addr, exp_svc_id, exp_obj_type, exp_obj_id, exp_prop_id, rsp_flags, rsp_data, exp_value, exp_except, request):
    context = request.getfixturevalue("context")
    port    = request.getfixturevalue("unused_tcp_port")

    # The order of start is important, first server, then client.
    await context.start_server(port)
    await context.start_client(port)

    await context.server._waitConnected(5)
    assert context.server.connected == True
    assert context.client.connected == True

    dataset = await XcomDataset.create(XcomVoltage.AC240)
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
    task_server = asyncio.create_task(context.server.updateValue(param, test_value_update, test_dest, retries=1, timeout=5))
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


@pytest_asyncio.fixture
async def dataset():
    dataset = await XcomDataset.create(XcomVoltage.AC240)
    yield dataset

@pytest_asyncio.fixture
async def data_infos_dev(dataset):
    info_3021 = dataset.getByNr(3021)
    info_3022 = dataset.getByNr(3022)
    info_3023 = dataset.getByNr(3023)

    req_data = XcomValues([
        XcomValuesItem(info_3021, code="XT1"),
        XcomValuesItem(info_3022, aggregation_type=XcomAggregationType.DEVICE1),
        XcomValuesItem(info_3023, address=101),
    ])
    rsp_multi = XcomValues(
        flags = 0x00, 
        datetime = 0, 
        items=[
            XcomValuesItem(info_3021, aggregation_type=XcomAggregationType.MASTER, value=12.3),
            XcomValuesItem(info_3022, aggregation_type=XcomAggregationType.DEVICE1, value=45.6),
            XcomValuesItem(info_3023, aggregation_type=XcomAggregationType.DEVICE1, value=78.9),
        ]
    )
    rsp_single_val = None
    
    yield req_data, rsp_multi, rsp_single_val

@pytest_asyncio.fixture
async def data_infos_aggr(dataset):
    info_3021 = dataset.getByNr(3021)
    info_3022 = dataset.getByNr(3022)
    info_3023 = dataset.getByNr(3023)

    req_data = XcomValues([
        XcomValuesItem(info_3021, aggregation_type=XcomAggregationType.MASTER),
        XcomValuesItem(info_3022, aggregation_type=XcomAggregationType.AVERAGE),
        XcomValuesItem(info_3023, aggregation_type=XcomAggregationType.SUM),
    ])
    rsp_multi = XcomValues(
        flags = 0x00, 
        datetime = 0, 
        items=[
            XcomValuesItem(info_3021, aggregation_type=XcomAggregationType.MASTER, value=12.3),
            XcomValuesItem(info_3022, aggregation_type=XcomAggregationType.AVERAGE, value=45.6),
            XcomValuesItem(info_3023, aggregation_type=XcomAggregationType.SUM, value=78.9),
        ]
    )
    rsp_single_val = None
    
    yield req_data, rsp_multi, rsp_single_val

@pytest_asyncio.fixture
async def data_infos_params_dev(dataset):
    info_3021 = dataset.getByNr(3021)
    info_3022 = dataset.getByNr(3022)
    param_1107 = dataset.getByNr(1107)

    req_data = XcomValues([
        XcomValuesItem(info_3021, code="XT1"),
        XcomValuesItem(info_3022, aggregation_type=XcomAggregationType.DEVICE1),
        XcomValuesItem(param_1107, address=101),
    ])
    rsp_multi = XcomValues(
        flags = 0x00, 
        datetime = 0, 
        items=[
            XcomValuesItem(info_3021, aggregation_type=XcomAggregationType.MASTER, value=12.3),
            XcomValuesItem(info_3022, aggregation_type=XcomAggregationType.DEVICE1, value=45.6),
        ]
    )
    rsp_single_val = 1234.0

    yield req_data, rsp_multi, rsp_single_val


@pytest_asyncio.fixture
async def data_infos_params_aggr(dataset):
    info_3021 = dataset.getByNr(3021)
    info_3022 = dataset.getByNr(3022)
    param_1107 = dataset.getByNr(1107)

    req_data = XcomValues([
        XcomValuesItem(info_3021, aggregation_type=XcomAggregationType.MASTER),
        XcomValuesItem(info_3022, aggregation_type=XcomAggregationType.AVERAGE),
        XcomValuesItem(param_1107, address=101),
    ])
    rsp_multi = XcomValues(
        flags = 0x00, 
        datetime = 0, 
        items=[
            XcomValuesItem(info_3021, aggregation_type=XcomAggregationType.MASTER, value=12.3),
            XcomValuesItem(info_3022, aggregation_type=XcomAggregationType.AVERAGE, value=45.6),
        ]
    )
    rsp_single_val = 1234.0

    yield req_data, rsp_multi, rsp_single_val


@pytest.mark.asyncio
@pytest.mark.usefixtures("context", "unused_tcp_port", "dataset", "data_infos_dev", "data_infos_aggr", "data_infos_params_dev", "data_infos_params_aggr")
@pytest.mark.parametrize(
    "name, values_fixture, run_client, exp_src_addr, exp_dst_addr, exp_svc_id, exp_obj_type, exp_obj_id, exp_prop_id, rsp_flags, exp_except",
    [
        ("request infos dev ok",       "data_infos_dev",         True,  ScomAddress.SOURCE, 501, ScomService.READ, ScomObjType.MULTI_INFO, ScomObjId.MULTI_INFO, ScomQspId.MULTI_INFO, 0x02, None),
        ("request infos dev err",      "data_infos_dev",         True,  ScomAddress.SOURCE, 501, ScomService.READ, ScomObjType.MULTI_INFO, ScomObjId.MULTI_INFO, ScomQspId.MULTI_INFO, 0x03, XcomApiResponseIsError),
        ("request infos dev timeout",  "data_infos_dev",         False, ScomAddress.SOURCE, 501, ScomService.READ, ScomObjType.MULTI_INFO, ScomObjId.MULTI_INFO, ScomQspId.MULTI_INFO, 0x02, XcomApiTimeoutException),
        ("request infos aggr ok",      "data_infos_aggr",        True,  ScomAddress.SOURCE, 501, ScomService.READ, ScomObjType.MULTI_INFO, ScomObjId.MULTI_INFO, ScomQspId.MULTI_INFO, 0x02, None),
        ("request infos aggr err",     "data_infos_aggr",        True,  ScomAddress.SOURCE, 501, ScomService.READ, ScomObjType.MULTI_INFO, ScomObjId.MULTI_INFO, ScomQspId.MULTI_INFO, 0x03, XcomApiResponseIsError),
        ("request infos aggr timeout", "data_infos_aggr",        False, ScomAddress.SOURCE, 501, ScomService.READ, ScomObjType.MULTI_INFO, ScomObjId.MULTI_INFO, ScomQspId.MULTI_INFO, 0x02, XcomApiTimeoutException),
        ("request infos params err",   "data_infos_params_dev",  False, ScomAddress.SOURCE, 501, ScomService.READ, ScomObjType.MULTI_INFO, ScomObjId.MULTI_INFO, ScomQspId.MULTI_INFO, 0x03, XcomParamException),
        ("request infos params aggr",  "data_infos_params_aggr", False, ScomAddress.SOURCE, 501, ScomService.READ, ScomObjType.MULTI_INFO, ScomObjId.MULTI_INFO, ScomQspId.MULTI_INFO, 0x03, XcomParamException),
    ]
)
async def test_requestInfos(name, values_fixture, run_client, exp_src_addr, exp_dst_addr, exp_svc_id, exp_obj_type, exp_obj_id, exp_prop_id, rsp_flags, exp_except, request):
    context = request.getfixturevalue("context")
    port    = request.getfixturevalue("unused_tcp_port")

    # The order of start is important, first server, then client.
    await context.start_server(port)
    await context.start_client(port)

    await context.server._waitConnected(5)
    assert context.server.connected == True
    assert context.client.connected == True

    req_data, exp_rsp_multi, _ = request.getfixturevalue(values_fixture)

    # Helper function for client to handle a request and submit a response
    async def clientHandler():

        # Receive the request from the server
        req: XcomPackage = await context.client.receivePackage()

        # Make a deep copy of the request and turn it into a response
        rsp = copy.deepcopy(req)
        rsp.frame_data.service_flags = rsp_flags

        if rsp_flags & 0x01:
            rsp.frame_data.service_data.property_data = XcomData.pack(ScomErrorCode.READ_PROPERTY_FAILED, XcomFormat.ERROR)
        else:
            rsp.frame_data.service_data.property_data = exp_rsp_multi.packResponse()

        rsp.header.data_length = len(rsp.frame_data)

        # Send the response back to the server
        await context.client.sendPackage(rsp)
        return req,rsp

    # Start 2 parallel tasks, for server and for client
    task_server = asyncio.create_task(context.server.requestInfos(req_data, retries=1, timeout=5))
    if run_client:
        task_client = asyncio.create_task(clientHandler())

    # Wait for client to finish and check the received request
    if run_client:
        req, rsp = await task_client

        assert req.header.src_addr == exp_src_addr
        assert req.header.dst_addr == exp_dst_addr
        assert req.frame_data.service_id == exp_svc_id
        assert req.frame_data.service_data.object_type == exp_obj_type
        assert req.frame_data.service_data.object_id == exp_obj_id
        assert req.frame_data.service_data.property_id == exp_prop_id

    # Wait for server to finish and check the handling of the received response
    if exp_except == None:
        rsp_data = await task_server

        assert rsp_data is not None
        assert len(rsp_data.items) == len(exp_rsp_multi.items)

        for item in rsp_data.items:
            exp_item = next((i for i in exp_rsp_multi.items if i.datapoint.nr==item.datapoint.nr and i.aggregation_type==item.aggregation_type), None)
            assert exp_item is not None
            assert exp_item.error is None

            match item.datapoint.format:
                case XcomFormat.FLOAT:
                    # carefull with comparing floats
                    assert item.value == pytest.approx(exp_item.value, abs=0.01)
                case _:
                    assert item.value == exp_item.value
    else:
        with pytest.raises(exp_except):
            await task_server


@pytest.mark.asyncio
@pytest.mark.usefixtures("context", "unused_tcp_port", "dataset", "data_infos_dev", "data_infos_aggr", "data_infos_params_dev", "data_infos_params_aggr")
@pytest.mark.parametrize(
    "name, values_fixture, run_client, loops_client, rsp_flags, exp_value, exp_error, exp_except",
    [
        ("request values infos ok",       "data_infos_dev",         True,  1, 0x02, True,  False, None),
        ("request values infos err",      "data_infos_dev",         True,  4, 0x03, False, True,  None),
        ("request values infos timeout",  "data_infos_dev",         False, 0, 0x02, False, True,  None),
        ("request values infos aggr",     "data_infos_aggr",        False, 0, 0x02, False, False, XcomParamException),
        ("request values params ok",      "data_infos_params_dev",  True,  2, 0x02, True,  False, None),
        ("request values params aggr",    "data_infos_params_aggr", False, 0, 0x02, False, False, XcomParamException),
    ]
)
async def test_requestValues(name, values_fixture, run_client, loops_client, rsp_flags, exp_value, exp_error, exp_except, request):
    context = request.getfixturevalue("context")
    port    = request.getfixturevalue("unused_tcp_port")

    # The order of start is important, first server, then client.
    await context.start_server(port)
    await context.start_client(port)

    await context.server._waitConnected(5)
    assert context.server.connected == True
    assert context.client.connected == True

    req_data, exp_rsp_multi, exp_rsp_single_val = request.getfixturevalue(values_fixture)

    # Helper function for client to handle a request and submit a response
    async def clientHandler():

        # Receive the request from the server
        req: XcomPackage = await context.client.receivePackage()

        # Make a deep copy of the request and turn it into a response
        rsp = copy.deepcopy(req)
        rsp.frame_data.service_flags = rsp_flags

        if rsp_flags & 0x01:
            rsp.frame_data.service_data.property_data = XcomData.pack(ScomErrorCode.READ_PROPERTY_FAILED, XcomFormat.ERROR)

        elif req.frame_data.service_data.object_type == ScomObjType.MULTI_INFO:
            rsp.frame_data.service_data.property_data = exp_rsp_multi.packResponse()

        else:
            rsp.frame_data.service_data.property_data = XcomData.pack(exp_rsp_single_val, XcomFormat.FLOAT)

        rsp.header.data_length = len(rsp.frame_data)

        # Send the response back to the server
        await context.client.sendPackage(rsp)
        return req,rsp

    # Start 2 parallel tasks, for server and for client
    task_server = asyncio.create_task(context.server.requestValues(req_data, retries=1, timeout=5))
    if run_client:
        for i in range(loops_client):
            task_client = asyncio.create_task(clientHandler())

            # Wait for client to finish and check the received request
            req, rsp = await task_client

    # Wait for server to finish and check the handling of the received response
    if exp_except == None:
        rsp_data = await task_server

        assert rsp_data is not None
        assert len(rsp_data.items) == len(req_data.items)

        for item in rsp_data.items:
            if exp_value:
                exp_item = next((i for i in exp_rsp_multi.items if i.datapoint.nr==item.datapoint.nr and i.aggregation_type==item.aggregation_type), None)
                if exp_item is not None:
                    exp_val = exp_item.value
                else:
                    exp_val = exp_rsp_single_val

                match item.datapoint.format:
                    case XcomFormat.FLOAT:
                        # carefull with comparing floats
                        assert item.value == pytest.approx(exp_val, abs=0.01)
                    case _:
                        assert item.value == exp_val
            else:
                assert item.value is None
    else:
        with pytest.raises(exp_except):
            await task_server


@pytest.mark.asyncio
@pytest.mark.usefixtures("context", "unused_tcp_port")
@pytest.mark.parametrize(
    "name, exp_dst_addr, exp_svc_id, exp_obj_type, exp_obj_id, exp_prop_id, rsp_flags, rsp_data, exp_value, exp_except",
    [
        ("request guid ok",      501, ScomService.READ, ScomObjType.GUID, ScomObjId.NONE, ScomQspId.NONE, 0x02, XcomData.pack("00112233-4455-6677-8899-aabbccddeeff", XcomFormat.GUID), "00112233-4455-6677-8899-aabbccddeeff",  None),
        ("request guid err",     501, ScomService.READ, ScomObjType.GUID, ScomObjId.NONE, ScomQspId.NONE, 0x03, XcomData.pack(ScomErrorCode.READ_PROPERTY_FAILED, XcomFormat.ERROR),            None, XcomApiResponseIsError),
        ("request guid timeout", 501, ScomService.READ, ScomObjType.GUID, ScomObjId.NONE, ScomQspId.NONE, 0x00, XcomData.pack("00112233-4455-6677-8899-aabbccddeeff", XcomFormat.GUID), None, XcomApiTimeoutException),
    ]
)
async def test_requestGuid(name, exp_dst_addr, exp_svc_id, exp_obj_type, exp_obj_id, exp_prop_id, rsp_flags, rsp_data, exp_value, exp_except, request):
    context = request.getfixturevalue("context")
    port    = request.getfixturevalue("unused_tcp_port")

    # The order of start is important, first server, then client.
    await context.start_server(port)
    await context.start_client(port)

    await context.server._waitConnected(5)
    assert context.server.connected == True
    assert context.client.connected == True

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
    task_server = asyncio.create_task(context.server.requestGuid(retries=1, timeout=5))
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


@pytest_asyncio.fixture
async def data_message():
    rsp_data = XcomDataMessageRsp(10, 1, 101, datetime.now().timestamp(), 1234)
    yield rsp_data


@pytest.mark.asyncio
@pytest.mark.usefixtures("context", "unused_tcp_port", "data_message")
@pytest.mark.parametrize(
    "name, test_nr, exp_svc_id, exp_obj_type, exp_obj_id, exp_prop_id, rsp_flags, rsp_data, exp_value, exp_except",
    [
        ("request msg ok",      1, ScomService.READ, ScomObjType.MESSAGE, 1, ScomQspId.NONE, 0x02, "data_message", None, None),
        ("request msg err",     1, ScomService.READ, ScomObjType.MESSAGE, 1, ScomQspId.NONE, 0x03, XcomData.pack(ScomErrorCode.READ_PROPERTY_FAILED, XcomFormat.ERROR), None, XcomApiResponseIsError),
        ("request msg timeout", 1, ScomService.READ, ScomObjType.MESSAGE, 1, ScomQspId.NONE, 0x00, "data_message", None, XcomApiTimeoutException),
    ]
)
async def test_requestMessage(name, test_nr, exp_svc_id, exp_obj_type, exp_obj_id, exp_prop_id, rsp_flags, rsp_data, exp_value, exp_except, request):
    context = request.getfixturevalue("context")
    port    = request.getfixturevalue("unused_tcp_port")

    if isinstance(rsp_data, str):
        rsp_data = request.getfixturevalue(rsp_data)
        rsp_data = rsp_data.pack()

    # The order of start is important, first server, then client.
    await context.start_server(port)
    await context.start_client(port)

    await context.server._waitConnected(5)
    assert context.server.connected == True
    assert context.client.connected == True

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
    task_server = asyncio.create_task(context.server.requestMessage(test_nr, retries=1, timeout=5))
    task_client = asyncio.create_task(clientHandler())

    # Wait for client to finish and check the received request
    req, rsp = await task_client

    assert req.header.dst_addr == ScomAddress.RCC
    assert req.frame_data.service_id == exp_svc_id
    assert req.frame_data.service_data.object_type == exp_obj_type
    assert req.frame_data.service_data.object_id == exp_obj_id
    assert req.frame_data.service_data.property_id == exp_prop_id

    # Wait for server to finish and check the handling of the received response
    if exp_except == None:
        msg = await task_server
        assert msg.message_total == 10
        assert msg.message_number == 1
        assert msg.source_address == 101
        assert msg.timestamp != 0
        assert msg.value == 1234
        assert msg.message_string is not None
    else:
        with pytest.raises(exp_except):
            await task_server


