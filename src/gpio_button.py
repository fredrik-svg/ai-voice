import threading, time

try:
    import RPi.GPIO as GPIO
except Exception:
    GPIO = None

class Button:
    def __init__(self, pin: int, pull_up: bool = True):
        self.pin = pin
        self.pull_up = pull_up
        self._pressed_cb = None
        self._released_cb = None

    def on_pressed(self, cb): self._pressed_cb = cb
    def on_released(self, cb): self._released_cb = cb

    def start(self):
        if GPIO is None:
            print("[gpio] RPi.GPIO not available; simulating button (press Enter)")
            threading.Thread(target=self._simulate, daemon=True).start()
            return
        GPIO.setmode(GPIO.BCM)
        pud = GPIO.PUD_UP if self.pull_up else GPIO.PUD_DOWN
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=pud)
        edge = GPIO.FALLING if self.pull_up else GPIO.RISING
        # Remove any existing event detection before adding new one
        try:
            GPIO.remove_event_detect(self.pin)
        except Exception:
            pass  # Ignore if no event detection exists
        GPIO.add_event_detect(self.pin, edge, callback=self._edge, bouncetime=50)

    def _edge(self, channel):
        # Simple toggle: press triggers pressed; release not detected without state tracking.
        if self._pressed_cb:
            self._pressed_cb()

    def stop(self):
        """Clean up GPIO resources."""
        if GPIO is not None:
            try:
                GPIO.remove_event_detect(self.pin)
                GPIO.cleanup(self.pin)
            except Exception:
                pass  # Ignore cleanup errors

    def _simulate(self):
        while True:
            input()
            if self._pressed_cb: self._pressed_cb()
