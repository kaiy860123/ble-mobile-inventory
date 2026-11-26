"""Same-origin local dashboard, authenticated ingestion and task controls."""
import asyncio
import contextlib
import hmac
import json
import secrets
import time
from pathlib import Path
from aiohttp import web
from .cloud import CloudPublisher
from .contracts import validate_batch
from .engine import InventoryEngine
from .inputs import SyntheticSource, BleSource
from .storage import RunStore


def create_app(config, root, mode="demo", ingest_token=None):
    root = Path(root).resolve()
    engine = InventoryEngine(config)
    engine.start("physical" if mode == "ble" else "simulation")
    cloud = CloudPublisher(config.get("cloud", {}))
    source = SyntheticSource(config) if mode == "demo" else BleSource(config) if mode == "ble" else None
    control_token = secrets.token_urlsafe(32)
    ingest_token = ingest_token or secrets.token_urlsafe(32)
    app = web.Application(client_max_size=1024*1024)
    runtime = {"store": None, "websockets": set(), "input_error": ""}
    app[web.AppKey("runtime", dict)] = runtime

    def require_control(request):
        # Browsers must originate from this local service. No CORS is enabled.
        origin = request.headers.get("Origin")
        if origin and origin != f"{request.scheme}://{request.host}":
            raise web.HTTPForbidden(text="Cross-origin control rejected")
        if not hmac.compare_digest(request.headers.get("X-Control-Token", ""), control_token):
            raise web.HTTPForbidden(text="Local control token required")

    def current():
        state = engine.snapshot()
        return {**state, "cloud": cloud.status(), "input_error": runtime["input_error"], "input_mode": mode}

    async def bootstrap(request):
        return web.json_response({"local": True, "control_token": control_token, "mode": mode}, headers={"Cache-Control": "no-store"})

    async def state(request):
        return web.json_response(current(), headers={"Cache-Control": "no-store"})

    async def control(request):
        require_control(request)
        try:
            value = await request.json()
            action = value.get("action")
            if action == "start":
                if runtime["store"]:
                    runtime["store"].close()
                engine.start("physical" if mode == "ble" else "simulation")
                runtime["store"] = RunStore(root, engine, mode)
            elif action == "stop":
                engine.active = False
                runtime["store"].snapshot(current())
            elif action == "toggle_target" and mode == "demo":
                key = value.get("device_id")
                if key not in engine.target_samples:
                    raise ValueError("Unknown target")
                source.disabled.symmetric_difference_update({key})
            else:
                raise ValueError("Unsupported action")
        except (ValueError, TypeError, KeyError) as error:
            raise web.HTTPBadRequest(text=str(error))
        return web.json_response(current())

    async def observations(request):
        if mode != "external":
            raise web.HTTPConflict(text="Start with --mode external for Gazebo input")
        if not hmac.compare_digest(request.headers.get("Authorization", ""), "Bearer "+ingest_token):
            raise web.HTTPUnauthorized()
        try:
            value = validate_batch(await request.json())
            if abs(value["timestamp"]-time.time()) > 30:
                raise ValueError("Live observations must be within 30s of server UTC clock")
            accepted = engine.ingest(value)
            if accepted:
                runtime["store"].observation(value)
            return web.json_response({"accepted": accepted})
        except (ValueError, TypeError, KeyError) as error:
            raise web.HTTPBadRequest(text=str(error))

    async def export(request):
        store = runtime["store"]
        if request.query.get("format") == "csv":
            return web.Response(text="\ufeff"+store.csv(), content_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{engine.run_id}.csv"'})
        return web.json_response(store.replay(), headers={"Content-Disposition": f'attachment; filename="{engine.run_id}.json"'})

    async def websocket(request):
        origin = request.headers.get("Origin")
        if origin and origin != f"{request.scheme}://{request.host}":
            raise web.HTTPForbidden()
        ws = web.WebSocketResponse(heartbeat=20, max_msg_size=1024)
        await ws.prepare(request)
        runtime["websockets"].add(ws)
        try:
            await ws.send_json(current())
            async for _ in ws:
                pass
        finally:
            runtime["websockets"].discard(ws)
        return ws

    async def ticker():
        if isinstance(source, BleSource):
            try:
                await source.start()
            except Exception as error:
                runtime["input_error"] = f"BLE 啟動失敗：{type(error).__name__}；請檢查藍牙與權限"
        while True:
            started = time.monotonic()
            if source and engine.active and not runtime["input_error"]:
                batch = source.sample()[0] if mode == "demo" else source.sample()
                try:
                    if engine.ingest(batch):
                        runtime["store"].observation(batch)
                except ValueError as error:
                    runtime["input_error"] = str(error)
            snapshot = current()
            if engine.active:
                runtime["store"].snapshot(snapshot)
            cloud.publish(snapshot)
            for ws in list(runtime["websockets"]):
                if not ws.closed:
                    try:
                        await asyncio.wait_for(ws.send_json(snapshot), timeout=0.5)
                    except (ConnectionError, asyncio.TimeoutError):
                        await ws.close()
            await asyncio.sleep(max(0.05, config["publish_interval_s"]-(time.monotonic()-started)))

    async def lifecycle(application):
        runtime["store"] = RunStore(root, engine, mode)
        try:
            cloud.start()
        except (ValueError, OSError) as error:
            cloud.error = f"雲端設定未就緒：{type(error).__name__}，本地持續運作"
        task = asyncio.create_task(ticker())
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        if isinstance(source, BleSource):
            await source.stop()
        for ws in list(runtime["websockets"]):
            await ws.close()
        cloud.stop()
        runtime["store"].close()

    app.cleanup_ctx.append(lifecycle)
    app.router.add_get("/api/bootstrap", bootstrap)
    app.router.add_get("/api/state", state)
    app.router.add_post("/api/control", control)
    app.router.add_post("/api/observations", observations)
    app.router.add_get("/api/export", export)
    app.router.add_get("/api/ws", websocket)
    dist = root / "web" / "dist"
    if dist.is_dir():
        app.router.add_get("/", lambda request: web.FileResponse(dist / "index.html"))
        app.router.add_static("/", dist, show_index=False)
    return app
