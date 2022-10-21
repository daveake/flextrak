from camera import *
from avr import *
from prediction import *
from time import sleep
import os
import threading
import configparser

Modes=[{'implicit': 0, 'coding': 8, 'bandwidth': 3, 'spreading': 11, 'lowopt': 1},
       {'implicit': 1, 'coding': 5, 'bandwidth': 3, 'spreading':  6, 'lowopt': 0},
       {'implicit': 0, 'coding': 8, 'bandwidth': 6, 'spreading':  8, 'lowopt': 0},
       {'implicit': 0, 'coding': 6, 'bandwidth': 8, 'spreading':  7, 'lowopt': 0},
       {'implicit': 1, 'coding': 5, 'bandwidth': 8, 'spreading':  6, 'lowopt': 0},
       {'implicit': 0, 'coding': 8, 'bandwidth': 5, 'spreading': 11, 'lowopt': 0},
       {'implicit': 1, 'coding': 5, 'bandwidth': 5, 'spreading':  6, 'lowopt': 0}]

def StringToBoolean(Value):
    return (Value + 'F')[0] in ('1', 'T', 't', 'Y', 'y')

def GetConfigInteger(config, section, value, default):
    try:
        return config.getint(section, value)
    except:
        return default

def GetConfigBoolean(config, section, value, default):
    try:
        return StringToBoolean(config.get(section, value))
    except:
        return default
        
def GetConfigString(config, section, value, default):
    try:
        return config.get(section, value)
    except:
        return default

class Tracker(object):
    def __init__(self):
        self.camera = None
        self.comms = None
        self.SentenceCallback = None
        self.ImageCallback = None
        self._WhenNewPosition = None
        self._WhenNewSentence = None
        self._WhenNewBattery = None
        self._WhenNewTemperatureInternal = None
        self._WhenNewTemperatureExternal = None
        self._WhenNewVersion = None
        self._WhenNewPrediction = None
        self.SendNextSSDVPacket = False
        self.Predictor = None

        # General settings
        self.Settings_General_SerialDevice = '/dev/ttyAMA0';
        self.Settings_General_PayloadID = 'CHANGEME'
        self.Settings_General_FieldList = '01234569A'
        self.Settings_General_SendFieldList = False
        self.Settings_General_FakeGPS = ''
        
        # LoRa settings
        self.Settings_LoRa_Frequency = 434.225
        self.Settings_LoRa_Mode = 1      
        
        # APRS Settings
        self.Settings_APRS_Callsign = ''
        
        print ("FlexTrak Module Loaded")
        
    def GotNewSentence(self, Sentence):
        if self._WhenNewSentence:
            self._WhenNewSentence(Sentence)
        
    def GotNewPosition(self, Position):
        # print(str(Position['time']) + ',' + str(Position['lat']) + ', ' + str(Position['lon']) + ', ' + str(Position['alt']) + ', ' + str(Position['sats']))
        if self._WhenNewPosition:
            self._WhenNewPosition(Position)
        
        # Send to AVR if we are faking GPS
        if self.Settings_General_FakeGPS != '':
            self.avr.AddCommand('FT' + "{:.5f}".format(Position['lat']))
            self.avr.AddCommand('FG' + "{:.5f}".format(Position['lon']))
            self.avr.AddCommand('FU' + str(int(Position['alt'])))

        # Send to predictor
        if self.Predictor:
            LandingPrediction = self.Predictor.AddGPSPosition(Position)
            if LandingPrediction:
                # Should get one of these during flight, every 5 seconds currently
                # Send to AVR
                self.avr.AddCommand('FA' + "{:.5f}".format(LandingPrediction['pred_lat']))
                self.avr.AddCommand('FO' + "{:.5f}".format(LandingPrediction['pred_lon']))

        # Send to camera
        if self.camera:
            self.camera.SetAltitude(Position['alt'])

    def SSDVBufferEmpty(self):
        self.SendNextSSDVPacket = True
    
    def AddField(self, FieldIndex, FieldValue):
        if (FieldIndex >= 0) and (FieldIndex <= 5):
            self.avr.AddCommand('F' + str(FieldIndex) + "{:.1f}".format(FieldValue))

    def LoadSettings(self, filename):
        if os.path.isfile(filename):
            print ('Loading config file ' + filename)
            config = configparser.RawConfigParser()   
            config.read(filename)
                                
            # General settings
            self.Settings_General_SerialDevice = config.get('General', 'SerialDevice')
            print ('Serial device ' + self.Settings_General_SerialDevice)
            self.Settings_General_PayloadID = config.get('General', 'PayloadID')
            print ('Payload ID ' + self.Settings_General_PayloadID)
            self.Settings_General_FieldList = config.get('General', 'FieldList')
            self.Settings_General_SendFieldList = GetConfigBoolean(config, 'General', 'SendFieldList', False)
            try:
                self.Settings_General_FakeGPS = config.get('General', 'FakeGPS')
            except:
                pass
                
            self.Settings_Cutdown_Altitude = GetConfigInteger(config, 'Cutdown', 'Altitude', 0)
            self.Settings_Cutdown_Time = GetConfigInteger(config, 'Cutdown', 'Time', 5)
            
            # GPS Settings
            self.Settings_GPS_FlightModeAltitude = config.get('GPS', 'FlightModeAltitude')
            
            # LoRa settings
            self.Settings_LoRa_Frequency = config.get('LORA', 'Frequency')
            self.Settings_LoRa_Mode = config.getint('LORA', 'Mode')
            self.Settings_LoRa_Cycle = GetConfigInteger(config, 'LORA', 'Cycle', 0)
            self.Settings_LoRa_Slot = GetConfigInteger(config, 'LORA', 'Slot', -1)
            self.Settings_LoRa_UplinkCode = GetConfigString(config, 'LORA', 'Uplink', '')
            
            # Camera settings
            # Altitude for switching image sizes and packet rates
            self.Settings_Camera_Enabled = GetConfigBoolean(config, 'Camera', 'Enabled', True)
            if self.Settings_Camera_Enabled:
                self.Settings_Camera_High = config.getint('Camera', 'High')
                self.Settings_Camera_Rotate = StringToBoolean(config.get('Camera', 'Rotate'))
                
                # Full settings, low altitude
                self.Settings_Camera_LowFullPeriod = config.getint('Camera', 'LowFullPeriod')
                self.Settings_Camera_LowFullWidth = config.getint('Camera', 'LowFullWidth')
                self.Settings_Camera_LowFullHeight = config.getint('Camera', 'LowFullHeight')
                    
                # Full settings, high altitude
                self.Settings_Camera_HighFullPeriod = config.getint('Camera', 'HighFullPeriod')
                self.Settings_Camera_HighFullWidth = config.getint('Camera', 'HighFullWidth')
                self.Settings_Camera_HighFullHeight = config.getint('Camera', 'HighFullHeight')
                
                # Add schedule for full size images
                if (self.Settings_Camera_LowFullPeriod > 0) or (self.Settings_Camera_HighFullPeriod > 0):
                    self.add_full_camera_schedule(lowperiod=self.Settings_Camera_LowFullPeriod, lowwidth=self.Settings_Camera_LowFullWidth, lowheight=self.Settings_Camera_LowFullHeight,
                                                  highperiod=self.Settings_Camera_HighFullPeriod, highwidth=self.Settings_Camera_HighFullWidth, highheight=self.Settings_Camera_HighFullHeight)
                    
                # Radio settings, low altitude
                self.Settings_Camera_LowRadioPeriod = config.getint('Camera', 'LowRadioPeriod')
                self.Settings_Camera_LowRadioWidth = config.getint('Camera', 'LowRadioWidth')
                self.Settings_Camera_LowRadioHeight = config.getint('Camera', 'LowRadioHeight')
                               
                # Full settings, high altitude
                self.Settings_Camera_HighRadioPeriod = config.getint('Camera', 'HighRadioPeriod')
                self.Settings_Camera_HighRadioWidth = config.getint('Camera', 'HighRadioWidth')
                self.Settings_Camera_HighRadioHeight = config.getint('Camera', 'HighRadioHeight')
                #self.add_lora_camera_schedule(callsign=self.Settings_General_PayloadID, period=self.Settings_Camera_RadioPeriod, width=self.Settings_Camera_RadioWidth, height=self.Settings_Camera_RadioHeight)
                
                # Add schedule for radio
                if (self.Settings_Camera_LowRadioPeriod > 0) or (self.Settings_Camera_HighRadioPeriod):
                    self.add_lora_camera_schedule(callsign=self.Settings_General_PayloadID,
                                                  lowperiod=self.Settings_Camera_LowRadioPeriod, lowwidth=self.Settings_Camera_LowRadioWidth, lowheight=self.Settings_Camera_LowRadioHeight,
                                                  highperiod=self.Settings_Camera_HighRadioPeriod, highwidth=self.Settings_Camera_HighRadioWidth, highheight=self.Settings_Camera_HighRadioHeight)
                # SSDV settings
                self.Settings_SSDV_LowImageCount = config.getint('SSDV', 'LowImageCount')
                self.Settings_SSDV_HighImageCount = config.getint('SSDV', 'HighImageCount')
            
            # Predictor settings
            self.Settings_Prediction_Enabled = StringToBoolean(config.get('Prediction', 'Enabled'))
            self.Settings_Prediction_LandingAltitude = config.getint('Prediction', 'LandingAltitude')
            self.Settings_Prediction_DefaultCDA = config.getfloat('Prediction', 'DefaultCDA')

            # APRS settings
            try:
                self.Settings_APRS_Callsign = config.get('APRS', 'Callsign')
                self.Settings_APRS_SSID = config.getint('APRS', 'SSID')
                self.Settings_APRS_Frequency = config.getfloat('APRS', 'Frequency')
                self.Settings_APRS_WideAltitude = config.getint('APRS', 'WideAltitude')
                self.Settings_APRS_HighUseWide2 = StringToBoolean(config.get('APRS', 'HighUseWide2'))
                self.Settings_APRS_TxInterval = config.getint('APRS', 'TxInterval')
                self.Settings_APRS_PreEmphasis = StringToBoolean(config.get('APRS', 'PreEmphasis'))
                self.Settings_APRS_Random = config.getint('APRS', 'Random')
                self.Settings_APRS_TelemInterval = config.getint('APRS', 'TelemInterval')
            except:
                self.Settings_APRS_Callsign = ''
            
    def SendSettings(self):
        self.avr.AddCommand('CH0')      # Low priority mode

        self.avr.AddCommand('CV');		# Request Firmware Version
        
        # // Common Settings
        self.avr.AddCommand('CP' + self.Settings_General_PayloadID)
        self.avr.AddCommand('CF' + self.Settings_General_FieldList)
        self.avr.AddCommand('CL' + str(int(self.Settings_General_SendFieldList)))
        
        # // GPS Settings
        self.avr.AddCommand('GF' + str(self.Settings_GPS_FlightModeAltitude))

        # Cutdown Settings
        self.avr.AddCommand('CC' + str(self.Settings_Cutdown_Altitude))
        self.avr.AddCommand('CT' + str(self.Settings_Cutdown_Time))

        # // LoRa Settings
        self.avr.AddCommand('LF' + str(self.Settings_LoRa_Frequency))
        
        self.avr.AddCommand('LI' + str(Modes[self.Settings_LoRa_Mode]['implicit']))
        self.avr.AddCommand('LE' + str(Modes[self.Settings_LoRa_Mode]['coding']))
        self.avr.AddCommand('LB' + str(Modes[self.Settings_LoRa_Mode]['bandwidth']))
        self.avr.AddCommand('LS' + str(Modes[self.Settings_LoRa_Mode]['spreading']))
        self.avr.AddCommand('LL' + str(Modes[self.Settings_LoRa_Mode]['lowopt']))
        
        self.avr.AddCommand('LT' + str(self.Settings_LoRa_Cycle));
        self.avr.AddCommand('LO' + str(self.Settings_LoRa_Slot));
        
        self.avr.AddCommand('LU' + str(self.Settings_LoRa_UplinkCode));
        
        # // SSDV Settings
        if self.Settings_Camera_Enabled:
            self.avr.AddCommand('SI' + str(self.Settings_SSDV_LowImageCount) + ',' + str(self.Settings_SSDV_HighImageCount) + ',' + str(self.Settings_Camera_High))

        # APRS settings
        print("APRS: " + self.Settings_APRS_Callsign)
        self.avr.AddCommand('AP' + self.Settings_APRS_Callsign)
        if self.Settings_APRS_Callsign != '':
            self.avr.AddCommand('AS' + str(self.Settings_APRS_SSID))
            self.avr.AddCommand('AF' + "{:.3f}".format(self.Settings_APRS_Frequency))
            self.avr.AddCommand('AA' + str(self.Settings_APRS_WideAltitude))
            self.avr.AddCommand('AI' + str(int(self.Settings_APRS_HighUseWide2)))
            self.avr.AddCommand('AI' + str(self.Settings_APRS_TxInterval))
            self.avr.AddCommand('AM' + str(int(self.Settings_APRS_PreEmphasis)))
            self.avr.AddCommand('AR' + str(self.Settings_APRS_Random))
            self.avr.AddCommand('AT' + str(self.Settings_APRS_TelemInterval))

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

    def add_lora_camera_schedule(self, callsign='SSDV', path='images/LORA', lowperiod=60, lowwidth=320, lowheight=240, highperiod=30, highwidth=640, highheight=480):
        """
        Adds a LoRa camera schedule.  The default parameters are for an image of size 640x480 pixels every 60 seconds and the resulting file saved in the images/LORA folder.
        """
        if not self.camera:
            self.camera = SSDVCamera(self.Settings_Camera_High, self.Settings_Camera_Rotate)
        print("Enable camera for LoRa")
        self.camera.add_schedule('LoRa', callsign, path, lowperiod, lowwidth, lowheight, highperiod, highwidth, highheight)

    def add_full_camera_schedule(self, path='images/FULL', lowperiod=60, lowwidth=0, lowheight=0, highperiod=30, highwidth=0, highheight=0):
        """
        Adds a camera schedule for full-sized images.  The default parameters are for an image of full sensor resolution, every 60 seconds and the resulting file saved in the images/FULL folder.
        """
        if not self.camera:
            self.camera = SSDVCamera(self.Settings_Camera_High, self.Settings_Camera_Rotate)
        self.camera.add_schedule('FULL', '', path, lowperiod, lowwidth, lowheight, highperiod, highwidth, highheight)

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

    @property
    def WhenNewBattery(self):
        return self._WhenNewBattery

    @WhenNewBattery.setter
    def WhenNewBattery(self, value):
        self._WhenNewBattery = value

    @property
    def WhenNewTemperatureInternal(self):
        return self._WhenNewTemperatureInternal

    @WhenNewTemperatureInternal.setter
    def WhenNewTemperatureInternal(self, value):
        self._WhenNewTemperatureInternal = value

    @property
    def WhenNewTemperatureExternal(self):
        return self._WhenNewTemperatureExternal

    @WhenNewTemperatureExternal.setter
    def WhenNewTemperatureExternal(self, value):
        self._WhenNewTemperatureExternal = value

    @property
    def WhenNewPrediction(self):
        return self._WhenNewPrediction

    @WhenNewPrediction.setter
    def WhenNewPrediction(self, value):
        self._WhenNewPrediction = value

    @property
    def WhenNewVersion(self):
        return self._WhenNewVersion

    @WhenNewVersion.setter
    def WhenNewVersion(self, value):
        self._WhenNewVersion = value

    def __tracker_thread(self):
        while True:
            # test if we need to send next SSDV packet yet
            if self.camera:
                if self.SendNextSSDVPacket:
                    # print ("GET NEXT SSDV PACKET")
                    Packet = self.camera.get_next_ssdv_packet('LoRa')
                    if Packet:
                        self.SendNextSSDVPacket = False
                        print ("GOT NEXT SSDV PACKET")
                        self.avr.SendPacket(Packet)
                    
            sleep(0.01)

    def start(self):
        """
        Starts the tracker.
        """

        # AVR
        self.avr = AVR(self.Settings_General_SerialDevice, self.Settings_General_FakeGPS)
        self.avr.WhenNewSentence = self.GotNewSentence
        self.avr.WhenNewPosition = self.GotNewPosition
        self.avr.WhenNewBattery = self._WhenNewBattery
        self.avr.WhenNewTemperatureInternal = self._WhenNewTemperatureInternal
        self.avr.WhenNewTemperatureExternal = self._WhenNewTemperatureExternal
        self.avr.WhenNewVersion = self._WhenNewVersion
        self.avr.WhenSSDVReady = self.SSDVBufferEmpty
        
        self.avr.start()
        
        self.SendSettings()

        self.avr.AddCommand('SC');		# Clear SSDV buffer
        self.avr.AddCommand('SS');		# Request SSDV status
        
        # Camera
        if self.camera:
            if self.ImageCallback:
                self.camera.take_photos(self.__ImageCallback)
            else:
                self.camera.take_photos(None)

        # Predictor
        if self.Settings_Prediction_Enabled:
            self.Predictor = Predictor(self.Settings_Prediction_LandingAltitude, self.Settings_Prediction_DefaultCDA)
            if self.WhenNewPrediction:
                self.Predictor.WhenNewPrediction = self._WhenNewPrediction

        t = threading.Thread(target=self.__tracker_thread)
        t.daemon = True
        t.start()
