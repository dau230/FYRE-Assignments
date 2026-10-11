# Team Member Names: Josh, Daniel, Ts
# Purpose of Code: Toggle Rotation of a servo based on a switch input
# Date started: 9/16/2026
# Date of Last Update: 9/16/2026
# Explination of AI: We used AI to write the code and accomedate for wiring mistakes after correcting them. 

# AI prompt 1: I have an Arduino Nano esp32 so refer to the documentation. I am coding in micro-phython. I want to program a servo that will rotate based on a switch sensor. I want the switch to alternate between 0 and 180 degrees based on how many times it is pressed.the switch is a momentary contact switch so when it is only TRUE when the switch is depressed and FALSE when the switch is releasd. We want this switch to control a togggle variable where 1 press toggles the variable to true and another press after that will toggle the variable to false. When this toggle variable is true, we want the servo motor to rotate 180 degrees. When the servo motor is false, we want it to rotate another 180 degrees to reset back to the 0 degree position. i Count the number of times the switch is pressed if it is an odd integer set the position to 0 degrees if it is even set it to 180 degrees. \Ex. the switch has been pressed one time the position is 0 if it is pressed for the 2nd time the position is 180 and for the 3rd complete time it is pressed it returns to 0 degrees and so on. The switch is connected to the pin number D2 GPI105. The servo is connected to GPI 014 A7 D24. The servo takes PWM.

# AI prompt 2: add a print statement in the while true loop that prints every second what is stored in each varaible.

# AI prompt 3: can you set the servo pin to digital output?

from machine import Pin, PWM
from time import sleep_ms

# -------------------------
# Pin setup
# -------------------------

SWITCH_PIN = 5       # D2 = GPIO5
SERVO_PIN = 1       # D24 / A7 = GPIO14

# Switch is a digital input
switch = Pin(SWITCH_PIN, Pin.IN, Pin.PULL_UP)

# Servo pin is a digital output controlled by PWM
servo_pin = Pin(SERVO_PIN, Pin.OUT)

# PWM controls the servo pin
servo = PWM(servo_pin)
servo.freq(50)       # 50 Hz for standard servo


# -------------------------
# Servo function
# -------------------------

def servo_angle(angle):

    # 50 Hz = 20 ms period
    # Typical servo:
    # 0 degrees   = ~0.5 ms
    # 180 degrees = ~2.5 ms

    min_duty = 1638
    max_duty = 8192

    duty = min_duty + int((angle / 180) * (max_duty - min_duty))

    servo.duty_u16(duty)


# -------------------------
# Initial servo position
# -------------------------

servo_angle(0)


# -------------------------
# Toggle variables
# -------------------------

toggle = False
previous_switch = False
servo_position = 0

# Timer for status printing
print_timer = 0


# -------------------------
# Main loop
# -------------------------

while True:

    # With PULL_UP:
    # Released = 1
    # Pressed = 0

    pressed = not switch.value()

    # Detect a NEW press
    if pressed and not previous_switch:

        # Toggle between False and True
        toggle = not toggle

        if toggle:
            servo_position = 180
            servo_angle(180)
        else:
            servo_position = 0
            servo_angle(0)

        print("Press detected")
        print("Toggle:", toggle)

    # Store current switch state
    previous_switch = pressed


    # -------------------------
    # Print variables
    # once per second
    # -------------------------

    print_timer += 20

    if print_timer >= 1000:

        print_timer = 0

        print("-------------------------")
        print("switch.value():", switch.value())
        print("pressed:", pressed)
        print("previous_switch:", previous_switch)
        print("toggle:", toggle)
        print("servo_position:", servo_position)
        print("-------------------------")


    # Loop delay
    sleep_ms(20)
