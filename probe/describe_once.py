"""One node.describe request. Password is read from stdin, never saved."""
import getpass
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paho.mqtt.client as mqtt


def now():
    return datetime.now(timezone(timedelta(hours=8)))


def main():
    password = getpass.getpass("MQTT password: ") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\r\n")
    if not password:
        raise ValueError("Password required")
    task_id = str(uuid.uuid4())
    directory = Path(__file__).resolve().parents[1] / "evidence" / (now().strftime("%Y%m%d-%H%M%S") + "-" + task_id[:8])
    directory.mkdir(parents=True, exist_ok=False)
    base = "cardpool/v1/nodes/ec20test"
    state = {"connected": False, "subscribed": False, "terminal": None, "failure": None}
    pending = {}
    received = {}

    def record(kind, **fields):
        with (directory / "trace.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"observed_at": now().isoformat(), "kind": kind, **fields}, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def on_connect(client, userdata, flags, reason, properties):
        record("connack", reason=str(reason))
        if reason.is_failure:
            state["failure"] = "Broker rejected connection: " + str(reason)
        else:
            state["connected"] = True
            code, mid = client.subscribe(base + "/task", qos=1)
            if code != mqtt.MQTT_ERR_SUCCESS:
                state["failure"] = "Could not request subscription"

    def on_subscribe(client, userdata, mid, reasons, properties):
        record("suback", reasons=[str(reason) for reason in reasons])
        if not reasons or any(reason.is_failure for reason in reasons):
            state["failure"] = "Subscription rejected"
        else:
            state["subscribed"] = True

    def on_publish(client, userdata, mid, reason, properties):
        purpose = pending.pop(mid, "unknown")
        record("puback", purpose=purpose, reason=str(reason))
        if reason.is_failure:
            state["failure"] = "Publish rejected: " + str(reason)

    def on_message(client, userdata, message):
        try:
            payload = json.loads(message.payload)
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(payload, dict) or payload.get("id") != task_id:
            return
        record("task", topic=message.topic, retained=message.retain, raw=message.payload.decode("utf-8"))
        seq = payload.get("seq")
        if message.retain or type(seq) is not int or seq < 1:
            state["failure"] = "Unexpected retained reply or invalid sequence"
            return
        if seq in received and received[seq] != payload:
            state["failure"] = "Conflicting replies with the same sequence"
            return
        received[seq] = payload
        ack = {"time": now().strftime("%Y-%m-%d %H:%M:%S"), "items": [{"kind": "task", "id": task_id, "seq": seq}]}
        # Matching reply is durably saved above before its business ACK is sent.
        record("ack_intent", payload=ack)
        info = client.publish(base + "/ack", json.dumps(ack), qos=1, retain=False)
        pending[info.mid] = "business_ack"
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            state["failure"] = "Could not send business ACK"
        if payload.get("state") in {"succeeded", "rejected", "failed", "expired", "uncertain"}:
            if state["terminal"] is None or seq > state["terminal"]["seq"]:
                state["terminal"] = payload

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="tester-ec20test-xiaoming", protocol=mqtt.MQTTv5)
    client.username_pw_set("pingcode_demo_test", password)
    del password
    client.connect_timeout = 10
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.on_publish = on_publish
    record("environment", broker="120.55.75.51:1883", tls=False, mqtt_version=5,
           node="ec20test", client_id="tester-ec20test-xiaoming", task_id=task_id,
           scope="One node.describe query; no hardware operations")
    try:
        client.connect("120.55.75.51", 1883, keepalive=30)
        deadline = time.monotonic() + 12
        while not state["subscribed"] and not state["failure"] and time.monotonic() < deadline:
            code = client.loop(timeout=1)
            if code != mqtt.MQTT_ERR_SUCCESS:
                state["failure"] = "Connection loop error: " + str(code)
        if not state["subscribed"]:
            state["failure"] = state["failure"] or "Timed out waiting for subscription"
        if not state["failure"]:
            created = now()
            request = {"id": task_id, "action": "node.describe", "time": created.strftime("%Y-%m-%d %H:%M:%S"),
                       "expires_at": (created + timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S"), "params": {}}
            record("command_intent", topic=base + "/command", payload=request, qos=1, retain=False)
            info = client.publish(base + "/command", json.dumps(request), qos=1, retain=False)
            pending[info.mid] = "command"
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                state["failure"] = "Could not publish command"
            deadline = time.monotonic() + 15
            while not state["terminal"] and not state["failure"] and time.monotonic() < deadline:
                code = client.loop(timeout=1)
                if code != mqtt.MQTT_ERR_SUCCESS:
                    state["failure"] = "Connection loop error: " + str(code)
            if not state["terminal"]:
                state["failure"] = state["failure"] or "No matching terminal reply within 15 seconds"
            deadline = time.monotonic() + 3
            while pending and not state["failure"] and time.monotonic() < deadline:
                client.loop(timeout=0.5)
    except (OSError, mqtt.MQTTException) as error:
        state["failure"] = type(error).__name__ + ": " + str(error)
    finally:
        client.disconnect()
    result = {"task_id": task_id, "evidence_directory": str(directory), **state,
              "unconfirmed_publishes": list(pending.values())}
    record("summary", **result)
    (directory / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if state["terminal"] and state["terminal"]["state"] == "succeeded" and not state["failure"] else 1


if __name__ == "__main__":
    sys.exit(main())
