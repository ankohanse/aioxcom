import math
import pytest
import pytest_asyncio
from aioxcom import XcomMultiInfoReq, XcomMultiInfoReqItem, XcomMultiInfoRsp, XcomMultiInfoRspItem
from aioxcom import XcomFormat, XcomVoltage, XcomAggregationType
from aioxcom import XcomDataset, XcomDatapoint


@pytest_asyncio.fixture
async def multi_info_req():
    dataset = await XcomDataset.create(XcomVoltage.AC240)
    info_3031 = dataset.getByNr(3031)
    info_3032 = dataset.getByNr(3032)

    yield XcomMultiInfoReq([
        XcomMultiInfoReqItem(info_3031, XcomAggregationType.MASTER),
        XcomMultiInfoReqItem(info_3032, XcomAggregationType.DEVICE1),
    ])


@pytest.mark.usefixtures("multi_info_req")
def test_multi_info(request):
    multi_info_req: XcomMultiInfoReq = request.getfixturevalue("multi_info_req")

    # test pack request
    buf = multi_info_req.pack()

    assert buf is not None
    assert len(buf) == len(multi_info_req.items) * 3

    # test pack response
    rsp = XcomMultiInfoRsp(
        flags = 123,
        datetime = 456,
        items = [ XcomMultiInfoRspItem(req.datapoint, req.aggregation_type, 7) for req in multi_info_req.items ],
    )
    buf = rsp.pack()

    assert buf is not None
    assert len(buf) == len(multi_info_req.items) * 7 + 8

    # test unpack response
    clone = XcomMultiInfoRsp.unpack(buf, req_data=multi_info_req)

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
