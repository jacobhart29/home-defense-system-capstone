import motor_control
import time
from gpiozero import PWMOutputDevice, OutputDevice, Servo
import json
from pathlib import Path

config_path = Path(__file__).resolve().parent.parent / 'config' / 'config.json'
with config_path.open('r', encoding='utf-8') as config_file:
    config = json.load(config_file)
    buzzer_pin = config["pinouts"]["buzzer"]

buzzer = OutputDevice(buzzer_pin)

def error_buzzer(beeps):
    for _ in range(beeps):
        buzzer.on()
        time.sleep(0.2)  # Short beep duration
        buzzer.off()
        time.sleep(0.2)
     
# SELF TEST
motor_control.run_motor_test()

error_buzzer(5)