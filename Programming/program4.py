from machine import Pin
from time import sleep

# ESP32 Pin connection
led = Pin(0, Pin.OUT)

# Blinking loop
while True:
    
    # Turn the LED on
    led.value(1)
    sleep(0.5)

    # Turn the LED off
    led.value(0)
    sleep(0.5)