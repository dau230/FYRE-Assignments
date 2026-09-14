from machine import Pin, ADC
import time


# ============================================================
# USER SETTINGS
# ============================================================

# Light sensor threshold.
# If the light sensor reading is LESS than this value,
# the system is ENABLED.
#
# ESP32 ADC readings are typically 0-4095.
LIGHT_THRESHOLD = 2000

# Red LED flashing interval in milliseconds.
# Example: 500 = 0.5 seconds ON, 0.5 seconds OFF
FLASH_INTERVAL_MS = 500


# ============================================================
# PIN DEFINITIONS
# ============================================================

# Light sensor:
# Arduino A7 = D24 = GPIO14
LIGHT_SENSOR_PIN = 14

# Momentary contact switch:
# Arduino D12 = GPIO47
BUTTON_PIN = 47

# Green LED:
# Arduino D2 = GPIO5
GREEN_LED_PIN = 5

# Red LED:
# Arduino D3 = GPIO6
RED_LED_PIN = 6


# ============================================================
# EXTERNAL / PROGRAM STATE VARIABLES
# ============================================================

# This Boolean becomes TRUE when the button is pressed
# while the system is enabled.
triggered = False

# Current system enabled/disabled state
system_enabled = False

# Current state of the flashing red LED
red_led_state = False

# Used to control the flashing without stopping the
# light sensor from being checked.
last_flash_time = time.ticks_ms()

# Used to print status once per second
last_report_time = time.ticks_ms()


# ============================================================
# HARDWARE SETUP
# ============================================================

# Analog light sensor
light_sensor = ADC(Pin(LIGHT_SENSOR_PIN))

# Digital momentary switch
#
# No internal pull-up/down is enabled because the switch
# is assumed to provide a definite TRUE/FALSE signal.
button = Pin(BUTTON_PIN, Pin.IN)

# LEDs
green_led = Pin(GREEN_LED_PIN, Pin.OUT)
red_led = Pin(RED_LED_PIN, Pin.OUT)


# Make sure outputs start OFF
green_led.value(0)
red_led.value(0)


# ============================================================
# MAIN LOOP
# ============================================================

while True:

    # --------------------------------------------------------
    # ALWAYS READ THE LIGHT SENSOR
    # --------------------------------------------------------

    light_value = light_sensor.read()

    # Determine whether the system should be enabled
    if light_value < LIGHT_THRESHOLD:
        system_enabled = True
    else:
        system_enabled = False


    # --------------------------------------------------------
    # SYSTEM ENABLED
    # --------------------------------------------------------

    if system_enabled:

        # Green LED ON
        green_led.value(1)

        # ----------------------------------------------------
        # CHECK MOMENTARY SWITCH
        # ----------------------------------------------------

        if button.value():
            triggered = True


        # ----------------------------------------------------
        # FLASH RED LED IF TRIGGERED
        # ----------------------------------------------------

        if triggered:

            current_time = time.ticks_ms()

            # Has the flash interval elapsed?
            if time.ticks_diff(current_time, last_flash_time) >= FLASH_INTERVAL_MS:

                # Toggle the red LED
                red_led_state = not red_led_state
                red_led.value(1 if red_led_state else 0)

                # Start timing the next interval
                last_flash_time = current_time

        else:
            # Not triggered, so red LED must remain OFF
            red_led_state = False
            red_led.value(0)

            # Reset flash timer
            last_flash_time = time.ticks_ms()


    # --------------------------------------------------------
    # SYSTEM DISABLED
    # --------------------------------------------------------

    else:

        # Green LED OFF
        green_led.value(0)

        # Red LED OFF
        red_led.value(0)

        # Reset the external Boolean
        triggered = False

        # Reset flashing state
        red_led_state = False

        # Reset flash timer
        last_flash_time = time.ticks_ms()


    # --------------------------------------------------------
    # STATUS REPORT - ONCE PER SECOND
    # --------------------------------------------------------

    current_time = time.ticks_ms()

    if time.ticks_diff(current_time, last_report_time) >= 1000:

        print("----------------------------------------")
        print("Light Sensor :", light_value)
        print("Threshold    :", LIGHT_THRESHOLD)
        print("System       :", "ENABLED" if system_enabled else "DISABLED")
        print("Button       :", "PRESSED" if button.value() else "NOT PRESSED")
        print("Triggered    :", triggered)
        print("Green LED    :", green_led.value())
        print("Red LED      :", red_led.value())
        print("----------------------------------------")

        last_report_time = current_time


    # Very short delay prevents the loop from running completely
    # flat-out while still checking the sensor very frequently.
    time.sleep_ms(10)
