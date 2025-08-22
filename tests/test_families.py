
import pytest
from aioxcom import XcomDeviceFamilies
from aioxcom import XcomDeviceFamilyUnknownException, XcomDeviceCodeUnknownException, XcomDeviceAddrUnknownException, XcomParamException
from aioxcom import SCOM_AGGREGATION_TYPE


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
        (SCOM_AGGREGATION_TYPE.MASTER,   SCOM_AGGREGATION_TYPE.MASTER,   None),
        (SCOM_AGGREGATION_TYPE.DEVICE1,  SCOM_AGGREGATION_TYPE.DEVICE1,  None),
        (SCOM_AGGREGATION_TYPE.AVERAGE,  SCOM_AGGREGATION_TYPE.AVERAGE,  None),
        (SCOM_AGGREGATION_TYPE.SUM,      SCOM_AGGREGATION_TYPE.SUM,      None),
        (0,      SCOM_AGGREGATION_TYPE.MASTER,   None),
        (1,      SCOM_AGGREGATION_TYPE.DEVICE1,  None),
        (15,     SCOM_AGGREGATION_TYPE.DEVICE15, None),
        (0xfd,   SCOM_AGGREGATION_TYPE.AVERAGE,  None),
        (0xfe,   SCOM_AGGREGATION_TYPE.SUM,      None),
        (16,     None,                           XcomDeviceAddrUnknownException),
        (0xfc,   None,                           XcomDeviceAddrUnknownException),
        (0xff,   None,                           XcomDeviceAddrUnknownException),
        ("XT",   SCOM_AGGREGATION_TYPE.MASTER,   None),
        ("XT1",  SCOM_AGGREGATION_TYPE.DEVICE1,  None),
        ("XT9",  SCOM_AGGREGATION_TYPE.DEVICE9,  None),
        ("L3",   SCOM_AGGREGATION_TYPE.DEVICE1,  None),
        ("RCC",  SCOM_AGGREGATION_TYPE.DEVICE1,  None),
        ("BSP",  SCOM_AGGREGATION_TYPE.DEVICE1,  None),
        ("BMS",  SCOM_AGGREGATION_TYPE.DEVICE1,  None),
        ("VT",   SCOM_AGGREGATION_TYPE.MASTER,   None),
        ("VT1",  SCOM_AGGREGATION_TYPE.DEVICE1,  None),
        ("VT15", SCOM_AGGREGATION_TYPE.DEVICE15, None),
        ("VS",   SCOM_AGGREGATION_TYPE.MASTER,   None),
        ("VS1",  SCOM_AGGREGATION_TYPE.DEVICE1,  None),
        ("VS15", SCOM_AGGREGATION_TYPE.DEVICE15, None),
        ("ABC",  None,                           XcomDeviceCodeUnknownException),
        ("abc",  None,                           XcomDeviceCodeUnknownException),
        ("xt",   None,                           XcomDeviceCodeUnknownException),
        (101,    SCOM_AGGREGATION_TYPE.DEVICE1,  None), # XT1
        (109,    SCOM_AGGREGATION_TYPE.DEVICE9,  None), # XT9
        (193,    SCOM_AGGREGATION_TYPE.DEVICE1,  None), # L3
        (501,    SCOM_AGGREGATION_TYPE.DEVICE1,  None), # RCC
        (601,    SCOM_AGGREGATION_TYPE.DEVICE1,  None), # either BSP or BMS
        (301,    SCOM_AGGREGATION_TYPE.DEVICE1,  None), # VS1
        (315,    SCOM_AGGREGATION_TYPE.DEVICE15, None), # VS15
        (701,    SCOM_AGGREGATION_TYPE.DEVICE1,  None), # VT1
        (715,    SCOM_AGGREGATION_TYPE.DEVICE15, None), # VT15
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


