from typing import Literal
import pytest
import pytest_asyncio
from aioxcom import VOLTAGE, LEVEL, FORMAT


@pytest.mark.parametrize(
    "fixture, inp_str, inp_def, exp_val, exp_except",
    [
        ("120 VAC", "120 VAC", None, VOLTAGE.AC120, None),
        ("120_VAC", "120_VAC", None, VOLTAGE.AC120, None),
        ("240 VAC", "240 VAC", None, VOLTAGE.AC240, None),
        ("240_VAC", "240_VAC", None, VOLTAGE.AC240, None),

        ("value",   "120 VAC", VOLTAGE.AC240, VOLTAGE.AC120, None),
        ("default", "xxxxxxx", VOLTAGE.AC240, VOLTAGE.AC240, None),
        ("except",  "xxxxxxx", None,          None,          Exception),
    ]
)
def test_voltage(fixture:str, inp_str:str, inp_def: VOLTAGE|None, exp_val: VOLTAGE|None, exp_except: type[Exception]|None):

    if exp_except is None:
        val = VOLTAGE.from_str(inp_str, inp_def)
        assert val == exp_val
        assert type(val) is VOLTAGE
    else:
        with pytest.raises(exp_except):
            val = VOLTAGE.from_str(inp_str, inp_def)


@pytest.mark.parametrize(
    "fixture, inp_str, inp_def, exp_val, exp_except",
    [
        ("INFO",    "INFO",   None, LEVEL.INFO,   None),
        ("VO",      "VO",     None, LEVEL.VO,     None),
        ("V.O.",    "V.O.",   None, LEVEL.VO,     None),
        ("BASIC",   "BASIC",  None, LEVEL.BASIC,  None),
        ("EXPERT",  "EXPERT", None, LEVEL.EXPERT, None),
        ("INST",    "INST",   None, LEVEL.INST,   None),
        ("INST.",   "INST.",  None, LEVEL.INST,   None),
        ("QSP",     "QSP",    None, LEVEL.QSP,    None),

        ("value",   "EXPERT", LEVEL.BASIC, LEVEL.EXPERT, None),
        ("default", "xxxxxx", LEVEL.BASIC, LEVEL.BASIC,  None),
        ("except",  "xxxxxx", None,        None,         Exception),
    ]
)
def test_level(fixture:str, inp_str:str, inp_def: LEVEL|None, exp_val: LEVEL|None, exp_except: type[Exception]|None):

    if exp_except is None:
        val = LEVEL.from_str(inp_str, inp_def)
        assert val == exp_val
        assert type(val) is LEVEL
    else:
        with pytest.raises(exp_except):
            val = LEVEL.from_str(inp_str, inp_def)


@pytest.mark.parametrize(
    "fixture, inp_str, inp_def, exp_val, exp_except",
    [
        ("BOOL",          "BOOL",          None, FORMAT.BOOL, None),
        ("FORMAT",        "FORMAT",        None, FORMAT.FORMAT, None),
        ("SHORT_ENUM",    "SHORT_ENUM",    None, FORMAT.SHORT_ENUM, None),
        ("SHORT ENUM",    "SHORT ENUM",    None, FORMAT.SHORT_ENUM, None),
        ("ERROR",         "ERROR",         None, FORMAT.ERROR, None),
        ("INT32",         "INT32",         None, FORMAT.INT32, None),
        ("FLOAT",         "FLOAT",         None, FORMAT.FLOAT, None),
        ("LONG_ENUM",     "LONG_ENUM",     None, FORMAT.LONG_ENUM, None),
        ("LONG ENUM",     "LONG ENUM",     None, FORMAT.LONG_ENUM, None),
        ("STRING",        "STRING",        None, FORMAT.STRING, None),
        ("DYNAMIC",       "DYNAMIC",       None, FORMAT.DYNAMIC, None),
        ("BYTES",         "BYTES",         None, FORMAT.BYTES, None),
        ("MENU",          "MENU",          None, FORMAT.MENU, None),
        ("ONLY_LEVEL",    "ONLY_LEVEL",    None, FORMAT.MENU, None),
        ("ONLY LEVEL",    "ONLY LEVEL",    None, FORMAT.MENU, None),
        ("NOT SUPPORTED", "NOT SUPPORTED", None, FORMAT.INVALID, None),

        ("value",         "INT32", FORMAT.FLOAT, FORMAT.INT32, None),
        ("default",       "xxxxx", FORMAT.FLOAT, FORMAT.FLOAT, None),
        ("except",        "xxxxx", None,         None,         Exception),
    ]
)
def test_format(fixture:str, inp_str:str, inp_def: FORMAT|None, exp_val: FORMAT|None, exp_except: type[Exception]|None):

    if exp_except is None:
        val = FORMAT.from_str(inp_str, inp_def)
        assert val == exp_val
        assert type(val) is FORMAT
    else:
        with pytest.raises(exp_except):
            val = FORMAT.from_str(inp_str, inp_def)
