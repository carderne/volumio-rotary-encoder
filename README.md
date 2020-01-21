# volumio-rotary-encoder
Script and systemd service to add a physical volume/mute/pause knob (with a rotary encoder) to a Volumio-based system. My setup uses a KY-040 rotary encoder connected to a Raspberry Pi 4 with a HifiBerry Amp2.

## Usage
Make sure Python and [RPi](https://pypi.org/project/RPi.GPIO/) are installed. The latter is probably easier to install with `apt` than `pip`.

Then clone this repo:
```
git clone https://github.com/carderne/volumio-rotary-encoder.git
cd volumio-rotary-encoder
```

Edit the values for `GPIO_A`, `GPIO_B` and `GPIO_BUTTON` in `main.py` to the GPIO pins you connected the rotary encoder to (BCM numbering).

Then you can test the script as follows:
```
./main.py
```

Does it work? If so, register the systemd service:
```
sudo cp rotary-volume.service /etc/systemd/system/
sudo systemctl enable rotary-volume
sudo systemctl start rotary-volume
```

And (in theory) you should be all set!
