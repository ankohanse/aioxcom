
import pytest
from aioxcom import XcomDeviceFamilies
from aioxcom import XcomDeviceFamilyUnknownException, XcomDeviceCodeUnknownException, XcomDeviceAddrUnknownException, XcomParamException
from aioxcom import XcomAggregationType


def test_list():
    families = XcomDeviceFamilies.getList()
    assert len(families) == 9


def test_id():
    families = XcomDeviceFamilies.getList()
    for family in families:
        assert family == XcomDeviceFamilies.getById(family.id)

    with pytest.raises(XcomDeviceFamilyUnknownException):
        family = XcomDeviceFamilies.getById("XXX")


@pytest.mark.parametrize(
    "family_id, code, addr, aggr",
    [
        ("xt",  "XT1", 101, 1),
        ("xt",  "XT9", 109, 9),
        ("l1",  "L1",  191, 1),
        ("l2",  "L2",  192, 1),
        ("l3",  "L3",  193, 1),
        ("rcc", "RCC", 501, 1),
        ("bsp", "BSP", 601, 1),
        ("bms", "BMS", 601, 1),
        ("vt",  "VT1", 301, 1),
        ("vt",  "VT15",315, 15),
        ("vs",  "VS1", 701, 1),
        ("vs",  "VS15",715, 15),
    ]
)
def test_addr(family_id, code, addr, aggr):

    family = XcomDeviceFamilies.getById(family_id)

    assert family.getCode(addr) == code
    assert XcomDeviceFamilies.getByCode(code) == family
    assert XcomDeviceFamilies.getAddrByCode(code) == addr
    assert XcomDeviceFamilies.getAggregationTypeByCode(code) == aggr
    assert XcomDeviceFamilies.getAggregationTypeByAddr(addr) == aggr


def test_addr_fail():
    with pytest.raises(XcomDeviceAddrUnknownException):
        family = XcomDeviceFamilies.getById("xt")
        code = family.getCode(999)

    with pytest.raises(XcomDeviceCodeUnknownException):
        addr = XcomDeviceFamilies.getAddrByCode("ABC")

    with pytest.raises(XcomDeviceCodeUnknownException):
        addr = XcomDeviceFamilies.getAggregationTypeByCode("ABC")

    with pytest.raises(XcomDeviceAddrUnknownException):
        addr = XcomDeviceFamilies.getAggregationTypeByAddr(999)


@pytest.mark.parametrize(
    "val, exp_aggr, exp_except",
    [
        (XcomAggregationType.MASTER,   XcomAggregationType.MASTER,   None),
        (XcomAggregationType.DEVICE1,  XcomAggregationType.DEVICE1,  None),
        (XcomAggregationType.AVERAGE,  XcomAggregationType.AVERAGE,  None),
        (XcomAggregationType.SUM,      XcomAggregationType.SUM,      None),
        (0,      XcomAggregationType.MASTER,   None),
        (1,      XcomAggregationType.DEVICE1,  None),
        (15,     XcomAggregationType.DEVICE15, None),
        (0xfd,   XcomAggregationType.AVERAGE,  None),
        (0xfe,   XcomAggregationType.SUM,      None),
        (16,     None,                           XcomDeviceAddrUnknownException),
        (0xfc,   None,                           XcomDeviceAddrUnknownException),
        (0xff,   None,                           XcomDeviceAddrUnknownException),
        ("XT",   XcomAggregationType.MASTER,   None),
        ("XT1",  XcomAggregationType.DEVICE1,  None),
        ("XT9",  XcomAggregationType.DEVICE9,  None),
        ("L3",   XcomAggregationType.DEVICE1,  None),
        ("RCC",  XcomAggregationType.DEVICE1,  None),
        ("BSP",  XcomAggregationType.DEVICE1,  None),
        ("BMS",  XcomAggregationType.DEVICE1,  None),
        ("VT",   XcomAggregationType.MASTER,   None),
        ("VT1",  XcomAggregationType.DEVICE1,  None),
        ("VT15", XcomAggregationType.DEVICE15, None),
        ("VS",   XcomAggregationType.MASTER,   None),
        ("VS1",  XcomAggregationType.DEVICE1,  None),
        ("VS15", XcomAggregationType.DEVICE15, None),
        ("ABC",  None,                           XcomDeviceCodeUnknownException),
        ("abc",  None,                           XcomDeviceCodeUnknownException),
        ("xt",   None,                           XcomDeviceCodeUnknownException),
        (101,    XcomAggregationType.DEVICE1,  None), # XT1
        (109,    XcomAggregationType.DEVICE9,  None), # XT9
        (193,    XcomAggregationType.DEVICE1,  None), # L3
        (501,    XcomAggregationType.DEVICE1,  None), # RCC
        (601,    XcomAggregationType.DEVICE1,  None), # either BSP or BMS
        (301,    XcomAggregationType.DEVICE1,  None), # VS1
        (315,    XcomAggregationType.DEVICE15, None), # VS15
        (701,    XcomAggregationType.DEVICE1,  None), # VT1
        (715,    XcomAggregationType.DEVICE15, None), # VT15
        (110,    None,                           XcomDeviceAddrUnknownException),
        (190,    None,                           XcomDeviceAddrUnknownException),
        (300,    None,                           XcomDeviceAddrUnknownException),
        (316,    None,                           XcomDeviceAddrUnknownException),
        (700,    None,                           XcomDeviceAddrUnknownException),
        (716,    None,                           XcomDeviceAddrUnknownException),
        (12.3,   None,                           XcomParamException),
    ]
)
def test_aggregration_type(val, exp_aggr, exp_except):

    if exp_except is None:
        aggr = XcomDeviceFamilies.getAggregationTypeByAny(val)
        assert aggr == exp_aggr

    else:
        with pytest.raises(exp_except):
            aggr = XcomDeviceFamilies.getAggregationTypeByAny(val)


