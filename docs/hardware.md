# Hardware

## Recommended: Thermalright Trofeo Vision 9.16"

- USB `0416:5408`, 1920×462 IPS, sold as a PC case temperature display.
- Talks the "LY" protocol over plain USB bulk transfers, so libusb works on
  macOS without any driver.
- It's the panel makideck is designed on. Every layout is drawn at 1920×462.
- It fits on a small desk clamp or stand, or leans against the bottom of a
  monitor.

Things worth knowing:

- **It's not a monitor.** macOS doesn't see a display. makideck sends it JPEG
  frames, about 15 ms each, and it takes roughly 24 frames per second.
- **It blanks if nothing arrives** for a few seconds, which is why makideck
  streams frames all the time (2 fps normally, 15 while music plays).
- **Frames over ~512 KB are silently dropped.** makideck lowers JPEG quality
  when a frame would be too big.
- **Only one program can hold it at a time.** Close Thermalright's own app, or
  any other driver, before starting makideck.
- **The firmware can hang** if a transfer is cut off halfway, for example
  when a process is killed while sending. The symptom: the last frame stays on
  screen and the log shows `Operation timed out` on every reconnect. A USB
  reset from software doesn't help. Unplug the panel for a few seconds.
  makideck reconnects by itself.

## Thermalright Trofeo Vision 6.86"

USB `0416:5302`, 1280×480. This one is a HID device, and macOS keeps libusb
away from HID, so makideck talks to it through hidapi instead. The driver is
in [device.py](../makideck/device.py), but it hasn't been tried on a real unit
yet. Tiles are stretched to the narrower width. Reports and pull requests are
welcome.

## Other panels

The protocol work comes from
[thermalright-trcc-linux](https://github.com/Lexonight1/thermalright-trcc-linux),
which knows many more Thermalright LCDs. Supporting one in makideck usually
means adding a `Model` to `device.py` with its USB product ID and the trcc
device class to use. If you try one, please open an issue with what you
found.
