from numpy import array, linalg
import numpy
import os, subprocess, time, math
import paramiko

# control constants
ORIGIN_THETA = 59.15

# control variables
Wr = 1 # rad/s
Wl = 3 # rad/s
Wpl = 0.05 # rad/s
r = 1.5 # cm
L = 18 # cm
theta = 0 # degrees

# secure shell configuration and commands
# configure usb0 ip and net mask
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print "Starting SSH connection with EV3."
ssh.connect('10.42.0.3', username='root', password='r00tme', timeout=10)

def get_camera_position():
    stdin, stdout, sterr = ssh.exec_command("cat /sys/class/tacho-motor/tacho-motor0/position")
    return int(stdout.read().strip())

# get motor speed in rad/s
def get_motor_speed(motor):
    stdin, stdout, sterr = ssh.exec_command("cat /sys/class/tacho-motor/tacho-motor" + str(motor) + "/duty_cycle_sp")
    speed_percent = stdout.read().strip()
    direction = 1
    if int(speed_percent) < 0:
        speed_percent = str(-int(speed_percent))
        direction = -1
    speed = {'0': 0,
        '10': 1.88,
        '20': 3.67,
        '30': 5.34,
        '40': 7.12,
        '50': 8.9,
        '60': 10.9,
        '70': 12.35,
        '80': 14.34,
        '90': 15.18,
        '100': 15.28}.get(speed_percent, 0)
    return speed * direction

# speed relation
def getSr():
    global Wr, Wl
    Dr = array([r/2, r/2, r/L, -r/L]).reshape(2, 2)
    Ws = array([Wr, Wl]).reshape(2, 1)
    Sr = numpy.dot(Dr, Ws) # returns v, w
    return Rv

# monocycle model
def getMm():
    theta = ORIGIN_THETA + get_camera_position()
    Rdt = array([r/2*math.cos(theta), r/2*math.cos(theta), 0, r/2*math.sin(theta), r/2*math.sin(theta), 0, r/L, -r/L, 0, 0, 0, 1]).reshape(4, 3)
    Wa = array([Wr, Wl, Wpl]).reshape(3, 1)
    Pa = numpy.dot(Rdt, Wa) # returns xom, yom, theta, Thetapl
    return Pa
    

def test():
#    print get_motor_speed(1)
    print getMm()
    time.sleep(1)

while True:
    test()