"""
Humidity-controlled vent system
Board:    Arduino Nano ESP32
Language: MicroPython (single file, runs fully offline)

Vent = DC motor + servo motor + external LED.
"""

from machine import Pin, ADC, PWM
import time

# =============================================================================
# GLOBAL CONSTANTS - PINS  (change pin numbers here only)
# =============================================================================
# Values are ESP32 GPIO numbers. The Arduino label is shown next to each one.
# Arduino label -> GPIO:  D2=5  D3=6  D4=7  D5=8  D6=9  D7=10  D8=17  D9=18
#                         D10=21 D11=38 D12=47 D13=48  A0=1 A1=2 A2=3 A3=4

POWER_BUTTON_DIGITAL_PIN_INPUT = 5            # D2  - toggles the whole system on/off
MANUAL_VENT_BUTTON_DIGITAL_PIN_INPUT = 6      # D3  - manually toggles the vent on/off
HUMIDITY_SENSOR_ANALOG_PIN_INPUT = 1          # A0  - humidity sensor analog output
VENT_DC_MOTOR_DIGITAL_PIN_OUTPUT = 7          # D4  - DC motor (drive through a transistor/MOSFET!)
EXTERNAL_LED_DIGITAL_PIN_OUTPUT = 8           # D5  - external LED (use a series resistor)
VENT_SERVO_MOTOR_DIGITAL_PWM_PIN_OUTPUT = 9   # D6  - servo signal wire (PWM on a digital pin)
ONBOARD_LED_DIGITAL_PIN_OUTPUT = 48           # D13 - Nano ESP32 built-in LED

# =============================================================================
# GLOBAL CONSTANTS - TUNABLE SETTINGS
# =============================================================================

# How far the servo rotates (in DEGREES) when the vent turns ON.
# OFF position is SERVO_OFF_POSITION_DEGREES, ON position is OFF + this amount.
# A standard hobby servo can only travel ~180 degrees (max value here is 180).
SERVO_ROTATION_AMOUNT_DEGREES = 90
SERVO_OFF_POSITION_DEGREES = 0

# Humidity threshold on the ADC scale 0 - 65535 (0 = 0 V, 65535 = ~3.3 V).
# The comparison that uses this value is in run_automatic_vent_logic().
HUMIDITY_MEASUREMENT_OUTPUT_THRESHOLD = 40000

# How long (seconds) the vent stays ON after humidity drops back below the threshold.
VENT_OFF_DEBOUNCE_TIME_SECONDS = 5

# External LED blink interval while the debounce timer is active (milliseconds).
DEBOUNCE_LED_BLINK_INTERVAL_MS = 500

# How often the status line is printed to the console (milliseconds).
STATUS_PRINT_INTERVAL_MS = 1000

# Button electrical settings.
# 1 = pin reads HIGH when pressed (button wired to 3.3 V, internal pull-down used).
# 0 = pin reads LOW when pressed (button wired to GND, internal pull-up used).
BUTTON_PRESSED_LOGIC_LEVEL = 1
BUTTON_SOFTWARE_DEBOUNCE_MS = 50   # ignores contact bounce of the physical switch

# Servo pulse settings (standard hobby servo: 50 Hz, 0.5 ms - 2.5 ms pulse).
SERVO_PWM_FREQUENCY_HZ = 50
SERVO_MIN_PULSE_WIDTH_US = 500
SERVO_MAX_PULSE_WIDTH_US = 2500
SERVO_MAX_ANGLE_DEGREES = 180

# Delay at the end of each main-loop pass (milliseconds).
MAIN_LOOP_DELAY_MS = 10

# =============================================================================
# HARDWARE SETUP
# =============================================================================

# Buttons: pull resistor chosen to match BUTTON_PRESSED_LOGIC_LEVEL.
_button_pull = Pin.PULL_DOWN if BUTTON_PRESSED_LOGIC_LEVEL == 1 else Pin.PULL_UP
power_button = Pin(POWER_BUTTON_DIGITAL_PIN_INPUT, Pin.IN, _button_pull)
manual_vent_button = Pin(MANUAL_VENT_BUTTON_DIGITAL_PIN_INPUT, Pin.IN, _button_pull)

# Humidity sensor: ADC with full 0 - ~3.3 V range.
humidity_adc = ADC(Pin(HUMIDITY_SENSOR_ANALOG_PIN_INPUT))
humidity_adc.atten(ADC.ATTN_11DB)

# Digital outputs.
dc_motor = Pin(VENT_DC_MOTOR_DIGITAL_PIN_OUTPUT, Pin.OUT)
external_led = Pin(EXTERNAL_LED_DIGITAL_PIN_OUTPUT, Pin.OUT)
onboard_led = Pin(ONBOARD_LED_DIGITAL_PIN_OUTPUT, Pin.OUT)

# Servo: PWM output at 50 Hz (duty is set later when an angle is commanded).
servo_pwm = PWM(Pin(VENT_SERVO_MOTOR_DIGITAL_PWM_PIN_OUTPUT), freq=SERVO_PWM_FREQUENCY_HZ, duty_u16=0)

# =============================================================================
# STATE VARIABLES (reset to defaults whenever the system is turned OFF)
# =============================================================================

system_is_on = False                 # True when the power button has turned the system on
vent_is_on = False                   # True when the vent is ON (motor + servo + LED)
manual_override_active = False       # True when the manual button turned the vent on (ignores humidity)
auto_vent_suppressed = False         # True after a manual OFF while humidity is still high;
                                     # blocks auto turn-on until humidity drops below threshold once
debounce_timer_active = False        # True while the vent is waiting to turn off after humidity dropped
debounce_timer_start_ms = 0          # time.ticks_ms() value when the debounce timer started
dc_motor_is_on = False               # Mirrors the DC motor output
servo_current_angle_degrees = SERVO_OFF_POSITION_DEGREES  # Last angle commanded to the servo
external_led_status = "OFF"          # "ON" (solid), "DEBOUNCE" (blinking) or "OFF"
external_led_is_lit = False          # Physical state of the external LED right now

# =============================================================================
# STATE VARIABLES (NOT reset when the system turns off)
# =============================================================================

latest_humidity_reading = 0          # Most recent raw ADC reading (0 - 65535); read every loop
last_status_print_ms = 0             # When the status line was last printed

# Button trackers. These follow the physical button, so they are intentionally NOT
# reset with the system (resetting could cause a phantom press if a button is held).
power_button_tracker = {"last_raw": False, "last_change_ms": 0, "stable": False}
manual_button_tracker = {"last_raw": False, "last_change_ms": 0, "stable": False}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def button_was_just_pressed(button_pin, tracker, now_ms):
    """Returns True once each time a button goes from released to pressed (debounced)."""
    raw_pressed = (button_pin.value() == BUTTON_PRESSED_LOGIC_LEVEL)

    # Restart the settling timer whenever the raw reading changes.
    if raw_pressed != tracker["last_raw"]:
        tracker["last_raw"] = raw_pressed
        tracker["last_change_ms"] = now_ms

    # Accept the new state only after it has been stable long enough.
    settled = time.ticks_diff(now_ms, tracker["last_change_ms"]) >= BUTTON_SOFTWARE_DEBOUNCE_MS
    if settled and raw_pressed != tracker["stable"]:
        tracker["stable"] = raw_pressed
        return raw_pressed   # True only on the press, not on the release

    return False


def set_servo_angle(angle_degrees):
    """Moves the servo to the requested angle (in degrees)."""
    global servo_current_angle_degrees

    # Keep the angle inside the servo's physical range.
    angle_degrees = max(0, min(SERVO_MAX_ANGLE_DEGREES, angle_degrees))

    # Convert angle -> pulse width (microseconds) -> 16-bit duty value.
    pulse_us = SERVO_MIN_PULSE_WIDTH_US + (
        angle_degrees / SERVO_MAX_ANGLE_DEGREES
    ) * (SERVO_MAX_PULSE_WIDTH_US - SERVO_MIN_PULSE_WIDTH_US)
    period_us = 1000000 / SERVO_PWM_FREQUENCY_HZ
    servo_pwm.duty_u16(int(pulse_us / period_us * 65535))

    servo_current_angle_degrees = angle_degrees


def set_vent_outputs(turn_on):
    """Sets the DC motor and servo for ON or OFF (the external LED is handled by update_external_led)."""
    global vent_is_on, dc_motor_is_on

    vent_is_on = turn_on
    dc_motor_is_on = turn_on
    dc_motor.value(1 if turn_on else 0)

    if turn_on:
        set_servo_angle(SERVO_OFF_POSITION_DEGREES + SERVO_ROTATION_AMOUNT_DEGREES)
    else:
        set_servo_angle(SERVO_OFF_POSITION_DEGREES)


def start_debounce_timer(now_ms):
    """Starts the delay that keeps the vent on after humidity drops."""
    global debounce_timer_active, debounce_timer_start_ms
    debounce_timer_active = True
    debounce_timer_start_ms = now_ms


def cancel_debounce_timer():
    """Stops the debounce timer without changing the vent."""
    global debounce_timer_active
    debounce_timer_active = False


def update_external_led(now_ms):
    """Sets the external LED: solid when vent ON, blinking during debounce, off otherwise."""
    global external_led_status, external_led_is_lit

    if debounce_timer_active:
        # Blink phase is derived from the time since the timer started (on, off, on, ...).
        blink_step = time.ticks_diff(now_ms, debounce_timer_start_ms) // DEBOUNCE_LED_BLINK_INTERVAL_MS
        external_led_is_lit = (blink_step % 2 == 0)
        external_led_status = "DEBOUNCE"
    elif vent_is_on:
        external_led_is_lit = True
        external_led_status = "ON"
    else:
        external_led_is_lit = False
        external_led_status = "OFF"

    external_led.value(1 if external_led_is_lit else 0)


def reset_state_variables(now_ms):
    """Puts every mutable state variable back to its default (vent OFF)."""
    global manual_override_active, auto_vent_suppressed

    manual_override_active = False
    auto_vent_suppressed = False
    cancel_debounce_timer()
    set_vent_outputs(False)
    update_external_led(now_ms)


def toggle_system(now_ms):
    """Flips the system on/off, updates the onboard LED, and resets state when turning off."""
    global system_is_on

    system_is_on = not system_is_on
    onboard_led.value(1 if system_is_on else 0)

    if not system_is_on:
        reset_state_variables(now_ms)


def handle_manual_vent_button(now_ms):
    """Manual button: vent ON -> instant OFF (skips debounce); vent OFF -> ON regardless of humidity."""
    global manual_override_active, auto_vent_suppressed

    cancel_debounce_timer()

    if vent_is_on:
        # Manual OFF: shut off immediately.
        manual_override_active = False
        set_vent_outputs(False)
        # If humidity is still high, stop the automatic logic from instantly re-starting the vent.
        if latest_humidity_reading > HUMIDITY_MEASUREMENT_OUTPUT_THRESHOLD:
            auto_vent_suppressed = True
    else:
        # Manual ON: humidity is ignored until the manual button turns the vent off.
        manual_override_active = True
        set_vent_outputs(True)

    update_external_led(now_ms)


def run_automatic_vent_logic(now_ms):
    """Humidity-driven vent control with the off-delay (debounce) timer."""
    global auto_vent_suppressed

    # A manual ON overrides humidity completely.
    if manual_override_active:
        return

    # ---- HUMIDITY THRESHOLD COMPARISON (adjust here if your sensor works the other way) ----
    # Currently: humidity is "high" when the reading EXCEEDS the threshold.
    # For a sensor whose output DROPS as humidity rises, change ">" to "<".
    humidity_is_high = latest_humidity_reading > HUMIDITY_MEASUREMENT_OUTPUT_THRESHOLD
    # -----------------------------------------------------------------------------------------

    # Humidity has cleared once, so a manual-off suppression can end.
    if not humidity_is_high:
        auto_vent_suppressed = False

    if humidity_is_high and not auto_vent_suppressed:
        # Humidity high: cancel any pending shut-off and make sure the vent is ON.
        cancel_debounce_timer()
        if not vent_is_on:
            set_vent_outputs(True)

    elif vent_is_on and not humidity_is_high:
        # Humidity dropped below the threshold: run the debounce timer, then turn off.
        if not debounce_timer_active:
            start_debounce_timer(now_ms)
        elif time.ticks_diff(now_ms, debounce_timer_start_ms) >= VENT_OFF_DEBOUNCE_TIME_SECONDS * 1000:
            cancel_debounce_timer()
            set_vent_outputs(False)


def print_status_if_due(now_ms):
    """Prints all mutable values once per second, whether the system is on or off."""
    global last_status_print_ms

    if time.ticks_diff(now_ms, last_status_print_ms) < STATUS_PRINT_INTERVAL_MS:
        return
    last_status_print_ms = now_ms

    # Seconds left on the debounce timer (0 when not running).
    if debounce_timer_active:
        remaining_ms = VENT_OFF_DEBOUNCE_TIME_SECONDS * 1000 - time.ticks_diff(now_ms, debounce_timer_start_ms)
        debounce_remaining_s = max(0, remaining_ms) / 1000
    else:
        debounce_remaining_s = 0

    print("System: {} | Onboard LED: {} | Vent: {} | Manual override: {}".format(
        "ON" if system_is_on else "OFF",
        "ON" if onboard_led.value() else "OFF",
        "ON" if vent_is_on else "OFF",
        manual_override_active))
    print("  Humidity reading: {} (threshold {}) | DC motor: {} | Servo angle: {} deg".format(
        latest_humidity_reading,
        HUMIDITY_MEASUREMENT_OUTPUT_THRESHOLD,
        "ON" if dc_motor_is_on else "OFF",
        servo_current_angle_degrees))
    print("  External LED: {} | Debounce active: {} ({:.1f}s left) | Auto suppressed: {}".format(
        external_led_status,
        debounce_timer_active,
        debounce_remaining_s,
        auto_vent_suppressed))


# =============================================================================
# STARTUP
# =============================================================================

# Start with the system off and the vent in its OFF position.
onboard_led.value(0)
reset_state_variables(time.ticks_ms())

# =============================================================================
# MAIN LOOP
# =============================================================================

while True:
    now = time.ticks_ms()

    # Read inputs every pass (the sensor is read even when the system is off, for the status print).
    latest_humidity_reading = humidity_adc.read_u16()
    power_pressed = button_was_just_pressed(power_button, power_button_tracker, now)
    manual_pressed = button_was_just_pressed(manual_vent_button, manual_button_tracker, now)

    # Power button always works.
    if power_pressed:
        toggle_system(now)

    # Everything else only runs while the system is on.
    if system_is_on:
        if manual_pressed:
            handle_manual_vent_button(now)
        run_automatic_vent_logic(now)
        update_external_led(now)

    # Status print always runs.
    print_status_if_due(now)

    time.sleep_ms(MAIN_LOOP_DELAY_MS)
