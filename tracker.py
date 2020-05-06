from flextrak import *
from time import sleep

def extra_telemetry():
	# Return any extra fields as CSV string
    return ""

def take_photo(filename, width, height, gps):
	# sample code to take a photo
	# Use the gps object if you want to add a telemetry overlay, or use different image sizes at different altitudes, for example
	with picamera.PiCamera() as camera:
		camera.resolution = (width, height)
		camera.start_preview()
		time.sleep(2)
		camera.capture(filename)
		camera.stop_preview()					

def GotNewPosition(Position):
    print(str(Position['time']) + ',' + str(Position['lat']) + ', ' + str(Position['lon']) + ', ' + str(Position['alt']) + ', ' + str(Position['sats']))

print ("Load tracker ...")
mytracker = Tracker()

mytracker.LoadSettings("flextrak.ini")

# mytracker.set_sentence_callback(extra_telemetry)

# mytracker.set_image_callback(take_photo)

mytracker.WhenNewPosition = GotNewPosition

print ("Start tracker ...")
mytracker.start()

print ("Loop ...")
while True:
	sleep(1)
