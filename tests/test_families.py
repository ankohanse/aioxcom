
import pytest
from aioxcom import XcomDeviceFamilies, XcomDeviceFamilyUnknownException, XcomDeviceCodeUnknownException, XcomDeviceAddrUnknownException


def test_list():
    families = XcomDeviceFamilies.getList()
    assert len(families) == 9


def test_id():
    families = XcomDeviceFamilies.getList()
    for family in families:
        assert family == XcomDeviceFamilies.getById(family.id)

    with pytest.raises(XcomDeviceFamilyUnknownException):
        family = XcomDeviceFamilies.getById("XXX")


def test_addr():
    tests = {
        ("xt", 101, "XT1"),
        ("xt", 109, "XT9"),
        ("l1", 191, "L1"),
        ("l2", 192, "L2"),
        ("l3", 193, "L3"),
        ("rcc", 501, "RCC"),
        ("bsp", 601, "BSP"),
        ("bms", 601, "BMS"),
        ("vt", 301, "VT1"),
        ("vt", 315, "VT15"),
        ("vs", 701, "VS1"),
        ("vs", 715, "VS15"),
    }
    for (family_id, addr, code) in tests:
        family = XcomDeviceFamilies.getById(family_id)
        assert family.getCode(addr) == code
        assert XcomDeviceFamilies.getAddrByCode(code) == addr


def test_addr_fail():
    with pytest.raises(XcomDeviceAddrUnknownException):
        family = XcomDeviceFamilies.getById("xt")
        code = family.getCode(999)

    with pytest.raises(XcomDeviceCodeUnknownException):
        addr = XcomDeviceFamilies.getAddrByCode("ABC")
