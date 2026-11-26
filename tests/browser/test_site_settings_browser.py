"""Real headless Chromium/Edge UI verification for web/site-settings.js (AG-001).

Drives an actual Chromium/Edge browser via Chrome DevTools Protocol (CDP) using
only aiohttp (already in project dependencies) and the real backend create_app()
plus unmodified web/site-settings.js, web/style.css, and web/overrides.css.
"""
import asyncio
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time

import aiohttp
from aiohttp import web
import pytest

from ble_inventory.config import load_config
from ble_inventory.server import create_app


REPO_ROOT = Path(__file__).resolve().parents[2]


def _find_chromium_binary():
    candidates = [
        os.environ.get("CHROME_BIN"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        shutil.which("chrome"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("msedge"),
    ]
    for path in candidates:
        if path and Path(path).is_file():
            return str(path)
    return None


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _indep_local_to_wgs84(origin_lat, origin_lon, origin_h, rot_deg, x_m, y_m, z_m):
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)
    theta = math.radians(rot_deg)
    east = math.cos(theta) * x_m - math.sin(theta) * y_m
    north = math.sin(theta) * x_m + math.cos(theta) * y_m
    up = z_m
    lat0, lon0 = math.radians(origin_lat), math.radians(origin_lon)
    nu0 = a / math.sqrt(1.0 - e2 * math.sin(lat0) ** 2)
    ox = (nu0 + origin_h) * math.cos(lat0) * math.cos(lon0)
    oy = (nu0 + origin_h) * math.cos(lat0) * math.sin(lon0)
    oz = (nu0 * (1.0 - e2) + origin_h) * math.sin(lat0)
    dx = -math.sin(lon0) * east - math.sin(lat0) * math.cos(lon0) * north + math.cos(lat0) * math.cos(lon0) * up
    dy = math.cos(lon0) * east - math.sin(lat0) * math.sin(lon0) * north + math.cos(lat0) * math.sin(lon0) * up
    dz = math.cos(lat0) * north + math.sin(lat0) * up
    x, y, z = ox + dx, oy + dy, oz + dz
    p = math.hypot(x, y)
    lon = math.atan2(y, x)
    lat = math.atan2(z, p * (1.0 - e2))
    for _ in range(15):
        nu = a / math.sqrt(1.0 - e2 * math.sin(lat) ** 2)
        lat = math.atan2(z + e2 * nu * math.sin(lat), p)
    nu = a / math.sqrt(1.0 - e2 * math.sin(lat) ** 2)
    h = p / math.cos(lat) - nu
    return {"latitude_deg": math.degrees(lat), "longitude_deg": math.degrees(lon), "height_m": h}


LOCAL_HARNESS_HTML = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>AG-001 Local Harness</title>
  <link rel="stylesheet" href="./_ag001_web/style.css">
  <link rel="stylesheet" href="./_ag001_web/overrides.css">
</head>
<body>
  <main>
    <div id="notice" class="notice" role="status">initializing</div>
    <div class="heading-actions"><button class="button secondary" id="settings-button" disabled>場地／Anchor 座標設定</button></div>
    <div id="run-label"></div>
  </main>
  <script type="module">
    import { initSiteSettings } from './_ag001_web/site-settings.js';
    window.__harness = { mode: 'local', bootstrap: null, states: [], notices: [], ready: false };
    const api = initSiteSettings(
      () => ({ mode: window.__harness.mode, bootstrap: window.__harness.bootstrap }),
      (state) => {
        window.__harness.states.push(state);
        document.getElementById('run-label').textContent = state.run_id;
      },
      (msg) => {
        window.__harness.notices.push(msg);
        document.getElementById('notice').textContent = msg;
      },
    );
    window.__harness.updateAvailability = () => api.updateAvailability();
    const bootRes = await fetch('./api/bootstrap', { cache: 'no-store' });
    window.__harness.bootstrap = await bootRes.json();
    const stateRes = await fetch('./api/state', { cache: 'no-store' });
    const initialState = await stateRes.json();
    window.__harness.states.push(initialState);
    document.getElementById('run-label').textContent = initialState.run_id;
    api.updateAvailability();
    window.__harness.ready = true;
  </script>
</body>
</html>
"""

PUBLIC_HARNESS_HTML = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>AG-001 Public Read-Only Harness</title>
  <link rel="stylesheet" href="./_ag001_web/style.css">
  <link rel="stylesheet" href="./_ag001_web/overrides.css">
</head>
<body>
  <main>
    <div id="notice" class="notice" role="status">public replay</div>
    <div class="heading-actions"><button class="button secondary" id="settings-button" disabled>場地／Anchor 座標設定</button></div>
  </main>
  <script type="module">
    import { initSiteSettings } from './_ag001_web/site-settings.js';
    window.__harness = { mode: 'replay', bootstrap: null, states: [], notices: [], ready: false };
    const api = initSiteSettings(
      () => ({ mode: window.__harness.mode, bootstrap: window.__harness.bootstrap }),
      (state) => { window.__harness.states.push(state); },
      (msg) => { window.__harness.notices.push(msg); },
    );
    window.__harness.setMode = (m) => { window.__harness.mode = m; api.updateAvailability(); };
    api.updateAvailability();
    window.__harness.ready = true;
  </script>
</body>
</html>
"""


class CDPPage:
    def __init__(self, session, ws_url):
        self._session = session
        self._ws_url = ws_url
        self._ws = None
        self._seq = 0
        self._pending = {}
        self._reader = None
        self.console_errors = []
        self.exceptions = []

    async def connect(self):
        self._ws = await self._session.ws_connect(self._ws_url, max_msg_size=16 * 1024 * 1024)
        self._reader = asyncio.create_task(self._listen())
        await self.send("Runtime.enable")
        await self.send("Page.enable")

    async def _listen(self):
        async for msg in self._ws:
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            data = json.loads(msg.data)
            if "id" in data:
                fut = self._pending.pop(data["id"], None)
                if fut and not fut.done():
                    if "error" in data:
                        fut.set_exception(RuntimeError(f"CDP error: {data['error']}"))
                    else:
                        fut.set_result(data.get("result", {}))
            elif data.get("method") == "Runtime.consoleAPICalled":
                params = data.get("params", {})
                if params.get("type") in ("error", "warning"):
                    text = " ".join(arg.get("value", str(arg)) for arg in params.get("args", []))
                    self.console_errors.append((params["type"], text))
            elif data.get("method") == "Runtime.exceptionThrown":
                self.exceptions.append(str(data.get("params", {})))

    async def send(self, method, params=None):
        self._seq += 1
        call_id = self._seq
        fut = asyncio.get_running_loop().create_future()
        self._pending[call_id] = fut
        await self._ws.send_json({"id": call_id, "method": method, "params": params or {}})
        return await asyncio.wait_for(fut, timeout=15)

    async def eval(self, expression):
        res = await self.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if "exceptionDetails" in res:
            raise AssertionError(f"JS exception: {res['exceptionDetails']}")
        return res.get("result", {}).get("value")

    async def wait_until(self, js_condition, timeout=8.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if await self.eval(f"Boolean({js_condition})"):
                return
            await asyncio.sleep(0.05)
        raise TimeoutError(f"Timed out waiting for: {js_condition}")

    async def close(self):
        if self._reader:
            self._reader.cancel()
            try:
                await self._reader
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()


class HeadlessBrowser:
    def __init__(self, binary, profile_dir):
        self.binary = binary
        self.profile_dir = profile_dir
        self.port = _free_port()
        self.proc = None
        self.session = None

    async def __aenter__(self):
        cmd = [
            self.binary,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-background-networking",
            "--window-size=1280,800",
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.profile_dir}",
            "about:blank",
        ]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.session = aiohttp.ClientSession()
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            try:
                async with self.session.get(f"http://127.0.0.1:{self.port}/json/version") as resp:
                    if resp.status == 200:
                        return self
            except OSError:
                pass
            await asyncio.sleep(0.1)
        raise RuntimeError("Headless Chromium/Edge CDP did not become ready")

    async def new_page(self, url):
        async with self.session.put(f"http://127.0.0.1:{self.port}/json/new?{url}") as resp:
            if resp.status != 200:
                async with self.session.get(f"http://127.0.0.1:{self.port}/json/new?{url}") as resp2:
                    info = await resp2.json()
            else:
                info = await resp.json()
        page = CDPPage(self.session, info["webSocketDebuggerUrl"])
        await page.connect()
        await page.wait_until("document.readyState === 'complete'")
        return page

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def _attach_test_routes(app):
    async def serve_local(_req):
        return web.Response(text=LOCAL_HARNESS_HTML, content_type="text/html", charset="utf-8")

    async def serve_public(_req):
        return web.Response(text=PUBLIC_HARNESS_HTML, content_type="text/html", charset="utf-8")

    app.router.add_get("/_ag001_local.html", serve_local)
    app.router.add_get("/_ag001_public.html", serve_public)
    app.router.add_static("/_ag001_web/", REPO_ROOT / "web", show_index=False)


def test_real_browser_site_settings_full_acceptance(config, tmp_path, monkeypatch):
    binary = _find_chromium_binary()
    if not binary:
        pytest.skip("Chrome/Edge binary not found for real-browser test")

    async def scenario():
        site_path = tmp_path / "config" / "site.local.json"
        site_path.parent.mkdir(parents=True, exist_ok=True)
        site_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

        app = create_app(config, tmp_path, mode="external", ingest_token="tok", config_path=site_path)
        _attach_test_routes(app)

        runner = web.AppRunner(app)
        await runner.setup()
        port = _free_port()
        site = web.TCPSite(runner, "127.0.0.1", port)
        await site.start()
        base_url = f"http://127.0.0.1:{port}"
        profile_dir = tmp_path / "chrome-profile"

        try:
            async with HeadlessBrowser(binary, profile_dir) as browser:
                # === B1: Desktop Local edit, preview gating, save & reload ===
                page = await browser.new_page(f"{base_url}/_ag001_local.html")
                await page.wait_until("window.__harness && window.__harness.ready")
                assert await page.eval("document.getElementById('settings-button').disabled") is False
                run_0 = await page.eval("window.__harness.states[0].run_id")
                bytes_0 = site_path.read_bytes()

                await page.eval("document.getElementById('settings-button').click()")
                await page.wait_until("document.getElementById('settings-dialog').open")
                assert await page.eval("document.getElementById('site-save').disabled") is True

                # Edit frame_id and A01 X, click preview -> save enabled, disk NOT written.
                await page.eval("""(() => {
                    const f = document.querySelector('#site-fields input[type=text]');
                    f.value = 'ui-local-v2'; f.dispatchEvent(new Event('input', {bubbles:true}));
                    const a1x = document.querySelector('#anchor-fields fieldset input[type=number]');
                    a1x.value = '1.25'; a1x.dispatchEvent(new Event('input', {bubbles:true}));
                })()""")
                assert await page.eval("document.getElementById('site-save').disabled") is True
                await page.eval("document.getElementById('site-check').click()")
                await page.wait_until("!document.getElementById('site-save').disabled")
                preview_text = await page.eval("document.getElementById('site-preview').textContent")
                assert "A01 Local: 1.250, 0.000, 1.200 m" in preview_text
                assert site_path.read_bytes() == bytes_0

                # Editing again must immediately disable Save until re-previewed.
                await page.eval("""(() => {
                    const a1x = document.querySelector('#anchor-fields fieldset input[type=number]');
                    a1x.value = '1.5'; a1x.dispatchEvent(new Event('input', {bubbles:true}));
                })()""")
                assert await page.eval("document.getElementById('site-save').disabled") is True

                # Preview again and Save -> dialog closes, run_id switches, disk persists.
                await page.eval("document.getElementById('site-check').click()")
                await page.wait_until("!document.getElementById('site-save').disabled")
                await page.eval("document.getElementById('site-save').click()")
                await page.wait_until("!document.getElementById('settings-dialog').open")
                run_1 = await page.eval("window.__harness.states.at(-1).run_id")
                assert run_1 != run_0
                assert "已保存" in await page.eval("window.__harness.notices.at(-1)")
                assert load_config(site_path)["frame_id"] == "ui-local-v2"
                assert load_config(site_path)["devices"][0]["position"][0] == pytest.approx(1.5)

                # Re-open dialog and verify reloaded values match persisted file.
                await page.eval("document.getElementById('settings-button').click()")
                await page.wait_until("document.getElementById('settings-dialog').open")
                assert await page.eval("document.querySelector('#site-fields input[type=text]').value") == "ui-local-v2"
                assert float(await page.eval("document.querySelector('#anchor-fields fieldset input[type=number]').value")) == pytest.approx(1.5)

                # === B4: Cancel & Escape do not write file ===
                bytes_after_b1 = site_path.read_bytes()
                await page.eval("""(() => {
                    const f = document.querySelector('#site-fields input[type=text]');
                    f.value = 'cancelled-edit'; f.dispatchEvent(new Event('input', {bubbles:true}));
                })()""")
                await page.eval("document.getElementById('site-check').click()")
                await page.wait_until("!document.getElementById('site-save').disabled")
                await page.eval("document.getElementById('site-cancel').click()")
                await page.wait_until("!document.getElementById('settings-dialog').open")
                assert site_path.read_bytes() == bytes_after_b1
                assert await page.eval("window.__harness.states.at(-1).run_id") == run_1

                # Re-open, edit, press real Escape key -> closes without writing.
                await page.eval("document.getElementById('settings-button').click()")
                await page.wait_until("document.getElementById('settings-dialog').open")
                await page.eval("""(() => {
                    const f = document.querySelector('#site-fields input[type=text]');
                    f.value = 'escape-edit'; f.dispatchEvent(new Event('input', {bubbles:true}));
                })()""")
                await page.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
                await page.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
                await page.wait_until("!document.getElementById('settings-dialog').open")
                assert site_path.read_bytes() == bytes_after_b1

                # === B3: UI validation (empty, Infinity/1e309, collinear) ===
                await page.eval("document.getElementById('settings-button').click()")
                await page.wait_until("document.getElementById('settings-dialog').open")

                # Empty required field.
                await page.eval("""(() => {
                    const a1x = document.querySelector('#anchor-fields fieldset input[type=number]');
                    a1x.value = ''; a1x.dispatchEvent(new Event('input', {bubbles:true}));
                })()""")
                await page.eval("document.getElementById('site-check').click()")
                await page.wait_until("document.getElementById('site-error').textContent.length > 0")
                assert "完整且有效" in await page.eval("document.getElementById('site-error').textContent")
                assert await page.eval("document.getElementById('site-save').disabled") is True

                # Non-finite string ("NaN" / "1e309") in <input type=number> is rejected by browser validity.
                for bad_val in ("NaN", "1e309"):
                    await page.eval(f"""(() => {{
                        const a1x = document.querySelector('#anchor-fields fieldset input[type=number]');
                        a1x.value = '{bad_val}'; a1x.dispatchEvent(new Event('input', {{bubbles:true}}));
                    }})()""")
                    await page.eval("document.getElementById('site-check').click()")
                    await page.wait_until("document.getElementById('site-error').textContent.includes('完整且有效')")
                    assert await page.eval("document.getElementById('site-save').disabled") is True

                # Out-of-range finite value (2e6 > 1e6) passes HTML5 validity and is rejected by server preview.
                await page.eval("""(() => {
                    const a1x = document.querySelector('#anchor-fields fieldset input[type=number]');
                    a1x.value = '2000000'; a1x.dispatchEvent(new Event('input', {bubbles:true}));
                })()""")
                await page.eval("document.getElementById('site-check').click()")
                await page.wait_until("document.getElementById('site-error').textContent.includes('允許範圍內')")
                assert await page.eval("document.getElementById('site-save').disabled") is True

                # Collinear anchors rejected by server preview.
                await page.eval("""(() => {
                    const sets = [...document.querySelectorAll('#anchor-fields fieldset')];
                    sets.forEach((fs, idx) => {
                        const nums = fs.querySelectorAll('input[type=number]');
                        nums[0].value = String(idx * 3);
                        nums[1].value = '0';
                        nums[2].value = '1.2';
                    });
                    sets[0].querySelector('input[type=number]').dispatchEvent(new Event('input', {bubbles:true}));
                })()""")
                await page.eval("document.getElementById('site-check').click()")
                await page.wait_until("document.getElementById('site-error').textContent.includes('共線')")
                assert await page.eval("document.getElementById('site-save').disabled") is True
                assert await page.eval("document.getElementById('site-preview').textContent") == ""
                assert site_path.read_bytes() == bytes_after_b1

                # === B2: WGS84 with rotation (37 deg) in UI ===
                await page.eval("document.getElementById('site-reload').click()")
                await page.wait_until("!document.getElementById('site-reload').disabled && document.querySelector('#anchor-fields fieldset input[type=number]').value === '1.5'")
                wgs_a01 = _indep_local_to_wgs84(25.01734, 121.53975, 20.0, 37.0, 2.0, 1.0, 1.2)
                await page.eval(f"""(() => {{
                    const geoSel = document.querySelectorAll('#site-fields select')[1];
                    geoSel.value = 'yes'; geoSel.dispatchEvent(new Event('change', {{bubbles:true}}));
                    const geoInputs = document.querySelectorAll('#site-fields .site-grid input');
                    geoInputs[0].value = '25.01734';
                    geoInputs[1].value = '121.53975';
                    geoInputs[2].value = '20';
                    geoInputs[3].value = '37';
                    geoInputs[4].value = 'ui-rot37';
                    const a1 = document.querySelector('#anchor-fields fieldset');
                    const modeSel = a1.querySelector('select');
                    modeSel.value = 'wgs'; modeSel.dispatchEvent(new Event('change', {{bubbles:true}}));
                    const llh = a1.querySelectorAll('.site-grid')[1].querySelectorAll('input');
                    llh[0].value = '{wgs_a01["latitude_deg"]:.10f}';
                    llh[1].value = '{wgs_a01["longitude_deg"]:.10f}';
                    llh[2].value = '{wgs_a01["height_m"]:.6f}';
                    llh[0].dispatchEvent(new Event('input', {{bubbles:true}}));
                }})()""")
                assert await page.eval("document.querySelector('#site-fields .site-grid select').value") == "example"
                await page.eval("document.querySelector('#site-fields .site-grid select').value = 'measured'")
                await page.eval("document.getElementById('site-check').click()")
                await page.wait_until("!document.getElementById('site-save').disabled")
                wgs_preview = await page.eval("document.getElementById('site-preview').textContent")
                assert "A01 Local: 2.000, 1.000, 1.200 m" in wgs_preview
                assert "WGS84: 25.017" in wgs_preview
                await page.eval("document.getElementById('site-save').click()")
                await page.wait_until("!document.getElementById('settings-dialog').open")
                run_2 = await page.eval("window.__harness.states.at(-1).run_id")
                assert run_2 != run_1
                loaded_wgs = load_config(site_path)
                assert loaded_wgs["georeference"]["source"] == "measured"
                assert loaded_wgs["georeference"]["rotation_deg"] == 37.0
                assert loaded_wgs["devices"][0]["position"] == pytest.approx([2.0, 1.0, 1.2], abs=1e-4)

                # === B5: Real two-tab conflict (Tab 1 saves, Tab 2 gets 409, reloads, saves) ===
                page2 = await browser.new_page(f"{base_url}/_ag001_local.html")
                await page2.wait_until("window.__harness && window.__harness.ready")

                # Both tabs open dialog on the same revision.
                await page.eval("document.getElementById('settings-button').click()")
                await page.wait_until("document.getElementById('settings-dialog').open")
                await page2.eval("document.getElementById('settings-button').click()")
                await page2.wait_until("document.getElementById('settings-dialog').open")

                # Tab 1 changes frame_id and saves.
                await page.eval("""(() => {
                    const f = document.querySelector('#site-fields input[type=text]');
                    f.value = 'tab1-won'; f.dispatchEvent(new Event('input', {bubbles:true}));
                })()""")
                await page.eval("document.getElementById('site-check').click()")
                await page.wait_until("!document.getElementById('site-save').disabled")
                await page.eval("document.getElementById('site-save').click()")
                await page.wait_until("!document.getElementById('settings-dialog').open")
                bytes_tab1 = site_path.read_bytes()
                assert load_config(site_path)["frame_id"] == "tab1-won"

                # Tab 2 changes A02 X, previews, tries to save -> 409 conflict UI!
                tab2_states_before = await page2.eval("window.__harness.states.length")
                await page2.eval("""(() => {
                    const a2x = document.querySelectorAll('#anchor-fields fieldset')[1].querySelector('input[type=number]');
                    a2x.value = '11.25'; a2x.dispatchEvent(new Event('input', {bubbles:true}));
                })()""")
                await page2.eval("document.getElementById('site-check').click()")
                await page2.wait_until("!document.getElementById('site-save').disabled")
                await page2.eval("document.getElementById('site-save').click()")
                await page2.wait_until("document.getElementById('site-error').textContent.includes('設定版本已變更')")
                assert await page2.eval("document.getElementById('settings-dialog').open") is True
                assert await page2.eval("document.getElementById('site-save').disabled") is True
                assert await page2.eval("window.__harness.states.length") == tab2_states_before
                assert site_path.read_bytes() == bytes_tab1

                # Tab 2 clicks Reload -> receives Tab 1's frame_id, reapplies A02 X, saves cleanly.
                await page2.eval("document.getElementById('site-reload').click()")
                await page2.wait_until("!document.getElementById('site-reload').disabled && document.querySelector('#site-fields input[type=text]').value === 'tab1-won'")
                await page2.eval("""(() => {
                    const a2x = document.querySelectorAll('#anchor-fields fieldset')[1].querySelector('input[type=number]');
                    a2x.value = '11.25'; a2x.dispatchEvent(new Event('input', {bubbles:true}));
                })()""")
                await page2.eval("document.getElementById('site-check').click()")
                await page2.wait_until("!document.getElementById('site-save').disabled")
                await page2.eval("document.getElementById('site-save').click()")
                await page2.wait_until("!document.getElementById('settings-dialog').open")
                merged_cfg = load_config(site_path)
                assert merged_cfg["frame_id"] == "tab1-won"
                assert merged_cfg["devices"][1]["position"][0] == pytest.approx(11.25)

                # === B6: Save failure (507) keeps dialog open and does not switch run_id ===
                from ble_inventory import server as server_mod

                real_persist = server_mod.persist_edit
                monkeypatch.setattr(server_mod, "persist_edit", lambda *args: (_ for _ in ()).throw(OSError("disk full")))
                bytes_before_507 = site_path.read_bytes()
                states_before_507 = await page.eval("window.__harness.states.length")

                await page.eval("document.getElementById('settings-button').click()")
                await page.wait_until("document.getElementById('settings-dialog').open")
                await page.eval("""(() => {
                    const f = document.querySelector('#site-fields input[type=text]');
                    f.value = 'failed-507'; f.dispatchEvent(new Event('input', {bubbles:true}));
                })()""")
                await page.eval("document.getElementById('site-check').click()")
                await page.wait_until("!document.getElementById('site-save').disabled")
                await page.eval("document.getElementById('site-save').click()")
                await page.wait_until("document.getElementById('site-error').textContent.includes('原設定繼續使用')")
                assert await page.eval("document.getElementById('settings-dialog').open") is True
                assert await page.eval("document.getElementById('site-save').disabled") is True
                assert await page.eval("window.__harness.states.length") == states_before_507
                assert site_path.read_bytes() == bytes_before_507
                monkeypatch.setattr(server_mod, "persist_edit", real_persist)
                await page.eval("document.getElementById('site-cancel').click()")
                await page.wait_until("!document.getElementById('settings-dialog').open")

                # === B7: Public / Replay / Cloud read-only mode ===
                pub = await browser.new_page(f"{base_url}/_ag001_public.html")
                await pub.wait_until("window.__harness && window.__harness.ready")
                for mode_name in ("replay", "cloud"):
                    await pub.eval(f"window.__harness.setMode('{mode_name}')")
                    assert await pub.eval("document.getElementById('settings-button').disabled") is True
                    assert "RPi 本地即時模式" in await pub.eval("document.getElementById('settings-button').title")
                # Even if button disabled attribute is removed manually, request() blocks any API write.
                await pub.eval("document.getElementById('settings-button').disabled = false; document.getElementById('settings-button').click();")
                await pub.wait_until("document.getElementById('site-error').textContent.includes('RPi 本地即時頁面編輯')")
                assert await pub.eval("document.getElementById('settings-dialog').open") is False

                # === B8: Mobile viewport (390x844) layout + Keyboard Tab/Enter/Escape ===
                await page.send(
                    "Emulation.setDeviceMetricsOverride",
                    {"width": 390, "height": 844, "deviceScaleFactor": 3, "mobile": True},
                )
                await page.eval("document.getElementById('settings-button').click()")
                await page.wait_until("document.getElementById('settings-dialog').open")
                metrics = await page.eval("""(() => {
                    const d = document.getElementById('settings-dialog');
                    const dr = d.getBoundingClientRect();
                    const actions = ['site-cancel', 'site-reload', 'site-check', 'site-save'].map(id => {
                        const r = document.getElementById(id).getBoundingClientRect();
                        return { id, width: r.width, height: r.height, right: r.right, left: r.left };
                    });
                    return {
                        dialogWidth: dr.width,
                        viewportWidth: window.innerWidth,
                        overflowX: d.scrollWidth - d.clientWidth,
                        actions,
                    };
                })()""")
                assert metrics["dialogWidth"] <= metrics["viewportWidth"]
                assert metrics["overflowX"] <= 2
                for act in metrics["actions"]:
                    assert act["height"] >= 32
                    assert act["right"] <= metrics["viewportWidth"] + 1

                # Keyboard: Tab moves focus inside dialog; Enter before preview does NOT save; Escape closes.
                await page.eval("document.querySelector('#site-fields input[type=text]').focus()")
                first_tag = await page.eval("document.activeElement.tagName")
                await page.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
                await page.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
                second_el_changed = await page.eval("document.activeElement !== document.querySelector('#site-fields input[type=text]')")
                assert first_tag == "INPUT" and second_el_changed is True

                # Press Enter while save is disabled -> must NOT submit or close dialog.
                await page.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                await page.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                await asyncio.sleep(0.1)
                assert await page.eval("document.getElementById('settings-dialog').open") is True
                assert site_path.read_bytes() == bytes_before_507

                # Escape closes dialog.
                await page.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
                await page.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
                await page.wait_until("!document.getElementById('settings-dialog').open")

                # Assert zero uncaught JS exceptions across all tabs.
                for tab in (page, page2, pub):
                    assert tab.exceptions == []
                    await tab.close()
        finally:
            await runner.cleanup()

    asyncio.run(scenario())
