import pytest
from aioxcom import XcomDataset, VOLTAGE, FORMAT, OBJ_TYPE, XcomDatapointUnknownException

def test_create():
    dataset120 = XcomDataset.create(VOLTAGE.AC120)    
    dataset240 = XcomDataset.create(VOLTAGE.AC240)

    assert len(dataset120._datapoints) == 1435
    assert len(dataset240._datapoints) == 1435


def test_nr():
    dataset = XcomDataset.create(VOLTAGE.AC240)

    param = dataset.getByNr(1107)
    assert param.family_id == "xt"
    assert param.nr == 1107
    assert param.format == FORMAT.FLOAT
    assert param.obj_type == OBJ_TYPE.PARAMETER

    param = dataset.getByNr(3000)
    assert param.family_id == "xt"
    assert param.nr == 3000
    assert param.format == FORMAT.FLOAT
    assert param.obj_type == OBJ_TYPE.INFO

    param = dataset.getByNr(3000, "xt")
    assert param.family_id == "xt"
    assert param.nr == 3000
    assert param.format == FORMAT.FLOAT
    assert param.obj_type == OBJ_TYPE.INFO

    with pytest.raises(XcomDatapointUnknownException):
        param = dataset.getByNr(9999)

    with pytest.raises(XcomDatapointUnknownException):
        param = dataset.getByNr(3000, "bsp")


def test_menu():
    dataset = XcomDataset.create(VOLTAGE.AC240)
    
    root_items = dataset.getMenuItems(0)
    assert len(root_items) == 11

    for item in root_items:
        sub_items = dataset.getMenuItems(item.nr)
        assert len(sub_items) > 0

