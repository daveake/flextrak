from flextrak import *
from time import sleep

def take_photo(filename, width, height, gps):
	# sample code to take a photo
	# Use the gps object if you want to add a telemetry overlay, or use different image sizes at different altitudes, for example
	with picamera.PiCamera() as camera:
		camera.resolution = (width, height)
		camera.start_preview()
		time.sleep(2)
		camera.capture(filename)
		camera.stop_preview()					

def GotNewSentence(Sentence):
    print(Sentence)

def GotNewPosition(Position):
    print(str(Position['time']) + ', ' + "{:.5f}".format(Position['lat']) + ', ' + "{:.5f}".format(Position['lon']) + ', ' + str(Position['alt']) + ', ' + str(Position['sats']))

def GotNewBattery(battery):
	print('Battery voltage is', battery, 'V')

def GotNewTemperatureInternal(temp):
	print('Temperature internal is', temp, '°C')

def GotNewTemperatureExternal(temp):
	print('Temperature external is', temp, '°C')

def GotNewPrediction(prediction):
	print('Prediction is', prediction)

print ("Load tracker ...")
mytracker = Tracker()

mytracker.LoadSettings("flextrak.ini")

# Callbacks
mytracker.WhenNewSentence = GotNewSentence
mytracker.WhenNewPosition = GotNewPosition
mytracker.WhenNewBattery = GotNewBattery
mytracker.WhenNewTemperatureInternal = GotNewTemperatureInternal
mytracker.WhenNewTemperatureExternal = GotNewTemperatureExternal
mytracker.WhenNewPrediction = GotNewPrediction

print ("Start tracker ...")
mytracker.start()

print ("Loop ...")
while True:
    # if you have extra sensor values to include in the telemetry, add them with lines like:
    # mytracker.AddField(0, 12)
    # The first value (0) is the field number from 0 to 3
    # The second valve (12) is the value of that field

    # ** If you are using floating point values, then scale them to be integers.  **

    # The tracker will include this new value until you call thus routine with a different value
    #
    # ** VERY IMPORTANT **
    #
    # You also need to include the field in the field list.  These fields are I (field 0), through N (field 5).

    sleep(5)
