import math
import pytest
import pytest_asyncio
from aioxcom import XcomData, XcomDataMultiInfoReq, XcomDataMultiInfoReqItem, XcomDataMultiInfoRsp, XcomDataMultiInfoRspItem
from aioxcom import XcomFormat, XcomVoltage, XcomAggregationType
from aioxcom import XcomDataset, XcomDatapoint


@pytest_asyncio.fixture
async def data_multi_info():
    yield XcomDataMultiInfoReq([
        XcomDataMultiInfoReqItem(3031, XcomAggregationType.MASTER),
        XcomDataMultiInfoReqItem(3032, XcomAggregationType.DEVICE1),
    ])


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
    data_multi_info: XcomDataMultiInfoReq = request.getfixturevalue("data_multi_info")

    # test pack request
    buf = data_multi_info.pack()

    assert buf is not None
    assert len(buf) == len(data_multi_info.items) * 3

    # test pack response
    rsp = XcomDataMultiInfoRsp(
        flags = 123,
        datetime = 456,
        items = [ XcomDataMultiInfoRspItem(req.user_info_ref, req.aggregation_type, 7.8) for req in data_multi_info.items ],
    )
    buf = rsp.pack()

    assert buf is not None
    assert len(buf) == len(data_multi_info.items) * 7 + 8

    # test unpack response
    clone = XcomDataMultiInfoRsp.unpack(buf)

    assert clone is not None
    assert type(clone) == type(rsp)
    assert clone.flags == rsp.flags
    assert clone.datetime == rsp.datetime
    assert len(clone.items) == len(rsp.items)

    for clone_item in clone.items:
        assert clone_item.user_info_ref is not None
        rsp_item = next((item for item in rsp.items if item.user_info_ref == clone_item.user_info_ref), None)    
        assert rsp_item is not None

        assert clone_item.aggregation_type == rsp_item.aggregation_type
        assert clone_item.data == pytest.approx(rsp_item.data, abs=0.01) # carefull with comparing floats
