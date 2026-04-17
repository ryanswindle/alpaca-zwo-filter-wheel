# ZWO – ASCOM Alpaca Server for the ZWO Filter Wheel (EFW)

A FastAPI-based server, implementing the **IFilterWheelV3** interface. Communication is via the EFW SDK (`libEFWFilter.so` / `EFW_filter.dll`).

---

## Implemented IFilterWheelV3 capabilities as of this driver version

| Property/Method | Supported |
|-----------------|-----------|
| FocusOffsets    | ✔         |
| Names           | ✔         |
| Position        | ✔         |

Tested on the EFW (7-position).

---

## Architecture

| File                    | Purpose                                     |
|-------------------------|---------------------------------------------|
| `main.py`               | FastAPI app, lifespan, router wiring        |
| `config.py`             | Pydantic config models, YAML loader         |
| `config.yaml`           | User-editable configuration                 |
| `libefw.py`             | ctypes wrapper for the ZWO EFW SDK          |
| `filter_wheel.py`       | FastAPI router – IFilterWheelV3 endpoints   |
| `filter_wheel_device.py`| Low-level EFW SDK driver                    |
| `management.py`         | `/management` Alpaca management endpoints   |
| `setup.py`              | `/setup` HTML stub pages                    |
| `discovery.py`          | UDP Alpaca discovery responder (port 32227) |
| `responses.py`          | Pydantic response models                    |
| `exceptions.py`         | ASCOM Alpaca error classes                  |
| `shr.py`                | Shared FastAPI dependencies / helpers       |
| `log.py`                | Loguru config + stdlib intercept handler    |
| `test.py`               | Quick smoke-test script                     |
| `requirements.txt`      | Python package dependencies                 |
| `Dockerfile`            | Container build                             |

---

## SDK notes

The ZWO EFW filter wheels communicate over USB using the EFW SDK
(`libEFWFilter.so` on Linux, `EFW_filter.dll` on Windows).

- **Enumeration** — `EFWGetNum` → `EFWGetID` → `EFWOpen` → `EFWGetProperty`.
- **Position query** — `EFWGetPosition` returns 0–N or −1 while moving.
- **Position command** — `EFWSetPosition` starts the move and returns immediately.
- **Direction** — `EFWSetDirection` controls unidirectional rotation.
- **Calibration** — `EFWCalibrate` triggers a homing/calibration sequence.
- **Serial matching** — `EFWGetSerialNumber` is used to match configured
  devices when multiple EFWs are connected.

On Linux, if the SDK can detect but not open the device, copy the udev rules
file from the SDK's `lib/` directory:

```bash
sudo cp efw.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
```

Then re-plug the USB cable.

---

## Configuration

Edit `config.yaml` to match your filter wheel setup.

Multiple ZWO filter wheels can be registered by adding further entries under
`devices:` with distinct `device_number` values and their respective
`serial_number` for identification.

---

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

The server starts on `0.0.0.0:5000` by default (configurable in `config.yaml`).

---

## Smoke test

```bash
# Requires hardware connected – will cycle through all filter positions
python test.py
```

---

## Docker

```bash
docker build -t alpaca-zwo-filter-wheel .
docker run -d --name alpaca-zwo-filter-wheel \
    -v ./config.yaml:/alpyca/config.yaml:ro \
    --network host \
    --privileged \
    -v /dev/bus/usb:/dev/bus/usb \
    --restart unless-stopped \
    alpaca-zwo-filter-wheel
docker logs -f alpaca-zwo-filter-wheel
```
