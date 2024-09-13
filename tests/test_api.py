import asyncio
import pytest
import pytest_asyncio
from aioxcom import XcomApiTcp, XcomDataset, XcomData
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


    async def run_request_response(self,
        port,
        test_nr,
        test_dest,
        test_value_update,
        expected_service_id,
        expected_object_type,
        expected_object_id,
        expected_property_id,
        response_flags,
        response_data,
        expected_value,
        expected_exception_type,
    ):
        # The order of start is important, first server, then client.
        await self.start_server(port)
        await self.start_client(port)

        await self.server._waitConnected(5)
        assert self.server.connected == True
        assert self.client.connected == True

        dataset = await XcomDataset.create(VOLTAGE.AC240)
        param = dataset.getByNr(test_nr)

        if test_value_update:
            task_server = asyncio.create_task(self.server.updateValue(param, test_value_update, test_dest, retries=1, timeout=5))
        else:
            task_server = asyncio.create_task(self.server.requestValue(param, test_dest, retries=1, timeout=5))

        task_client = asyncio.create_task(self.client.requestHandle(
            expected_dst_addr = test_dest,
            expected_service_id = expected_service_id,
            expected_object_type = expected_object_type,
            expected_object_id = expected_object_id,
            expected_property_id = expected_property_id,
            response_flags = response_flags,
            response_data = response_data,
        ))

        await task_client

        if expected_exception_type == None:
            value = await task_server
            assert value == expected_value
        else:
            with pytest.raises(expected_exception_type):
                await task_server


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
async def test_connect_timeout(context, unused_tcp_port):
    port = unused_tcp_port
    await context.start_server(port)
    assert context.server.connected == False

    await context.server._waitConnected(1)
    assert context.server.connected == False


@pytest.mark.asyncio()
async def test_connect_ok(context, unused_tcp_port):
    port = unused_tcp_port
    await context.start_server(port)
    await context.start_client(port)

    await context.server._waitConnected(5)
    assert context.server.connected == True
    assert context.client.connected == True


@pytest.mark.asyncio()
async def test_request_info_ok(context, unused_tcp_port):

    await context.run_request_response(
        port = unused_tcp_port,
        test_nr = 3000,
        test_dest = 100,
        test_value_update = None,
        expected_service_id = SCOM_SERVICE.READ,
        expected_object_type = SCOM_OBJ_TYPE.INFO,
        expected_object_id = 3000,
        expected_property_id = SCOM_QSP_ID.VALUE,
        response_flags = 0x02,   # value response
        response_data = XcomData.pack(1234.0, FORMAT.FLOAT),
        expected_value = 1234.0,
        expected_exception_type = None,
    )


@pytest.mark.asyncio()
async def test_request_info_err(context, unused_tcp_port):

    await context.run_request_response(
        port = unused_tcp_port,
        test_nr = 3000,
        test_dest = 100,
        test_value_update = None,
        expected_service_id = SCOM_SERVICE.READ,
        expected_object_type = SCOM_OBJ_TYPE.INFO,
        expected_object_id = 3000,
        expected_property_id = SCOM_QSP_ID.VALUE,
        response_flags = 0x03,   # error response
        response_data = SCOM_ERROR_CODES.READ_PROPERTY_FAILED,
        expected_value = None,
        expected_exception_type = XcomApiResponseIsError,
    )


@pytest.mark.asyncio()
async def test_request_info_timeout(context, unused_tcp_port):

    await context.run_request_response(
        port = unused_tcp_port,
        test_nr = 3000,
        test_dest = 100,
        test_value_update = None,
        expected_service_id = SCOM_SERVICE.READ,
        expected_object_type = SCOM_OBJ_TYPE.INFO,
        expected_object_id = 3000,
        expected_property_id = SCOM_QSP_ID.VALUE,
        response_flags = 0x00,   # not a response
        response_data = XcomData.pack(1234.0, FORMAT.FLOAT),
        expected_value = None,
        expected_exception_type = XcomApiTimeoutException,
    )


@pytest.mark.asyncio()
async def test_request_param_ok(context, unused_tcp_port):

    await context.run_request_response(
        port = unused_tcp_port,
        test_nr = 1107,
        test_dest = 100,
        test_value_update = None,
        expected_service_id = SCOM_SERVICE.READ,
        expected_object_type = SCOM_OBJ_TYPE.PARAMETER,
        expected_object_id = 1107,
        expected_property_id = SCOM_QSP_ID.UNSAVED_VALUE,
        response_flags = 0x02,   # value response
        response_data = XcomData.pack(1234.0, FORMAT.FLOAT),
        expected_value = 1234.0,
        expected_exception_type = None,
    )


@pytest.mark.asyncio()
async def test_update_param_ok(context, unused_tcp_port):

    await context.run_request_response(
        port = unused_tcp_port,
        test_nr = 1107,
        test_dest = 100,
        test_value_update = 4.0,
        expected_service_id = SCOM_SERVICE.WRITE,
        expected_object_type = SCOM_OBJ_TYPE.PARAMETER,
        expected_object_id = 1107,
        expected_property_id = SCOM_QSP_ID.UNSAVED_VALUE,
        response_flags = 0x02,   # response
        response_data = b'', # empty data means success
        expected_value = True,
        expected_exception_type = None,
    )


@pytest.mark.asyncio()
async def test_update_param_err(context, unused_tcp_port):

    await context.run_request_response(
        port = unused_tcp_port,
        test_nr = 1107,
        test_dest = 100,
        test_value_update = 4.0,
        expected_service_id = SCOM_SERVICE.WRITE,
        expected_object_type = SCOM_OBJ_TYPE.PARAMETER,
        expected_object_id = 1107,
        expected_property_id = SCOM_QSP_ID.UNSAVED_VALUE,
        response_flags = 0x03,   # error response
        response_data = SCOM_ERROR_CODES.WRITE_PROPERTY_FAILED,
        expected_value = None,
        expected_exception_type = XcomApiResponseIsError,
    )


@pytest.mark.asyncio()
async def test_update_param_timeout(context, unused_tcp_port):

    await context.run_request_response(
        port = unused_tcp_port,
        test_nr = 1107,
        test_dest = 100,
        test_value_update = 4.0,
        expected_service_id = SCOM_SERVICE.WRITE,
        expected_object_type = SCOM_OBJ_TYPE.PARAMETER,
        expected_object_id = 1107,
        expected_property_id = SCOM_QSP_ID.UNSAVED_VALUE,
        response_flags = 0x00,   # no response
        response_data = b'', # empty data means success
        expected_value = None,
        expected_exception_type = XcomApiTimeoutException,
    )

