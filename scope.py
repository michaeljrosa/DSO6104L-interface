#!/usr/bin/env python3

import socket   
from sys import exit  
from sys import maxsize
from time import sleep
import struct

import RPi.GPIO as GPIO
from RPLCD.gpio import CharLCD

import spidev

from gpiozero import Button
from gpiozero import DigitalInputDevice
from gpiozero import DigitalOutputDevice
from gpiozero import PWMOutputDevice
    

def pwm_backlight(f):
    print("backlight:", f)
    #if (bklt_fault.value == False):
        #bklt_en.off()
    #else:
        #write error message to scope


def disable_backlight():
    bklt_en.off()
    #write message to scope

def enable_power():
    if (pwr_fault.value == False):
        pwr_en.on()
    #else:
        #write error message to scope

def disable_power():
    pwr_en.off()
    #write message to scope
    
def autoscale():
    cmd = b':AUTOSCALE\r\n'
    Sock.sendall(cmd)

def print_reply():
    reply = Sock.recv(4096)
    print(reply)

def get_reply():
    reply = Sock.recv(4096)

# Set up socket to scope
remote_ip = "169.254.254.254"
port = 5024

#create an AF_INET, STREAM socket (TCP)
Sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#NODELAY turns of Nagle improves chatty performance
Sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 0)

if maxsize > 2**32:
  time = struct.pack(str("ll"), int(1), int(0))
else:
  time = struct.pack(str("ii"), int(1), int(0))
Sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, time)

#Connect to remote server
while True:
    try:
        print("Attempting to connect")
        Sock.connect((remote_ip , port))
        break
    except OSError:
        print("Unable to connect, trying again in 30s")
        sleep(30)
        
print ('Socket Connected to ip ' + remote_ip)
print_reply()
get_reply()
get_reply()

# Set up LCD
lcd = CharLCD(
    pin_rs=17, pin_rw=18, pin_e=12, pins_data=[27, 22, 23, 24],
    cols=16, rows=2,
    numbering_mode=GPIO.BCM)
bklt_en = PWMOutputDevice(2)

#bklt_fault = DigitalInputDevice(4, pull_up=True)
#bklt_fault.when_activated = disable_backlight

# Set up SPI and interrupt pins
spi = spidev.SpiDev()
cs2 = DigitalOutputDevice(25, active_high=False)

interrupt1 = DigitalInputDevice(13)
interrupt2 = DigitalInputDevice(19)
interrupt3 = DigitalInputDevice(16)
interrupt4 = DigitalInputDevice(26)
interrupt5 = DigitalInputDevice(20)
interrupt6 = DigitalInputDevice(21)

# Set up other I/O
pwr_en = DigitalOutputDevice(5)
pwr_fault = DigitalInputDevice(6, pull_up=True)
pwr_fault.when_activated = disable_power

autoscale_btn = Button(4, pull_up=True, bounce_time=0.2)
autoscale_btn.when_activated = autoscale

    
def main(): 
    # Turn the power on and write splash message
    pwm_backlight(0.5)
    enable_power()
    
    lcd.clear()
    lcd.write_string("EPM Lab DSO6104L")
    
    cmd = b'*IDN?\r\n'
    Sock.sendall(cmd)
    print_reply()
    print_reply()
 
    try:
        while True:
            pass
    except:
        Sock.close()
        GPIO.cleanup()
        exit()

if __name__ == "__main__":
    main()