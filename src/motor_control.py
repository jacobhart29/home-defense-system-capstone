import RPi.GPIO as GPIO
import time
import json
from pathlib import Path

config_path = Path(__file__).resolve().parent.parent / 'config' / 'config.json'
with config_path.open('r', encoding='utf-8') as config_file:
    config = json.load(config_file)
    fly_wheel_speed = config["motor_speeds"]["fly_wheel"]
    pan_servo_speed = config["motor_speeds"]["pan_servo"]
    tilt_servo_speed = config["motor_speeds"]["tilt_servo"]

    fly_wheel_pin = config["pinouts"]["fly_wheel"]
    pan_servo_pin = config["pinouts"]["pan_servo"]
    tilt_servo_pin = config["pinouts"]["tilt_servo"]
