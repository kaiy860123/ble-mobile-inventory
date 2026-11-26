"""Optional non-blocking, latest-state AWS IoT publisher. History stays local."""
import json
import ssl
from pathlib import Path
from .storage import compact_snapshot


class CloudPublisher:
    def __init__(self, config):
        self.config = config
        self.client = None
        self.connected = False
        self.error = "未啟用"
        self.sent = 0

    def start(self):
        if not self.config.get("enabled"):
            return
        import paho.mqtt.client as mqtt
        for key in ("cert_path", "key_path", "ca_path"):
            if not Path(self.config.get(key, "")).is_file():
                raise ValueError(f"Cloud {key} is missing")
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.config["client_id"], protocol=mqtt.MQTTv311)
        self.client.max_queued_messages_set(1)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.tls_set(self.config["ca_path"], certfile=self.config["cert_path"], keyfile=self.config["key_path"], tls_version=ssl.PROTOCOL_TLS_CLIENT)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.connect_async(self.config["endpoint"], 8883, keepalive=30)
        self.client.loop_start()
        self.error = "連線中"

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self.connected = reason_code == 0
        self.error = "" if self.connected else "AWS 拒絕連線"

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        self.error = "AWS 連線中斷，本地持續運作"

    def publish(self, snapshot):
        if not self.connected:
            return False
        # QoS 0 + no retain + no offline app queue: no historical replay after reconnect.
        payload = json.dumps(compact_snapshot(snapshot), ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        result = self.client.publish(self.config["topic"], payload, qos=0, retain=False)
        if result.rc == 0:
            self.sent += 1
            return True
        return False

    def status(self):
        return {"enabled": bool(self.config.get("enabled")), "connected": self.connected, "sent": self.sent, "message": self.error}

    def stop(self):
        if self.client:
            self.client.disconnect()
            self.client.loop_stop()
