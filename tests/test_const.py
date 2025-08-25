from typing import Literal
import pytest
import pytest_asyncio
from aioxcom import XcomVoltage, XcomLevel, XcomFormat


@pytest.mark.parametrize(
    "fixture, inp_str, inp_def, exp_val, exp_except",
    [
        ("120 VAC", "120 VAC", None, XcomVoltage.AC120, None),
        ("120_VAC", "120_VAC", None, XcomVoltage.AC120, None),
        ("240 VAC", "240 VAC", None, XcomVoltage.AC240, None),
        ("240_VAC", "240_VAC", None, XcomVoltage.AC240, None),

        ("value",   "120 VAC", XcomVoltage.AC240, XcomVoltage.AC120, None),
        ("default", "xxxxxxx", XcomVoltage.AC240, XcomVoltage.AC240, None),
        ("except",  "xxxxxxx", None,          None,          Exception),
    ]
)
def test_voltage(fixture:str, inp_str:str, inp_def: XcomVoltage|None, exp_val: XcomVoltage|None, exp_except: type[Exception]|None):

    if exp_except is None:
        val = XcomVoltage.from_str(inp_str, inp_def)
        assert val == exp_val
        assert type(val) is XcomVoltage
    else:
        with pytest.raises(exp_except):
            val = XcomVoltage.from_str(inp_str, inp_def)


@pytest.mark.parametrize(
    "fixture, inp_str, inp_def, exp_val, exp_except",
    [
        ("INFO",    "INFO",   None, XcomLevel.INFO,   None),
        ("VO",      "VO",     None, XcomLevel.VO,     None),
        ("V.O.",    "V.O.",   None, XcomLevel.VO,     None),
        ("BASIC",   "BASIC",  None, XcomLevel.BASIC,  None),
        ("EXPERT",  "EXPERT", None, XcomLevel.EXPERT, None),
        ("INST",    "INST",   None, XcomLevel.INST,   None),
        ("INST.",   "INST.",  None, XcomLevel.INST,   None),
        ("QSP",     "QSP",    None, XcomLevel.QSP,    None),

        ("value",   "EXPERT", XcomLevel.BASIC, XcomLevel.EXPERT, None),
        ("default", "xxxxxx", XcomLevel.BASIC, XcomLevel.BASIC,  None),
        ("except",  "xxxxxx", None,        None,         Exception),
    ]
)
def test_level(fixture:str, inp_str:str, inp_def: XcomLevel|None, exp_val: XcomLevel|None, exp_except: type[Exception]|None):

    if exp_except is None:
        val = XcomLevel.from_str(inp_str, inp_def)
        assert val == exp_val
        assert type(val) is XcomLevel
    else:
        with pytest.raises(exp_except):
            val = XcomLevel.from_str(inp_str, inp_def)


@pytest.mark.parametrize(
    "fixture, inp_str, inp_def, exp_val, exp_except",
    [
        ("BOOL",          "BOOL",          None, XcomFormat.BOOL, None),
        ("FORMAT",        "FORMAT",        None, XcomFormat.FORMAT, None),
        ("SHORT_ENUM",    "SHORT_ENUM",    None, XcomFormat.SHORT_ENUM, None),
        ("SHORT ENUM",    "SHORT ENUM",    None, XcomFormat.SHORT_ENUM, None),
        ("ERROR",         "ERROR",         None, XcomFormat.ERROR, None),
        ("INT32",         "INT32",         None, XcomFormat.INT32, None),
        ("FLOAT",         "FLOAT",         None, XcomFormat.FLOAT, None),
        ("LONG_ENUM",     "LONG_ENUM",     None, XcomFormat.LONG_ENUM, None),
        ("LONG ENUM",     "LONG ENUM",     None, XcomFormat.LONG_ENUM, None),
        ("GUID",          "GUID",          None, XcomFormat.GUID, None),
        ("STRING",        "STRING",        None, XcomFormat.STRING, None),
        ("DYNAMIC",       "DYNAMIC",       None, XcomFormat.DYNAMIC, None),
        ("BYTES",         "BYTES",         None, XcomFormat.BYTES, None),
        ("MENU",          "MENU",          None, XcomFormat.MENU, None),
        ("ONLY_LEVEL",    "ONLY_LEVEL",    None, XcomFormat.MENU, None),
        ("ONLY LEVEL",    "ONLY LEVEL",    None, XcomFormat.MENU, None),
        ("NOT SUPPORTED", "NOT SUPPORTED", None, XcomFormat.INVALID, None),

        ("value",         "INT32", XcomFormat.FLOAT, XcomFormat.INT32, None),
        ("default",       "xxxxx", XcomFormat.FLOAT, XcomFormat.FLOAT, None),
        ("except",        "xxxxx", None,         None,         Exception),
    ]
)
def test_format(fixture:str, inp_str:str, inp_def: XcomFormat|None, exp_val: XcomFormat|None, exp_except: type[Exception]|None):

    if exp_except is None:
        val = XcomFormat.from_str(inp_str, inp_def)
        assert val == exp_val
        assert type(val) is XcomFormat
    else:
        with pytest.raises(exp_except):
            val = XcomFormat.from_str(inp_str, inp_def)
