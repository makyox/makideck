"""Regenerate the README images from demo data, driving the editor in Chrome.

    uvx --with playwright python tools/screenshots.py

Starts `makideck run --demo --no-panel` on a spare port, so nothing personal
ends up in the pictures, and doubles as an end-to-end check of the editor.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "img"
PORT = 8791
URL = f"http://127.0.0.1:{PORT}"


def get(path: str) -> dict:
    return json.load(urllib.request.urlopen(URL + path))


async def shoot() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        page = await browser.new_page(viewport={"width": 1500, "height": 980}, device_scale_factor=2)

        # The live view.
        await page.goto(URL + "/")
        await page.wait_for_timeout(1500)
        await page.locator(".wrap").screenshot(path=OUT / "mirror.png")

        # Drag the outside tile to the front, recording a GIF.
        await page.goto(URL + "/editor")
        await page.wait_for_timeout(1500)
        panel = page.locator("#panel")
        tile = page.locator(".tile[data-name='Outside']")
        box = await tile.bounding_box()
        frames: list[Image.Image] = []

        async def grab() -> None:
            shot = await panel.screenshot()
            img = Image.open(__import__("io").BytesIO(shot)).convert("RGB")
            frames.append(img.resize((img.width // 3, img.height // 3), Image.LANCZOS))

        x, y = box["x"] + box["width"] / 2, box["y"] + 120
        for _ in range(4):
            await grab()
        await page.mouse.move(x, y)
        await page.mouse.down()
        for i in range(1, 25):
            await page.mouse.move(x - i * 50, y)
            await page.wait_for_timeout(15)
            await grab()
        await page.mouse.up()
        for _ in range(10):
            await page.wait_for_timeout(120)
            await grab()
        assert get("/deck")["order"][0] == "outside", "drag did not reorder"
        frames[0].save(OUT / "drag.gif", save_all=True, append_images=frames[1:],
                       duration=[80] * (len(frames) - 1) + [1500], loop=0, optimize=True)

        # Hide a tile and add it back.
        await page.click(".tile[data-name='Session']")
        await page.click("#hide")
        await page.wait_for_timeout(300)
        assert "session" in get("/deck")["hidden"]
        await page.click("#tray button")
        await page.wait_for_timeout(300)
        assert "session" in get("/deck")["order"]

        # Back to the default layout; open the outside tile's settings.
        await page.click("#reset")
        await page.wait_for_timeout(1500)
        await page.click(".tile[data-name='Outside']")
        await page.fill(".f input[placeholder]", "Kraków")
        await page.wait_for_selector(".results button", timeout=10000)
        await page.wait_for_timeout(300)
        await page.screenshot(path=OUT / "editor.png", full_page=True)

        # A plain select field saves without the network.
        await page.click(".tile[data-name='Projects today']")
        await page.select_option(".f select", "3")
        await page.click("#save")
        await page.wait_for_selector("#msg.ok")
        assert get("/deck")["tiles"][2]["settings"]["rows"] == "3"
        await browser.close()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "makideck", "preview", str(OUT / "deck.png")], check=True)
    subprocess.run([sys.executable, "-m", "makideck", "preview", str(OUT / "forecast.png"),
                    "--view", "forecast"], check=True)
    server = subprocess.Popen([sys.executable, "-m", "makideck", "run", "--demo", "--no-panel",
                               "--port", str(PORT)], stderr=subprocess.DEVNULL)
    try:
        time.sleep(3)
        asyncio.run(shoot())
    finally:
        server.terminate()
    print("screenshots in", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
