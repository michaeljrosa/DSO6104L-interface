#!/usr/bin/env python3
from os import execv
from sys import argv
from sys import exit  
from sys import maxsize

import socket
from subprocess import check_call
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
# not extensively tested, mostly used when developing the menu system
SCOPELESS = False 

# LCD Characters
CURSOR = 0x7F
UP_ARROW = 0x00
DOWN_ARROW = 0x01
BLANK = 0x10
OMEGA = 0xF4
ACTIVE = 0x2A

# I/O expander device register addresses
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

DEBOUNCE = 0.035   # seconds
CMD_WAIT = 0.01    # gives time for scope to update
AUTOSCALE_WAIT = 1

# SPI device 2, port A
# button matrix columns
C1 = 1<<5
C2 = 1<<4
C3 = 1<<3
C4 = 1<<2
C5 = 1<<1
C6 = 1<<0

# SPI device 2, port B
# button matrix rows
R1 = 1<<5
R2 = 1<<4
R3 = 1<<3
R4 = 1<<2
R5 = 1<<1
R6 = 1<<0

# Encoders
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


def disable_backlight():
    bklt_en.off()
    print("backlight disabled")
    if(bklt_fault.value == True):
        cmd = b'SYST:DSP "An LCD backlight power fault has occurred"\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
    
def pwm_backlight(f): # dimming possible but mostly unused
    if (bklt_fault.value == False):
        bklt_en.on()
        bklt_en.value = f
        print("backlight:", f)
    else:
        disable_backlight()

def disable_power():
    pwr_en.off()
    print("power disabled")
    
    if(pwr_fault.value == True):
        cmd = b'SYST:DSP "A fatal power fault has occurred"\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
    
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
    
    
def update_select_funcs():
    global ActiveMenu
    EncoderBank1A.encoders[2].cw_action = ActiveMenu.increment_cursor
    EncoderBank1A.encoders[2].ccw_action = ActiveMenu.decrement_cursor
    
    
def init_encoders():
    # Bank 0A
    Ch1Scale = Encoder(A_CH1_SC, B_CH1_SC)
    Ch1Scale.detent = True
    Ch1Scale.enabled = True
    Ch1Scale.cw_action = Scope.Channel1.cw_scale
    Ch1Scale.ccw_action = Scope.Channel1.ccw_scale
    
    Ch1Offset = Encoder(A_CH1_OS, B_CH1_OS)
    Ch1Offset.enabled = True
    Ch1Offset.cw_action = Scope.Channel1.cw_offset
    Ch1Offset.ccw_action = Scope.Channel1.ccw_offset

    Ch2Scale = Encoder(A_CH2_SC, B_CH2_SC)
    Ch2Scale.detent = True
    Ch2Scale.enabled = True
    Ch2Scale.cw_action = Scope.Channel2.cw_scale
    Ch2Scale.ccw_action = Scope.Channel2.ccw_scale
    
    Ch2Offset = Encoder(A_CH2_OS, B_CH2_OS)
    Ch2Offset.enabled = True
    Ch2Offset.cw_action = Scope.Channel2.cw_offset
    Ch2Offset.ccw_action = Scope.Channel2.ccw_offset
    
    bank0A = [Ch1Scale, Ch1Offset,  Ch2Scale, Ch2Offset]
    EncoderBank0A.encoders = bank0A
    
    # Bank 0B
    Ch3Scale = Encoder(A_CH3_SC, B_CH3_SC)
    Ch3Scale.detent = True
    Ch3Scale.enabled = True
    Ch3Scale.cw_action = Scope.Channel3.cw_scale
    Ch3Scale.ccw_action = Scope.Channel3.ccw_scale
    
    Ch3Offset = Encoder(A_CH3_OS, B_CH3_OS)
    Ch3Offset.enabled = True
    Ch3Offset.cw_action = Scope.Channel3.cw_offset
    Ch3Offset.ccw_action = Scope.Channel3.ccw_offset
    
    Ch4Scale = Encoder(A_CH4_SC, B_CH4_SC)
    Ch4Scale.detent = True
    Ch4Scale.enabled = True
    Ch4Scale.cw_action = Scope.Channel4.cw_scale
    Ch4Scale.ccw_action = Scope.Channel4.ccw_scale
    
    Ch4Offset = Encoder(A_CH4_OS, B_CH4_OS)
    Ch4Offset.enabled = True
    Ch4Offset.cw_action = Scope.Channel4.cw_offset
    Ch4Offset.ccw_action = Scope.Channel4.ccw_offset
    
    bank0B = [Ch3Scale, Ch3Offset, Ch4Scale, Ch4Offset]
    EncoderBank0B.encoders = bank0B
    
    # Bank 1A
    Timebase = Encoder(A_HORIZ, B_HORIZ)
    Timebase.enabled = True
    Timebase.detent = True
    Timebase.cw_action = Scope.Timebase.cw_scale
    Timebase.ccw_action = Scope.Timebase.ccw_scale
    
    Delay = Encoder(A_DELAY, B_DELAY)
    Delay.enabled = True
    Delay.cw_action = Scope.Timebase.cw_delay
    Delay.ccw_action = Scope.Timebase.ccw_delay
    
    Select = Encoder(A_SEL, B_SEL)
    Select.enabled = True
    Select.sensitivity = 4
    Select.cw_action = ActiveMenu.increment_cursor
    Select.ccw_action = ActiveMenu.decrement_cursor
    
    bank1A = [Timebase, Delay, Select]
    EncoderBank1A.encoders = bank1A
    
    # Bank 1B
    MathScale = Encoder(A_MATH_SC, B_MATH_SC)
    MathScale.detent = True
    
    MathOffset = Encoder(A_MATH_OS, B_MATH_OS)
    
    Cursor = Encoder(A_CURS, B_CURS)
    Cursor.enabled = True
    Cursor.cw_action = Scope.Cursor.cw_cursor
    Cursor.ccw_action = Scope.Cursor.ccw_cursor
    
    Trigger = Encoder(A_TRIG, B_TRIG)
    Trigger.enabled = True
    Trigger.cw_action = Scope.Trigger.cw_level
    Trigger.ccw_action = Scope.Trigger.ccw_level
    
    bank1B = [MathScale, MathOffset, Cursor, Trigger]
    EncoderBank1B.encoders = bank1B
    

def get_reply():
    reply = Sock.recv(4096)
    return reply

def print_reply():
    print(get_reply())

    
def button_press(row, col):
    global ActiveMenu
    if   (row & R1):
        if   (col & C1): # select
            ActiveMenu.select()
        elif (col & C2): # back
            ActiveMenu.back()
        elif (col & C3): # horizontal
            if (not Scope.Timebase.Menu.is_active):
                ActiveMenu.disable()
                ActiveMenu = Scope.Timebase.Menu
                update_select_funcs()
                ActiveMenu.enable()
                ActiveMenu.display_menu()
            elif  (Scope.Timebase.Menu.is_active):
                ActiveMenu.disable()
                
        elif (col & C4): # delay knob
            Scope.Timebase.zero_delay()
            
        elif (col & C5): # run/stop
            cmd = b':OPER:COND?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
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
            
            sleep(CMD_WAIT)
            
        elif (col & C6): # single
            cmd = b':SINGLE\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
    elif (row & R2):
        if   (col & C1): # horizontal scale knob
            pass
        elif (col & C2): # zoom
            if (not Scope.Timebase.mode[0:1] == b'W'):
                Scope.Timebase.set_mode_window()
            else:
                Scope.Timebase.set_mode_main()
                
        elif (col & C3): # default setup
            cmd = b'*CLS\r\n'
            Sock.sendall(cmd)
            cmd = b'*RST\r\n'
            Sock.sendall(cmd)
            sleep(AUTOSCALE_WAIT)
            get_reply()
            Scope.get_state()
            
        elif (col & C4): # autoscale
            cmd = b':AUTOSCALE\r\n'
            Sock.sendall(cmd)
            sleep(AUTOSCALE_WAIT)
            get_reply()
            Scope.get_state()
            
        elif (col & C5): # math scale knob
            pass
        elif (col & C6): # invalid input
            pass 
    elif (row & R3):
        if   (col & C1): # trigger 
            if (not Scope.Trigger.Menu.is_active):
                ActiveMenu.disable()
                ActiveMenu = Scope.Trigger.Menu
                update_select_funcs()
                ActiveMenu.enable()
                ActiveMenu.display_menu()
            elif  (Scope.Trigger.Menu.is_active):
                ActiveMenu.disable()
                
        elif (col & C2): # trigger level knob
            Scope.Trigger.level = 0
            cmd = b':TRIG:LFIF\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
        elif (col & C3): # measure
            if (not Scope.Measure.Menu.is_active):
                ActiveMenu.disable()
                ActiveMenu = Scope.Measure.Menu
                update_select_funcs()
                ActiveMenu.enable()
                ActiveMenu.display_menu()
            elif  (Scope.Measure.Menu.is_active):
                ActiveMenu.disable()
                
        elif (col & C4): # cursors
            if (not Scope.Cursor.Menu.is_active):
                ActiveMenu.disable()
                ActiveMenu = Scope.Cursor.Menu
                update_select_funcs()
                ActiveMenu.enable()
                ActiveMenu.display_menu()
            elif  (Scope.Cursor.Menu.is_active):
                ActiveMenu.disable()
        
        elif (col & C5): # cursors knob
            if (Scope.Cursor.mode[0:1] == b'O'):
                Scope.Cursor.set_mode_manual()
                
            if (not Scope.Cursor.ActiveCursorMenu.is_active):
                ActiveMenu.disable()
                ActiveMenu = Scope.Cursor.ActiveCursorMenu
                Scope.Cursor.cursor_select = True
                ActiveMenu.enable()
                ActiveMenu.display_menu()
            elif (Scope.Cursor.ActiveCursorMenu.is_active and Scope.Cursor.cursor_select):
                ActiveMenu.select()
                Scope.Cursor.cursor_select = False
            elif (Scope.Cursor.ActiveCursorMenu.is_active and not Scope.Cursor.cursor_select):
                Scope.Cursor.cursor_select = True
            
        elif (col & C6): # math
            pass
    elif (row & R4):
        if   (col & C1): # acquire
            pass
            
        elif (col & C2): # display
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
            if (Scope.Timebase.mode[0:1] != b'X'): # only channels 1/2 active in XY mode
                if (not Scope.Channel3.enabled.value):
                    Scope.Channel3.enable()
                    ActiveMenu.disable()
                    ActiveMenu = Scope.Channel3.Menu
                    update_select_funcs()
                    ActiveMenu.enable()
                    ActiveMenu.display_menu()
                elif (Scope.Channel3.enabled.value and not Scope.Channel3.Menu.is_active):
                    ActiveMenu.disable()
                    ActiveMenu = Scope.Channel3.Menu
                    update_select_funcs()
                    ActiveMenu.enable()
                    ActiveMenu.display_menu()
                elif  (Scope.Channel3.enabled.value and Scope.Channel3.Menu.is_active):
                    Scope.Channel3.disable()
                    ActiveMenu.disable()
                
        elif (col & C6): # ch4
            if (Scope.Timebase.mode[0:1] != b'X'): # only channels 1/2 active in XY mode
                if (not Scope.Channel4.enabled.value):
                    Scope.Channel4.enable()
                    ActiveMenu.disable()
                    ActiveMenu = Scope.Channel4.Menu
                    update_select_funcs()
                    ActiveMenu.enable()
                    ActiveMenu.display_menu()
                elif (Scope.Channel4.enabled.value and not Scope.Channel4.Menu.is_active):
                    ActiveMenu.disable()
                    ActiveMenu = Scope.Channel4.Menu
                    update_select_funcs()
                    ActiveMenu.enable()
                    ActiveMenu.display_menu()
                elif  (Scope.Channel4.enabled.value and Scope.Channel4.Menu.is_active):
                    Scope.Channel4.disable()
                    ActiveMenu.disable()
                
    elif (row & R6):
        if   (col & C1): # ch1
            if (not Scope.Channel1.enabled.value):
                Scope.Channel1.enable()
                ActiveMenu.disable()
                ActiveMenu = Scope.Channel1.Menu
                update_select_funcs()
                ActiveMenu.enable()
                ActiveMenu.display_menu()
            elif (Scope.Channel1.enabled.value and not Scope.Channel1.Menu.is_active):
                ActiveMenu.disable()
                ActiveMenu = Scope.Channel1.Menu
                update_select_funcs()
                ActiveMenu.enable()
                ActiveMenu.display_menu()
            elif  (Scope.Channel1.enabled.value and Scope.Channel1.Menu.is_active):
                if (Scope.Timebase.mode[0:1] != b'X'): # can't disable channel 1 in xy mode
                    Scope.Channel1.disable()
                ActiveMenu.disable()
                
        elif (col & C2): # ch2
            if (not Scope.Channel2.enabled.value):
                Scope.Channel2.enable()
                ActiveMenu.disable()
                ActiveMenu = Scope.Channel2.Menu
                update_select_funcs()
                ActiveMenu.enable()
                ActiveMenu.display_menu()
            elif (Scope.Channel2.enabled.value and not Scope.Channel2.Menu.is_active):
                ActiveMenu.disable()
                ActiveMenu = Scope.Channel2.Menu
                update_select_funcs()
                ActiveMenu.enable()
                ActiveMenu.display_menu()
            elif  (Scope.Channel2.enabled.value and Scope.Channel2.Menu.is_active):
                if (Scope.Timebase.mode[0:1] != b'X'): # can't disable channel 2 in xy mode
                    Scope.Channel2.disable()
                ActiveMenu.disable()
                
        elif (col & C3): #ch1 offset knob
            Scope.Channel1.zero_offset()
        elif (col & C4): # ch2 offset knob
            Scope.Channel2.zero_offset()
        elif (col & C5): # ch3 offset knob
            Scope.Channel3.zero_offset()
        elif (col & C6): # ch4 offset knob
            Scope.Channel4.zero_offset()
            

# Set board power
pwr_en = DigitalOutputDevice(5)
pwr_fault = DigitalInputDevice(6, pull_up=True)
pwr_fault.when_activated = disable_power
enable_power()

# Set up SPI and interrupt pins
spi = spidev.SpiDev()
# in case bit banging were necessary
#cs0 = DigitalOutputDevice( 8, active_high=False)
#cs1 = DigitalOutputDevice( 7, active_high=False)
cs2 = DigitalOutputDevice(12, active_high=False)

interrupt1 = DigitalInputDevice(13)
interrupt2 = DigitalInputDevice(16)
# cut trace on board and rerouted
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
    # Code provided by Agilent/Keysight with minor modifications
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
            lcd.write_string("Trying to connect...\r\n")
            lcd.write_string("IP: " + remote_ip + '\r\n')
            lcd.write_string("Port: " + str(port) + '\r\n')
            
            Sock.connect((remote_ip , port))
            break
        
        except OSError as e:
            # wait and try to connect again
            print(e)
            print("Unable to connect, trying again in 30s")
            
            lcd.clear()
            lcd.write_string("Unable to connect...\r\n")
            lcd.write_string("Trying again in ")
            
            for i in range(1, 30):
                lcd.cursor_pos = (1,16)
                lcd.write_string(str(30-i) + "s")
                if (30-i == 9):
                    lcd.cursor_pos = (1,18)
                    lcd.write(BLANK)
                sleep(1)
            
    print ('Socket Connected to ip ' + remote_ip)

    lcd.clear()
    lcd.write_string("Connected!")
    sleep(1)

    print_reply() # greeting message


def main():
    init_spi()
    init_encoders()
    lcd.clear()
    print("initialized")
    
    global ActiveMenu
    ActiveMenu.enable()
    ActiveMenu.display_menu()
    
 
    try: 
        c = 0
        
        while True:
            # drive button matrix columns
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
            
            if (interrupt4.value): # button pressed
                to_send = [SPI_READ, INTFB]
                cs2.on()
                spi.xfer2(to_send)
                int_flag = spi.readbytes(1)
                cs2.off()
                
                sleep(DEBOUNCE)    # debounce
                
                to_send = [SPI_READ, GPIOB]
                cs2.on()
                spi.xfer2(to_send)
                button_io = spi.readbytes(1)
                cs2.off()
                
                to_send = [SPI_READ, INTCAPB, 0x00]
                cs2.on()
                spi.xfer(to_send)
                cs2.off()
                
                if (int_flag[0] & button_io[0] > 0): # real press
                    release = button_io
                    to_send = [SPI_READ, GPIOB]
                    cs2.on()
                    spi.xfer2(to_send)
                    while(release[0] != 0):          # wait until release
                        release = spi.readbytes(1)
                        sleep(0.01)
                    cs2.off()
                    
                    button_press(button_io[0], ~drive_col)  # perform action
                    
                    
            spi.close()
            
            # check for encoder change
            if (interrupt5.value):
                EncoderBank0A.update_encoders()
            
            if (interrupt6.value):
                EncoderBank0B.update_encoders()
                
            if (interrupt1.value):
                EncoderBank1A.update_encoders()
                
            if (interrupt2.value):
                EncoderBank1B.update_encoders()
            
        
    except Exception as e: # restart the program if anything goes wrong
        print(e)           # (usually happens when string parsing)
        ActiveMenu.disable()
        lcd.clear()
        lcd.write_string("An unexpected error\r\noccurred.\r\n\nRestarting...")
        sleep(3)
        disable_power()
        disable_backlight()
        Sock.close()
        GPIO.cleanup()
        execv(__file__, argv)
        
        
class ToggleSetting: # used for toggle menus
    def __init__(self, bool_value):
        self.value = bool_value


class MenuItem:
    text = ""
    
    def __init__(self, text):
        self.text = text
        
    def select(self):
        return
        
class Menu:
    is_active = False
    
    def enable(self):
        raise NotImplementedError
    
    def disable(self):
        raise NotImplementedError
    
    def display_menu(self):
        raise NotImplementedError
    
    def display_cursor(self):
        raise NotImplementedError
            
    def increment_cursor(self):
        raise NotImplementedError
        
    def decrement_cursor(self):
        raise NotImplementedError
        
    def select(self):
        raise NotImplementedError
        
    def back(self):
        raise NotImplementedError

class BlankMenu(Menu):
    def enable(self):
        return
    
    def disable(self):
        return
    
    def display_menu(self):
        lcd.clear()
    
    def display_cursor(self):
        return
            
    def increment_cursor(self):
        return
        
    def decrement_cursor(self):
        return
        
    def select(self):
        return
        
    def back(self):
        return

class ToggleMenu(Menu):
    text = ""
    options_set = False
    is_active = False
    
    def __init__(self, text):
        super().__init__()
        self.text = text
        
    def set_options(self, option1, option2, setting):
        self.option1 = option1
        self.option2 = option2
        self.setting = setting
        self.options_set = True
        
    def enable(self):
        if (self.options_set):
            self.is_active = True
            
    def disable(self):
        if (self.is_active):
            self.is_active = False
            lcd.clear()
            
    def display_menu(self):
        if (self.is_active and self.options_set):
            lcd.clear()
            lcd.write_string(self.text)
            lcd.cursor_pos = (1,2)
            lcd.write_string(self.option1.text)
            lcd.cursor_pos = (2,2)
            lcd.write_string(self.option2.text)
            
            if (self.setting.value):
                lcd.cursor_pos = (1,1)
                lcd.write(ACTIVE)
            else:
                lcd.cursor_pos = (2,1)
                lcd.write(ACTIVE)
            
        
    def display_cursor(self):
        return
        
    def increment_cursor(self):
        return
        
    def decrement_cursor(self):
        return
            
    def select(self):
        if (not self.is_active):
            self.container.disable()
            global ActiveMenu 
            ActiveMenu = self
            update_select_funcs()
            self.enable()
            self.display_menu()
        else:
            if (not self.setting.value):
                self.option1.select()
            else:
                self.option2.select()
            self.display_menu()
    
    def back(self):
        if (self.is_active):
            self.disable()
            global ActiveMenu 
            ActiveMenu = self.container
            update_select_funcs()
            self.container.enable()
            self.container.display_menu()
        
class ListMenu(Menu):
    cursor = 0
    start_index = 0
    max_index = -1
    is_active = False
    text = ""
    
    def __init__(self):
        super().__init__()
        self.menu_items = []
    
    def set_text(self, text):
        self.text = text
    
    def set_menu(self, menu_items):
        self.menu_items = menu_items
        self.max_index = len(self.menu_items) - 1
        
        for x in menu_items:
            x.container = self
        
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
                
    def select(self):
        if (not self.is_active):
            self.container.disable()
            global ActiveMenu
            ActiveMenu = self
            update_select_funcs()
            self.enable()
            self.display_menu()
        else:
            self.menu_items[self.cursor].select()
            self.display_menu()
        
    def back(self):
        if (self.is_active):
            self.disable()
            global ActiveMenu 
            ActiveMenu = self.container
            update_select_funcs()
            self.container.enable()
            self.container.display_menu()


# with regards to the classes used within Scope,
# a fair amount of refactoring can be done
# e.g.: - For functions that modify the same parameter,
#         have them call a function for common code as in Measure
#       - Remove "SCOPELESS" clauses for functions that do not parse replies
#       - Formatting, naming convention, unused/unnecessary  variables(?)
#       - Add a "send_cmd" function to Scope to eliminate all of the extra
#         "Sock.sendall(cmd)" "sleep(CMD_WAIT)" lines
class Scope: # state modeling/commands
    
    def __init__(self):
        self.Trigger = Trigger(self)
        self.Cursor = Cursor(self)
        self.Measure = Measure()
        self.Timebase = Timebase()
        
        self.Channel1 = Channel(1)
        self.Channel2 = Channel(2)
        self.Channel3 = Channel(3)
        self.Channel4 = Channel(4)
        self.channels = [self.Channel1, self.Channel2, self.Channel3, self.Channel4]
        
        self.get_state()
    
    def get_state(self):
        if (not SCOPELESS):
            for c in self.channels:
                c.get_state()
                
            self.Timebase.get_state()
            self.Trigger.get_state()
            self.Cursor.get_state()

class Channel: # implement: probe attenuation, vernier, units
        
    scale_base_b = b'+5'
    scale_base = 5
    scale_exp_b = b'+0'
    scale_exp = 0
    scale = 5
    channel_range = 40
    offset = 0
    offset_b = b'+0E+0'
    
    
    def __init__(self, number):
        if (number >=1 and number <= 4):
            self.number = number
            
            self.enabled = ToggleSetting(True)
            self.ac_coupling = ToggleSetting(False)
            self.high_input_imped = ToggleSetting(True) 
            self.bw_limit = ToggleSetting(False)        
            self.inverted = ToggleSetting(False)
            
            # Menus associated with each channel
            CouplingMenu = ToggleMenu("Coupling")
            ACCoupling = MenuItem("AC")
            ACCoupling.select = self.set_ac_coupling
            DCCoupling = MenuItem("DC")
            DCCoupling.select = self.set_dc_coupling
            CouplingMenu.set_options(ACCoupling, DCCoupling, self.ac_coupling)
            
            ImpedanceMenu = ToggleMenu("Input Z")
            OneMeg = MenuItem("1 MOhm")
            OneMeg.select = self.set_impedance_high
            Fifty = MenuItem("50 Ohm")
            Fifty.select = self.set_impedance_low
            ImpedanceMenu.set_options(OneMeg, Fifty, self.high_input_imped)
            
            BWLimitMenu = ToggleMenu("Bandwidth Limit")
            BWLimitOn = MenuItem("On")
            BWLimitOn.select = self.set_bw_limit
            BWLimitOff = MenuItem("Off")
            BWLimitOff.select = self.unset_bw_limit
            BWLimitMenu.set_options(BWLimitOn, BWLimitOff, self.bw_limit)
            
            InvertMenu = ToggleMenu("Invert")
            InvertOn = MenuItem("On")
            InvertOn.select = self.set_invert
            InvertOff = MenuItem("Off")
            InvertOff.select = self.unset_invert
            InvertMenu.set_options(InvertOn, InvertOff, self.inverted)
            
            #ProbeSettingsMenu = MenuItem("Probe settings") #implement
            
            ClearProtection = MenuItem("Clear protection")
            ClearProtection.select = self.clear_protection
            
            ChannelMenuItems = [CouplingMenu, ImpedanceMenu, BWLimitMenu, InvertMenu, ClearProtection] #, ProbeSettingsMenu]
            
            self.Menu = ListMenu()
            self.Menu.set_menu(ChannelMenuItems)
            Menu.container = BlankMenu()
            
        else:
            raise ValueError('Invalid number used to initialize Channel class')
    
    def get_state(self):
        if (not SCOPELESS):
            cmd = b'CHAN' + str(self.number).encode() + b':DISP?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            if (reply[0:1] == b'0'):
                self.enabled.value = False
            elif (reply[0:1] == b'1'):
                self.enabled.value = True
            
            
            cmd = b'CHAN'  + str(self.number).encode() + b':SCAL?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            num_end = reply.index(b'E')
            self.scale_base_b = reply[:num_end]
            self.scale_exp_b = reply[num_end+1:]
            
            self.scale_base = ascii_to_num(self.scale_base_b)
            self.scale_exp = ascii_to_num(self.scale_exp_b)
            
            self.scale = self.scale_base * 10 ** self.scale_exp
            self.channel_range = self.scale * 8
            
            
            cmd = b'CHAN'  + str(self.number).encode() + b':OFFS?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            self.offset_b = reply
            
            base_end = reply.index(b'E')
            base = reply[:base_end]
            exp = reply[base_end+1:]
            base = ascii_to_num(base)
            exp = ascii_to_num(exp)
            
            self.offset = base * 10 ** exp
            
            
            cmd = b'CHAN'  + str(self.number).encode() + b':COUP?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            if (reply[0:1] == b'D'):
                self.ac_coupling.value = False
            elif (reply[0:1] == b'A'):
                self.ac_coupling.value = True
                
                
            cmd = b'CHAN'  + str(self.number).encode() + b':IMP?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            if (reply[0:1] == b'O'):
                self.high_input_imped.value = True
            elif (reply[0:1] == b'F'):
                self.high_input_imped.value = False
            
            
            cmd = b'CHAN'  + str(self.number).encode() + b':BWL?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            if (reply[0:1] == b'1'):
                self.bw_limit.value = True
            elif (reply[0:1] == b'0'):
                self.bw_limit.value = False
            
            
            cmd = b'CHAN'  + str(self.number).encode() + b':INV?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            if (reply[0:1] == b'1'):
                self.inverted.value = True
            elif (reply[0:1] == b'0'):
                self.inverted.value = False
                
        
    def enable(self):
        if (not SCOPELESS):
            cmd = b':CHAN' + str(self.number).encode() + b':DISP 1\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            self.enabled.value = True
        
    def disable(self):
        if (not SCOPELESS):
            cmd = b':CHAN' + str(self.number).encode() + b':DISP 0\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            self.enabled.value = False
        
    def zero_offset(self):
        if (not SCOPELESS and self.enabled.value):
            if (not (Scope.Timebase.mode[0:1] == b'X' and (self.number == 3 or self.number == 4))): # only channels 1/2 active in XY mode
                self.offset = 0
                cmd = b'CHAN' + str(self.number).encode() + b':OFFS +0E+0V\r\n'
                Sock.sendall(cmd)
                sleep(CMD_WAIT)
                
    def clear_protection(self):
        if (self.enabled.value):
            cmd = b'CHAN' + str(self.number).encode() + b':PROT:CLE\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
        
    def cw_scale(self):
        # deal with probe attenuation factor here
        # fine adjustment?
        
        if (not SCOPELESS and self.enabled.value and self.scale < 5):
            if (not (Scope.Timebase.mode[0:1] == b'X' and (self.number == 3 or self.number == 4))): # only channels 1/2 active in XY mode
                if (self.scale_base_b[1:2] == b'1'):
                    self.scale_base = self.scale_base * 2
                    self.offset = self.offset * 2
                elif (self.scale_base_b[1:2] == b'2'):
                    self.scale_base = self.scale_base * 2.5
                    self.offset = self.offset * 2.5
                elif (self.scale_base_b[1:2] == b'5'):
                    self.scale_base = self.scale_base * 2 / 10
                    self.offset = self.offset * 2 / 10
                    self.scale_exp += 1
                    
                #update state
                self.scale = self.scale_base * 10 ** self.scale_exp
                self.channel_range = self.scale * 8
                self.scale_base_b = num_to_ascii(self.scale_base, False)
                self.scale_exp_b = num_to_ascii(self.scale_exp, True)
                
                cmd = b'CHAN' + str(self.number).encode() + b':SCAL ' + self.scale_base_b + b'E' + self.scale_exp_b + b'V\r\n'
                Sock.sendall(cmd)
        
    def ccw_scale(self):
        # deal with probe attenuation factor here
        # fine adjustment?
        
        if (not SCOPELESS and self.enabled.value and self.scale > 0.002):
            if (not (Scope.Timebase.mode[0:1] == b'X' and (self.number == 3 or self.number == 4))): # only channels 1/2 active in XY mode
                if (self.scale_base_b[1:2] == b'1'):
                    self.scale_base = self.scale_base / 2 * 10
                    self.offset = self.offset * 2 / 10
                    self.scale_exp -= 1
                elif (self.scale_base_b[1:2] == b'2'):
                    self.scale_base = self.scale_base / 2
                    self.offset = self.offset / 2
                elif (self.scale_base_b[1:2] == b'5'):
                    self.scale_base = self.scale_base * 2 / 5
                    self.offset = self.offset * 2 / 5
                
                #update state
                self.scale = self.scale_base * 10 ** self.scale_exp
                self.channel_range = self.scale * 8
                self.scale_base_b = num_to_ascii(self.scale_base, False)
                self.scale_exp_b = num_to_ascii(self.scale_exp, True)
                
                cmd = b'CHAN' + str(self.number).encode() + b':SCAL ' + self.scale_base_b + b'E' + self.scale_exp_b + b'V\r\n'
                Sock.sendall(cmd)

    def cw_offset(self):
        if (not SCOPELESS and self.enabled.value):
            if (not (Scope.Timebase.mode[0:1] == b'X' and (self.number == 3 or self.number == 4))): # only channels 1/2 active in XY mode
                step = 0.125 * self.scale
                self.offset -= step
                
                cmd = b'CHAN' + str(self.number).encode() + b':OFFS ' + "{:.6E}".format(self.offset).encode() + b'V\r\n'
                Sock.sendall(cmd)
        
    def ccw_offset(self):
        if (not SCOPELESS and self.enabled.value):
            if (not (Scope.Timebase.mode[0:1] == b'X' and (self.number == 3 or self.number == 4))): # only channels 1/2 active in XY mode
                step = 0.125 * self.scale
                self.offset += step
                
                cmd = b'CHAN' + str(self.number).encode() + b':OFFS ' + "{:.6E}".format(self.offset).encode() + b'V\r\n'
                Sock.sendall(cmd)
        
    def set_ac_coupling(self):
        if (not SCOPELESS and self.enabled.value):
            if (not (Scope.Timebase.mode[0:1] == b'X' and (self.number == 3 or self.number == 4))): # only channels 1/2 active in XY mode
                cmd = b'CHAN' + str(self.number).encode() + b':COUP AC\r\n'
                Sock.sendall(cmd)
                self.ac_coupling.value = True
        
    def set_dc_coupling(self):
        if (not SCOPELESS and self.enabled.value):
            if (not (Scope.Timebase.mode[0:1] == b'X' and (self.number == 3 or self.number == 4))): # only channels 1/2 active in XY mode
                cmd = b'CHAN' + str(self.number).encode() + b':COUP DC\r\n'
                Sock.sendall(cmd)
                self.ac_coupling.value = False

    def set_impedance_high(self):
        if (not SCOPELESS and self.enabled.value):
            if (not (Scope.Timebase.mode[0:1] == b'X' and (self.number == 3 or self.number == 4))): # only channels 1/2 active in XY mode
                cmd = b'CHAN' + str(self.number).encode() + b':IMP ONEM\r\n'
                Sock.sendall(cmd)
                self.high_input_imped.value = True
    
    def set_impedance_low(self):
        if (not SCOPELESS and self.enabled.value):
            if (not (Scope.Timebase.mode[0:1] == b'X' and (self.number == 3 or self.number == 4))): # only channels 1/2 active in XY mode
                cmd = b'CHAN' + str(self.number).encode() + b':IMP FIFT\r\n'
                Sock.sendall(cmd)
                self.high_input_imped.value = False
                
    def set_bw_limit(self):
        if (not SCOPELESS and self.enabled.value):
            if (not (Scope.Timebase.mode[0:1] == b'X' and (self.number == 3 or self.number == 4))): # only channels 1/2 active in XY mode
                cmd = b'CHAN' + str(self.number).encode() + b':BWL 1\r\n'
                Sock.sendall(cmd)
                self.bw_limit.value = True
    
    def unset_bw_limit(self):
        if (not SCOPELESS and self.enabled.value):
            if (not (Scope.Timebase.mode[0:1] == b'X' and (self.number == 3 or self.number == 4))): # only channels 1/2 active in XY mode
                cmd = b'CHAN' + str(self.number).encode() + b':BWL 0\r\n'
                Sock.sendall(cmd)
                self.bw_limit.value = False
                
    def set_invert(self):
        if (not SCOPELESS and self.enabled.value):
            if (not (Scope.Timebase.mode[0:1] == b'X' and (self.number == 3 or self.number == 4))): # only channels 1/2 active in XY mode
                cmd = b'CHAN' + str(self.number).encode() + b':INV 1\r\n'
                Sock.sendall(cmd)
                self.inverted.value = True
    
    def unset_invert(self):
        if (not SCOPELESS and self.enabled.value):
            if (not (Scope.Timebase.mode[0:1] == b'X' and (self.number == 3 or self.number == 4))): # only channels 1/2 active in XY mode
                cmd = b'CHAN' + str(self.number).encode() + b':INV 0\r\n'
                Sock.sendall(cmd)
                self.inverted.value = False
       
class Timebase: # implement: vernier, window scale/position
    mode = b'MAIN'
    reference = b'CENT'
    scale_base_b = b'+5'
    scale_base = 5
    scale_exp_b = b'+0'
    scale_exp = 0
    scale = 5
    position = 0
    position_b = b'+0E+0'
    
    def __init__(self):
        MainMode = MenuItem("Main")
        MainMode.select = self.set_mode_main
        WindowMode = MenuItem("Window")            
        WindowMode.select = self.set_mode_window
        XYMode = MenuItem("XY")
        XYMode.select = self.set_mode_xy
        RollMode = MenuItem("Roll")
        RollMode.select = self.set_mode_roll
        
        ModeMenuItems = [MainMode, WindowMode, XYMode, RollMode]
        ModeMenu = ListMenu()
        ModeMenu.set_menu(ModeMenuItems)
        ModeMenu.text = "Mode"
        
        
        RefLeft = MenuItem("Left")
        RefLeft.select = self.set_ref_left
        RefCent = MenuItem("Center")
        RefCent.select = self.set_ref_center
        RefRight = MenuItem("Right")
        RefRight.select = self.set_ref_right
        
        RefMenuItems = [RefLeft, RefCent, RefRight]
        RefMenu = ListMenu()
        RefMenu.set_menu(RefMenuItems)
        RefMenu.text = "Reference"
        
        
        TimebaseMenuItems = [ModeMenu, RefMenu]
        self.Menu = ListMenu()
        self.Menu.set_menu(TimebaseMenuItems)
        self.Menu.container = BlankMenu()
    
    def get_state(self):
        if (not SCOPELESS):
            cmd = b'TIM:MODE?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            self.mode = reply
            
            cmd = b'TIM:REF?\r\n'
            Sock.sendall(cmd)
            sleep(2*CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            self.reference = reply
            
            cmd = b'TIM:SCAL?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            num_end = reply.index(b'E')
            self.scale_base_b = reply[:num_end]
            self.scale_exp_b = reply[num_end+1:]
            
            self.scale_base = ascii_to_num(self.scale_base_b)
            self.scale_exp = ascii_to_num(self.scale_exp_b)
            
            self.scale = self.scale_base * 10 ** self.scale_exp
            
            cmd = b'TIM:POS?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            self.position_b = reply
            
            base_end = reply.index(b'E')
            base = reply[:base_end]
            exp = reply[base_end+1:]
            base = ascii_to_num(base)
            exp = ascii_to_num(exp)
            
            self.position = base * 10 ** exp
            
    def zero_delay(self):
        if (not SCOPELESS):
            self.position = 0
            cmd = b'TIM:POS +0E+0\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
                
    def cw_delay(self):
        if (not SCOPELESS):
            step = 0.125 * self.scale
            self.position -= step
            
            cmd = b'TIM:POS ' + "{:.6E}".format(self.position).encode() + b'\r\n'
            Sock.sendall(cmd)
        
    def ccw_delay(self):
        if (not SCOPELESS):
            step = 0.125 * self.scale
            self.position += step
            
            cmd = b'TIM:POS ' + "{:.6E}".format(self.position).encode() + b'\r\n'
            Sock.sendall(cmd)
       
    def cw_scale(self):
        # fine adjustment?
        
        if (not SCOPELESS and self.mode[0:1] != b'X' and self.scale < 50):
            if (self.scale_base_b[1:2] == b'1'):
                self.scale_base = self.scale_base * 2
            elif (self.scale_base_b[1:2] == b'2'):
                self.scale_base = self.scale_base * 2.5
            elif (self.scale_base_b[1:2] == b'5'):
                self.scale_base = self.scale_base * 2 / 10
                self.scale_exp += 1
                    
            #update state
            self.scale = self.scale_base * 10 ** self.scale_exp
            self.scale_base_b = num_to_ascii(self.scale_base, False)
            self.scale_exp_b = num_to_ascii(self.scale_exp, True)
            
            cmd = b'TIM:SCAL ' + self.scale_base_b + b'E' + self.scale_exp_b + b'\r\n'
            Sock.sendall(cmd)
        
    def ccw_scale(self):
        # fine adjustment?
        min_scale = 500 * (10 ** -12) if (self.mode[0:1] != b'R') else 100 * (10 ** -3) 
        
        if (not SCOPELESS and self.mode[0:1] != b'X' and self.scale > min_scale):
            if (self.scale_base_b[1:2] == b'1'):
                self.scale_base = self.scale_base / 2 * 10
                self.scale_exp -= 1
            elif (self.scale_base_b[1:2] == b'2'):
                self.scale_base = self.scale_base / 2
            elif (self.scale_base_b[1:2] == b'5'):
                self.scale_base = self.scale_base * 2 / 5
            
            #update state
            self.scale = self.scale_base * 10 ** self.scale_exp
            self.scale_base_b = num_to_ascii(self.scale_base, False)
            self.scale_exp_b = num_to_ascii(self.scale_exp, True)
            
            cmd = b'TIM:SCAL ' + self.scale_base_b + b'E' + self.scale_exp_b + b'\r\n'
            Sock.sendall(cmd)
    
    def set_mode_main(self):
        if (not SCOPELESS and not self.mode[0:1] == b'M'):
            self.mode = b'MAIN'
            cmd = b'TIM:MODE '+ self.mode + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
    
    def set_mode_window(self):
        if (not SCOPELESS and not self.mode[0:1] == b'W'):
            self.mode = b'WIND'
            cmd = b'TIM:MODE '+ self.mode + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
    def set_mode_xy(self):
        if (not SCOPELESS and not self.mode[0:1] == b'X'):
            self.mode = b'XY'
            cmd = b'TIM:MODE '+ self.mode + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
    def set_mode_roll(self):
        if (not SCOPELESS and not self.mode[0:1] == b'R'):
            self.mode = b'ROLL'
            cmd = b'TIM:MODE '+ self.mode + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            self.get_state()
        
        
    def set_ref_left(self):
        if (not SCOPELESS and not (self.mode[0:1] == b'X' or self.mode[0:1] == b'R')):
            self.reference = b'LEFT'
            cmd = b'TIM:REF '+ self.reference + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
    def set_ref_center(self):
        if (not SCOPELESS and not (self.mode[0:1] == b'X' or self.mode[0:1] == b'R')):
            self.reference = b'CENT'
            cmd = b'TIM:REF '+ self.reference + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
    def set_ref_right(self):
        if (not SCOPELESS and not (self.mode[0:1] == b'X' or self.mode[0:1] == b'R')):
            self.reference = b'RIGH'
            cmd = b'TIM:REF '+ self.reference + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)

class Trigger: # implement: holdoff, external probe
    
    sweep = b'AUTO'
    mode = b'EDGE'
    source = b'CHAN1'
    source_range = 40
    level = 0
    #holdoff = 0
    
    def __init__(self, Scope):
        self.Scope = Scope
        
        self.HFReject = ToggleSetting(False)
        self.NReject = ToggleSetting(False)
        self.SweepIsAuto = ToggleSetting(True)
        
        # Most of these menus depend upon using 'edge' type triggering
        # There are many other trigger types available but this was most important
        
        ACCoupling = MenuItem("AC")
        ACCoupling.select = self.set_edge_coupling_ac
        DCCoupling = MenuItem("DC")
        DCCoupling.select = self.set_edge_coupling_dc
        LFCoupling = MenuItem("LF reject (50kHz)")
        LFCoupling.select = self.set_edge_coupling_lf
        CouplingMenuItems = [ACCoupling, DCCoupling, LFCoupling]
        CouplingMenu = ListMenu()
        CouplingMenu.set_menu(CouplingMenuItems)
        CouplingMenu.set_text("Coupling")
        
        RejectOff = MenuItem("Off")
        RejectOff.select = self.set_reject_off
        RejectLF = MenuItem("Low freq (50kHz)")
        RejectLF.select = self.set_reject_lf
        RejectHF = MenuItem("High freq (50kHz)")
        RejectHF.select = self.set_reject_hf
        RejectMenuItems = [RejectOff, RejectLF, RejectHF]
        RejectMenu = ListMenu()
        RejectMenu.set_menu(RejectMenuItems)
        RejectMenu.set_text("Reject")
        
        SlopePositive = MenuItem("Positive")
        SlopePositive.select = self.set_slope_positive
        SlopeNegative = MenuItem("Negative")
        SlopeNegative.select = self.set_slope_negative
        SlopeEither = MenuItem("Either")
        SlopeEither.select = self.set_slope_either
        SlopeAlternate = MenuItem("Alternate")
        SlopeAlternate.select = self.set_slope_alternate
        SlopeMenuItems = [SlopePositive, SlopeNegative, SlopeEither, SlopeAlternate]
        SlopeMenu = ListMenu()
        SlopeMenu.set_menu(SlopeMenuItems)
        SlopeMenu.set_text("Slope")
        
        SourceCh1 = MenuItem("Channel 1")
        SourceCh1.select = self.set_source_ch1
        SourceCh2 = MenuItem("Channel 2")
        SourceCh2.select = self.set_source_ch2
        SourceCh3 = MenuItem("Channel 3")
        SourceCh3.select = self.set_source_ch3
        SourceCh4 = MenuItem("Channel 4")
        SourceCh4.select = self.set_source_ch4
        #SourceExternal = MenuItem("External")
        #SourceExternal.select = self.set_source_external
        SourceLine = MenuItem("Line")
        SourceLine.select = self.set_source_line
        SourceMenuItems = [SourceCh1, SourceCh2, SourceCh3, SourceCh4, SourceLine] #, SourceExternal]
        SourceMenu = ListMenu()
        SourceMenu.set_menu(SourceMenuItems)
        SourceMenu.set_text("Source")
        
        """
        HFRejectMenu = ToggleMenu("HF Reject (50 kHz)")
        HFRejectOn = MenuItem("On")
        HFRejectOn.select = self.enable_HFRej
        HFRejectOff = MenuItem("Off")
        HFRejectOff.select = self.disable_HFRej
        HFRejectMenu.set_options(HFRejectOn, HFRejectOff, self.HFReject)
        """
        
        NRejectMenu = ToggleMenu("Noise Reject")
        NRejectOn = MenuItem("On")
        NRejectOn.select = self.enable_NRej
        NRejectOff = MenuItem("Off")
        NRejectOff.select = self.disable_NRej
        NRejectMenu.set_options(NRejectOn, NRejectOff, self.NReject)
        
        SweepMenu = ToggleMenu("Sweep")
        SweepAuto = MenuItem("Auto")
        SweepAuto.select = self.set_sweep_auto
        SweepNormal = MenuItem("Normal")
        SweepNormal.select = self.set_sweep_normal
        SweepMenu.set_options(SweepAuto, SweepNormal, self.SweepIsAuto)
        
        TriggerMenuItems = [SourceMenu, SweepMenu, CouplingMenu, RejectMenu, NRejectMenu, SlopeMenu]
        
        self.Menu = ListMenu()
        self.Menu.set_menu(TriggerMenuItems)
        Menu.container = BlankMenu()
        
    def get_state(self):
        if (not SCOPELESS):
            """
            cmd = b':TRIG:HFR?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            if (reply[0:1] == b'0'):
                self.HFReject.value = False
            elif (reply[0:1] == b'1'):
                self.HFReject.value = True
            """
                
                
            cmd = b':TRIG:NREJ?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            if (reply[0:1] == b'0'):
                self.NReject.value = False
            elif (reply[0:1] == b'1'):
                self.NReject.value = True
                
            
            cmd = b':TRIG:MODE?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            self.mode = reply
            
            
            cmd = b':TRIG:SWE?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            self.sweep = reply
            
            
            cmd = b':TRIG:EDGE:SOUR?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            self.source = reply
            
            self.get_source_range()
            self.get_level()
            
            
    def get_source_range(self):
        if (self.source[4:5] == b'1'):
            self.source_range = self.Scope.Channel1.channel_range
        if (self.source[4:5] == b'2'):
            self.source_range = self.Scope.Channel2.channel_range
        if (self.source[4:5] == b'3'):
            self.source_range = self.Scope.Channel3.channel_range
        if (self.source[4:5] == b'4'):
            self.source_range = self.Scope.Channel4.channel_range
        elif (self.source[0:1] == b'E'):
            cmd = self.source + b':RANG?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            if (not SCOPELESS):
                reply = get_reply()
                reply = reply[::-1]
                reply = reply[4:]
                start = reply.index(b'\n')
                reply = reply[:start]
                reply = reply[::-1]
                
                num_end = reply.index(b'E')
                range_base_b = reply[:num_end]
                range_exp_b = reply[num_end+1:]
                
                range_base = ascii_to_num(range_base_b)
                range_exp = ascii_to_num(range_exp_b)
                
                self.source_range = range_base * 10 ** range_exp
            
    def get_level(self):
            cmd = b'TRIG:EDGE:LEV?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            if (not SCOPELESS):
                reply = get_reply()
                reply = reply[::-1]
                reply = reply[4:]
                start = reply.index(b'\n')
                reply = reply[:start]
                reply = reply[::-1]
                self.offset_b = reply
                
                base_end = reply.index(b'E')
                base = reply[:base_end]
                exp = reply[base_end+1:]
                base = ascii_to_num(base)
                exp = ascii_to_num(exp)
                
                self.level = base * 10 ** exp
                
            
    def cw_level(self):
        if (self.source[0:1] == b'C' or self.source[0:1] == b'E'):
            self.get_source_range()

            step = 0.01 * self.source_range
            self.level += step
                
            if (self.source[0:1] == b'C'):
                if(self.level > self.source_range * 0.75):
                    self.level = self.source_range * 0.75
                    
                cmd = b'TRIG:EDGE:LEV ' + "{:.6E}".format(self.level).encode() + b'V\r\n'
                Sock.sendall(cmd)
                
            elif (self.source[0:1] == b'E'):
                if (self.level > self.source_range * 1):
                    self.level = self.source_range * 1
                cmd = b'TRIG:EDGE:LEV ' + "{:.6E}".format(self.level).encode() + b'V\r\n'
                Sock.sendall(cmd)
                   
    def ccw_level(self):
        if (self.source[0:1] == b'C' or self.source[0:1] == b'E'):
            self.get_source_range()
            
            step = 0.01 * self.source_range
            self.level -= step
                
            if (self.source[0:1] == b'C'):
                if(self.level < self.source_range * -0.75):
                    self.level = self.source_range * -0.75
                cmd = b'TRIG:EDGE:LEV ' + "{:.6E}".format(self.level).encode() + b'V\r\n'
                Sock.sendall(cmd)
                
            elif (self.source[0:1] == b'E'):
                if (self.level < self.source_range * -1):
                    self.level = self.source_range * -1
                cmd = b'TRIG:EDGE:LEV ' + "{:.6E}".format(self.level).encode() + b'V\r\n'
                Sock.sendall(cmd)
                
            
    """
    def enable_HFRej(self):
        self.HFReject.value = True
        cmd = b':TRIG:HFR 1\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
            
    def disable_HFRej(self):
        self.HFReject.value = False
        cmd = b':TRIG:HFR 0\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
    """
            
    def enable_NRej(self):
        self.NReject.value = True
        cmd = b':TRIG:NREJ 1\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
            
    def disable_NRej(self):
        self.NReject.value = False
        cmd = b':TRIG:NREJ 0\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
         
    """
    def set_mode_edge(self):
        self.mode = b'EDGE'
        cmd = b':TRIG:MODE ' + self.mode + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
    """
            
    def set_sweep_auto(self):
        self.SweepIsAuto.value = True
        self.sweep = b'AUTO'
        cmd = b':TRIG:SWE ' + self.sweep + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
            
    def set_sweep_normal(self):
        self.SweepIsAuto.value = False
        self.sweep = b'NORM'
        cmd = b':TRIG:SWE ' + self.sweep + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def set_edge_coupling_ac(self):
        cmd = b':TRIG:EDGE:COUP AC\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
    
    def set_edge_coupling_dc(self):
        cmd = b':TRIG:EDGE:COUP DC\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def set_edge_coupling_lf(self):
        cmd = b':TRIG:EDGE:COUP LFR\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
    
    def set_reject_off(self):
        cmd = b':TRIG:EDGE:REJ OFF\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def set_reject_lf(self):
        cmd = b':TRIG:EDGE:REJ LFR\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def set_reject_hf(self):
        cmd = b':TRIG:EDGE:REJ HFR\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
            
    def set_slope_positive(self):
        cmd = b':TRIG:EDGE:SLOP POS\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def set_slope_negative(self):
        cmd = b':TRIG:EDGE:SLOP NEG\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def set_slope_either(self):
        cmd = b':TRIG:EDGE:SLOP EITH\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def set_slope_alternate(self):
        cmd = b':TRIG:EDGE:SLOP ALT\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def set_source_ch1(self):
        self.source = b'CHAN1'
        cmd = b':TRIG:EDGE:SOUR ' + self.source + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        self.get_source_range()
        self.get_level()
        
    def set_source_ch2(self):
        self.source = b'CHAN2'
        cmd = b':TRIG:EDGE:SOUR ' + self.source + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        self.get_source_range()
        self.get_level()
        
    def set_source_ch3(self):
        self.source = b'CHAN3'
        cmd = b':TRIG:EDGE:SOUR ' + self.source + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        self.get_source_range()
        self.get_level()
        
    def set_source_ch4(self):
        self.source = b'CHAN4'
        cmd = b':TRIG:EDGE:SOUR ' + self.source + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        self.get_source_range()
        self.get_level()
        
    def set_source_external(self):
        self.source = b'EXT'
        cmd = b':TRIG:EDGE:SOUR ' + self.source + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        self.get_source_range()
        self.get_level()
        
    def set_source_line(self):
        self.source = b'LINE'
        cmd = b':TRIG:EDGE:SOUR ' + self.source + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        self.level = 0

class Cursor: # update appropriate functions for Math class
    mode = b'OFF'
    source1 = b'NONE'
    source2 = b'NONE'
    active_cursor = b'X1'
    cursor_position = 0
    cursor_select = False
 
    def __init__(self, Scope): #update for math
        self.Scope = Scope
        
        # menus
        ModeOff = MenuItem("Off")
        ModeOff.select = self.set_mode_off
        ModeManual = MenuItem("Manual")
        ModeManual.select = self.set_mode_manual
        ModeMeasure = MenuItem("Measurement")
        ModeMeasure.select = self.set_mode_measurement
        ModeWaveform = MenuItem("Waveform")
        ModeWaveform.select = self.set_mode_waveform
        ModeMenuItems = [ModeOff, ModeManual, ModeMeasure, ModeWaveform]
        ModeMenu = ListMenu()
        ModeMenu.set_menu(ModeMenuItems)
        ModeMenu.set_text("Mode")
        
        CursorX1 = MenuItem("X1") 
        CursorX1.select = self.set_cursor_x1
        CursorY1 = MenuItem("Y1") 
        CursorY1.select = self.set_cursor_y1
        CursorX2 = MenuItem("X2")
        CursorX2.select = self.set_cursor_x2
        CursorY2 = MenuItem("Y2")
        CursorY2.select = self.set_cursor_y2
        ActiveCursorMenuItems = [CursorX1, CursorY1, CursorX2, CursorY2]
        self.ActiveCursorMenu = ListMenu()
        self.ActiveCursorMenu.set_menu(ActiveCursorMenuItems)
        self.ActiveCursorMenu.set_text("Select cursor")
        
        Source1Ch1 = MenuItem("Channel 1")
        Source1Ch1.select = self.set_source1_ch1
        Source1Ch2 = MenuItem("Channel 2")
        Source1Ch2.select = self.set_source1_ch2
        Source1Ch3 = MenuItem("Channel 3")
        Source1Ch3.select = self.set_source1_ch3
        Source1Ch4 = MenuItem("Channel 4")
        Source1Ch4.select = self.set_source1_ch4
        #Source1Func = MenuItem("Math")
        #Source1Func.select = self.set_source1_func
        Source1MenuItems = [Source1Ch1, Source1Ch2, Source1Ch3, Source1Ch4] #, Source1Func]
        Source1Menu = ListMenu()
        Source1Menu.set_menu(Source1MenuItems)
        Source1Menu.set_text("X1Y1 source")
        
        Source2Ch1 = MenuItem("Channel 1")
        Source2Ch1.select = self.set_source2_ch1
        Source2Ch2 = MenuItem("Channel 2")
        Source2Ch2.select = self.set_source2_ch2
        Source2Ch3 = MenuItem("Channel 3")
        Source2Ch3.select = self.set_source2_ch3
        Source2Ch4 = MenuItem("Channel 4")
        Source2Ch4.select = self.set_source2_ch4
        #Source2Func = MenuItem("Math")
        #Source2Func.select = self.set_source2_func
        Source2MenuItems = [Source2Ch1, Source2Ch2, Source2Ch3, Source2Ch4] #, Source2Func]
        Source2Menu = ListMenu()
        Source2Menu.set_menu(Source2MenuItems)
        Source2Menu.set_text("X2Y2 source")
        
        Zero = MenuItem("Zero cursor")
        Zero.select = self.zero_cursor
        
        CursorMenuItems = [ModeMenu, Zero, self.ActiveCursorMenu, Source1Menu, Source2Menu]
        
        self.Menu = ListMenu()
        self.Menu.set_menu(CursorMenuItems)
        self.Menu.container = BlankMenu()
        
    def get_state(self):
        if (not SCOPELESS):
            cmd = b'MARK:MODE?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            self.mode = reply
            
            self.get_cursor_pos()
            self.get_cursor_source()
    
    def zero_cursor(self):
        if (not (self.mode[0:1] == b'O')):
            suffix = b's'
            
            if (self.active_cursor[0:1] == b'Y'): #Y1, Y2
                suffix = b'V'
            
            self.cursor_position = 0
            
            cmd = b'MARK:' + self.active_cursor + b'P ' + "{:.6E}".format(self.cursor_position).encode() + suffix + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
    
    def cw_cursor(self): #update for math
        if (not (self.mode[0:1] == b'O')):
            if (self.cursor_select and self.ActiveCursorMenu.is_active):
                ActiveMenu.increment_cursor()
            else:
                suffix = b's'
                scale = self.Scope.Timebase.scale
                
                if (self.active_cursor[0:1] == b'Y'): #Y1, Y2
                    suffix = b'V'
                    
                    source = self.source1
                    if (self.active_cursor[1:2] == b'1'):
                        source = self.source1
                    else:
                        source = self.source2
                        
                    if (source[0:1] == b'C'):
                        if (source[4:5] == b'1'):
                            scale = self.Scope.Channel1.scale
                        elif (source[4:5] == b'2'):
                            scale = self.Scope.Channel2.scale
                        elif (source[4:5] == b'3'):
                            scale = self.Scope.Channel3.scale
                        elif (source[4:5] == b'4'):
                            scale = self.Scope.Channel4.scale
                    else:
                        # scale = self.Scope.Math.scale
                        pass
                
                step = 0.125 * scale
                self.cursor_position += step
                
                cmd = b'MARK:' + self.active_cursor + b'P ' + "{:.6E}".format(self.cursor_position).encode() + suffix + b'\r\n'
                Sock.sendall(cmd)
                sleep(CMD_WAIT)
            
    def ccw_cursor(self): #update for math
        if (not (self.mode[0:1] == b'O')):
            if (self.cursor_select and self.ActiveCursorMenu.is_active):
                ActiveMenu.decrement_cursor()
            else:
                suffix = b's'
                scale = self.Scope.Timebase.scale
                
                if (self.active_cursor[0:1] == b'Y'): #Y1, Y2
                    suffix = b'V'
                    
                    source = self.source1
                    if (self.active_cursor[1:2] == b'1'):
                        source = self.source1
                    else:
                        source = self.source2
                    
                    if (source[0:1] == b'C'):
                        if (source[4:5] == b'1'):
                            scale = self.Scope.Channel1.scale
                        elif (source[4:5] == b'2'):
                            scale = self.Scope.Channel2.scale
                        elif (source[4:5] == b'3'):
                            scale = self.Scope.Channel3.scale
                        elif (source[4:5] == b'4'):
                            scale = self.Scope.Channel4.scale
                    else:
                        # scale = self.Scope.Math.scale
                        pass
                        
                step = 0.125 * scale
                self.cursor_position -= step
                
                cmd = b'MARK:' + self.active_cursor + b'P ' + "{:.6E}".format(self.cursor_position).encode() + suffix + b'\r\n'
                Sock.sendall(cmd)
                sleep(CMD_WAIT)
            
    def get_cursor_pos(self):
        if (not self.mode[0:1] == b'O'):
            cmd = b'MARK:' + self.active_cursor + b'P?\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            if (not SCOPELESS):
                reply = get_reply()
                reply = reply[::-1]
                reply = reply[4:]
                start = reply.index(b'\n')
                reply = reply[:start]
                reply = reply[::-1]
                
                num_end = reply.index(b'E')
                pos_base_b = reply[:num_end]
                pos_exp_b = reply[num_end+1:]
                
                pos_base = ascii_to_num(pos_base_b)
                pos_exp = ascii_to_num(pos_exp_b)
                
                self.cursor_position = pos_base * 10 ** pos_exp
        
    def get_cursor_source(self):
        cmd = b'MARK:X1Y1?\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
        if (not SCOPELESS):
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            self.source1 = reply
            
        cmd = b'MARK:X2Y2?\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
        if (not SCOPELESS):
            reply = get_reply()
            reply = reply[::-1]
            reply = reply[4:]
            start = reply.index(b'\n')
            reply = reply[:start]
            reply = reply[::-1]
            
            self.source2 = reply
    
    def set_mode_off(self):
        self.mode = b'OFF'
        cmd = b'MARK:MODE ' + self.mode + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
    
    def set_mode_manual(self):
        self.mode = b'MAN'
        cmd = b'MARK:MODE ' + self.mode + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
        self.get_cursor_pos()
        self.get_cursor_source()
        
    def set_mode_measurement(self):
        self.mode = b'MEAS'
        cmd = b'MARK:MODE ' + self.mode + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
                
        self.get_cursor_pos()
        self.get_cursor_source()
    
    def set_mode_waveform(self):
        self.mode = b'WAV'
        cmd = b'MARK:MODE ' + self.mode + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
        self.get_cursor_pos()
        self.get_cursor_source()
        
    def set_cursor_x1(self):
        self.active_cursor = b'X1'
        self.get_cursor_pos()
        
    def set_cursor_y1(self):
        self.active_cursor = b'Y1'
        self.get_cursor_pos()
        
    def set_cursor_x2(self):
        self.active_cursor = b'X2'
        self.get_cursor_pos()
        
    def set_cursor_y2(self):
        self.active_cursor = b'Y2'
        self.get_cursor_pos()
    
    def set_source1_ch1(self):
        if(self.Scope.Channel1.enabled.value):
            self.source1 = b'CHAN1'
            cmd = b'MARK:X1Y1 ' + self.source1 + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            if(not (self.mode[0:1] == b'W')):
                self.mode = b'MAN'
                
            self.get_cursor_pos()
        
    def set_source1_ch2(self):
        if(self.Scope.Channel2.enabled.value):
            self.source1 = b'CHAN2'
            cmd = b'MARK:X1Y1 ' + self.source1 + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            if(not (self.mode[0:1] == b'W')):
                self.mode = b'MAN'
                
            self.get_cursor_pos()
        
    def set_source1_ch3(self):
        if(self.Scope.Channel3.enabled.value):
            self.source1 = b'CHAN3'
            cmd = b'MARK:X1Y1 ' + self.source1 + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            if(not (self.mode[0:1] == b'W')):
                self.mode = b'MAN'
                
            self.get_cursor_pos()
        
    def set_source1_ch4(self):
        if(self.Scope.Channel2.enabled.value):
            self.source1 = b'CHAN4'
            cmd = b'MARK:X1Y1 ' + self.source1 + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            if(not (self.mode[0:1] == b'W')):
                self.mode = b'MAN'
                
            self.get_cursor_pos()
        
    def set_source1_func(self): # update for Math
        if(False):
            self.source1 = b'FUNC'
            cmd = b'MARK:X1Y1 ' + self.source1 + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            if(not (self.mode[0:1] == b'W')):
                self.mode = b'MAN'
                
            self.get_cursor_pos()
            
    def set_source2_ch1(self):
        if(self.Scope.Channel1.enabled.value):
            self.source2 = b'CHAN1'
            cmd = b'MARK:X2Y2 ' + self.source2 + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            if(not (self.mode[0:1] == b'W')):
                self.mode = b'MAN'
                
            self.get_cursor_pos()
        
    def set_source2_ch2(self):
        if(self.Scope.Channel2.enabled.value):
            self.source2 = b'CHAN2'
            cmd = b'MARK:X2Y2 ' + self.source2 + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            if(not (self.mode[0:1] == b'W')):
                self.mode = b'MAN'
                
            self.get_cursor_pos()
        
    def set_source2_ch3(self):
        if(self.Scope.Channel3.enabled.value):
            self.source2 = b'CHAN3'
            cmd = b'MARK:X2Y2 ' + self.source2 + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            if(not (self.mode[0:1] == b'W')):
                self.mode = b'MAN'
                
            self.get_cursor_pos()
        
    def set_source2_ch4(self):
        if(self.Scope.Channel2.enabled.value):
            self.source2 = b'CHAN4'
            cmd = b'MARK:X2Y2 ' + self.source2 + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            if(not (self.mode[0:1] == b'W')):
                self.mode = b'MAN'
                
            self.get_cursor_pos()
        
    def set_source2_func(self): # update for Math
        if(False):
            self.source2 = b'FUNC'
            cmd = b'MARK:X2Y2 ' + self.source2 + b'\r\n'
            Sock.sendall(cmd)
            sleep(CMD_WAIT)
            
            if(not (self.mode[0:1] == b'W')):
                self.mode = b'MAN'
                
            self.get_cursor_pos()
            
class Measure: # update appropriate functions for Math class    
               # add ability to change thresholds, other settings if needed
    
    source1 = b'CHAN1'
    source2 = b'CHAN2'
    
    def __init__(self): #update for math
        Clear = MenuItem("Clear")
        Clear.select = self.clear
        
        S1Ch1 = MenuItem("Channel 1")
        S1Ch1.select = self.set_source1_ch1
        S1Ch2 = MenuItem("Channel 2")
        S1Ch2.select = self.set_source1_ch2
        S1Ch3 = MenuItem("Channel 3")
        S1Ch3.select = self.set_source1_ch3
        S1Ch4 = MenuItem("Channel 4")
        S1Ch4.select = self.set_source1_ch4
        #S1Func = MenuItem("Math")
        #S1Func.select = self.set_source1_func
        Source1MenuItems = [S1Ch1, S1Ch2, S1Ch3, S1Ch4] #, S1Func] # external probe is also an option
        Source1 = ListMenu()
        Source1.set_menu(Source1MenuItems)
        Source1.set_text("Source 1")
        
        S2Ch1 = MenuItem("Channel 1")
        S2Ch1.select = self.set_source2_ch1
        S2Ch2 = MenuItem("Channel 2")
        S2Ch2.select = self.set_source2_ch2
        S2Ch3 = MenuItem("Channel 3")
        S2Ch3.select = self.set_source2_ch3
        S2Ch4 = MenuItem("Channel 4")
        S2Ch4.select = self.set_source2_ch4
        #S2Func = MenuItem("Math")
        #S2Func.select = self.set_source2_func
        Source2MenuItems = [S2Ch1, S2Ch2, S2Ch3, S2Ch4] #, S2Func]
        Source2 = ListMenu()
        Source2.set_menu(Source2MenuItems)
        Source2.set_text("Source 2")
        
        ResetStat = MenuItem("Reset")
        ResetStat.select = self.reset_statistics
        
        WindowMain = MenuItem("Main")
        WindowMain.select = self.set_window_main
        WindowZoom = MenuItem("Zoom")
        WindowZoom.select = self.set_window_zoom
        WindowAuto = MenuItem("Auto")
        WindowAuto.select = self.set_window_auto
        WindowMenuItems = [WindowMain, WindowZoom, WindowAuto]
        Window = ListMenu()
        Window.set_menu(WindowMenuItems)
        Window.set_text("Window")
        
        Counter = MenuItem("Counter")
        Counter.select = self.counter
        
        Delay = MenuItem("Delay")
        Delay.select = self.delay
        
        DutyCycle = MenuItem("Duty cycle")
        DutyCycle.select = self.duty_cycle
        
        FallTime = MenuItem("Fall time")
        FallTime.select = self.fall_time
        
        Frequency = MenuItem("Frequency")
        Frequency.select = self.frequency
        
        NPulseWidth = MenuItem("Neg p width")
        NPulseWidth.select = self.neg_pulse_width
        
        Overshoot = MenuItem("Overshoot")
        Overshoot.select = self.overshoot
        
        Period = MenuItem("Period")
        Period.select = self.period
        
        Phase = MenuItem("Phase")
        Phase.select = self.phase
        
        Preshoot = MenuItem("Preshoot")
        Preshoot.select = self.preshoot
        
        PulseWidth = MenuItem("Pulse width")
        PulseWidth.select = self.pulse_width
        
        RiseTime = MenuItem("Rise time")
        RiseTime.select = self.rise_time
        
        StdDev = MenuItem("Std dev")
        StdDev.select = self.std_dev
        
        VAmp = MenuItem("V amplitude")
        VAmp.select = self.v_amp
        
        VAvg = MenuItem("V average")
        VAvg.select = self.v_avg
        
        VBase = MenuItem("V base")
        VBase.select = self.v_base
        
        VMax = MenuItem("V max")
        VMax.select = self.v_max
        
        VMin = MenuItem("V min")
        VMin.select = self.v_min
        
        VPP = MenuItem("V peak-peak")
        VPP.select = self.v_pp
        
        VRatio = MenuItem("V ratio")
        VRatio.select = self.v_ratio
        
        VRMS = MenuItem("V RMS")
        VRMS.select = self.v_rms
        
        VTop = MenuItem("V top")
        VTop.select = self.v_top
        
        XMax = MenuItem("X max")
        XMax.select = self.x_max
        
        XMin = MenuItem("X min")
        XMin.select = self.x_min
        
        MeasureMenuItems = [Clear, ResetStat, Source1, Source2, Window, 
            Counter, Delay, DutyCycle, FallTime, Frequency, NPulseWidth, Overshoot,
            Period, Phase, Preshoot, PulseWidth, RiseTime, StdDev, VAmp, VAvg,
            VBase, VMax, VMin, VPP, VRatio, VRMS, VTop, XMax, XMin]
            
        self.Menu = ListMenu()
        self.Menu.set_menu(MeasureMenuItems)
        self.Menu.container = BlankMenu()
    
    def clear(self):
        cmd = b':MEAS:CLE\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def reset_statistics(self):
        cmd = b':MEAS:STAT:RES\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def set_source1(self):
        cmd = b':MEAS:SOUR ' + self.source1 + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def set_source2(self):
        cmd = b':MEAS:SOUR ' + self.source1 + b',' + self.source2 + b'\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
    
    def set_source1_ch1(self):
        self.source1 = b'CHAN1'
        self.set_source1()
    
    def set_source1_ch2(self):
        self.source1 = b'CHAN2'
        self.set_source1()
    
    def set_source1_ch3(self):
        self.source1 = b'CHAN3'
        self.set_source1()
    
    def set_source1_ch4(self):
        self.source1 = b'CHAN4'
        self.set_source1()
    
    def set_source1_func(self):
        self.source1 = b'FUNC'
        self.set_source1()
        
    def set_source2_ch1(self):
        self.source2 = b'CHAN1'
        self.set_source2()
    
    def set_source2_ch2(self):
        self.source2 = b'CHAN2'
        self.set_source2()
    
    def set_source2_ch3(self):
        self.source2 = b'CHAN3'
        self.set_source2()
    
    def set_source2_ch4(self):
        self.source2 = b'CHAN4'
        self.set_source2()
    
    def set_source2_func(self):
        self.source2 = b'FUNC'
        self.set_source2()
        
    def set_window_main(self):
        cmd = b':MEAS:WIND MAIN\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def set_window_zoom(self):
        cmd = b':MEAS:WIND ZOOM\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def set_window_auto(self):
        cmd = b':MEAS:WIND AUTO\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def counter(self):
        cmd = b':MEAS:COUN\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def delay(self):
        cmd = b':MEAS:DEL\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def duty_cycle(self):
        cmd = b':MEAS:DUTY\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def fall_time(self):
        cmd = b':MEAS:FALL\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def frequency(self):
        cmd = b':MEAS:FREQ\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def neg_pulse_width(self):
        cmd = b':MEAS:NWID\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def overshoot(self):
        cmd = b':MEAS:OVER\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def period(self):
        cmd = b':MEAS:PER\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def phase(self):
        cmd = b':MEAS:PHAS\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def preshoot(self):
        cmd = b':MEAS:PRES\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def pulse_width(self):
        cmd = b':MEAS:PWID\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def rise_time(self):
        cmd = b':MEAS:RIS\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def std_dev(self):
        cmd = b':MEAS:SDEV\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def v_amp(self):
        cmd = b':MEAS:VAMP\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def v_avg(self):
        cmd = b':MEAS:VAV\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def v_base(self):
        cmd = b':MEAS:VBAS\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def v_max(self):
        cmd = b':MEAS:VMAX\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def v_min(self):
        cmd = b':MEAS:VMIN\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def v_pp(self):
        cmd = b':MEAS:VPP\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def v_ratio(self):
        cmd = b':MEAS:VRAT\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def v_rms(self):
        cmd = b':MEAS:VRMS\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def v_top(self):
        cmd = b':MEAS:VTOP\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def x_max(self):
        cmd = b':MEAS:XMAX\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
        
    def x_min(self):
        cmd = b':MEAS:XMIN\r\n'
        Sock.sendall(cmd)
        sleep(CMD_WAIT)
    
            
class Encoder:
    a = 0
    b = 0
    ppr = 24
    raw_count = 0
    clockwise = False
    
    sensitivity = 1 # higher = less sensitive, modify for instances (e.g. select knob)
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
    
    def __init__(self, device, gpio_addr):
        self.device = device
        self.gpio_addr = gpio_addr
        self.encoders = []
        
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


ActiveMenu = BlankMenu()

Scope = Scope()

EncoderBank0A = EncoderBank(0, GPIOA)
EncoderBank0B = EncoderBank(0, GPIOB)
EncoderBank1A = EncoderBank(1, GPIOA)
EncoderBank1B = EncoderBank(1, GPIOB)

if __name__ == "__main__":
    main()
