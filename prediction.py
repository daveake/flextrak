from enum import Enum
import math

class FlightMode(Enum):
    fmIdle          = 0
    fmLaunched      = 1
    fmDescending    = 2
    fmLanded        = 3

class Delta():
    def __init__(self, latitude, longitude):
        self.latitude = latitude 
        self.longitude = longitude
        
class Predictor(object):
    def __init__(self, LandingAltitude, DefaultCDA):
        self.SlotSize = 100
        self.SlotCount = 60000 // self.SlotSize
        self.Deltas = []
        self.FlightMode = FlightMode.fmIdle
        self.PreviousPosition = {'time': '00:00:00', 'lat': 0.0, 'lon': 0.0, 'alt': 0, 'sats': 0, 'fixtype': 0}
        self.MinimumAltitude = 0
        self.MaximumAltitude = 0
        self.AscentRate = 0
        self.LandingAltitude = LandingAltitude
        self.LandingLatitude = 0.0
        self.LandingLongitude = 0.0
        self.PollPeriod = 5
        self.Counter = 0
        self.CDA = DefaultCDA
        for i in range(self.SlotCount):
            self.Deltas.append(Delta(0,0))


    def GetSlot(self, Altitude):
        Slot = int(Altitude // self.SlotSize)

        if Slot < 0:
            Slot = 0
        if Slot >= self.SlotSize:
            Slot = self.SlotSize-1

        return Slot

    def CalculateAirDensity(self, Altitude):
        if Altitude < 11000.0:
            # below 11Km - Troposphere
            Temperature = 15.04 - (0.00649 * Altitude)
            Pressure = 101.29 * pow((Temperature + 273.1) / 288.08, 5.256)
        elif Altitude < 25000.0:
            # between 11Km and 25Km - lower Stratosphere
            Temperature = -56.46
            Pressure = 22.65 * math.exp(1.73 - ( 0.000157 * Altitude))
        else:
            # above 25Km - upper Stratosphere
            Temperature = -131.21 + (0.00299 * Altitude)
            Pressure = 2.488 * math.pow((Temperature + 273.1) / 216.6, -11.388)

        return Pressure / (0.2869 * (Temperature + 273.1))

    def CalculateDescentRate(self, Weight, CDTimesArea, Altitude):
        Density = self.CalculateAirDensity(Altitude)
	
        return math.sqrt((Weight * 9.81)/(0.5 * Density * CDTimesArea))
            
    def CalculateCDA(self, Weight, Altitude, DescentRate):
        if DescentRate > 0.0:
            Density = self.CalculateAirDensity(Altitude)
	
            # printf("Alt %.0lf, Rate %.1lf, CDA %.1lf\n", Altitude, DescentRate, (Weight * 9.81)/(0.5 * Density * DescentRate * DescentRate));
        
            return (Weight * 9.81)/(0.5 * Density * DescentRate * DescentRate)
        else:
            return self.CDA
            
    def CalculateLandingPosition(self, Latitude, Longitude, Altitude):
        TimeTillLanding = 0;
	
        Slot = self.GetSlot(Altitude);
        DistanceInSlot = Altitude + 1 - Slot * self.SlotSize
	
        while Altitude > self.LandingAltitude:
            Slot = self.GetSlot(Altitude)
		
            if Slot == self.GetSlot(self.LandingAltitude):
                DistanceInSlot = Altitude - self.LandingAltitude
		
            DescentRate = self.CalculateDescentRate(1.0, self.CDA, Altitude)
            
            TimeInSlot = DistanceInSlot / DescentRate
            
            Latitude += self.Deltas[Slot].latitude * TimeInSlot
            Longitude += self.Deltas[Slot].longitude * TimeInSlot
            
            # printf("SLOT %d: alt %lu, lat=%lf, long=%lf, rate=%lf, dist=%lu, time=%lf\n", Slot, Altitude, Latitude, Longitude, DescentRate, DistanceInSlot, TimeInSlot);
            
            TimeTillLanding = TimeTillLanding + TimeInSlot
            Altitude -= DistanceInSlot
            DistanceInSlot = self.SlotSize
                    
        return {'pred_lat': Latitude, 'pred_lon': Longitude ,'TTL': TimeTillLanding}

    def AddGPSPosition(self, Position):
        Result = None
        
        if Position['sats'] >= 4:
            self.Counter = self.Counter + 1
            if self.Counter >= self.PollPeriod:
                self.Counter = 0
                
                if Position['alt'] <= 0:
                    self.AscentRate = 0
                else:
                    self.AscentRate = self.AscentRate * 0.7 + (Position['alt'] - self.PreviousPosition['alt']) * 0.3;

                if (Position['alt'] < self.MinimumAltitude) or (self.MinimumAltitude == 0):
                    self.MinimumAltitude = Position['alt']
                    
                if Position['alt'] > self.MaximumAltitude:
                    self.MaximumAltitude = Position['alt']               

                if (self.AscentRate >= 1.0) and (Position['alt'] > (self.MinimumAltitude+150)) and (self.FlightMode == FlightMode.fmIdle):
                    self.FlightMode = FlightMode.fmLaunched
                    print("*** LAUNCHED ***");
            
                if (self.AscentRate < -10.0) and (self.MaximumAltitude >= (self.MinimumAltitude+2000)) and (self.FlightMode == FlightMode.fmLaunched):
                    self.FlightMode = FlightMode.fmDescending
                    print("*** DESCENDING ***");

                if (self.AscentRate >= -0.1) and (Position['alt'] <= self.LandingAltitude+2000) and (self.FlightMode == FlightMode.fmDescending):
                    self.FlightMode = FlightMode.fmLanded
                    print("*** LANDED ***")
                   
                if self.FlightMode == FlightMode.fmLaunched:
                    # Going up - store deltas
                    
                    Slot = self.GetSlot(Position['alt']/2 + self.PreviousPosition['alt']/2);
                        
                    # Deltas are scaled to be horizontal distance per second (i.e. speed)
                    self.Deltas[Slot].latitude = (Position['lat'] - self.PreviousPosition['lat']) / self.PollPeriod
                    self.Deltas[Slot].longitude = (Position['lon'] - self.PreviousPosition['lon']) / self.PollPeriod
                    
                    print("Slot " + str(Slot) + " = " + str(Position['alt']) + "," + str(self.Deltas[Slot].latitude) + "," + str(self.Deltas[Slot].longitude))
                elif self.FlightMode == FlightMode.fmDescending:
                    # Coming down - try and calculate how well chute is doing

                    self.CDA = (self.CDA * 4 + self.CalculateCDA(1.0, Position['alt']/2 + self.PreviousPosition['alt']/2, (self.PreviousPosition['alt'] - Position['alt']) / self.PollPeriod)) / 5
                
                
                if (self.FlightMode == FlightMode.fmLaunched) or (self.FlightMode == FlightMode.fmDescending):
                    Result = self.CalculateLandingPosition(Position['lat'], Position['lon'], Position['alt']);

                    # GPS->PredictedLandingSpeed = CalculateDescentRate(Config.payload_weight, GPS->CDA, Config.LandingAltitude);
				
                    # printf("Expected Descent Rate = %4.1lf (now) %3.1lf (landing), time till landing %d\n", 
                            # CalculateDescentRate(Config.payload_weight, GPS->CDA, GPS->Altitude),
                            # GPS->PredictedLandingSpeed,
                            # GPS->TimeTillLanding);

                    # printf("Current    %f, %f, alt %" PRId32 "\n", GPS->Latitude, GPS->Longitude, GPS->Altitude);
                    # printf("Prediction %f, %f, CDA %lf\n", GPS->PredictedLatitude, GPS->PredictedLongitude, GPS->CDA);


                print('PREDICTOR: ' + str(Position['time']) + ', ' + "{:.5f}".format(Position['lat']) + ', ' + "{:.5f}".format(Position['lon']) + ', ' + str(Position['alt']) + ', ' + str(Position['sats']))

                self.PreviousPosition = Position.copy()
                
        return Result