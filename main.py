import time
import datetime
import os
import glob
import logging
import RPi.GPIO as GPIO
import temperature_probe
import mysql.connector
import record_SQL_data
	
def read_config_file(config_file):
	# Standard function to read in config files.
	with open(config_file,"r") as file:
		lines=file.read().splitlines()
		configs=[]
		for line in lines:
			line=line.split(",")
			line[0]=float(line[0])
			configs=configs+[line]
	return configs
	
# Configs
time_interval=15		# Interval in seconds for when the code runs
brewID=3			# TODO: make this a user input when code runs
write_to_database=0	# Determines whether or not data written to sql database

# Log file information
logging.basicConfig(level=logging.DEBUG)
logger=logging.getLogger(__name__)
handler=logging.FileHandler(os.getcwd()+"/"+
			datetime.datetime.now().strftime('./logs/main_%H_%M_%d_%m_%Y.log'))
handler.setLevel(logging.INFO)
logger.addHandler(handler)

# Mysql startup info
mydb=mysql.connector.connect(
  host="localhost",
  user="dmueller",
  passwd="Spartan1",
  database="beerCode"
)
mycursor=mydb.cursor()

# Read config file settings to establish run parameters.
logger.info("Reading config file data")
pinout_config_file="pinout.config"
temperature_config_file="temperature_settings.config"
pinout_data=read_config_file("./configs/"+pinout_config_file)
temperature_settings=read_config_file("./configs/"+temperature_config_file)

# Assign pinouts to relays
logger.info("Assigning pinouts to relays")
for idx,pinout in enumerate(pinout_data):
	if pinout[1]=="relay_cool":
		relay_cool=int(pinout[0])
	if pinout[1]=="relay_hot":
		relay_hot=int(pinout[0])
logger.debug("relay_cool: "+str(relay_cool))
logger.debug("relay_hot: "+str(relay_hot))

# Assign temperature run parameters
logger.info("Assigning temperature to run parameters")
for idx,temperature_config in enumerate(temperature_settings):
	if temperature_config[1]=="setpoint_low":
		setpoint_low=temperature_config[0]
	if temperature_config[1]=="setpoint_high":
		setpoint_high=temperature_config[0]
	if temperature_config[1]=="trigger_cool":
		trigger_cool=temperature_config[0]
	if temperature_config[1]=="trigger_hot":
		trigger_hot=temperature_config[0]
logger.debug("setpoint_low: "+str(setpoint_low))
logger.debug("setpoint_high: "+str(setpoint_high))
logger.debug("trigger_cool: "+str(trigger_cool))
logger.debug("trigger_hot: "+str(trigger_hot))

# Configure how the pins are interacted with
logger.info("Configuring how the pins are interacted with")
GPIO.setmode(GPIO.BCM) # GPIO Numbers instead of board numbers
GPIO.setup([relay_cool,relay_hot], GPIO.OUT) # GPIO assign mode
GPIO.output([relay_cool,relay_hot], GPIO.LOW) # Initialize all pinouts to off

# Run main code to check temperature and operate heating/cooling
logger.info("Running main code...")
fout=open(datetime.datetime.now().strftime('./logs/temp_log_%H_%M_%d_%m_%Y.csv'),'w')
fout.write('time,temperature_air,temperature_liquid,op_hot,op_cold')
fout.write('\n')
try:
	while True:
		timeNow=datetime.datetime.now()
		temperature_air=temperature_probe.read_temp(0)
		temperature_liquid=temperature_probe.read_temp(1)
		logger.info("Current time: "+str(timeNow))
		logger.info("Current liquid temperature: "+str(temperature_liquid))
		logger.info("Current outside temperature: "+str(temperature_air))
		logger.info("Tempearture between setpoints: "+
						str(temperature_liquid>setpoint_low and temperature_liquid<=setpoint_high))
		
		if temperature_liquid<=(setpoint_low+trigger_cool):
			# Need to heat chamber
			GPIO.output(relay_cool, GPIO.LOW) # Turn off cooler, if on
			GPIO.output(relay_hot, GPIO.HIGH) # Turn on heater
			
			logger.debug("Chamber heating now. Resolving difference of "+
				str(setpoint_low+trigger_cool-temperature_liquid)+" deg F")
			if write_to_database:
				record_SQL_data.add_to_temp_log(mydb,mycursor,brewID,timeNow,temperature_air,temperature_liquid,1,0)
			fout.write(str(timeNow)+','+str(temperature_air)+','+str(temperature_liquid)+',1,0')
			fout.write('\n')
			
			time.sleep(time_interval)
		elif temperature_liquid>=(setpoint_high+trigger_hot):
			# Need to cool chamber
			GPIO.output(relay_cool, GPIO.HIGH) # Turn on cooler
			GPIO.output(relay_hot, GPIO.LOW) # Turn off heater, if on
			
			logging.debug("Chamber cooling now. Resolving difference of "+
				str(setpoint_high+trigger_hot-temperature_liquid)+" deg F")
			if write_to_database:
				record_SQL_data.add_to_temp_log(mydb,mycursor,brewID,timeNow,temperature_air,temperature_liquid,0,1)
			fout.write(str(timeNow)+','+str(temperature_air)+','+str(temperature_liquid)+',0,1')
			fout.write('\n')
			
			time.sleep(time_interval)
		else:
			# Chamber within operational limits, do nothing
			GPIO.output(relay_cool, GPIO.LOW) # Turn off cooler, if on
			GPIO.output(relay_hot, GPIO.LOW) # Turn off heater, if on
			
			logging.debug("Fermenter is in the happy zone, everything's off.")
			if write_to_database:
				record_SQL_data.add_to_temp_log(mydb,mycursor,brewID,timeNow,temperature_air,temperature_liquid,0,0)
			fout.write(str(timeNow)+','+str(temperature_air)+','+str(temperature_liquid)+',0,0')
			fout.write('\n')
			
			time.sleep(time_interval)
finally:
	fout.close()
	mydb.close()
	GPIO.cleanup()
	print('Program ended, files closed.')
