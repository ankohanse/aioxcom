import math
import pytest
import pytest_asyncio
from aioxcom import XcomPackage, XcomDataset, XcomData, XcomDataMultiInfoReq, XcomDataMultiInfoReqItem, XcomDataMultiInfoRsp, XcomDataMultiInfoRspItem
from aioxcom import XcomFormat, XcomVoltage, ScomService, ScomObjType, ScomQspId, XcomAggregationType


@pytest_asyncio.fixture
async def data_multi_info():
    dataset = await XcomDataset.create(XcomVoltage.AC240)
    info_3031 = dataset.getByNr(3031)
    info_3032 = dataset.getByNr(3032)

    yield XcomDataMultiInfoReq([
        XcomDataMultiInfoReqItem(info_3031, XcomAggregationType.MASTER),
        XcomDataMultiInfoReqItem(info_3032, XcomAggregationType.DEVICE1),
    ])

@pytest_asyncio.fixture
async def package_read_info():
    yield XcomPackage.genPackage(
        service_id = ScomService.READ,
        object_type = ScomObjType.INFO,
        object_id = 0x01020304,
        property_id = ScomQspId.VALUE,
        property_data = b'',
        src_addr = 1,
        dst_addr = 101,
    )

@pytest_asyncio.fixture
async def package_read_param():
    yield XcomPackage.genPackage(
        service_id = ScomService.READ,
        object_type = ScomObjType.PARAMETER,
        object_id = 0x01020304,
        property_id = ScomQspId.UNSAVED_VALUE,
        property_data = b'',
        src_addr = 1,
        dst_addr = 101,
    )

@pytest_asyncio.fixture
async def package_write_param():
    yield XcomPackage.genPackage(
        service_id = ScomService.WRITE,
        object_type = ScomObjType.PARAMETER,
        object_id = 0x01020304,
        property_id = ScomQspId.UNSAVED_VALUE,
        property_data = b'0A0B0C0D',
        src_addr = 1,
        dst_addr = 101,
    )

@pytest_asyncio.fixture
async def package_read_multiinfo(data_multi_info):
    yield XcomPackage.genPackage(
        service_id = ScomService.READ,
        object_type = ScomObjType.MULTI_INFO,
        object_id = 0x01,
        property_id = ScomQspId.NONE,
        property_data = data_multi_info.pack(),
        src_addr = 1,
        dst_addr = 501,
    )



@pytest.mark.asyncio
@pytest.mark.usefixtures("package_read_info", "package_read_param", "package_write_param", "package_read_multiinfo", "data_multi_info")
@pytest.mark.parametrize(
    "fixture, exp_src_addr, exp_dst_addr, exp_svc_id, exp_svc_flags, exp_obj_type, exp_obj_id, exp_prop_id, exp_prop_data",
    [
        ("package_read_info",      1, 101, ScomService.READ,  0x00, ScomObjType.INFO,       0x01020304, ScomQspId.VALUE,         b''),
        ("package_read_param",     1, 101, ScomService.READ,  0x00, ScomObjType.PARAMETER,  0x01020304, ScomQspId.UNSAVED_VALUE, b''),
        ("package_write_param",    1, 101, ScomService.WRITE, 0x00, ScomObjType.PARAMETER,  0x01020304, ScomQspId.UNSAVED_VALUE, b'0A0B0C0D'),
        ("package_read_multiinfo", 1, 501, ScomService.READ,  0x00, ScomObjType.MULTI_INFO, 0x01,       ScomQspId.NONE,          "data_multi_info.pack()")
    ]
)
async def test_package_props(fixture, exp_src_addr, exp_dst_addr, exp_svc_id, exp_svc_flags, exp_obj_type, exp_obj_id, exp_prop_id, exp_prop_data, request):
    package: XcomPackage = request.getfixturevalue(fixture)
    data_multi_info = request.getfixturevalue("data_multi_info")

    if exp_prop_data == "data_multi_info.pack()":
        exp_prop_data = data_multi_info.pack()

    assert package.header.src_addr == exp_src_addr
    assert package.header.dst_addr == exp_dst_addr
    assert package.frame_data.service_id == exp_svc_id
    assert package.frame_data.service_flags == exp_svc_flags
    assert package.frame_data.service_data.object_type == exp_obj_type
    assert package.frame_data.service_data.object_id == exp_obj_id
    assert package.frame_data.service_data.property_id == exp_prop_id
    assert package.frame_data.service_data.property_data == exp_prop_data or exp_prop_data is None

    # Test getBytes (calls compose)
    buf = package.getBytes()

    assert buf is not None
    assert len(buf) > 0

    # Test parseBytes (calls parse)
    clone = await XcomPackage.parseBytes(buf)

    assert clone.header.src_addr == exp_src_addr
    assert clone.header.dst_addr == exp_dst_addr
    assert clone.frame_data.service_id == exp_svc_id
    assert clone.frame_data.service_flags == exp_svc_flags
    assert clone.frame_data.service_data.object_type == exp_obj_type
    assert clone.frame_data.service_data.object_id == exp_obj_id
    assert clone.frame_data.service_data.property_id == exp_prop_id
    assert package.frame_data.service_data.property_data == exp_prop_data or exp_prop_data is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("package_read_info", "package_read_param", "package_write_param", "package_read_multiinfo")
@pytest.mark.parametrize(
    "name, fixture, modify_flags, modify_data, expected_isResponse, expected_isError, expected_getError",
    [
        ("read info req",           "package_read_info",      0x00, b'',         False, False, None),
        ("read info rsp_ok",        "package_read_info",      0x02, b'',         True,  False, None),
        ("read info rsp_err",       "package_read_info",      0x03, b'\x2A\x00', True,  True,  "READ_PROPERTY_FAILED"),
        ("read info rsp_unk",       "package_read_info",      0x03, b'\xDC\xFE', True,  True,  "unknown error 'fedc'"),
        ("read param req",          "package_read_param",     0x00, b'',         False, False, None),
        ("read param rsp_ok",       "package_read_param",     0x02, b'',         True,  False, None),
        ("read param rsp_err",      "package_read_param",     0x03, b'\x2A\x00', True,  True,  "READ_PROPERTY_FAILED"),
        ("read param rsp_unk",      "package_read_param",     0x03, b'\xDC\xFE', True,  True,  "unknown error 'fedc'"),
        ("write param req",         "package_write_param",    0x00, b'',         False, False, None),
        ("write param rsp_ok",      "package_write_param",    0x02, b'',         True,  False, None),
        ("write param rsp_err",     "package_write_param",    0x03, b'\x29\x00', True,  True,  "WRITE_PROPERTY_FAILED"),
        ("write param rsp_unk",     "package_write_param",    0x03, b'\xDC\xFE', True,  True,  "unknown error 'fedc'"),
        ("read multi-info req",     "package_read_multiinfo", 0x00, b'',         False, False, None),
        ("read multi-info rsp_ok",  "package_read_multiinfo", 0x02, b'',         True,  False, None),
        ("read multi-info rsp_err", "package_read_multiinfo", 0x03, b'\x2A\x00', True,  True,  "READ_PROPERTY_FAILED"),
        ("read multi-info rsp_unk", "package_read_multiinfo", 0x03, b'\xDC\xFE', True,  True,  "unknown error 'fedc'"),
    ]
)
async def test_package_flags(name, fixture, modify_flags, modify_data, expected_isResponse, expected_isError, expected_getError, request):
    # Modify the package
    package: XcomPackage = request.getfixturevalue(fixture)
    package.frame_data.service_flags = modify_flags
    package.frame_data.service_data.property_data = modify_data
    package.header.data_length = len(package.frame_data)

    # Test information functions
    assert package.isResponse() == expected_isResponse
    assert package.isError() == expected_isError
    assert package.getError() == expected_getError

    # Test getBytes and parseBytes
    buf = package.getBytes()
    clone = await XcomPackage.parseBytes(buf)

    assert clone.isResponse() == expected_isResponse
    assert clone.isError() == expected_isError
    assert clone.getError() == expected_getError


@pytest.mark.parametrize(
    "name, value, format, expected_length",
    [
        ("bool",       True, XcomFormat.BOOL, 1),
        ("short enum", 1234, XcomFormat.SHORT_ENUM, 2),
        ("int32",      1234, XcomFormat.INT32, 4),
        ("long enum",  1234, XcomFormat.LONG_ENUM, 4),
        ("float",      123.4, XcomFormat.FLOAT, 4),
        ("guid",       "00:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee:ff", XcomFormat.GUID, 16),
        ("string",     "abcde", XcomFormat.STRING, 5),
    ]
)
def test_data(name, value, format, expected_length):
    # test pack
    buf = XcomData.pack(value, format)

    assert buf is not None
    assert len(buf) == expected_length

    # test unpack
    clone = XcomData.unpack(buf, format)

    assert type(clone) == type(value)
    match format:
        case XcomFormat.FLOAT:
            # carefull with comparing floats
            assert clone == pytest.approx(value, abs=0.01)
        case _:
            assert clone == value


@pytest.mark.usefixtures("data_multi_info")
def test_data_multiinfo(request):
    data_multi_info: XcomPackage = request.getfixturevalue("data_multi_info")

    # test pack request
    buf = data_multi_info.pack()

    assert buf is not None
    assert len(buf) == len(data_multi_info.items) * 3

    # test pack response
    rsp = XcomDataMultiInfoRsp(
        flags = 123,
        datetime = 456,
        items = [ XcomDataMultiInfoRspItem(req.datapoint, req.aggregation_type, 7) for req in data_multi_info.items ],
    )
    buf = rsp.pack()

    assert buf is not None
    assert len(buf) == len(data_multi_info.items) * 7 + 8

    # test unpack response
    clone = XcomDataMultiInfoRsp.unpack(buf, req_data=data_multi_info)

    assert clone is not None
    assert type(clone) == type(rsp)
    assert clone.flags == rsp.flags
    assert clone.datetime == rsp.datetime
    assert len(clone.items) == len(rsp.items)

    for clone_item in clone.items:
        assert clone_item.datapoint is not None
        rsp_item = next((item for item in rsp.items if item.datapoint.nr == clone_item.datapoint.nr), None)    
        assert rsp_item is not None

        assert clone_item.aggregation_type == rsp_item.aggregation_type
        assert clone_item.value == rsp_item.value
        assert clone_item.code is not None
