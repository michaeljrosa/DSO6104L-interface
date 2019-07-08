#!/usr/bin/env python3

from subprocess import check_call
from time import sleep
from gpiozero import Button
import RPi.GPIO as GPIO

def shutdown():
    GPIO.cleanup()
    check_call(['sudo', 'poweroff'])
    exit()
    
pwr_btn = Button(3, pull_up=True, bounce_time=0.2, hold_time=2)
pwr_btn.when_held = shutdown

while True:
    pass