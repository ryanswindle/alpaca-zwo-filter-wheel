"""
ZWO EFW filter wheel SDK wrapper with proper ctypes function signatures.

Provides constants, structures, error codes, and library loading
with explicit argtypes/restype declarations for 64-bit stability.
"""

from ctypes import (
    CDLL, POINTER, Structure, c_bool, c_char, c_char_p, c_int,
    c_uint8, cdll,
)

from log import get_logger


logger = get_logger()


###############
# Error codes #
###############
class EFW_ERROR_CODE:
    SUCCESS = 0
    ERROR_INVALID_INDEX = 1
    ERROR_INVALID_ID = 2
    ERROR_INVALID_VALUE = 3
    ERROR_REMOVED = 4
    ERROR_MOVING = 5
    ERROR_ERROR_STATE = 6
    ERROR_GENERAL_ERROR = 7
    ERROR_NOT_SUPPORTED = 8
    ERROR_INVALID_LENGTH = 9
    ERROR_CLOSED = 10
    ERROR_END = -1

    _names = {
        0: "EFW_SUCCESS",
        1: "EFW_ERROR_INVALID_INDEX",
        2: "EFW_ERROR_INVALID_ID",
        3: "EFW_ERROR_INVALID_VALUE",
        4: "EFW_ERROR_REMOVED",
        5: "EFW_ERROR_MOVING",
        6: "EFW_ERROR_ERROR_STATE",
        7: "EFW_ERROR_GENERAL_ERROR",
        8: "EFW_ERROR_NOT_SUPPORTED",
        9: "EFW_ERROR_INVALID_LENGTH",
        10: "EFW_ERROR_CLOSED",
        -1: "EFW_ERROR_END",
    }

    @classmethod
    def name(cls, code: int) -> str:
        return cls._names.get(code, f"UNKNOWN({code})")


##############
# Structures #
##############
class EFW_INFO(Structure):
    _fields_ = [
        ("ID", c_int),
        ("Name", c_char * 64),
        ("slotNum", c_int),
    ]


class EFW_ID(Structure):
    _fields_ = [
        ("id", c_uint8 * 8),
    ]


class EFW_SN(Structure):
    _fields_ = [
        ("id", c_uint8 * 8),
    ]


def load_efw_library(library_path: str) -> CDLL:
    """Load the ZWO EFW shared library with proper function signatures."""
    lib = cdll.LoadLibrary(library_path)

    # ---- Device enumeration ----
    lib.EFWGetNum.argtypes = []
    lib.EFWGetNum.restype = c_int

    lib.EFWGetProductIDs.argtypes = [POINTER(c_int)]
    lib.EFWGetProductIDs.restype = c_int

    lib.EFWCheck.argtypes = [c_int, c_int]
    lib.EFWCheck.restype = c_int

    lib.EFWGetID.argtypes = [c_int, POINTER(c_int)]
    lib.EFWGetID.restype = c_int

    # ---- Open / Close ----
    lib.EFWOpen.argtypes = [c_int]
    lib.EFWOpen.restype = c_int

    lib.EFWClose.argtypes = [c_int]
    lib.EFWClose.restype = c_int

    # ---- Properties ----
    lib.EFWGetProperty.argtypes = [c_int, POINTER(EFW_INFO)]
    lib.EFWGetProperty.restype = c_int

    # ---- Position ----
    lib.EFWGetPosition.argtypes = [c_int, POINTER(c_int)]
    lib.EFWGetPosition.restype = c_int

    lib.EFWSetPosition.argtypes = [c_int, c_int]
    lib.EFWSetPosition.restype = c_int

    # ---- Direction ----
    lib.EFWSetDirection.argtypes = [c_int, c_bool]
    lib.EFWSetDirection.restype = c_int

    lib.EFWGetDirection.argtypes = [c_int, POINTER(c_bool)]
    lib.EFWGetDirection.restype = c_int

    # ---- Calibration ----
    lib.EFWCalibrate.argtypes = [c_int]
    lib.EFWCalibrate.restype = c_int

    # ---- Version info ----
    lib.EFWGetSDKVersion.argtypes = []
    lib.EFWGetSDKVersion.restype = c_char_p

    lib.EFWGetFirmwareVersion.argtypes = [
        c_int, POINTER(c_uint8), POINTER(c_uint8), POINTER(c_uint8)
    ]
    lib.EFWGetFirmwareVersion.restype = c_int

    # ---- Serial number ----
    lib.EFWGetSerialNumber.argtypes = [c_int, POINTER(EFW_SN)]
    lib.EFWGetSerialNumber.restype = c_int

    # ---- Hardware error code ----
    lib.EFWGetHWErrorCode.argtypes = [c_int, POINTER(c_int)]
    lib.EFWGetHWErrorCode.restype = c_int

    # ---- Alias ----
    lib.EFWSetID.argtypes = [c_int, EFW_ID]
    lib.EFWSetID.restype = c_int

    logger.debug(f"Loaded EFW library from {library_path}")
    return lib
