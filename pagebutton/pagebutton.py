#!/usr/bin/env python3
"""
Page-turn button for Orange Pi 3 LTS (Allwinner H6) using libgpiod v2.

Wiring: button between PD21 (wPi 13, GPIO117) and GND. The internal pull-up
is used, so the pin reads HIGH when idle and LOW when pressed.

The PD bank on the H6 has no interrupt support, so the pin is polled
instead of using edge events.
"""
import time
import urllib.request

import gpiod
from gpiod.line import Bias, Direction, Value

URL = "http://localhost:8080/api/notification/PAGE_INCREMENT"

# PD21 -> main pin controller (gpiochip1, 256 lines), offset 3*32 + 21 = 117
CHIP = "/dev/gpiochip1"
LINE = 117

POLL_INTERVAL = 0.01   # seconds between reads (100 Hz)
DEBOUNCE = 0.03        # pin must stay pressed this long to count
LOCKOUT = 0.5          # seconds between accepted presses


def send_page_increment():
    try:
        urllib.request.urlopen(URL, timeout=3).read()
        print("PAGE_INCREMENT sent")
    except Exception as e:
        print(f"Failed to send notification: {e}")


def main():
    settings = gpiod.LineSettings(
        direction=Direction.INPUT,
        bias=Bias.PULL_UP,
    )

    print(f"Watching {CHIP} line {LINE} (PD21)")
    last_press = 0.0
    was_pressed = False

    with gpiod.request_lines(
        CHIP,
        consumer="pagebutton",
        config={LINE: settings},
    ) as request:
        while True:
            pressed = request.get_value(LINE) == Value.INACTIVE  # LOW = pressed

            if pressed and not was_pressed:
                # Confirm it's a real press, not contact bounce or noise
                time.sleep(DEBOUNCE)
                if request.get_value(LINE) == Value.INACTIVE:
                    now = time.monotonic()
                    if now - last_press >= LOCKOUT:
                        last_press = now
                        send_page_increment()
                else:
                    pressed = False

            was_pressed = pressed
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
