import serial
import serial.tools.list_ports
class serimane():
    def __init__(self):
        # Scan for available ports. return a list of tuples (num, name)
        self.portlist = serial.tools.list_ports.comports()
        self.port = None
        self.baudrate = 115200
        self.timeout = 1
        self.ser = None
        self.connected = False
        self.data = None

    def scan(self):
        return self.portlist
    
    def connect(self, port, baudrate=115200, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            self.connected = True
            return True
        except:
            return False
        
    def disconnect(self):
        self.ser.close()
        self.connected = False
        return True
    

    def read(self):
        if self.connected:
            self.data = self.ser.readline()
            return self.data
        else:
            return None
        
    def write(self, data):
        if self.connected:
            self.ser.write(data)
            return True
        else:
            return False
        
    def isConnected(self):
        return self.connected
    
    def getData(self):
        return self.data
    
    def getPort(self):
        return self.port
            

    def is_arduino(port):
        try:
            ser = serial.Serial(port)
            ser.close()
            return True
        except (OSError, serial.SerialException):
            return False

        # Get a list of all available serial ports
        available_ports = list(serial.tools.list_ports.comports())

        # Filter the list to find Arduino boards
        arduino_ports = [port[0] for port in available_ports if is_arduino(port[0])]

        if arduino_ports:
            if len(arduino_ports) == 1:
                # Automatically select the only available Arduino port
                selected_port = arduino_ports[0]
                print(f"Found Arduino on port: {selected_port}")
            else:
                print("Multiple Arduino boards found. Please specify the port.")
        else:
            print("No Arduino board found on any port.")
