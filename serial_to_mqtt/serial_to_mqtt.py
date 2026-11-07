#!/usr/bin/env python3
"""
serial_to_mqtt.py

Reads JSON sensor lines from the ESP32-C3 ESP-NOW receiver (connected via
USB serial) and publishes each value to MQTT topics that MMM-MQTT can
subscribe to.

Expected input from the receiver's serial output (one JSON object per line):
    {"id":"bme280","temp_f":72.14,"humidity":41.2,"pressure":1013.2}
    {"id":"am2301b","temp_f":71.80,"humidity":39.5}
Status/error lines from the receiver (e.g. {"status":"ready"}) are logged
and ignored -- they don't get published to MQTT.

Published MQTT topics (Fahrenheit, plain number payloads):
    sensors/bme280/temperature
    sensors/bme280/humidity
    sensors/bme280/pressure
    sensors/am2301b/temperature
    sensors/am2301b/humidity

Settings come from environment variables (see mqtt.env.example).
"""

import json
import logging
import os
import time

import serial
import paho.mqtt.client as mqtt

# ---- Configuration ----
SERIAL_PORT = os.environ.get("SERIAL_PORT", "/dev/ttyACM0")
BAUD_RATE = int(os.environ.get("BAUD_RATE", "115200"))

MQTT_BROKER = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
TOPIC_PREFIX = os.environ.get("TOPIC_PREFIX", "sensors")  # topics: <prefix>/<id>/<field>

RECONNECT_DELAY_SECONDS = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("serial_to_mqtt")


def build_mqtt_client():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            log.info("Connected to MQTT broker %s:%s", MQTT_BROKER, MQTT_PORT)
        else:
            log.error("MQTT connect failed, return code %s", rc)

    def on_disconnect(client, userdata, rc):
        log.warning("Disconnected from MQTT broker (rc=%s)", rc)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    client.reconnect_delay_set(min_delay=1, max_delay=60)
    client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)  # keeps retrying if the broker is not up yet
    client.loop_start()  # runs MQTT network loop in a background thread,
                         # handles automatic reconnects
    return client


def publish_reading(client, reading):
    """
    reading: dict parsed from one JSON line, e.g.
        {"id": "bme280", "temp_f": 72.14, "humidity": 41.2, "pressure": 1013.2}
    """
    sensor_id = reading.get("id")
    if not sensor_id:
        return  # not a sensor reading line (e.g. a status/error line)

    field_map = {
        "temp_f": "temperature",
        "humidity": "humidity",
        "pressure": "pressure",
    }

    for json_key, topic_field in field_map.items():
        if json_key in reading:
            topic = f"{TOPIC_PREFIX}/{sensor_id}/{topic_field}"
            payload = str(reading[json_key])
            result = client.publish(topic, payload, retain=True)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                log.warning("Publish failed for %s: rc=%s", topic, result.rc)
            else:
                log.debug("Published %s = %s", topic, payload)


def open_serial():
    while True:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            log.info("Opened serial port %s at %d baud", SERIAL_PORT, BAUD_RATE)
            return ser
        except serial.SerialException as e:
            log.error("Could not open serial port %s: %s", SERIAL_PORT, e)
            log.info("Retrying in %d seconds...", RECONNECT_DELAY_SECONDS)
            time.sleep(RECONNECT_DELAY_SECONDS)


def main():
    mqtt_client = build_mqtt_client()
    ser = open_serial()

    log.info("Listening for sensor readings...")

    while True:
        try:
            raw_line = ser.readline()
            if not raw_line:
                continue  # timeout with no data, loop again

            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            try:
                reading = json.loads(line)
            except json.JSONDecodeError:
                log.warning("Skipping unparseable line: %r", line)
                continue

            if "error" in reading:
                log.warning("Receiver reported error: %s", reading)
                continue

            if "status" in reading:
                log.info("Receiver status: %s", reading)
                continue

            publish_reading(mqtt_client, reading)
            log.info("Reading: %s", reading)

        except serial.SerialException as e:
            log.error("Serial error: %s -- reconnecting...", e)
            try:
                ser.close()
            except Exception:
                pass
            ser = open_serial()

        except KeyboardInterrupt:
            log.info("Shutting down.")
            break

    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    ser.close()


if __name__ == "__main__":
    main()
