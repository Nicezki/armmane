import serial
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
    
    def getBaudrate(self):
        return self.baudrate
    
    def getTimeout(self):
        return self.timeout
    
    def getSerial(self):
        return self.ser