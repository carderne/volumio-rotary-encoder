#!/usr/bin/env python3

# From here: https://gist.github.com/savetheclocktower/9b5f67c20f6c04e65ed88f2e594d43c1

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

# The two pins that the encoder uses (BCM numbering).
GPIO_A = 6
GPIO_B = 13

# The pin that the knob's button is hooked up to.
GPIO_BUTTON = 5

# The minimum and maximum volumes, and increment.
MIN = 0
MAX = 100
INCREMENT = 1

# When the knob is turned, the callback happens in a separate thread. If
# those turn callbacks fire erratically or out of order, we'll get confused
# about which direction the knob is being turned, so we'll use a queue to
# enforce FIFO. The callback will push onto a queue, and all the actual
# volume-changing will happen in the main thread.
QUEUE = Queue()

# When we put something in the queue, we'll use an event to signal to the
# main thread that there's something in there. Then the main thread will
# process the queue and reset the event. If the knob is turned very quickly,
# this event loop will fall behind, but that's OK because it consumes the
# queue completely each time through the loop, so it's guaranteed to catch up.
EVENT = threading.Event()


class RotaryEncoder:
    """
    A class to decode mechanical rotary encoder pulses.

    Ported to RPi.GPIO from the pigpio sample here:
    http://abyz.co.uk/rpi/pigpio/examples.html
    """

    def __init__(
        self, gpioA, gpioB, callback=None, buttonPin=None, buttonCallback=None
    ):
        """
        Instantiate the class. Takes three arguments: the two pin numbers to
        which the rotary encoder is connected, plus a callback to run when the
        switch is turned.

        The callback receives one argument: a `delta` that will be either 1 or -1.
        One of them means that the dial is being turned to the right; the other
        means that the dial is being turned to the left. I'll be damned if I know
        yet which one is which.
        """

        self.lastGpio = None
        self.gpioA = gpioA
        self.gpioB = gpioB
        self.callback = callback

        self.gpioButton = buttonPin
        self.buttonCallback = buttonCallback

        self.levA = 0
        self.levB = 0

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpioA, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.gpioB, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        GPIO.add_event_detect(self.gpioA, GPIO.BOTH, self._callback)
        GPIO.add_event_detect(self.gpioB, GPIO.BOTH, self._callback)

        if self.gpioButton:
            GPIO.setup(self.gpioButton, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                self.gpioButton, GPIO.FALLING, self._buttonCallback, bouncetime=500
            )

    def destroy(self):
        GPIO.remove_event_detect(self.gpioA)
        GPIO.remove_event_detect(self.gpioB)
        GPIO.cleanup()

    def _buttonCallback(self, channel):
        self.buttonCallback(GPIO.input(channel))

    def _callback(self, channel):
        level = GPIO.input(channel)
        if channel == self.gpioA:
            self.levA = level
        else:
            self.levB = level

        # Debounce.
        if channel == self.lastGpio:
            return

        # When both inputs are at 1, we'll fire a callback. If A was the most
        # recent pin set high, it'll be forward, and if B was the most recent pin
        # set high, it'll be reverse.
        self.lastGpio = channel
        if channel == self.gpioA and level == 1:
            if self.levB == 1:
                self.callback(1)
        elif channel == self.gpioB and level == 1:
            if self.levA == 1:
                self.callback(-1)


class VolumeError(Exception):
    pass


class Volume:
    """
    A wrapper API for interacting with the volume settings on the RPi.
    """

    def __init__(self):
        self.last_volume = MIN
        self._sync()

    def up(self):
        self.set_volume(self.volume + INCREMENT)

    def down(self):
        self.set_volume(self.volume - INCREMENT)

    def set_volume(self, v):
        self.volume = self.clamp(v)
        self._sync(self.volume)
        self.volumio(self.volume)

    def toggle(self):
        self.volumio("toggle")

    def _sync(self, v=None):
        if not v:
            v = int(subprocess.check_output(["volumio", "volume"]).strip())
        self.volume = v

    def clamp(self, v):
        return max(min(MAX, v), MIN)

    def volumio(self, cmd):
        subprocess.call(["volumio", "volume", str(cmd)])


if __name__ == "__main__":
    v = Volume()

    def on_press(value):
        v.toggle()
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
            v.up()
        else:
            v.down()

    def on_exit(a, b):
        print("Exiting...")
        encoder.destroy()
        sys.exit(0)

    encoder = RotaryEncoder(
        GPIO_A, GPIO_B, callback=on_turn, buttonPin=GPIO_BUTTON, buttonCallback=on_press
    )
    signal.signal(signal.SIGINT, on_exit)

    while True:
        EVENT.wait(1200)
        consume_queue()
        EVENT.clear()
