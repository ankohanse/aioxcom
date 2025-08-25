import math
import pytest
import pytest_asyncio
from aioxcom import XcomPackage, XcomDataset, XcomData, XcomDataMultiInfoReq, XcomDataMultiInfoReqItem, XcomDataMultiInfoRsp, XcomDataMultiInfoRspItem
from aioxcom import XcomFormat, XcomVoltage, XcomAggregationType, ScomService, ScomObjType, ScomQspId, ScomAddress


@pytest_asyncio.fixture
async def data_multi_info():
    yield XcomDataMultiInfoReq([
        XcomDataMultiInfoReqItem(3031, XcomAggregationType.MASTER),
        XcomDataMultiInfoReqItem(3032, XcomAggregationType.DEVICE1),
    ])

@pytest_asyncio.fixture
async def package_read_info():
    yield XcomPackage.genPackage(
        service_id = ScomService.READ,
        object_type = ScomObjType.INFO,
        object_id = 0x01020304,
        property_id = ScomQspId.VALUE,
        property_data = b'',
        src_addr = ScomAddress.SOURCE,
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
        src_addr = ScomAddress.SOURCE,
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
        src_addr = ScomAddress.SOURCE,
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
        src_addr = ScomAddress.SOURCE,
        dst_addr = 501,
    )



@pytest.mark.asyncio
@pytest.mark.usefixtures("package_read_info", "package_read_param", "package_write_param", "package_read_multiinfo", "data_multi_info")
@pytest.mark.parametrize(
    "fixture, exp_src_addr, exp_dst_addr, exp_svc_id, exp_svc_flags, exp_obj_type, exp_obj_id, exp_prop_id, exp_prop_data",
    [
        ("package_read_info",      ScomAddress.SOURCE, 101, ScomService.READ,  0x00, ScomObjType.INFO,       0x01020304, ScomQspId.VALUE,         b''),
        ("package_read_param",     ScomAddress.SOURCE, 101, ScomService.READ,  0x00, ScomObjType.PARAMETER,  0x01020304, ScomQspId.UNSAVED_VALUE, b''),
        ("package_write_param",    ScomAddress.SOURCE, 101, ScomService.WRITE, 0x00, ScomObjType.PARAMETER,  0x01020304, ScomQspId.UNSAVED_VALUE, b'0A0B0C0D'),
        ("package_read_multiinfo", ScomAddress.SOURCE, 501, ScomService.READ,  0x00, ScomObjType.MULTI_INFO, 0x01,       ScomQspId.NONE,          "data_multi_info.pack()")
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


