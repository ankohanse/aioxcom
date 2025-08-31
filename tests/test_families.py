
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
        ("xt",  "XT1", 101, XcomAggregationType.DEVICE1),
        ("xt",  "XT9", 109, XcomAggregationType.DEVICE9),
        ("xt",  "ABC", None, None),
        ("l1",  "L1",  191, None),
        ("l2",  "L2",  192, None),
        ("l3",  "L3",  193, None),
        ("rcc", "RCC", 501, XcomAggregationType.DEVICE1),
        ("bsp", "BSP", 601, XcomAggregationType.DEVICE1),
        ("bms", "BMS", 601, XcomAggregationType.DEVICE1),
        ("vt",  "VT1", 301, XcomAggregationType.DEVICE1),
        ("vt",  "VT15",315, XcomAggregationType.DEVICE15),
        ("vs",  "VS1", 701, XcomAggregationType.DEVICE1),
        ("vs",  "VS15",715, XcomAggregationType.DEVICE15),
    ]
)
def test_code(family_id, code, addr, aggr):

    family = XcomDeviceFamilies.getById(family_id)

    if addr is not None:
        assert XcomDeviceFamilies.getByCode(code) == family
    else:
        assert XcomDeviceFamilies.getByCode(code) is None

    assert XcomDeviceFamilies.getAddrByCode(code) == addr
    assert XcomDeviceFamilies.getAggregationTypeByCode(code) == aggr


@pytest.mark.parametrize(
    "family_id, addr, fam_code, code, aggr",
    [
        ("xt",  101, "XT1", "XT1", XcomAggregationType.DEVICE1),
        ("xt",  109, "XT9", "XT9", XcomAggregationType.DEVICE9),
        ("xt",  110, None,  None,  None),
        ("xt",  191, None,  "L1",  None),  # because "xt" datapoints are shared with L1, L2 and L3
        ("xt",  192, None,  "L2",  None),
        ("xt",  193, None,  "L3",  None),
        ("l1",  191, "L1",  "L1",  None),
        ("l2",  192, "L2",  "L2",  None),
        ("l3",  193, "L3",  "L3",  None),
        ("rcc", 501, "RCC", "RCC", XcomAggregationType.DEVICE1),
        ("bsp", 601, "BSP", "BSP", XcomAggregationType.DEVICE1),
        ("bms", 601, "BMS", "BMS", XcomAggregationType.DEVICE1),
        ("vt",  301, "VT1", "VT1", XcomAggregationType.DEVICE1),
        ("vt",  315, "VT15","VT15",XcomAggregationType.DEVICE15),
        ("vs",  701, "VS1", "VS1", XcomAggregationType.DEVICE1),
        ("vs",  715, "VS15","VS15",XcomAggregationType.DEVICE15),
    ]
)
def test_addr(family_id, addr, fam_code, code, aggr):

    family = XcomDeviceFamilies.getById(family_id)

    if fam_code is not None:
        assert family.getCode(addr) == fam_code
    else:
        with pytest.raises(XcomDeviceAddrUnknownException):
            family.getCode(addr)

    assert XcomDeviceFamilies.getCodeByAddr(addr, family.id) == code
    assert XcomDeviceFamilies.getAggregationTypeByAddr(addr) == aggr


@pytest.mark.parametrize(
    "family_id, aggr, code, addr",
    [
        ("xt",  XcomAggregationType.DEVICE1,  "XT1", 101),
        ("xt",  XcomAggregationType.DEVICE9,  "XT9", 109),
        ("xt",  XcomAggregationType.DEVICE10, None,  None),
        ("xt",  XcomAggregationType.MASTER,   None,  None),
        ("xt",  XcomAggregationType.AVERAGE,  None,  None),
        ("xt",  XcomAggregationType.SUM,      None,  None),
        ("l1",  XcomAggregationType.DEVICE1,  None,  None),
        ("l1",  XcomAggregationType.MASTER,   None,  None),
        ("l1",  XcomAggregationType.AVERAGE,  None,  None),
        ("l1",  XcomAggregationType.SUM,      None,  None),
        ("l2",  XcomAggregationType.DEVICE1,  None,  None),
        ("l2",  XcomAggregationType.MASTER,   None,  None),
        ("l2",  XcomAggregationType.AVERAGE,  None,  None),
        ("l2",  XcomAggregationType.SUM,      None,  None),
        ("l3",  XcomAggregationType.DEVICE1,  None,  None),
        ("l3",  XcomAggregationType.MASTER,   None,  None),
        ("l3",  XcomAggregationType.AVERAGE,  None,  None),
        ("l3",  XcomAggregationType.SUM,      None,  None),
        ("rcc", XcomAggregationType.DEVICE1,  "RCC", 501),
        ("rcc", XcomAggregationType.MASTER,   None,  None),
        ("rcc", XcomAggregationType.AVERAGE,  None,  None),
        ("rcc", XcomAggregationType.SUM,      None,  None),
        ("bsp", XcomAggregationType.DEVICE1,  "BSP", 601),
        ("bsp", XcomAggregationType.MASTER,   None,  None),
        ("bsp", XcomAggregationType.AVERAGE,  None,  None),
        ("bsp", XcomAggregationType.SUM,      None,  None),
        ("bms", XcomAggregationType.DEVICE1,  "BMS", 601),
        ("bms", XcomAggregationType.MASTER,   None,  None),
        ("bms", XcomAggregationType.AVERAGE,  None,  None),
        ("bms", XcomAggregationType.SUM,      None,  None),
        ("vt",  XcomAggregationType.DEVICE1,  "VT1", 301),
        ("vt",  XcomAggregationType.DEVICE15, "VT15",315),
        ("vt",  XcomAggregationType.MASTER,   None,  None),
        ("vt",  XcomAggregationType.AVERAGE,  None,  None),
        ("vt",  XcomAggregationType.SUM,      None,  None),
        ("vs",  XcomAggregationType.DEVICE1,  "VS1", 701),
        ("vs",  XcomAggregationType.DEVICE15, "VS15",715),
        ("vs",  XcomAggregationType.MASTER,   None,  None),
        ("vs",  XcomAggregationType.AVERAGE,  None,  None),
        ("vs",  XcomAggregationType.SUM,      None,  None),
    ]
)
def test_aggr(family_id, aggr, code, addr):

    assert XcomDeviceFamilies.getCodeByAggregationType(aggr, family_id) == code
    assert XcomDeviceFamilies.getAddrByAggregationType(aggr, family_id) == addr



