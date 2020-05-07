# from .camera import *
from avr import *

from time import sleep
import os
import threading
import configparser

Modes=[{'implicit': 0, 'coding': 8, 'bandwidth': 20.8, 'spreading': 11, 'lowopt': 1},
       {'implicit': 1, 'coding': 5, 'bandwidth': 20.8, 'spreading':  6, 'lowopt': 0},
       {'implicit': 0, 'coding': 8, 'bandwidth': 62.5, 'spreading':  8, 'lowopt': 0},
       {'implicit': 0, 'coding': 6, 'bandwidth':  250, 'spreading':  7, 'lowopt': 0},
       {'implicit': 1, 'coding': 5, 'bandwidth':  250, 'spreading':  6, 'lowopt': 0},
       {'implicit': 0, 'coding': 8, 'bandwidth': 41.7, 'spreading': 11, 'lowopt': 0},
       {'implicit': 1, 'coding': 5, 'bandwidth': 41.7, 'spreading':  6, 'lowopt': 0}]
       
class Tracker(object):
    def __init__(self):
        self.camera = None
        self.comms = None
        self.SentenceCallback = None
        self.ImageCallback = None
        self._WhenNewPosition = None
        self._WhenNewSentence = None

        # General settings
        self.Settings_General_SerialDevice = '/dev/ttyAMA0';
        self.Settings_General_PayloadID = 'CHANGEME'
        self.Settings_General_FieldList = '01234569A'
        
        # LoRa settings
        self.Settings_LoRa_Frequency = 434.225
        self.Settings_LoRa_Mode = 1
        
        
        print ("FlexTrak Module Loaded")
        
    def GotNewSentence(self, Sentence):
        if self._WhenNewSentence:
            self._WhenNewSentence(Sentence)
        
    def GotNewPosition(self, Position):
        # print(str(Position['time']) + ',' + str(Position['lat']) + ', ' + str(Position['lon']) + ', ' + str(Position['alt']) + ', ' + str(Position['sats']))
        if self._WhenNewPosition:
            self._WhenNewPosition(Position)

    def LoadSettings(self, filename):
        if os.path.isfile(filename):
            print ('Loading config file ' + filename)
            config = configparser.RawConfigParser()   
            config.read(filename)
                                
            # General settings
            self.Settings_General_SerialDevice = config.get('General', 'SerialDevice')
            self.Settings_General_PayloadID = config.get('General', 'PayloadID')
            self.Settings_General_FieldList = config.get('General', 'FieldList')
            
            # GPS Settings
            self.Settings_GPS_FlightModeAltitude = config.get('GPS', 'FlightModeAltitude')
            
            # LoRa settings
            self.Settings_LoRa_Frequency = config.get('LORA', 'Frequency')
            self.Settings_LoRa_Mode = config.getint('LORA', 'Mode')
            
            
    def SendSettings(self):
        self.avr.AddCommand('CV');		# Request Firmware Version
        
        # // Common Settings
        self.avr.AddCommand('CP' + self.Settings_General_PayloadID)
        self.avr.AddCommand('CF' + self.Settings_General_FieldList);
        
        # // GPS Settings
        self.avr.AddCommand('GF' + str(self.Settings_GPS_FlightModeAltitude));
        
        # // LoRa Settings
        self.avr.AddCommand('LF' + str(self.Settings_LoRa_Frequency));
        
        self.avr.AddCommand('LI' + str(Modes[self.Settings_LoRa_Mode]['implicit']))
        self.avr.AddCommand('LE' + str(Modes[self.Settings_LoRa_Mode]['coding']))
        self.avr.AddCommand('LB' + str(Modes[self.Settings_LoRa_Mode]['bandwidth']))
        self.avr.AddCommand('LS' + str(Modes[self.Settings_LoRa_Mode]['spreading']))
        self.avr.AddCommand('LL' + str(Modes[self.Settings_LoRa_Mode]['lowopt']))
        
        # self.avr.AddCommand('LC' + str(self.Settings_LoRa_Count);
        # LORA_Count:			Integer;
        # LORA_CycleTime:		Integer;
        # LORA_Slot:			Integer;
        
        # // SSDV Settings
        # self.avr.AddCommand('SI' + str(Settings.SSDV_ImageCount))

        self.avr.AddCommand('CS');			# Store settings
    

    def set_lora(self, payload_id='CHANGEME', channel=0, frequency=424.250, mode=1, camera=False, image_packet_ratio=6):
        """

        This sets the LoRa payload ID, radio frequency, mode (use 0 for telemetry-only; 1 (which is faster) if you want to include images), and ratio of image packets to telemetry packets.

        Note that the LoRa stream will only include image packets if you add a camera schedule (see add_rtty_camera_schedule)
        """
        self.LoRaPayloadID = payload_id
        self.LoRaChannel = channel
        self.LoRaFrequency = frequency
        self.LoRaMode = mode
        self.LORAImagePacketsPerSentence = image_packet_ratio

        # self.lora = LoRa(Channel=self.LoRaChannel, Frequency=self.LoRaFrequency, Mode=self.LoRaMode, DIO0=DIO0)

    def add_camera_schedule(self, path='images/LORA', period=60, width=640, height=480):
        """
        Adds a LoRa camera schedule.  The default parameters are for an image of size 640x480 pixels every 60 seconds and the resulting file saved in the images/LORA folder.
        """
        if not self.camera:
            self.camera = SSDVCamera()
        if self.LoRaMode == 1:
            print("Enable camera for LoRa")
            self.camera.add_schedule('LoRa0', self.LoRaPayloadID, path, period, width, height)
        else:
            print("LoRa camera schedule not added - LoRa mode needs to be set to 1 not 0")

    def add_full_camera_schedule(self, path='images/FULL', period=60, width=0, height=0):
        """
        Adds a camera schedule for full-sized images.  The default parameters are for an image of full sensor resolution, every 60 seconds and the resulting file saved in the images/FULL folder.
        """
        if not self.camera:
            self.camera = SSDVCamera()
        self.camera.add_schedule('FULL', '', path, period, width, height)

    def set_sentence_callback(self, callback):
        """
        This specifies a function to be called whenever a telemetry sentence is built.  That function should return a string containing a comma-separated list of fields to append to the telemetry sentence.
        """
        self.SentenceCallback = callback

    def set_image_callback(self, callback):
        """
        The callback function is called whenever an image is required.  **If you specify this callback, then it's up to you to provide code to take the photograph (see tracker.md for an example)**.
        """
        self.ImageCallback = callback

    def __ImageCallback(self, filename, width, height):
        self.ImageCallback(filename, width, height, self.gps)


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

    def __tracker_thread(self):
        while True:
            sleep(0.01)

    def start(self):
        """
        Starts the tracker.
        """

        self.avr = AVR(self.Settings_General_SerialDevice)
        self.avr.WhenNewSentence = self.GotNewSentence
        self.avr.WhenNewPosition = self.GotNewPosition
        self.avr.start()
        
        self.SendSettings()

        if self.camera:
            if self.ImageCallback:
                self.camera.take_photos(self.__ImageCallback)
            else:
                self.camera.take_photos(None)

        t = threading.Thread(target=self.__tracker_thread)
        t.daemon = True
        t.start()
