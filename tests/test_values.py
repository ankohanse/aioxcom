import math
import pytest
import pytest_asyncio
from aioxcom import XcomValues, XcomValuesItem
from aioxcom import XcomFormat, XcomVoltage, XcomAggregationType
from aioxcom import XcomDataset, XcomDatapoint


@pytest_asyncio.fixture
async def dataset():
    dataset = await XcomDataset.create(XcomVoltage.AC240)
    yield dataset

@pytest_asyncio.fixture
async def values_req(dataset):
    info_3021 = dataset.getByNr(3021)
    info_3022 = dataset.getByNr(3022)
    info_3023 = dataset.getByNr(3023)
    info_3032 = dataset.getByNr(3032)

    yield XcomValues([
        XcomValuesItem(info_3021, code='XT1'),
        XcomValuesItem(info_3022, address=101),
        XcomValuesItem(info_3023, aggregation_type=XcomAggregationType.MASTER),
        XcomValuesItem(info_3032, aggregation_type=XcomAggregationType.DEVICE1),
    ])

@pytest_asyncio.fixture
async def values_rsp(dataset):
    info_3021 = dataset.getByNr(3021)
    info_3022 = dataset.getByNr(3022)
    info_3023 = dataset.getByNr(3023)
    info_3032 = dataset.getByNr(3032)

    yield XcomValues(
        flags = 123,
        datetime = 456,
        items = [
            XcomValuesItem(info_3021, code='XT1', value=1.0),   # Float
            XcomValuesItem(info_3022, address=101, value=2.0),     # Float
            XcomValuesItem(info_3023, aggregation_type=XcomAggregationType.MASTER, value=3.0),   # Float
            XcomValuesItem(info_3032, aggregation_type=XcomAggregationType.DEVICE1, value=7),    # Long Enum
        ]
    )

@pytest.mark.usefixtures("dataset", "values_req", "values_rsp")
@pytest.mark.parametrize(
    "name, values_fixture",
    [
        ("request", "values_req"),
        ("response", "values_rsp"),
    ]
)
async def test_pack_unpack(name, values_fixture, request):
    dataset: XcomDataset = request.getfixturevalue("dataset")
    values_req: XcomValues = request.getfixturevalue("values_req")
    values_def: XcomValues = request.getfixturevalue(values_fixture)

    # test pack
    if name=="request":
        buf = values_def.packRequest()
    else:
        buf = values_def.packResponse()

    assert buf is not None

    # test unpack
    if name=="request":
        clone = XcomValues.unpackRequest(buf, dataset=dataset)
    else:
        clone = XcomValues.unpackResponse(buf, values_req)

    assert clone is not None
    assert clone.flags == values_def.flags
    assert clone.datetime == values_def.datetime
    assert len(clone.items) == len(values_def.items)

    for clone_item in clone.items:
        assert clone_item.datapoint is not None
        org_item = next((item for item in values_def.items if item.datapoint.nr == clone_item.datapoint.nr and item.aggregation_type==clone_item.aggregation_type), None)    
        assert org_item is not None
        assert clone_item.aggregation_type is not None
        # clone_item.code could be None or not None
        # clone_item.address could be None or not None

        assert clone_item.code == org_item.code
        assert clone_item.address == org_item.address
        assert clone_item.aggregation_type == org_item.aggregation_type
        assert clone_item.value == org_item.value
