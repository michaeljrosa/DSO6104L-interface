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

# for programming without the instrument connected
SCOPELESS = True 

# LCD Characters
CURSOR = 0x7F
UP_ARROW = 0x00
DOWN_ARROW = 0x01
BLANK = 0x10
OMEGA = 0xF4

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
    
def ascii_to_num(txt):
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
    
def num_to_ascii(num, is_integer):
    sign = b'+' if num >= 0 else b'-'
    if is_integer:
        return sign + str(abs(floor(num))).encode()
    else:
        return sign + str(num).encode()
    
def cw_action_ch1_sc():
    # deal with probe attenuation factor here
    # fine adjustment?
    
    if (Scope.ch1_scale < 5):
        if (Scope.ch1_scale_base_b[1:2] == b'1'):
            Scope.ch1_scale_base = Scope.ch1_scale_base * 2
            Scope.ch1_offset = Scope.ch1_offset * 2
        elif (Scope.ch1_scale_base_b[1:2] == b'2'):
            Scope.ch1_scale_base = Scope.ch1_scale_base * 2.5
            Scope.ch1_offset = Scope.ch1_offset * 2.5
        elif (Scope.ch1_scale_base_b[1:2] == b'5'):
            Scope.ch1_scale_base = Scope.ch1_scale_base * 2 / 10
            Scope.ch1_offset = Scope.ch1_offset * 2 / 10
            Scope.ch1_scale_exp += 1
            
        #update state
        Scope.ch1_scale = Scope.ch1_scale_base * 10 ** Scope.ch1_scale_exp
        Scope.ch1_scale_base_b = num_to_ascii(Scope.ch1_scale_base, False)
        Scope.ch1_scale_exp_b = num_to_ascii(Scope.ch1_scale_exp, True)
        
        cmd = b'CHAN1:SCAL ' + Scope.ch1_scale_base_b + b'E' + Scope.ch1_scale_exp_b + b'V\r\n'
        Sock.sendall(cmd)
        
    
def ccw_action_ch1_sc():
    # deal with probe attenuation factor here
    # fine adjustment?
    
    if (Scope.ch1_scale > 0.002):
        if (Scope.ch1_scale_base_b[1:2] == b'1'):
            Scope.ch1_scale_base = Scope.ch1_scale_base / 2 * 10
            Scope.ch1_offset = Scope.ch1_offset * 2 / 10
            Scope.ch1_scale_exp -= 1
        elif (Scope.ch1_scale_base_b[1:2] == b'2'):
            Scope.ch1_scale_base = Scope.ch1_scale_base / 2
            Scope.ch1_offset = Scope.ch1_offset / 2
        elif (Scope.ch1_scale_base_b[1:2] == b'5'):
            Scope.ch1_scale_base = Scope.ch1_scale_base * 2 / 5
            Scope.ch1_offset = Scope.ch1_offset * 2 / 5
        
        #update state
        Scope.ch1_scale = Scope.ch1_scale_base * 10 ** Scope.ch1_scale_exp
        Scope.ch1_scale_base_b = num_to_ascii(Scope.ch1_scale_base, False)
        Scope.ch1_scale_exp_b = num_to_ascii(Scope.ch1_scale_exp, True)
        
        cmd = b'CHAN1:SCAL ' + Scope.ch1_scale_base_b + b'E' + Scope.ch1_scale_exp_b + b'V\r\n'
        Sock.sendall(cmd)


def ccw_ch1_offset():
    step = 0.125 * Scope.ch1_scale
    Scope.ch1_offset += step
    
    cmd = b'CHAN1:OFFS ' + "{:.6E}".format(Scope.ch1_offset).encode() + b'V\r\n'
    Sock.sendall(cmd)
    
def cw_ch1_offset():
    step = 0.125 * Scope.ch1_scale
    Scope.ch1_offset -= step
    
    cmd = b'CHAN1:OFFS ' + "{:.6E}".format(Scope.ch1_offset).encode() + b'V\r\n'
    Sock.sendall(cmd)
    
def init_encoders():
    # Bank 0A
    Ch1Scale = Encoder(A_CH1_SC, B_CH1_SC)
    Ch1Scale.enabled = True
    Ch1Scale.detent = True
    Ch1Scale.cw_action = cw_action_ch1_sc
    Ch1Scale.ccw_action = ccw_action_ch1_sc
    
    Ch1Offset = Encoder(A_CH1_OS, B_CH1_OS)
    Ch1Offset.enabled = True
    Ch1Offset.cw_action = cw_ch1_offset
    Ch1Offset.ccw_action = ccw_ch1_offset

    Ch2Scale = Encoder(A_CH2_SC, B_CH2_SC)
    Ch2Scale.detent = True
    
    Ch2Offset = Encoder(A_CH2_OS, B_CH2_OS)
    
    bank0A = [Ch1Scale, Ch1Offset,  Ch2Scale, Ch2Offset]
    EncoderBank0A.encoders = bank0A
    
    # Bank 0B
    Ch3Scale = Encoder(A_CH3_SC, B_CH3_SC)
    Ch3Scale.detent = True
    
    Ch3Offset = Encoder(A_CH3_OS, B_CH3_OS)
    
    Ch4Scale = Encoder(A_CH4_SC, B_CH4_SC)
    Ch4Scale.detent = True
    
    Ch4Offset = Encoder(A_CH4_OS, B_CH4_OS)
    
    bank0B = [Ch3Scale, Ch3Offset, Ch4Scale, Ch4Offset]
    EncoderBank0B.encoders = bank0B
    
    # Bank 1A
    Timebase = Encoder(A_HORIZ, B_HORIZ)
    Timebase.detent = True
    
    Delay = Encoder(A_DELAY, B_DELAY)
    
    Select = Encoder(A_SEL, B_SEL)
    Select.enabled = True
    Select.sensitivity = 4
    Select.cw_action = Menu.increment_cursor
    Select.ccw_action = Menu.decrement_cursor
    
    bank1A = [Timebase, Delay, Select]
    EncoderBank1A.encoders = bank1A
    
    # Bank 1B
    MathScale = Encoder(A_MATH_SC, B_MATH_SC)
    MathScale.detent = True
    
    MathOffset = Encoder(A_MATH_OS, B_MATH_OS)
    
    Cursor = Encoder(A_CURS, B_CURS)
    
    Trigger = Encoder(A_TRIG, B_TRIG)
    
    bank1B = [MathScale, MathOffset, Cursor, Trigger]
    EncoderBank1B.encoders = bank1B
    

def get_reply():
    reply = Sock.recv(4096)
    return reply

def print_reply():
    print(get_reply())

    
def button_press(row, col):
    if   (row & R1):
        if   (col & C1): # select
            pass
        elif (col & C2): # back
            pass
        elif (col & C3): # horizontal
            pass
        elif (col & C4): # delay knob
            pass
            
        elif (col & C5): # run/stop
            cmd = b':OPER:COND?\r\n'
            Sock.sendall(cmd)
            sleep(0.01)
            reply = get_reply()
            print(reply)
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
            
        elif (col & C6): # single
            cmd = b':SINGLE\r\n'
            Sock.sendall(cmd)
            
    elif (row & R2):
        if   (col & C1): # horizontal scale knob
            pass
        elif (col & C2): # zoom
            pass
        elif (col & C3): # default setup
            cmd = b'*CLS\r\n'
            Sock.sendall(cmd)
            cmd = b'*RST\r\n'
            Sock.sendall(cmd)
            Scope.get_state()
            
        elif (col & C4): # autoscale
            cmd = b':AUTOSCALE\r\n'
            Sock.sendall(cmd)
            sleep(0.01)
            Scope.get_state()
            
        elif (col & C5): # math scale knob
            pass
        elif (col & C6): # invalid input
            pass 
    elif (row & R3):
        if   (col & C1): # trigger 
            pass
        elif (col & C2): # trigger level knob
            pass
        elif (col & C3): # measure
            pass
        elif (col & C4): # cursors
            pass
        elif (col & C5): # cursors knob
            pass
        elif (col & C6): # math
            pass
    elif (row & R4):
        if   (col & C1): # acquire
            pass
        elif (col & C2): # dsiplay
            pass
        elif (col & C3): # label
            pass
        elif (col & C4): # save/recall
            pass
        elif (col & C5): # utility
            pass
        elif (col & C6): # math offset knob
            pass
    elif (row & R5):
        if   (col & C1): # ch1 scale knob
            pass
        elif (col & C2): # ch2 scale knob
            pass
        elif (col & C3): # ch2 scale knob
            pass
        elif (col & C4): # ch4 scale knob
            pass
        elif (col & C5): # ch3
            pass
        elif (col & C6): # ch4
            pass
    elif (row & R6):
        if   (col & C1): # ch1
            pass
        elif (col & C2): # ch2
            pass
        elif (col & C3): #ch1 offset knob
            Scope.ch1_offset = 0
            cmd = b'CHAN1:OFFS +0E+0V\r\n'
            Sock.sendall(cmd)
        elif (col & C4): # ch2 offset knob
            pass
        elif (col & C5): # ch3 offset knob
            pass
        elif (col & C6): # ch4 offset knob
            pass
            

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
    numbering_mode=GPIO.BCM,
    auto_linebreaks = False,
    charmap = 'A02')

up_arrow = (
	0b00000,
	0b00000,
	0b00100,
	0b00100,
	0b01110,
	0b01110,
	0b11111,
	0b00000
)
lcd.create_char(0, up_arrow)

down_arrow = (
    0b00000,
	0b00000,
	0b11111,
	0b01110,
	0b01110,
	0b00100,
	0b00100,
	0b00000
)
lcd.create_char(1, down_arrow)
    
bklt_en = PWMOutputDevice(4)
bklt_fault = DigitalInputDevice(2, pull_up=True)
bklt_fault.when_activated = disable_backlight
bklt_en.on()


if (SCOPELESS):
    class DummySocket:
        def sendall(self, data):
            return
        def close(self):
            return
    Sock = DummySocket()
else:
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
    print("initialized")
    
    Menu.enable()
    Menu.display_menu()
    
 
    try:
        #events = 0
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
                    
            spi.close()
            
            if (interrupt5.value):
                EncoderBank0A.update_encoders()
            
            if (interrupt6.value):
                EncoderBank0B.update_encoders()
                
            if (interrupt1.value):
                EncoderBank1A.update_encoders()
                
            if (interrupt2.value):
                EncoderBank1B.update_encoders()
            
        
    except Exception as e:
        print(e)
        Sock.close()
        disable_power()
        disable_backlight()
        #GPIO.cleanup()
        exit()
        

class Scope:
    # ch1
    ch1_enabled = False
    ch1_probe_aten = 0
    ch1_scale_base_b = b'+5'
    ch1_scale_base = 5
    ch1_scale_exp_b = b'+0'
    ch1_scale_exp = 0
    ch1_scale = 5
    ch1_offset = 0
    ch1_offset_b = b'+0e+0'
    
    def __init__(self):
        self.get_state()
    
    def get_state(self):
        if (not SCOPELESS):
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
            self.ch1_scale_base_b = reply[:num_end]
            self.ch1_scale_exp_b = reply[num_end+1:]
            
            self.ch1_scale_base = ascii_to_num(self.ch1_scale_base_b)
            self.ch1_scale_exp = ascii_to_num(self.ch1_scale_exp_b)
            
            self.ch1_scale = self.ch1_scale_base * 10 ** self.ch1_scale_exp
            
            cmd = b'CHAN1:OFFS?\r\n'
            Sock.sendall(cmd)
            sleep(0.1)
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            base_end = reply.index(b'E')
            base = reply[:base_end]
            exp = reply[num_end+1:]
            base = ascii_to_num(base)
            exp = ascii_to_num(exp)
            
            Scope.ch1_offset = base * 10 ** exp

        

class Encoder:
    a = 0
    b = 0
    ppr = 24
    raw_count = 0
    clockwise = False
    
    sensitivity = 1
    count = 0
    
    detent = False
    detent_max = 4
    detent_count = 0
    
    enabled = False
    
    def __init__(self, a_bit, b_bit):
        self.a_bit = a_bit
        self.b_bit = b_bit
        
    def action(self):
        if self.detent:
            if ((self.detent_count >= self.detent_max) != (self.detent_count <= -1 * self.detent_max)):
                self.detent_count = 0
                if (self.clockwise):
                    self.cw_action()
                else:
                    self.ccw_action()
        else: 
            if ((self.count >= self.sensitivity) != (self.count <= -1 * self.sensitivity)):
                self.count = 0
                if (self.clockwise):
                    self.cw_action()
                else:
                    self.ccw_action()
        
    def adjust_count(self):
        if (self.raw_count == 0 and not self.clockwise):
            self.raw_count = self.ppr - 1
        elif (self.raw_count == self.ppr - 1 and self.clockwise):
            self.raw_count = 0
        else :
            self.raw_count += 1 if self.clockwise else -1
            
        if (self.detent_count < self.detent_max and self.clockwise):
            self.detent_count += 1
        elif (self.detent_count > -1 * self.detent_max and not self.clockwise):
            self.detent_count += -1
        
        if (self.count < self.sensitivity and self.clockwise):
            self.count += 1
        elif (self.count > -1 * self.sensitivity and not self.clockwise):
            self.count += -1
            
    
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


Scope = Scope()
EncoderBank0A = EncoderBank(0, GPIOA)
EncoderBank0B = EncoderBank(0, GPIOB)
EncoderBank1A = EncoderBank(1, GPIOA)
EncoderBank1B = EncoderBank(1, GPIOB)


class MenuItem:
    text = ""
    
    def __init__(self, text):
        self.text = text
        
class Menu:
    menu_items = []
    is_active = False
    cursor = 0
    start_index = 0
    max_index = -1
    
    def __init__(self):
        return
    
    def set_menu(self, menu_items):
        self.menu_items = menu_items
        self.max_index = len(self.menu_items) - 1
        
    def enable(self):
        if(self.max_index >= 0):
            self.start_index = 0
            self.cursor = 0
            self.is_active = True
        
    def disable(self):
        if(self.is_active):
            self.is_active = False
            lcd.clear()
        
    def display_menu(self):
        if (self.is_active and self.max_index >= 0):
            lcd.clear()
            for i in range(self.start_index, self.start_index + 4):
                if (i <= self.max_index):
                    lcd.write_string(str(i + 1) + ".")
                    lcd.write_string(self.menu_items[i].text)
                    lcd.crlf()
                    
            if (self.start_index > 0):
                lcd.cursor_pos = (0,19)
                lcd.write(UP_ARROW)
                
            if (self.start_index + 3 < self.max_index):
                lcd.cursor_pos = (3,19)
                lcd.write(DOWN_ARROW)
            
            self.display_cursor()
                    
    def display_cursor(self):
        if (self.is_active and self.max_index >= 0):
            lcd.cursor_pos = (self.cursor - self.start_index, 18)
            lcd.write(CURSOR)
            
    def increment_cursor(self):
        if (self.is_active and self.cursor < self.max_index):
            self.cursor += 1
            if (self.start_index < self.cursor - 3):
                self.start_index += 1
                self.display_menu()
            else:
                lcd.cursor_pos = (self.cursor - 1 - self.start_index, 18)
                lcd.write(BLANK)
                self.display_cursor()
        
    def decrement_cursor(self):
        if (self.is_active and self.cursor > 0):
            self.cursor -= 1
            if (self.start_index > self.cursor):
                self.start_index = self.cursor
                self.display_menu()
            else:
                lcd.cursor_pos = (self.cursor + 1 - self.start_index, 18)
                lcd.write(BLANK)
                self.display_cursor()

Menu = Menu()

ChCoupling = MenuItem("Coupling")
ChImpedance = MenuItem("Input Z")
ChBWLimit = MenuItem("BW Limit")
ChInvert = MenuItem("Invert")
ChProbeSettings = MenuItem("Probe settings")
ChannelMenu = [ChCoupling, ChImpedance, ChBWLimit, ChInvert, ChProbeSettings]
Menu.set_menu(ChannelMenu)

if __name__ == "__main__":
    main()
