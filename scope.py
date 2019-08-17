#!/usr/bin/env python3

import socket
from subprocess import check_call
from sys import exit  
from sys import maxsize
from time import sleep
from math import floor
import struct

import RPi.GPIO as GPIO
from RPLCD.gpio import CharLCD

import spidev

from gpiozero import Button
from gpiozero import DigitalInputDevice
from gpiozero import DigitalOutputDevice
from gpiozero import PWMOutputDevice


# Device register addresses
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

SPI_WRITE = 0x40
SPI_READ = 0x41
SPI_MODE = 0b00
SPI_RATE = 10000000   # hertz

DEBOUNCE = 0.035  # seconds

# SPI device 2, port A
C1 = 1<<5
C2 = 1<<4
C3 = 1<<3
C4 = 1<<2
C5 = 1<<1
C6 = 1<<0

# SPI device 2, port B
R1 = 1<<5
R2 = 1<<4
R3 = 1<<3
R4 = 1<<2
R5 = 1<<1
R6 = 1<<0


# SPI device 0, port A
A_CH2_OS = 1
B_CH2_OS = 0

A_CH1_OS = 2
B_CH1_OS = 3

A_CH1_SC = 4
B_CH1_SC = 5

A_CH2_SC = 7
B_CH2_SC = 6

# SPI device 0, port B
A_CH3_SC = 1
B_CH3_SC = 0

A_CH4_SC = 3
B_CH4_SC = 2

A_CH4_OS = 5
B_CH4_OS = 4

A_CH3_OS = 7
B_CH3_OS = 6


# SPI device 1, port A
A_HORIZ = 2
B_HORIZ = 3

A_DELAY = 4
B_DELAY = 5

A_SEL = 6
B_SEL = 7

#SPI device 1, port B
A_MATH_SC = 1
B_MATH_SC = 0

A_MATH_OS = 3
B_MATH_OS = 2

A_CURS = 4
B_CURS = 5

A_TRIG = 6
B_TRIG = 7


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

def init_spi():
    spi_reset.on()
    sleep(0.001)
    spi_reset.off()
    
    #buttons
    spi.open(0, 0)
    spi.mode = SPI_MODE
    spi.max_speed_hz = SPI_RATE
    
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
    
    
    # encoder bank 0
    spi.open(0, 0)
    spi.mode = SPI_MODE
    spi.max_speed_hz = SPI_RATE
    
    to_send = [SPI_WRITE, IOCON_INITIAL, 0xA2]
    spi.xfer2(to_send)
    
    to_send = [SPI_WRITE, GPINTENA, 0xFF]
    spi.xfer2(to_send)
    
    to_send = [SPI_WRITE, GPINTENB, 0xFF]
    spi.xfer2(to_send)
    
    spi.close()
    
    
    # encoder bank 1
    spi.open(0, 1)
    spi.mode = SPI_MODE
    spi.max_speed_hz = SPI_RATE
    
    to_send = [SPI_WRITE, IOCON_INITIAL, 0xA2]
    spi.xfer2(to_send)
    
    to_send = [SPI_WRITE, GPINTENA, 0xFC]
    spi.xfer2(to_send)
    
    to_send = [SPI_WRITE, GPINTENB, 0xFF]
    spi.xfer2(to_send)
    
    to_send = [SPI_WRITE, GPPUA, 0x03]
    spi.xfer2(to_send)
    
    spi.close()
    
    
def num_from_ascii(txt):
    sign = 1 if txt[0] == 43 else -1
    
    try:
        decimal = txt.index(b'.')
        mult = 10 ** max(0,decimal - 2)
        
    except ValueError:
        mult = 10 ** (len(txt)-2)
        pass
    
    num = 0
    for x in txt:
        if (x == 43 or x == 45 or x == 46):
            continue
        else:
            num += mult * (x-48)
            mult = mult / 10
    return num * sign
    
def cw_action_ch1_sc():
    cmd = b'CHAN1:SCAL?\r\n'
    Sock.sendall(cmd)
    sleep(0.1)
    
    reply = get_reply()
    reply = reply[::-1]
    reply = reply[4:]
    start = reply.index(b'\n')
    reply = reply[:start]
    reply = reply[::-1]
    
    num_end = reply.index(b'E')
    num = reply[:num_end]
    exp = reply[num_end+1:]
    
    num_conv = num_from_ascii(num)
    exp_conv = num_from_ascii(exp)
    
    # deal with probe attenuation factor here
    # fine adjustment?
    
    if (num_conv * 10 ** exp_conv < 5):
        if (num[1:2] == b'1'):
            num_conv = num_conv * 2
        elif (num[1:2] == b'2'):
            num_conv = num_conv * 2.5
        elif (num[1:2] == b'5'):
            num_conv = num_conv * 2 / 10
            exp_conv += 1
        
        
        num = str(num_conv).encode()
        exp = exp[0:1] + str(abs(floor(exp_conv))).encode()
        cmd = b'CHAN1:SCAL +' + num + b'E' + exp + b'V\r\n'
        Sock.sendall(cmd)
        
    
def ccw_action_ch1_sc():
    cmd = b'CHAN1:SCAL?\r\n'
    Sock.sendall(cmd)
    sleep(0.1)
    
    reply = get_reply()
    reply = reply[::-1]
    reply = reply[4:]
    start = reply.index(b'\n')
    reply = reply[:start]
    reply = reply[::-1]
    
    num_end = reply.index(b'E')
    num = reply[:num_end]
    exp = reply[num_end+1:]
    
    num_conv = num_from_ascii(num)
    exp_conv = num_from_ascii(exp)
    
    # deal with probe attenuation factor here
    # fine adjustment?
    
    if (num_conv * 10 ** exp_conv > 0.002):
        if (num[1:2] == b'1'):
            num_conv = num_conv / 2
        elif (num[1:2] == b'2'):
            num_conv = num_conv / 2
        elif (num[1:2] == b'5'):
            num_conv = num_conv * 2 / 5
        
        
        num = str(num_conv).encode()
        exp = exp[0:1] + str(abs(floor(exp_conv))).encode()
        cmd = b'CHAN1:SCAL +' + num + b'E' + exp + b'V\r\n'
        Sock.sendall(cmd)


def cw_ch1_offset():
    cmd = b'CHAN1:SCAL?\r\n'
    Sock.sendall(cmd)
    sleep(0.1)
    reply = get_reply()
    reply = reply[::-1]
    reply = reply[4:]
    start = reply.index(b'\n')
    reply = reply[:start]
    reply = reply[::-1]
    
    num_end = reply.index(b'E')
    num = reply[:num_end]
    exp = reply[num_end+1:]
    
    num_conv = num_from_ascii(num)
    exp_conv = num_from_ascii(exp)
    
    step = 0.125 * num_conv * 10 ** exp_conv
    
    cmd = b'CHAN1:OFFS?\r\n'
    Sock.sendall(cmd)
    sleep(0.1)
    reply = get_reply()
    reply = reply[::-1]
    reply = reply[4:]
    start = reply.index(b'\n')
    reply = reply[:start]
    reply = reply[::-1]
    
    num_end = reply.index(b'E')
    num = reply[:num_end]
    exp = reply[num_end+1:]
    
    num_conv = num_from_ascii(num)
    exp_conv = num_from_ascii(exp)
    
    offset = num_conv * 10 ** exp_conv + step
    offset = "{:.6E}".format(offset).encode()
    
    cmd = b'CHAN1:OFFS ' + offset + b'V\r\n'
    print(cmd)
    Sock.sendall(cmd)
    
def ccw_ch1_offset():
    #can definitely make this more efficient by making a subclass
    #and giving it a step field, have it only be updated whenever the channel scale is updated
    #might fuck up with a default setup tho
    #but i also know when I send that
    cmd = b'CHAN1:SCAL?\r\n'
    Sock.sendall(cmd)
    sleep(0.1)
    reply = get_reply()
    reply = reply[::-1]
    reply = reply[4:]
    start = reply.index(b'\n')
    reply = reply[:start]
    reply = reply[::-1]
    
    num_end = reply.index(b'E')
    num = reply[:num_end]
    exp = reply[num_end+1:]
    
    num_conv = num_from_ascii(num)
    exp_conv = num_from_ascii(exp)
    
    step = 0.125 * num_conv * 10 ** exp_conv
    
    cmd = b'CHAN1:OFFS?\r\n'
    Sock.sendall(cmd)
    sleep(0.1)
    reply = get_reply()
    reply = reply[::-1]
    reply = reply[4:]
    start = reply.index(b'\n')
    reply = reply[:start]
    reply = reply[::-1]
    
    num_end = reply.index(b'E')
    num = reply[:num_end]
    exp = reply[num_end+1:]
    
    num_conv = num_from_ascii(num)
    exp_conv = num_from_ascii(exp)
    
    offset = num_conv * 10 ** exp_conv - step
    offset = "{:.6E}".format(offset).encode()
    
    cmd = b'CHAN1:OFFS ' + offset + b'V\r\n'
    print(cmd)
    Sock.sendall(cmd)
    
def init_encoders():
    # Bank 0A
    ch1_scale = Encoder(A_CH1_SC, B_CH1_SC)
    ch1_scale.enabled = True
    ch1_scale.detent = True
    ch1_scale.cw_action = cw_action_ch1_sc
    ch1_scale.ccw_action = ccw_action_ch1_sc

    ch2_scale = Encoder(A_CH2_SC, B_CH2_SC)
    ch2_scale.detent = True
    
    ch1_offset = Encoder(A_CH1_OS, B_CH1_OS)
    ch1_offset.enabled = True
    ch1_scale.detent = True
    ch1_offset.cw_action = cw_ch1_offset
    ch1_offset.ccw_action = ccw_ch1_offset
    
    ch2_offset = Encoder (A_CH2_OS, B_CH2_OS)
    
    bank0A = [ch1_scale, ch2_scale, ch1_offset, ch2_offset]
    
    EncoderBank0A.encoders = bank0A
    

def get_reply():
    reply = Sock.recv(4096)
    return reply

def print_reply():
    print(get_reply())

    
def button_press(row, col):
    lcd.cursor_pos = (0,0)
    lcd.write_string("                   ")
    lcd.cursor_pos = (0,0)
    if   (row & R1):
        if   (col & C1):
            lcd.write_string("Select")
        elif (col & C2):
            lcd.write_string("Back")
        elif (col & C3):
            lcd.write_string("Horizontal")
        elif (col & C4):
            lcd.write_string("Delay")
            
        elif (col & C5):
            lcd.write_string("Run/Stop")
            cmd = b':OPER:COND?\r\n'
            Sock.sendall(cmd)
            sleep(0.01)
            reply = get_reply()
            reply = reply[::-1]
            
            oscr = 0
            mult = 1
            for i in range(4, 9):
                if (reply[i] == 43):
                    break
                else:
                    oscr += mult * (reply[i]-48)
                    mult *= 10
            
            if (oscr & 1<<3):
                cmd = b':STOP\r\n'
                Sock.sendall(cmd)
            else:
                cmd = b'RUN\r\n'
                Sock.sendall(cmd)
            
        elif (col & C6):
            lcd.write_string("Single")
            cmd = b':SINGLE\r\n'
            Sock.sendall(cmd)
            
    elif (row & R2):
        if   (col & C1):
            lcd.write_string("Horiz Scale")
        elif (col & C2):
            lcd.write_string("Zoom")
            
        elif (col & C3):
            lcd.write_string("Default Setup")
            cmd = b'*CLS\r\n'
            Sock.sendall(cmd)
            cmd = b'*RST\r\n'
            Sock.sendall(cmd)
            
        elif (col & C4):
            lcd.write_string("Auto Scale")
            cmd = b':AUTOSCALE\r\n'
            Sock.sendall(cmd)
            
        elif (col & C5):
            lcd.write_string("Math Scale")
        elif (col & C6):
            return # invalid input
    elif (row & R3):
        if   (col & C1):
            lcd.write_string("Trigger")
        elif (col & C2):
            lcd.write_string("Trig level")
        elif (col & C3):
            lcd.write_string("Measure")
        elif (col & C4):
            lcd.write_string("Cursors")
        elif (col & C5):
            lcd.write_string("Cursor ctl")
        elif (col & C6):
            lcd.write_string("Math")
    elif (row & R4):
        if   (col & C1):
            lcd.write_string("Acquire")
        elif (col & C2):
            lcd.write_string("Display")
        elif (col & C3):
            lcd.write_string("Label")
        elif (col & C4):
            lcd.write_string("Save/Recall")
        elif (col & C5):
            lcd.write_string("Utility")
        elif (col & C6):
            lcd.write_string("Math offset")
    elif (row & R5):
        if   (col & C1):
            lcd.write_string("Ch1 Scale")
        elif (col & C2):
            lcd.write_string("Ch2 Scale")
        elif (col & C3):
            lcd.write_string("Ch3 Scale")
        elif (col & C4):
            lcd.write_string("Ch4 Scale")
        elif (col & C5):
            lcd.write_string("Ch3")
        elif (col & C6):
            lcd.write_string("Ch4")
    elif (row & R6):
        if   (col & C1):
            lcd.write_string("Ch1")
        elif (col & C2):
            lcd.write_string("Ch2")
        elif (col & C3):
            lcd.write_string("Ch1 offset")
            cmd = b'CHAN1:OFFS +0E+0V\r\n'
            Sock.sendall(cmd)
        elif (col & C4):
            lcd.write_string("Ch2 offset")
        elif (col & C5):
            lcd.write_string("Ch3 offset")
        elif (col & C6):
            lcd.write_string("Ch4 offset")
            

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
#cs0 = DigitalOutputDevice( 8, active_high=False)
#cs1 = DigitalOutputDevice( 7, active_high=False)
cs2 = DigitalOutputDevice(12, active_high=False)

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


def main():
    init_spi()
    init_encoders()
    lcd.clear()
 
    try:
        events = 0
        c = 0
        
        while True:
            if (c >= 6):
                c = 0
            drive_col = ~(1 << c)
            c += 1
            
            
            spi.open(0,0)
            spi.mode = SPI_MODE
            spi.max_speed_hz = SPI_RATE
            
            to_send = [SPI_WRITE, OLATA, drive_col]
            cs2.on()
            spi.xfer2(to_send)
            cs2.off()
            
            if (interrupt4.value):
                to_send = [SPI_READ, INTFB]
                cs2.on()
                spi.xfer2(to_send)
                int_flag = spi.readbytes(1)
                cs2.off()
                
                sleep(DEBOUNCE)
                
                to_send = [SPI_READ, GPIOB]
                cs2.on()
                spi.xfer2(to_send)
                button_io = spi.readbytes(1)
                cs2.off()
                
                to_send = [SPI_READ, INTCAPB, 0x00]
                cs2.on()
                spi.xfer(to_send)
                cs2.off()
                
                if (int_flag[0] & button_io[0] > 0):
                    release = button_io
                    to_send = [SPI_READ, GPIOB]
                    cs2.on()
                    spi.xfer2(to_send)
                    while(release[0] != 0):
                        release = spi.readbytes(1)
                        sleep(0.01)
                    cs2.off()
                    
                    button_press(button_io[0], ~drive_col)
                    events += 1
            spi.close()
            
            lcd.cursor_pos = (1,0)
            lcd.write_string(str(events))
            
            
            if (interrupt5.value):
                EncoderBank0A.update_encoders()
            """
            if (interrupt5.value):
                to_send = [SPI_READ, GPIOA, 0x00]
                spi.xfer2(to_send)
                lcd.cursor_pos = (2,0)
                lcd.write_string(format(to_send[2], '08b'))
            
            if (interrupt6.value):
                to_send = [SPI_READ, GPIOB, 0x00]
                spi.xfer2(to_send)            
                lcd.cursor_pos = (3,0)
                lcd.write_string(format(to_send[2], '08b'))
            
            spi.close()
            spi.open(0,1)
            spi.mode = SPI_MODE
            spi.max_speed_hz = SPI_RATE
            
            if (interrupt1.value):
                to_send = [SPI_READ, GPIOA, 0x00]
                spi.xfer2(to_send)
                lcd.cursor_pos = (2,10)
                lcd.write_string(format(to_send[2], '08b'))
            
            if (interrupt2.value):
                to_send = [SPI_READ, GPIOB, 0x00]
                spi.xfer2(to_send)            
                lcd.cursor_pos = (3,10)
                lcd.write_string(format(to_send[2], '08b'))
            
            spi.close()
            """
        
    except Exception as e:
        print(e)
        Sock.close()
        disable_power()
        disable_backlight()
        GPIO.cleanup()
        exit()


class Encoder:
    a = 0
    b = 0
    ppr = 24
    count = 0
    clockwise = False
    
    detent = False
    detent_max = 2
    detent_count = 0
    
    enabled = False
    
    def __init__(self, a_bit, b_bit):
        self.a_bit = a_bit
        self.b_bit = b_bit
        
    def action(self):
        if self.detent:
            if ((self.detent_count >= self.detent_max) != (self.detent_count <= -1 * self.detent_max)):
                self.detent_count = 0
                self.detent = False
                self.action()
                self.detent = True
        else: 
            if (self.clockwise):
                self.cw_action()
            else:
                self.ccw_action()
        
    def adjust_count(self):
        if (self.count == 0 and not self.clockwise):
            self.count = self.ppr - 1
        elif (self.count == self.ppr - 1 and self.clockwise):
            self.count = 0
        else :
            self.count += 1 if self.clockwise else -1
            
        if (self.detent_count < self.detent_max and self.clockwise):
            self.detent_count += 1
        elif (self.detent_count > -1 * self.detent_max and not self.clockwise):
            self.detent_count += -1
            
    
    def update(self, byte):
        a = (byte & (1<<self.a_bit)) >> self.a_bit
        b = (byte & (1<<self.b_bit)) >> self.b_bit
        if ((a != self.a) != (b != self.b)):
            if (a != self.a):
                self.clockwise = a != b
            elif (b != self.b):
                self.clockwise = a == b
            self.adjust_count()
            if self.enabled:
                self.action()
            else :
                pass
                #cmd = b'SYST:DSP "This control is disabled"\r\n'
                #Sock.sendall(cmd)
        self.a = a
        self.b = b


class EncoderBank:
    encoders = []
    
    def __init__(self, device, gpio_addr):
        self.device = device
        self.gpio_addr = gpio_addr
        
    def set_encoders(self, encoders):
        self.encoders = encoders
        
    def update_encoders(self):
        spi.open(0,self.device)
        spi.mode = SPI_MODE
        spi.max_speed_hz = SPI_RATE
        
        to_send = [SPI_READ, self.gpio_addr, 0x00]
        spi.xfer2(to_send)
        spi.close()
        
        for e in self.encoders:
            e.update(to_send[2])


EncoderBank0A = EncoderBank(0, GPIOA)
EncoderBank0B = EncoderBank(0, GPIOB)
EncoderBank1A = EncoderBank(1, GPIOA)
EncoderBank1B = EncoderBank(1, GPIOB)


if __name__ == "__main__":
    main()