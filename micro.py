# main.py -- put your code here!

import pyb
import machine as M
import servo as S
from sonar import HCSR04
import time



def rewind():
	global motor
	global ofset
	
	default_positions = [110, 140, 80, 50, 80, 110, 100, 60, 110, 120, 140]
	with open('data\servos.txt', 'r') as file:
		text = file.read()
		actual_positions = text.split()

	for n, i in enumerate(default_positions):
		difference = i - actual_positions[n]
		if difference > i:
			for j in range(difference):
				srv.position(n, j+actual_positions[n])	
				time.delay(10)	#10 milisegundos
		else:
			for j in reversed(range(difference)):
				srv.position(n, j+i)
				time.delay(10)	#10 milisegundos


	distance = round(sensor.distance_cm())
	while distance > 5:
		motor.value(1)
		distance = round(sensor.distance_cm())


	ofset = round(sensor.distance_cm())

	with open('data\ep_ready.txt', 'w') as file:
		text = '1'
		file.write(text)

	ep_time()


def set_servos():
		
	with open('data\servos.txt', 'r') as file:
		text = file.read()
		text = text.split()

	for n, i in enumerate(text):
		srv.position(n, int(float(i)))	#int(float(i)) es porque i es un str de un número con coma y hacer directamente int no es posible

	with open('data\do.txt', 'r') as file:
		do = file.read()
		do = do.split()
		do_servos = do[0]
		do_sensors = do[1]

	with open('data\do.txt', 'w') as file:
		text = '0		{}'.format(do_sensors)
		file.write(text)


def get_sensors():
	global ofset

	distance = round(sensor.distance_cm())


	with open('data\sensors.txt', 'w') as file:
		text = '{}'.format(distance-ofset)
		file.write(text)


	with open('data\do.txt', 'r') as file:
		do = file.read()
		do = do.split()
		do_servos = do[0]
		do_sensors = do[1]


	with open('data\do.txt', 'w') as file:
		text = '{}		0'.format(do_servos)
		file.write(text)


def func():
	global timeout
	global tim

	timeout = True
	tim.deinit()

def ep_time():
	global tim
	
	tim.init(freq=1/60) 
	
	tim.callback(lambda t: func())


def evaluate():
	global timeout
	global ofset
	global end



	if timeout or end:
		with open('data\done.txt', 'w') as file:
			text = '1'
			file.write(text)
		timeout = False
		end = False

		with open('data\ep_ready.txt', 'w') as file:
			text = '0'
			file.write(text)
		rewind()

	else:
		with open('data\do.txt', 'r') as file:
			do = file.read()
			do = do.split()
			do_servos = int(do[0])
			do_sensors = int(do[1])
		
		if do_servos == 1:
			set_servos()
		
		if do_sensors == 1:
			get_sensors()
	
		distance = round(sensor.distance_cm())
		if 40 < distance-ofset:
			end = True	
		else: 
			end = False








end = False
timeout = False

tim = pyb.Timer(4)

motor = M.Pin('X3', M.
	Pin.OUT)
motor.value(0)

i2c = M.I2C(scl=M.Pin('Y9'), sda=M.Pin('Y10'))
srv = S.Servos(i2c)

default_positions = [110, 140, 80, 50, 80, 110, 100, 60, 110, 120, 140]
for n, i  in enumerate(default_positions):
	srv.position(n, i)

sensor = HCSR04(trigger_pin='X11', echo_pin='X10', echo_timeout_us=1000000)


ep_time()
while True:
	evaluate()
