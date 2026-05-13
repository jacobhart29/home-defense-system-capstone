from gpiozero import PWMOutputDevice, OutputDevice, Servo
import time
import json
from pathlib import Path

motor_foward = OutputDevice(17)
motor_backward = OutputDevice(27)
motor_speed_controller = PWMOutputDevice(13)
step_pin = OutputDevice(6)
dir_pin = OutputDevice(5)

steps_per_rotation = 3200

config_path = Path(__file__).resolve().parent.parent / 'config' / 'config.json'
with config_path.open('r', encoding='utf-8') as config_file:
    config = json.load(config_file)
    fly_wheel_speed = config["motor_speeds"]["fly_wheel"]
    tilt_servo_pin = config["pinouts"]["tilt_servo"]

tilt_servo = Servo(tilt_servo_pin)

def stop_fly_wheel_coast():
    motor_foward.off()
    motor_backward.off()
    motor_speed_controller.value = 0

def stop_fly_wheel_brake():
    motor_foward.on()
    motor_backward.on()
    motor_speed_controller.value = 0

def set_fly_wheel(speed, direction):
    normalized_speed = speed / 100.0
    normalized_speed = max(0.0, min(1.0, normalized_speed))

    if direction == 1:
        motor_foward.on()
        motor_backward.off()
    elif direction == 0:
        motor_foward.off()
        motor_backward.on()
    else:
        raise ValueError("Direction must be 0 (backward) or 1 (forward)")
        
    motor_speed_controller.value = normalized_speed

def move_stepper(steps, direction):
    dir_pin.value = direction
    # We use a smaller delay because the steps are tiny
    for _ in range(steps):
        step_pin.on()
        time.sleep(0.0001) 
        step_pin.off()
        time.sleep(0.0001)

def run_motor_test():
    set_fly_wheel(fly_wheel_speed, 1)
    time.sleep(2)
    stop_fly_wheel_brake()

    move_stepper(steps_per_rotation, 1) 
    time.sleep(0.5)
    move_stepper(steps_per_rotation, 0) 

    test_angles = [0, -1, 1, 0] 
    for position in test_angles:
        tilt_servo.value = position
        time.sleep(1)

if __name__ == "__main__":
    try:
        run_motor_test()
    except KeyboardInterrupt:
        pass
    finally:
        stop_fly_wheel_coast()