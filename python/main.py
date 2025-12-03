# pyFirmata test
import tkinter as tk
from pyfirmata import Arduino

# Functions
def pingArdu():
    return

# Board connected to COM3
board = Arduino("COM3")

# Initializing tkinter window
win = tk.Tk()
win.title("pyFirmata Test")
win.minsize(200, 60)

# Label widget
label = tk.Label(win, text="Click to ping Arduino")
label.grid(column=1, row=1)

# Button widget
PINGbtn = tk.Button(win, bd=4, text = "PING", command=pingArdu)
