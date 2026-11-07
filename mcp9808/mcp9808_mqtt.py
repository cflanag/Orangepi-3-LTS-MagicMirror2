#!/usr/bin/env python3
import os
import time
from adafruit_extended_bus import ExtendedI2C as I2C
import adafruit_mcp9808
import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
TOPIC = os.environ.get("MQTT_TOPIC", "sensors/mcp9808/temperature")
INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "10"))
I2C_BUS = int(os.environ.get("I2C_BUS", "0"))  # /dev/i2c-0, see README step 6.1

i2c = I2C(I2C_BUS)
sensor = adafruit_mcp9808.MCP9808(i2c)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
if MQTT_USER:
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
client.reconnect_delay_set(min_delay=1, max_delay=60)
client.connect_async(MQTT_HOST, MQTT_PORT, 60)  # keeps retrying if the broker is not up yet
client.loop_start()

while True:
    temp_f = sensor.temperature * 9 / 5 + 32
    client.publish(TOPIC, round(temp_f, 1))
    time.sleep(INTERVAL_SECONDS)
