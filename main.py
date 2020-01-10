#!/usr/bin/env python

# Copied from: https://forum.volumio.org/getting-rotary-encoder-working-t9690.html

from RPi import GPIO
from time import sleep
import subprocess

clk = 13
dt = 6
sw = 5

GPIO.setmode(GPIO.BCM)
GPIO.setup(clk, GPIO.IN)
GPIO.setup(dt, GPIO.IN)
GPIO.setup(sw, GPIO.IN)

clkLastState = GPIO.input(clk)
stopped = True

try:
    while True:
        clkState = GPIO.input(clk)
        if clkState != clkLastState:
            dtState = GPIO.input(dt)
            if dtState != clkState:
                subprocess.call(
                    [
                        "curl",
                        "http://localhost:3000/api/v1/commands?cmd=volume&volume=plus",
                    ]
                )
            else:
                subprocess.call(
                    [
                        "curl",
                        "http://localhost:3000/api/v1/commands?cmd=volume&volume=minus",
                    ]
                )
            clkState = GPIO.input(clk)
        # swState = GPIO.input(sw)
        # if swState == 1:
        #     if not stopped:
        #         subprocess.call(["curl", "stop"])
        #         stopped = True
        #     else:
        #         subprocess.call(["curl", "play"])
        #         stopped = False
        #     swState = GPIO.input(sw)
        #     sleep(0.2)
        clkLastState = clkState
        sleep(0.005)
finally:
    GPIO.cleanup()
