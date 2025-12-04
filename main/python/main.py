import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from arduino_serial import ArduinoController
import json
import os
import csv
from datetime import datetime

class CalibrationWindow:
    """Simple calibration window"""
    def __init__(self, parent, arduino, main_text):
        self.arduino = arduino
        self.main_text = main_text
        self.window = tk.Toplevel(parent)
        self.window.title("Scale Calibration")
        self.window.geometry("450x300")
        self.window.grab_set()
        
        self.state = "init"
        self.create_ui()
        self.start()
        
    def create_ui(self):
        # Instructions
        self.instruction_label = ttk.Label(
            self.window, 
            text="Starting calibration...", 
            wraplength=400,
            justify=tk.LEFT,
            padding=20
        )
        self.instruction_label.pack(fill=tk.BOTH, expand=True)
        
        # Weight input
        self.weight_frame = ttk.Frame(self.window)
        ttk.Label(self.weight_frame, text="Known Weight (g):").pack(side=tk.LEFT, padx=5)
        self.weight_entry = ttk.Entry(self.weight_frame, width=15)
        self.weight_entry.pack(side=tk.LEFT, padx=5)
        
        # Buttons
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(pady=10)
        self.next_btn = ttk.Button(btn_frame, text="Next", command=self.on_next)
        self.next_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)
        
    def start(self):
        # Show step 1 immediately
        self.instruction_label.config(
            text="Step 1: Clear the scale\n\nRemove all items from the scale.\n\nWaiting 2 seconds before taring..."
        )
        self.state = "init"
        self.next_btn.pack_forget()  # Hide the Next button during step 1
        self.arduino.write_line("<calibrate>")
        self.monitor()
        
    def monitor(self):
        """Monitor Arduino responses"""
        if not self.window.winfo_exists():
            return
            
        try:
            while self.arduino.available() > 0:
                msg = self.arduino.read_line()
                if msg:
                    self.main_text.insert(tk.END, f"{msg}\n")
                    self.main_text.see(tk.END)
                    self.handle_message(msg)
        except:
            pass
            
        self.window.after(50, self.monitor)
        
    def handle_message(self, msg):
        if msg == "CAL_START":
            # Confirmation that calibration started
            self.state = "started"
            
        elif msg == "CAL_CLEAR_SCALE":
            # Redundant check, but update if somehow missed
            if self.state == "init":
                self.instruction_label.config(
                    text="Step 1: Clear the scale\n\nRemove all items from the scale.\n\nWaiting 2 seconds before taring..."
                )
            self.state = "clearing"
            
        elif msg == "CAL_TARED":
            self.instruction_label.config(
                text="Step 2: Place known weight\n\nPlace a known weight on the scale.\n"
                     "Enter the weight in grams and click Next."
            )
            self.weight_frame.pack(pady=10)
            self.weight_entry.focus()
            self.state = "need_weight"
            self.next_btn.pack(side=tk.LEFT, padx=5)  # Show Next button now
            self.next_btn.config(state=tk.NORMAL)
            
        elif msg.startswith("CAL_WEIGHT:"):
            weight = msg.split(":")[1]
            self.instruction_label.config(
                text=f"Step 3: Measuring\n\nWeight: {weight}g\nWaiting for stable reading..."
            )
            self.next_btn.config(state=tk.DISABLED)
            
        elif msg.startswith("CAL_RAW:"):
            raw = msg.split(":")[1]
            self.instruction_label.config(text=f"Reading scale...\nRaw value: {raw}")
            
        elif msg.startswith("CAL_FACTOR:"):
            factor = msg.split(":")[1]
            self.instruction_label.config(text=f"Calibration factor calculated: {factor}")
            
        elif msg.startswith("CAL_TEST:"):
            test = msg.split(":")[1]
            self.instruction_label.config(
                text=f"Calibration Complete!\n\nTest reading: {test}g\n\nYou can close this window."
            )
            self.next_btn.pack(side=tk.LEFT, padx=5)  # Show button as Close
            self.next_btn.config(text="Close", command=self.window.destroy, state=tk.NORMAL)
            self.weight_frame.pack_forget()
            
        elif msg.startswith("CAL_ERROR:"):
            error = msg.split(":", 1)[1]
            messagebox.showerror("Calibration Error", error)
            if "weight" in error.lower():
                self.next_btn.config(state=tk.NORMAL)
                
    def on_next(self):
        if self.state == "need_weight":
            weight = self.weight_entry.get().strip()
            if not weight:
                messagebox.showerror("Error", "Please enter a weight value")
                return
            try:
                w = float(weight)
                if w <= 0:
                    messagebox.showerror("Error", "Weight must be positive")
                    return
                self.arduino.write_line(f"<weight:{weight}>")
                self.next_btn.config(state=tk.DISABLED)
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid number")
                
    def on_cancel(self):
        self.arduino.write_line("<cancel>")
        self.window.destroy()


class ArduinoGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Arduino Scale Controller")
        self.root.geometry("700x550")
        
        self.arduino = ArduinoController()
        self.reading = False
        self.current_scale_factor = None
        self.waiting_for_scale = False
        
        # CSV recording variables
        self.recording = False
        self.csv_file = None
        self.csv_writer = None
        self.record_start_time = None
        self.record_duration = 0
        
        self.create_ui()
        
    def create_ui(self):
        # Create left and right frames for two-column layout
        left_frame = ttk.Frame(self.root)
        left_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        right_frame = ttk.Frame(self.root)
        right_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        # ===== LEFT COLUMN =====
        
        # Connection section
        conn_frame = ttk.LabelFrame(left_frame, text="Connection", padding=10)
        conn_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(conn_frame, text="COM Port:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.port_combo = ttk.Combobox(conn_frame, width=12, state="readonly")
        self.port_combo.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(conn_frame, text="Refresh", command=self.refresh_ports, width=8).grid(row=0, column=2, padx=5, pady=5)
        
        ttk.Label(conn_frame, text="Baud Rate:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.baud_combo = ttk.Combobox(conn_frame, width=12, state="readonly", values=[9600, 19200, 38400, 57600, 115200])
        self.baud_combo.current(4)
        self.baud_combo.grid(row=1, column=1, padx=5, pady=5)
        
        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.grid(row=2, column=0, columnspan=3, pady=10)
        
        self.status_label = ttk.Label(left_frame, text="Status: Disconnected", foreground="red")
        self.status_label.pack(pady=5)
        
        # Control section
        ctrl_frame = ttk.LabelFrame(left_frame, text="Controls", padding=10)
        ctrl_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Button(ctrl_frame, text="Start", command=self.start_measurement, width=10).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(ctrl_frame, text="Stop", command=self.stop_measurement, width=10).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(ctrl_frame, text="Tare", command=self.tare, width=10).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(ctrl_frame, text="Calibrate", command=self.calibrate, width=10).grid(row=1, column=1, padx=5, pady=5)
        
        # Calibration management
        cal_frame = ttk.LabelFrame(left_frame, text="Calibration Files", padding=10)
        cal_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Button(cal_frame, text="Save Calibration", command=self.save_calibration, width=22).pack(pady=5)
        ttk.Button(cal_frame, text="Load Calibration", command=self.load_calibration, width=22).pack(pady=5)
        
        # Recording section
        rec_frame = ttk.LabelFrame(left_frame, text="Recording", padding=10)
        rec_frame.pack(fill="both", expand=True)
        
        ttk.Label(rec_frame, text="Filename:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.filename_entry = ttk.Entry(rec_frame, width=18)
        self.filename_entry.insert(0, "measurement")
        self.filename_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(rec_frame, text="Duration (s):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.duration_entry = ttk.Entry(rec_frame, width=18)
        self.duration_entry.insert(0, "60")
        self.duration_entry.grid(row=1, column=1, padx=5, pady=5)
        
        self.record_btn = ttk.Button(rec_frame, text="Start Recording", command=self.toggle_recording, width=22)
        self.record_btn.grid(row=2, column=0, columnspan=2, padx=5, pady=10)
        
        self.record_status = ttk.Label(rec_frame, text="Not recording", foreground="gray", wraplength=200)
        self.record_status.grid(row=3, column=0, columnspan=2, padx=5, pady=5)
        
        # ===== RIGHT COLUMN =====
        
        # Send section
        send_frame = ttk.LabelFrame(right_frame, text="Send Command", padding=10)
        send_frame.pack(fill="x", pady=(0, 10))
        
        self.send_entry = ttk.Entry(send_frame, width=30)
        self.send_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(send_frame, text="Send", command=self.send_command).pack(side=tk.LEFT, padx=5)
        
        # Display section
        display_frame = ttk.LabelFrame(right_frame, text="Received Data", padding=10)
        display_frame.pack(fill="both", expand=True)
        
        self.display_text = tk.Text(display_frame, height=20, width=40)
        self.display_text.pack(side=tk.LEFT, fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(display_frame, command=self.display_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill="y")
        self.display_text.config(yscrollcommand=scrollbar.set)
        
        ttk.Button(right_frame, text="Clear Display", command=self.clear_display).pack(pady=5)
        
        self.refresh_ports()
        
    def refresh_ports(self):
        ports = ArduinoController.list_ports()
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.current(0)
            
    def toggle_connection(self):
        if not self.arduino.is_connected():
            self.connect()
        else:
            self.disconnect()
            
    def connect(self):
        port = self.port_combo.get()
        baud = int(self.baud_combo.get())
        
        if not port:
            messagebox.showerror("Error", "Please select a port")
            return
            
        try:
            self.arduino.connect(port=port, baudrate=baud)
            self.status_label.config(text=f"Status: Connected to {port}", foreground="green")
            self.connect_btn.config(text="Disconnect")
            self.port_combo.config(state="disabled")
            self.baud_combo.config(state="disabled")
            self.start_reading()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            
    def disconnect(self):
        self.reading = False
        self.arduino.disconnect()
        self.status_label.config(text="Status: Disconnected", foreground="red")
        self.connect_btn.config(text="Connect")
        self.port_combo.config(state="readonly")
        self.baud_combo.config(state="readonly")
        
    def start_reading(self):
        self.reading = True
        self.read_loop()
        
    def read_loop(self):
        if self.reading and self.arduino.is_connected():
            try:
                while self.arduino.available() > 0:
                    data = self.arduino.read_line()
                    if data:
                        self.display_text.insert(tk.END, f"{data}\n")
                        self.display_text.see(tk.END)
                        
                        # Check for scale factor response
                        if data.startswith("SCALE_FACTOR:") and self.waiting_for_scale:
                            self.current_scale_factor = float(data.split(":")[1])
                            self.waiting_for_scale = False
                        
                        # Record measurement data if recording
                        if self.recording:
                            self.record_measurement(data)
                            
                self.root.after(50, self.read_loop)
            except:
                self.reading = False
                
    def start_measurement(self):
        if not self.arduino.is_connected():
            messagebox.showwarning("Warning", "Not connected")
            return
        self.arduino.write_line("<start>")
        self.display_text.insert(tk.END, ">> START\n")
        
    def stop_measurement(self):
        if not self.arduino.is_connected():
            messagebox.showwarning("Warning", "Not connected")
            return
        self.arduino.write_line("<stop>")
        self.display_text.insert(tk.END, ">> STOP\n")
        
    def tare(self):
        if not self.arduino.is_connected():
            messagebox.showwarning("Warning", "Not connected")
            return
        self.arduino.write_line("<tare>")
        self.display_text.insert(tk.END, ">> TARE\n")
        
    def calibrate(self):
        if not self.arduino.is_connected():
            messagebox.showwarning("Warning", "Not connected")
            return
        CalibrationWindow(self.root, self.arduino, self.display_text)
        
    def send_command(self):
        if not self.arduino.is_connected():
            messagebox.showwarning("Warning", "Not connected")
            return
        cmd = self.send_entry.get()
        if cmd:
            self.arduino.write_line(f"<{cmd}>")
            self.display_text.insert(tk.END, f">> {cmd}\n")
            self.send_entry.delete(0, tk.END)
            
    def clear_display(self):
        self.display_text.delete(1.0, tk.END)
    
    def save_calibration(self):
        if not self.arduino.is_connected():
            messagebox.showwarning("Warning", "Not connected")
            return
        
        # Request current scale factor from Arduino
        self.waiting_for_scale = True
        self.arduino.write_line("<get_scale>")
        
        # Wait for response (with timeout)
        max_wait = 2000  # 2 seconds
        start = self.root.after(0, lambda: None)
        
        def check_response(waited=0):
            if not self.waiting_for_scale:
                # Got response
                filename = filedialog.asksaveasfilename(
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                )
                if filename:
                    try:
                        data = {
                            "scale_factor": self.current_scale_factor,
                            "port": self.port_combo.get(),
                            "baud_rate": int(self.baud_combo.get())
                        }
                        with open(filename, 'w') as f:
                            json.dump(data, f, indent=2)
                        messagebox.showinfo("Success", f"Calibration saved to:\n{filename}")
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to save:\n{str(e)}")
            elif waited < max_wait:
                self.root.after(50, lambda: check_response(waited + 50))
            else:
                self.waiting_for_scale = False
                messagebox.showerror("Error", "Timeout waiting for scale factor")
        
        self.root.after(50, check_response)
    
    def load_calibration(self):
        if not self.arduino.is_connected():
            messagebox.showwarning("Warning", "Not connected")
            return
        
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                
                scale_factor = data.get("scale_factor")
                if scale_factor:
                    self.arduino.write_line(f"<set_scale:{scale_factor}>")
                    messagebox.showinfo("Success", f"Calibration loaded!\nScale factor: {scale_factor}")
                else:
                    messagebox.showerror("Error", "Invalid calibration file")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load:\n{str(e)}")
    
    def toggle_recording(self):
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def start_recording(self):
        if not self.arduino.is_connected():
            messagebox.showwarning("Warning", "Not connected")
            return
        
        # Get filename and duration
        filename = self.filename_entry.get().strip()
        if not filename:
            messagebox.showerror("Error", "Please enter a filename")
            return
        
        try:
            duration = int(self.duration_entry.get())
            if duration <= 0:
                messagebox.showerror("Error", "Duration must be positive")
                return
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid duration")
            return
        
        # Add timestamp to filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_filename = f"{filename}_{timestamp}.csv"
        
        try:
            # Open CSV file
            self.csv_file = open(full_filename, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(['Timestamp', 'Elapsed_Time_s', 'Weight_g'])
            
            self.recording = True
            self.record_start_time = datetime.now()
            self.record_duration = duration
            
            # Update UI
            self.record_btn.config(text="Stop Recording")
            self.record_status.config(text=f"Recording to:\n{full_filename}", foreground="red")
            self.filename_entry.config(state="disabled")
            self.duration_entry.config(state="disabled")
            
            # Start measurement if not already measuring
            self.arduino.write_line("<start>")
            
            # Check duration
            self.check_recording_duration()
            
            messagebox.showinfo("Recording Started", f"Recording to:\n{full_filename}\nDuration: {duration} seconds")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start recording:\n{str(e)}")
            if self.csv_file:
                self.csv_file.close()
            self.recording = False
    
    def stop_recording(self):
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None
        
        self.recording = False
        self.record_btn.config(text="Start Recording")
        self.record_status.config(text="Status: Not recording", foreground="gray")
        self.filename_entry.config(state="normal")
        self.duration_entry.config(state="normal")
        
        messagebox.showinfo("Recording Stopped", "Recording has been saved")
    
    def record_measurement(self, data):
        # Only record numeric data (measurements)
        try:
            weight = float(data)
            timestamp = datetime.now()
            elapsed = (timestamp - self.record_start_time).total_seconds()
            
            self.csv_writer.writerow([
                timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                f"{elapsed:.3f}",
                f"{weight:.2f}"
            ])
            self.csv_file.flush()  # Ensure data is written immediately
            
        except ValueError:
            # Not a measurement, skip
            pass
    
    def check_recording_duration(self):
        if self.recording:
            elapsed = (datetime.now() - self.record_start_time).total_seconds()
            remaining = self.record_duration - elapsed
            
            if remaining > 0:
                self.record_status.config(
                    text=f"Recording...\n{remaining:.1f}s remaining",
                    foreground="red"
                )
                self.root.after(100, self.check_recording_duration)
            else:
                self.stop_recording()
        
    def on_closing(self):
        self.reading = False
        if self.recording:
            self.stop_recording()
        if self.arduino.is_connected():
            self.arduino.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ArduinoGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()