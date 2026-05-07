from gpiozero import PWMOutputDevice, OutputDevice
import time
import json
from pathlib import Path

motor_foward = OutputDevice(17)
motor_backward = OutputDevice(27)
motor_speed_controller = PWMOutputDevice(13)

config_path = Path(__file__).resolve().parent.parent / 'config' / 'config.json'
with config_path.open('r', encoding='utf-8') as config_file:
    config = json.load(config_file)
    fly_wheel_speed = config["motor_speeds"]["fly_wheel"]
    pan_servo_speed = config["motor_speeds"]["pan_servo"]
    tilt_servo_speed = config["motor_speeds"]["tilt_servo"]

    pan_servo_pin = config["pinouts"]["pan_servo"]
    tilt_servo_pin = config["pinouts"]["tilt_servo"]


def stop_fly_wheel_coast():
    motor_foward.off()
    motor_backward.off()
    motor_speed_controller.value = 0

def stop_fly_wheel_brake():
    motor_foward.on()
    motor_backward.on()
    motor_speed_controller.value = 0

def set_fly_wheel(speed, direction):
    if direction == 1:
        motor_foward.on()
        motor_backward.off()
    elif direction == 0:
        motor_foward.off()
        motor_backward.on()
    else:
        raise ValueError("Direction must be 0 (backward) or 1 (forward)")
    motor_speed_controller.value = speed


set_fly_wheel(fly_wheel_speed, 1)
time.sleep(5)
stop_fly_wheel_brake()