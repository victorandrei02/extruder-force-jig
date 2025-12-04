import serial
import serial.tools.list_ports
import time

class ArduinoController:

    def __init__(self, port=None, baud=115200, timeout=1):
        '''
        Initialize the Arduino Controller
        
        :param port: COM port (eg. 'COM3')
        :param baudrate: arduino baudrate
        :param timeout: Read timeout in seconds (default: 1)
        '''

        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser = None
        self.connected = False

    @staticmethod
    def list_ports():
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
    @staticmethod
    def get_ports_info():
        ports = serial.tools.list_ports.comports()
        return [(port.device, port.description, port.hwid) for port in ports]
    
    def connect(self, port=None, baudrate=None, timeout = 5):
        if self.connected:
            return
        if port:
            self.port = port
        if baudrate:
            self.baud = baudrate
        
        if not self.port:
            raise ValueError("Port not specified")
        
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=self.timeout
            )
            
            start_time = time.time()
            received_ready = False
        
            while (time.time() - start_time) < timeout:
                if self.ser.in_waiting > 0:
                    char = self.ser.read(1).decode('utf-8', errors='ignore')
                    if char == 'r':
                        received_ready = True
                        break
        
            if not received_ready:
                self.ser.close()
                self.connected = False
                raise ConnectionError(f"Arduino did not send ready signal 'r' within {timeout} seconds")
        
            self.connected = True
            return True
        except serial.SerialException as e:
            self.connected = False
            raise ConnectionError(f"Failed to connect to {self.port}: {str(e)}")
        
    def disconnect(self):
        if self.ser and self.connected:
            self.ser.close()
        self.connected = False

    def is_connected(self):
        return self.connected
    
    def write(self, data):
        if not self.is_connected:
            raise ConnectionError("Not connected to Arduino")
        
        if isinstance(data, str):
            data = data.encode('utf-8')

        return self.ser.write(data)
    
    def write_line(self, data):
        if not data.endswith("\n"):
            data += '\n'
        return self.write(data)
    
    def read(self, size=1):
        if not self.is_connected():
            raise ConnectionError("Not connected to Arduino")
        return self.ser.read(size)
    
    def read_line(self):
        if not self.is_connected():
            raise ConnectionError("Not connected to Arduino")
        
        if self.ser.in_waiting > 0:
            return self.ser.readline().decode('utf-8', errors='ignore').strip()
        return ""
    
    def available(self):
        if not self.is_connected():
            raise ConnectionError("Not connected to Arduino")
        return self.ser.in_waiting
    
    def flush(self):
        if self.is_connected():
            self.ser.flush()

    def __del__(self):
        self.disconnect()