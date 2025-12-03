import serial
import time
import struct

arduino = serial.Serial(port="COM3", baudrate=115200, timeout=0.5)

while True:
    value = arduino.read(4)
    if len(value) > 0:
        [printvalue] = struct.unpack('f', value)
        print(printvalue)