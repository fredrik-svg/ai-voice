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
        self._running = False
        self._thread = None

    def on_pressed(self, cb): self._pressed_cb = cb
    def on_released(self, cb): self._released_cb = cb

    def start(self):
        if GPIO is None:
            print("[gpio] RPi.GPIO not available; simulating button (press Enter)")
            threading.Thread(target=self._simulate, daemon=True).start()
            return
        GPIO.setmode(GPIO.BCM)
        # Configure internal pull resistor for reliable readings
        pud = GPIO.PUD_UP if self.pull_up else GPIO.PUD_DOWN
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=pud)
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def _poll(self):
        """Poll GPIO pin for button state changes."""
        # Wait briefly to ensure stable initial reading
        time.sleep(0.01)
        last_state = GPIO.input(self.pin)
        while self._running:
            state = GPIO.input(self.pin)
            # Detect press: if pull_up=True, button pressed means LOW (False)
            # if pull_up=False, button pressed means HIGH (True)
            if state != last_state:
                time.sleep(0.05)  # Debounce delay
                state = GPIO.input(self.pin)  # Re-read after debounce
                if state != last_state:
                    if self.pull_up and not state:  # Pull-up: press = LOW
                        if self._pressed_cb:
                            self._pressed_cb()
                    elif not self.pull_up and state:  # Pull-down: press = HIGH
                        if self._pressed_cb:
                            self._pressed_cb()
                    elif self.pull_up and state:  # Pull-up: release = HIGH
                        if self._released_cb:
                            self._released_cb()
                    elif not self.pull_up and not state:  # Pull-down: release = LOW
                        if self._released_cb:
                            self._released_cb()
                    last_state = state
            time.sleep(0.01)  # Poll interval

    def stop(self):
        """Clean up GPIO resources."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if GPIO is not None:
            try:
                GPIO.cleanup(self.pin)
            except Exception:
                pass  # Ignore cleanup errors

    def _simulate(self):
        while True:
            input()
            if self._pressed_cb: self._pressed_cb()
