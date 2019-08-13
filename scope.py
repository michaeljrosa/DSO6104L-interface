#!/usr/bin/env python3

import socket
from subprocess import check_call
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


IOCON_INITIAL = 0x0A

IODIRA   = 0x00
IPOLA    = 0x01
GPINTENA = 0x02
DEFVALA  = 0x03
INTCONA  = 0x04
IOCON    = 0x05
GPPUA    = 0x06
INTFA    = 0x07
INTCAPA  = 0x08
GPIOA    = 0x09
OLATA    = 0x0A

IODIRB   = 0x10
IPOLB    = 0x11
GPINTENB = 0x12
DEFVALB  = 0x13
INTCONB  = 0x14
GPPUB    = 0x16
INTFB    = 0X17
INTCAPB  = 0x18
GPIOB    = 0x19
OLATB    = 0x1A
    
    
def shutdown():
    GPIO.cleanup()
    check_call(['sudo', 'poweroff'])
    exit()
    
def disable_backlight():
    bklt_en.off()
    print("backlight disabled")
    #write message to scope
    
def pwm_backlight(f):
    if (bklt_fault.value == False):
        bklt_en.on()
        bklt_en.value = f
        print("backlight:", f)
    else:
        disable_backlight()

def disable_power():
    pwr_en.off()
    print("power disabled")
    #write message to scope
    
def enable_power():
    if (pwr_fault.value == False):
        pwr_en.on()
        print("power enabled")
    else:
        disable_power()

def print_reply():
    reply = Sock.recv(4096)
    print(reply)

def get_reply():
    reply = Sock.recv(4096)
    
        
def autoscale():
    cmd = b':AUTOSCALE\r\n'
    Sock.sendall(cmd)

# configure shutdown button
#pwr_btn = Button(3, pull_up=True, bounce_time=0.2, hold_time=2)
#pwr_btn.when_held = shutdown

# Set board power
pwr_en = DigitalOutputDevice(5)
pwr_fault = DigitalInputDevice(6, pull_up=True)
pwr_fault.when_activated = disable_power

enable_power()

# Set up SPI and interrupt pins
spi = spidev.SpiDev()
cs2 = DigitalOutputDevice(12, active_high=False)
SPI_WRITE = 0x40
SPI_READ = 0x41
SPI_MODE = 0b00
SPI_RATE = 1000000

interrupt1 = DigitalInputDevice(13)
interrupt2 = DigitalInputDevice(16)
#interrupt3 = DigitalInputDevice(19)
spi_reset = DigitalOutputDevice(19, active_high=False)
interrupt4 = DigitalInputDevice(20)
interrupt5 = DigitalInputDevice(26)
interrupt6 = DigitalInputDevice(21)

# Set up LCD
lcd = CharLCD(
    pin_rs=25, pin_rw=24, pin_e=22, pins_data=[23, 27, 17, 18],
    cols=20, rows=4,
    numbering_mode=GPIO.BCM)
bklt_en = PWMOutputDevice(4)

bklt_fault = DigitalInputDevice(2, pull_up=True)
bklt_fault.when_activated = disable_backlight
bklt_en.on()

"""
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
        
        lcd.clear()
        lcd.write_string("Trying to connect...")
        lcd.write_string("IP: " + remote_ip + '\r\n')
        lcd.write_string("Port: " + str(port) + '\n')
        
        Sock.connect((remote_ip , port))
        break
    
    except OSError:
        print("Unable to connect, trying again in 30s")
        
        lcd.clear()
        lcd.write_string("Unable to connect...\r\n")
        lcd.write_string("Trying again in ")
        
        for i in range(1, 30):
            lcd.cursor_pos = (1,16)
            lcd.write_string(str(30-i) + "s ")
            sleep(1)
        
print ('Socket Connected to ip ' + remote_ip)

lcd.clear()
lcd.write_string("Connected!")
sleep(1)

print_reply()
"""

def init_spi():
    spi_reset.on()
    sleep(0.001)
    spi_reset.off()
    
    #buttons
    spi.open(0, 0)
    spi.mode = SPI_MODE
    spi.max_speed_hz = SPI_RATE
    
    # there could be a problem with this w/o hardware reset
    to_send = [SPI_WRITE, IOCON_INITIAL, 0xA3]   # set up IOCON resgister
    cs2.on()
    spi.xfer2(to_send)
    cs2.off()
    
    to_send = [SPI_WRITE, IODIRA, 0xC0]   # configure columns as outputs
    cs2.on()
    spi.xfer2(to_send)
    cs2.off()
    
    to_send = [SPI_WRITE, OLATA, 0x3F]   # set columns high
    cs2.on()
    spi.xfer2(to_send)
    cs2.off()
    
    to_send = [SPI_WRITE, IPOLB, 0xFF]   # invert the logic level of the row inputs
    cs2.on()
    spi.xfer2(to_send)
    cs2.off()
    
    to_send = [SPI_WRITE, GPINTENB, 0x3F]   # enable interrupts for rows
    cs2.on()
    spi.xfer2(to_send)
    cs2.off()
    
    to_send = [SPI_WRITE, GPPUB, 0xFF]   # enable pullups for rows
    cs2.on()
    spi.xfer2(to_send)
    cs2.off()
    
    spi.close()
    

def main():
    init_spi()
    
    lcd.clear()
    #lcd.write_string("Use any control to\r\ncontinue")
    
    
    
    #cmd = b'*IDN?\r\n'
    #Sock.sendall(cmd)
    #print_reply()
    #print_reply()
 
    try:
        spi.open(0,0)
        spi.mode = SPI_MODE
        spi.max_speed_hz = SPI_RATE
        to_send = [SPI_WRITE, OLATA, 0x2F]  # write col2 low
        cs2.on()
        spi.xfer2(to_send)
        cs2.off()
        
        while True:
            to_send = [SPI_READ, GPIOB]   # read the rows
            cs2.on()
            spi.xfer2(to_send)
            resp = spi.readbytes(1)
            cs2.off()
            
            print(resp)
            
            lcd.cursor_pos = (0,0)
            lcd.write_string(str(resp))
            sleep(0.1)
        
        
    except:
        #Sock.close()
        spi.close()
        cs2.off()
        GPIO.cleanup()
        exit()

if __name__ == "__main__":
    main()