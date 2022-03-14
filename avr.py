import math
import serial
import threading
import time
import datetime

class AVR(object):
    PortOpen = False
    
    def __init__(self, Device='/dev/ttyAMA0', GPSFileName=''):
        print ("AVR module init - device " + Device)
        self._WhenLockGained = None
        self._WhenLockLost = None
        self._WhenNewPosition = None
        self._WhenNewSentence = None
        self._WhenNewBattery = None  # Callback for Battery voltage
        self._WhenNewTemperatureInternal = None  # Callback for internal temperature
        self._WhenNewTemperatureExternal = None  # Callback for external temperature
        self._WhenNewVersion = None  # Callback for version
        self._WhenSSDVReady = None
        self.IsOpen = False
        
        self.GPSPosition = {'time': '00:00:00', 'lat': 0.0, 'lon': 0.0, 'alt': 0, 'sats': 0, 'fixtype': 0}
        self.Sensors = {'battery_voltage': 0.0, 'internal_temperature': 0.0, 'external_temperature': 0.0, 'version': ''}
        
        # Serial port /dev/ttyAMA0
        self.ser = serial.Serial()
        self.ser.baudrate = 38400
        self.ser.stopbits = 1
        self.ser.bytesize = 8
        self.ser.timeout = 0
        self.ser.port = Device
        
        self.Commands = []
        
        # NMEA file
        if GPSFileName != '':
            self.GPSFile = open(GPSFileName, "r")
        else:
            self.GPSFile = None
            
    def SendPacket(self, Packet):
        HexString = Packet.hex()
        self.AddCommand('CH1')     # High priority mode
        for i in range(8):
            Start = i * 64
            End = Start + 64
            Section = HexString[Start : End]
            print(Section)
            self.AddCommand('SP' + Section)
        self.AddCommand('CH0')     # Normal priority mode
            
    def FixPosition(self, Position):
        Position = Position / 100

        MinutesSeconds = math.modf(Position)

        return MinutesSeconds[1] + MinutesSeconds[0] * 5 / 3            
    
    def ProcessNMEALine(self):
        Line = self.GPSFile.readline()
        if Line:
            # $GPGGA,113123.00,5215.18419,N,00005.56047,W,1,11,0.85,533.3,M,45.8,M,,*4C
            # $GPGGA,122008.00,5224.62734,N,00010.14499,E,1,11,0.81,15103.3,M,45.7,M,,*5A
            Fields = Line.split(',')

            if Fields[1] != '':
                # GPSPosition['time'] = Fields[1][0:2] + ':' + Fields[1][2:4] + ':' + Fields[1][4:6]
                if Fields[2] != '':
                    self.GPSPosition['lat'] = self.FixPosition(float(Fields[2]))
                    if Fields[3] == 'S':
                        self.GPSPosition['lat'] = -self.GPSPosition['lat']
                    self.GPSPosition['lon'] = self.FixPosition(float(Fields[4]))
                    if Fields[5] == 'W':
                        self.GPSPosition['lon'] = -self.GPSPosition['lon']
                    self.GPSPosition['alt'] = float(Fields[9])
            self.GPSPosition['sats'] = int(Fields[7])
        else:
            self.GPSFile = None
        

    def ProcessCommand(self, Command, Parameters):       
        if Command == 'SSDV':
            if Parameters == '0':
                print("SSDV BUFFER EMPTY")
                if self._WhenSSDVReady:
                    self._WhenSSDVReady()
            else:
                print(Command + ' = ' + Parameters)
        elif Command == 'GPS':
            # GPS=12:6:41,51.95056,-2.54472,102,6
            Fields = Parameters.split(',')
            
            if Fields[1] != '':
                self.GPSPosition['time'] = datetime.datetime.strptime(Fields[0] + ' ' + Fields[1], '%d/%m/%Y %H:%M:%S')

                if Fields[1] != '':
                    self.GPSPosition['lat'] = float(Fields[2])
                    self.GPSPosition['lon'] = float(Fields[3])
                    self.GPSPosition['alt'] = float(Fields[4])

                self.GPSPosition['sats'] = int(Fields[5])
                
                # Replace with data from NMEA file ?
                if self.GPSFile:
                    self.ProcessNMEALine()
                
                if self._WhenNewPosition:
                    self._WhenNewPosition(self.GPSPosition)
        elif Command == 'LORA':

            if self._WhenNewSentence:
                self._WhenNewSentence(Parameters)
        elif Command == 'BATT':
            self.Sensors['battery_voltage'] = float(Parameters) / 1000.0
            if self._WhenNewBattery:
                self._WhenNewBattery(self.Sensors['battery_voltage'])
        elif Command == 'TEMP0':
            self.Sensors['internal_temperature'] = float(Parameters)
            if self._WhenNewTemperatureInternal:
                self._WhenNewTemperatureInternal(self.Sensors['internal_temperature'])
        elif Command == 'TEMP1':
            self.Sensors['external_temperature'] = float(Parameters)
            if self._WhenNewTemperatureExternal:
                self._WhenNewTemperatureExternal(self.Sensors['external_temperature'])
        elif Command == 'VER':
            self.Sensors['version'] = Parameters
            if self._WhenNewVersion:
                self._WhenNewVersion(self.Sensors['version'])

        else:
           print("UNKNOWN RESPONSE " + Command + '=' + Parameters)

    def ProcessLine(self, Line):
        
        print('Rx: ' + Line);
        
        if Line == '*':
            print(Line)
            self.Commands = self.Commands[1:]
            self.CanSendNextCommand = True
        else:
            fields = Line.split('=', 2)
            
            if len(fields) == 2:
                self.ProcessCommand(fields[0].upper(), fields[1])
            else:
                pass
                # print(Line)
                
    def AddCommand(self, Command):
        self.Commands.append(Command)
        
    def __comms_thread(self):
        print ("Comms thread")
        self.CanSendNextCommand = True
        Line = ''
        TimeOut = 0
        HighPriorityMode = False

        while True:
            if self.IsOpen:
                # Do incoming characters
                Byte = self.ser.read(1)
                
                if len(Byte) > 0:
                    Character = chr(Byte[0])

                    if len(Line) > 256:
                        Line = ''
                    elif Character != '\r':
                        if Character == '\n':
                            self.ProcessLine(Line)
                            
                            Line = ''
                            time.sleep(0.01)
                        else:
                            Line = Line + Character
                else:
                    if not HighPriorityMode:
                        time.sleep(0.01)
                
                
                if self.CanSendNextCommand or (TimeOut <= 0):
                    if len(self.Commands) > 0:
                        # print("CAN SEND")
                        Command = '~' + self.Commands[0] + '\r\n'
                        self.ser.write(Command.encode())
                        print ('TX: ' + self.Commands[0])
                        if self.Commands[0] == 'CH1':
                            HighPriorityMode = True
                        if self.Commands[0] == 'CH0':
                            HighPriorityMode = False
                        TimeOut = 2000
                        self.CanSendNextCommand = False
                
                    
                if TimeOut > 0:
                    TimeOut -= 1
                        
            else:
                print("Waiting for port")
                time.sleep(1)

    def open(self):
        # Open connection to FlexTrak board
        try:
            self.ser.open()
            self.IsOpen = True
            print ("AVR module connected")
        except:
            self.IsOpen = False
            print ("AVR module connection failed")
    
    def Position(self):
        return GPSPosition
                  
    @property
    def WhenLockGained(self):
        return self._WhenLockGained

    @WhenLockGained.setter
    def WhenLockGained(self, value):
        self._WhenLockGained = value
    
    @property
    def WhenLockLost(self):
        return self._WhenLockLost

    @WhenLockLost.setter
    def WhenLockGained(self, value):
        self._WhenLockLost = value
    
    @property
    def WhenNewSentence(self):
        return self._WhenNewSentence

    @WhenNewSentence.setter
    def WhenNewSentence(self, value):
        self._WhenNewSentence = value
    
    @property
    def WhenNewPosition(self):
        return self._WhenNewPosition

    @WhenNewPosition.setter
    def WhenNewPosition(self, value):
        self._WhenNewPosition = value
    
    @property
    def WhenSSDVReady(self):
        return self._WhenSSDVReady
        
    @WhenSSDVReady.setter
    def WhenSSDVReady(self, value):
        self._WhenSSDVReady = value

    # Callback for battery voltage
    @property
    def WhenNewBattery(self):
        return self._WhenNewBattery

    @WhenNewBattery.setter
    def WhenNewBattery(self, value):
        self._WhenNewBattery = value

    # Callback for internal temperature
    @property
    def WhenNewTemperatureInternal(self):
        return self._WhenNewTemperatureInternal

    @WhenNewTemperatureInternal.setter
    def WhenNewTemperatureInternal(self, value):
        self._WhenNewTemperatureInternal = value

    # Callback for external temperature
    @property
    def WhenNewTemperatureExternal(self):
        return self._WhenNewTemperatureExternal

    @WhenNewTemperatureExternal.setter
    def WhenNewTemperatureExternal(self, value):
        self._WhenNewTemperatureExternal = value

    # Callback for version
    @property
    def WhenNewVersion(self):
        return self._WhenNewVersion

    @WhenNewVersion.setter
    def WhenNewVersion(self, value):
        self._WhenNewVersion = value

    def start(self):
        print ("Comms module started")
        self.open()
        t = threading.Thread(target=self.__comms_thread)
        t.daemon = True
        t.start()
