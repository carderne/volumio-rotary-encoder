#!/usr/bin/env python3

# Modified from this gist:
# https://gist.github.com/savetheclocktower/9b5f67c20f6c04e65ed88f2e594d43c1

"""
The daemon responsible for changing the volume in response to a turn or press
of the volume knob.

The volume knob is a rotary encoder. It turns infinitely in either direction.
Turning it to the right will increase the volume; turning it to the left will
decrease the volume. The knob can also be pressed like a button in order to
turn muting on or off.

The knob uses two GPIO pins and we need some extra logic to decode it. The
button we can just treat like an ordinary button. Rather than poll
constantly, we use threads and interrupts to listen on all three pins in one
script.
"""

import signal
import subprocess
import sys
import threading
from queue import Queue

from RPi import GPIO

# The rotary and switch pins that the encoder uses (BCM numbering).
GPIO_A = 27
GPIO_B = 22
GPIO_BUTTON = 17

# The minimum and maximum volumes, and increment.
MIN = 0
MAX = 100
INCREMENT = 1

# When the knob is turned, the callback happens in a separate thread.
# We'll use a queue to enforce FIFO. When we put something in the queue,
# we'll use an event to signal to the main thread that there's something.
QUEUE = Queue()
EVENT = threading.Event()


class RotaryEncoder:
    """
    A class to decode mechanical rotary encoder pulses.
    """

    def __init__(self, callback=None, button_callback=None):
        """
        Instatiate the class with the two callbacks.

        The callback receives one argument: a `delta` that will be either 1 or -1.
        """

        self.last_gpio = None
        self.callback = callback
        self.button_callback = button_callback

        self.levA = 0
        self.levB = 0

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GPIO_A, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(GPIO_B, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(GPIO_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        GPIO.add_event_detect(GPIO_A, GPIO.BOTH, self._callback)
        GPIO.add_event_detect(GPIO_B, GPIO.BOTH, self._callback)
        GPIO.add_event_detect(
            GPIO_BUTTON, GPIO.FALLING, self._button_callback, bouncetime=500
        )

    def _button_callback(self, channel):
        self.button_callback(GPIO.input(channel))

    def _callback(self, channel):
        level = GPIO.input(channel)
        if channel == GPIO_A:
            self.levA = level
        else:
            self.levB = level

        # Debounce.
        if channel == self.last_gpio:
            return

        # If A was the most recent pin set high, it'll be forward
        # if B was the most recent pin set high, it'll be reverse.
        self.last_gpio = channel
        if channel == GPIO_A and level == 1:
            if self.levB == 1:
                self.callback(1)
        elif channel == GPIO_B and level == 1:
            if self.levA == 1:
                self.callback(-1)


def clamp(v):
    return max(min(MAX, v), MIN)


def volumio(cmd):
    subprocess.call(["volumio", "volume", str(cmd)])


def on_press(value):
    volumio("toggle")
    EVENT.set()


def on_turn(delta):
    QUEUE.put(delta)
    EVENT.set()


def consume_queue():
    while not QUEUE.empty():
        delta = QUEUE.get()
        handle_delta(delta)


def handle_delta(delta):
    if delta == 1:
        volumio("plus")
    else:
        volumio("minus")


def on_exit(a, b):
    print("Exiting...")
    GPIO.remove_event_detect(GPIO_A)
    GPIO.remove_event_detect(GPIO_B)
    GPIO.remove_event_detect(GPIO_BUTTON)
    GPIO.cleanup()
    sys.exit(0)


if __name__ == "__main__":
    encoder = RotaryEncoder(callback=on_turn, button_callback=on_press)
    signal.signal(signal.SIGINT, on_exit)
    while True:
        EVENT.wait(1200)
        consume_queue()
        EVENT.clear()
