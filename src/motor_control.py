import RPi.GPIO as GPIO
import time
import json

with open('../config/config.json', 'r', encoding='utf-8') as config:
  fly_wheel_speed = config["motor_speeds"]["fly_wheel"]
  pan_servo_speed = config["motor_speeds"]["pan_servo"]
  tilt_servo_speed = config["motor_speeds"]["tilt_servo"]

  fly_wheel_pin = config["pinouts"]["fly_wheel"]
  pan_servo_pin = config["pinouts"]["pan_servo"]
  tilt_servo_pin = config["pinouts"]["tilt_servo"]
