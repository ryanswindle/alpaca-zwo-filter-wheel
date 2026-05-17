from ctypes import byref, c_bool, c_int, c_uint8
from datetime import datetime, timezone
from threading import Lock

from config import DeviceConfig, config
from libefw import EFW_ERROR_CODE, EFW_INFO, EFW_SN, load_efw_library
from log import get_logger


logger = get_logger()


class FilterWheelDevice:
    """Low-level driver for the ZWO filter wheel."""

    def __init__(self, device_config: DeviceConfig):
        self._config = device_config

        self.libefw = None

        # SDK device ID (assigned by EFWGetID, used for all subsequent calls)
        self._efw_id: int | None = None

        # Device info populated on connect
        self._slot_num: int = 0
        self._hw_name: str = ""

        # Per-client connection tracking. The physical EFW is opened on
        # the first client to connect and closed only when the last client
        # disconnects, so multiple Alpaca clients can share the device
        # without one's Disconnect knocking another offline. ClientID is
        # taken from the Alpaca request params; alpyca defaults to 0 if
        # the caller doesn't set it, which means alpyca clients that
        # don't override ClientID will share that slot — unavoidable
        # given the spec.
        self._connected_clients: set[int] = set()
        self._clients_lock = Lock()
        self._connecting = False

    #######################################
    # ASCOM Methods Common To All Devices #
    #######################################
    def connect(self, client_id: int = 0) -> None:
        """Register a client. Opens the EFW if this is the first connection."""

        with self._clients_lock:
            if client_id in self._connected_clients:
                return
            first_client = not self._connected_clients
            if first_client:
                self._connecting = True
                try:
                    self._open_device()
                finally:
                    self._connecting = False
            self._connected_clients.add(client_id)
            logger.info(
                f"Client {client_id} connected to {self._config.entity} "
                f"({len(self._connected_clients)} active)"
            )

    def disconnect(self, client_id: int = 0) -> None:
        """Unregister a client. Closes the EFW when the last client leaves."""

        with self._clients_lock:
            if client_id not in self._connected_clients:
                return
            self._connected_clients.discard(client_id)
            remaining = len(self._connected_clients)
            if remaining == 0:
                self._close_device()
            logger.info(
                f"Client {client_id} disconnected from {self._config.entity} "
                f"({remaining} active)"
            )

    def shutdown(self) -> None:
        """Force-close the EFW regardless of client state (server shutdown)."""

        with self._clients_lock:
            self._connected_clients.clear()
            if self._efw_id is not None:
                self._close_device()

    def _open_device(self) -> None:
        """Scan for EFW devices, match by serial number, and open."""

        try:
            # Load the library
            if self.libefw is None:
                self.libefw = load_efw_library(config.library)

            num = self.libefw.EFWGetNum()
            if num <= 0:
                raise RuntimeError("No EFW devices found")

            logger.debug(f"Found {num} EFW device(s)")

            # Scan all connected devices and match by serial number
            matched_id = None

            for index in range(num):
                dev_id = c_int()
                rc = self.libefw.EFWGetID(index, byref(dev_id))
                if rc != EFW_ERROR_CODE.SUCCESS:
                    logger.warning(f"EFWGetID({index}) failed: {EFW_ERROR_CODE.name(rc)}")
                    continue

                rc = self.libefw.EFWOpen(dev_id.value)
                if rc != EFW_ERROR_CODE.SUCCESS:
                    logger.warning(f"EFWOpen({dev_id.value}) failed: {EFW_ERROR_CODE.name(rc)}")
                    continue

                # Check serial number if configured
                if self._config.serial_number:
                    sn = EFW_SN()
                    rc = self.libefw.EFWGetSerialNumber(dev_id.value, byref(sn))
                    if rc == EFW_ERROR_CODE.SUCCESS:
                        serial = bytes(sn.id).hex()
                        logger.debug(f"EFW {dev_id.value}: {serial}")
                        if serial == self._config.serial_number:
                            matched_id = dev_id.value
                            break
                    else:
                        logger.debug(f"EFWGetSerialNumber({dev_id.value}) failed: {EFW_ERROR_CODE.name(rc)}")

                    # Not a match – close and continue
                    self.libefw.EFWClose(dev_id.value)
                else:
                    # No serial configured – take the first device
                    matched_id = dev_id.value
                    break

            if matched_id is None:
                raise RuntimeError(
                    f"No EFW device matching serial '{self._config.serial_number}'"
                    if self._config.serial_number
                    else "Failed to open any EFW device"
                )

            self._efw_id = matched_id

            # Get device properties (required before SetPosition per SDK docs)
            info = EFW_INFO()
            rc = self.libefw.EFWGetProperty(self._efw_id, byref(info))
            if rc != EFW_ERROR_CODE.SUCCESS:
                self.libefw.EFWClose(self._efw_id)
                raise RuntimeError(f"EFWGetProperty failed: {EFW_ERROR_CODE.name(rc)}")

            self._slot_num = info.slotNum
            self._hw_name = info.Name.decode("utf-8", errors="replace").strip()

            # Set direction if configured
            if self._config.unidirectional is not None:
                rc = self.libefw.EFWSetDirection(self._efw_id, self._config.unidirectional)
                if rc != EFW_ERROR_CODE.SUCCESS:
                    logger.warning(f"EFWSetDirection failed: {EFW_ERROR_CODE.name(rc)}")

            # Log firmware version
            major, minor, build = c_uint8(), c_uint8(), c_uint8()
            rc = self.libefw.EFWGetFirmwareVersion(
                self._efw_id, byref(major), byref(minor), byref(build)
            )
            if rc == EFW_ERROR_CODE.SUCCESS:
                logger.debug(
                    f"Firmware: {major.value}.{minor.value}.{build.value}"
                )

            logger.info(f"Opened filter wheel {self._config.entity}")

        except Exception as e:
            logger.error(f"Connection error: {e}")
            self._efw_id = None
            raise

    @property
    def connected(self) -> bool:
        # Reading set truthiness is atomic in CPython, no lock needed
        return bool(self._connected_clients)

    @property
    def connecting(self) -> bool:
        return self._connecting

    def _close_device(self) -> None:
        """Close the underlying EFW handle (caller holds _clients_lock)."""

        if self._efw_id is not None:
            rc = self.libefw.EFWClose(self._efw_id)
            if rc != EFW_ERROR_CODE.SUCCESS:
                logger.warning(f"EFWClose failed: {EFW_ERROR_CODE.name(rc)}")

        self._efw_id = None
        logger.info(f"Closed filter wheel {self._config.entity}")

    @property
    def entity(self) -> str:
        return self._config.entity

    ###########################
    # IFilterWheel properties #
    ###########################
    @property
    def focus_offsets(self) -> list:
        return self._config.focus_offsets

    @property
    def names(self) -> list:
        return self._config.names

    @property
    def position(self) -> int:
        if self._efw_id is None:
            raise RuntimeError("Not connected to filter wheel")

        pos = c_int(-1)
        rc = self.libefw.EFWGetPosition(self._efw_id, byref(pos))
        if rc != EFW_ERROR_CODE.SUCCESS:
            logger.error(f"EFWGetPosition failed: {EFW_ERROR_CODE.name(rc)}")
            return -1
        return pos.value

    @position.setter
    def position(self, value: int):
        if self._efw_id is None:
            raise RuntimeError("Not connected to filter wheel")

        rc = self.libefw.EFWSetPosition(self._efw_id, value)
        if rc != EFW_ERROR_CODE.SUCCESS:
            raise RuntimeError(f"EFWSetPosition failed: {EFW_ERROR_CODE.name(rc)}")

        logger.debug(f"Moving to position {value}")

    @property
    def timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
