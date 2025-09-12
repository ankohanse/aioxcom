import pytest
import pytest_asyncio
from aioxcom import XcomDataset, XcomVoltage, XcomFormat, XcomCategory, XcomDatapointUnknownException


@pytest.mark.asyncio
async def test_create():
    dataset120 = await XcomDataset.create(XcomVoltage.AC120)    
    dataset240 = await XcomDataset.create(XcomVoltage.AC240)

    assert len(dataset120._datapoints) == 1436
    assert len(dataset240._datapoints) == 1436


@pytest.mark.asyncio
async def test_nr():
    dataset = await XcomDataset.create(XcomVoltage.AC240)

    param = dataset.getByNr(1107)
    assert param.family_id == "xt"
    assert param.nr == 1107
    assert param.format == XcomFormat.FLOAT
    assert param.category == XcomCategory.PARAMETER

    param = dataset.getByNr(1552)
    assert param.family_id == "xt"
    assert param.nr == 1552
    assert param.format == XcomFormat.LONG_ENUM
    assert param.category == XcomCategory.PARAMETER
    assert param.options != None
    assert type(param.options) is dict
    assert len(param.options) == 3

    param = dataset.getByNr(3000)
    assert param.family_id == "xt"
    assert param.nr == 3000
    assert param.format == XcomFormat.FLOAT
    assert param.category == XcomCategory.INFO

    param = dataset.getByNr(3000, "xt")
    assert param.family_id == "xt"
    assert param.nr == 3000
    assert param.format == XcomFormat.FLOAT
    assert param.category == XcomCategory.INFO

    param = dataset.getByNr(5012, "rcc")
    assert param.family_id == "rcc"
    assert param.nr == 5012
    assert param.format == XcomFormat.LONG_ENUM
    assert param.category == XcomCategory.PARAMETER
    assert param.options != None
    assert type(param.options) is dict

    with pytest.raises(XcomDatapointUnknownException):
        param = dataset.getByNr(9999)

    with pytest.raises(XcomDatapointUnknownException):
        param = dataset.getByNr(3000, "bsp")


@pytest.mark.asyncio
async def test_enum():
    dataset = await XcomDataset.create(XcomVoltage.AC240)

    param = dataset.getByNr(1552)
    assert param.options != None
    assert type(param.options) is dict
    assert len(param.options) == 3

    assert param.enum_value(1) == "Slow"
    assert param.enum_value("1") == "Slow"
    assert param.enum_value(0) == "0"
    assert param.enum_value("0") == "0"

    assert param.enum_key("Slow") == 1
    assert param.enum_key("Unknown") == None
    assert param.enum_key(1) == None
    assert param.enum_key("1") == None


@pytest.mark.asyncio
async def test_menu():
    dataset = await XcomDataset.create(XcomVoltage.AC240)
    
    root_items = dataset.getMenuItems(0)
    assert len(root_items) == 11

    for item in root_items:
        sub_items = dataset.getMenuItems(item.nr)
        assert len(sub_items) > 0

