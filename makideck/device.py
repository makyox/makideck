"""The Thermalright Trofeo Vision panel over USB.

These panels aren't displays to macOS — they take JPEG frames over a vendor
protocol. The protocol work is thermalright-trcc-linux's (GPL-3.0); we pick
the right device class and transport for the model that's plugged in:

    9.16"  0416:5408  1920×462  LY protocol, USB bulk via libusb   (tested)
    6.86"  0416:5302  1280×480  HID; macOS needs hidapi, not libusb (untested)

Both blank after a few seconds without frames, so the loop keeps sending.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from PIL import Image

log = logging.getLogger(__name__)

VENDOR = 0x0416
LARGEST_JPEG = 500 * 1024        # the 9.16" firmware drops frames above ~512 KB


@dataclass(frozen=True)
class Model:
    name: str
    product: int
    hid: bool


MODELS = (Model('Trofeo Vision 9.16"', 0x5408, hid=False),
          Model('Trofeo Vision 6.86"', 0x5302, hid=True))


def find_model() -> Model:
    import usb.core
    for m in MODELS:
        if m.hid:
            import hid
            if hid.enumerate(VENDOR, m.product):
                return m
        elif usb.core.find(idVendor=VENDOR, idProduct=m.product) is not None:
            return m
    raise RuntimeError("no Trofeo Vision panel on USB")


def _open(model: Model):
    from trcc.core.registry import find_product
    info = find_product(VENDOR, model.product)
    if model.hid:
        from trcc.adapters.device.hid_lcd import HidLcd
        from trcc.adapters.device.transport import HidApiTransport
        from trcc.core.models import quirks_for
        dev = HidLcd(info, HidApiTransport(VENDOR, model.product))
        dev.set_quirks(quirks_for(VENDOR, model.product, 0x0407))
        return dev
    from trcc.adapters.device.ly_lcd import LyLcd
    from trcc.adapters.device.transport import PyUsbBulkTransport
    return LyLcd(info, PyUsbBulkTransport(VENDOR, model.product))


def encode(img: Image.Image, quality: int = 90) -> bytes:
    """JPEG small enough for the firmware, lowering quality if it must."""
    rgb = img.convert("RGB")
    for q in (quality, 75, 60, 45):
        buf = io.BytesIO()
        rgb.save(buf, "JPEG", quality=q)
        if buf.tell() <= LARGEST_JPEG:
            break
    return buf.getvalue()


class Panel:
    def __init__(self, quality: int = 90) -> None:
        self.quality = quality
        self.size: tuple[int, int] | None = None
        self._dev = None

    @property
    def open(self) -> bool:
        return self._dev is not None

    def connect(self) -> tuple[int, int]:
        model = find_model()
        dev = _open(model)
        try:
            hello = dev.connect()
        except Exception:
            # Let go of the interface, or the next attempt from this process
            # fails with "Access denied" against our own claim.
            try:
                dev.disconnect()
            except Exception:
                pass
            raise
        self._dev, self.size = dev, tuple(hello.resolution)
        log.info("%s connected, %d×%d", model.name, *self.size)
        return self.size

    def show(self, img: Image.Image) -> bool:
        return bool(self._dev.send(encode(img, self.quality)))

    def close(self) -> None:
        dev, self._dev = self._dev, None
        if dev is not None:
            try:
                dev.disconnect()
            except Exception:
                log.debug("disconnect failed", exc_info=True)
