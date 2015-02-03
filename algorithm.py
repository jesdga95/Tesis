from numpy import array, linalg
import numpy
import os, subprocess, time, math
import paramiko

# control constants
ORIGIN_THETA = 59.15

# measurements
xc = 0 # cm
xp = 5 # cm
yc = 2 # cm
yp = 5 # cm
r = 1.5 # cm
l = 18 # cm

# control variables
w_pl = 4.19 # rad/s
theta = 0 # degrees
wa = None # v, w, w_pl

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
    return speed

# speed relation
def get_sr():
    wr = get_motor_speed(2) # rad/s
    wl = get_motor_speed(1) # rad/s
    dr = array([r/2, r/2, r/l, -r/l]).reshape(2, 2)
    ws = array([wr, wl]).reshape(2, 1)
    sr = numpy.dot(dr, ws) # returns v, w
    return sr

# monocycle model
def get_mm():
    sr = get_sr()
    v = sr[0]
    w = sr[1]
    theta = ORIGIN_THETA + get_camera_position()
    r_dt = array([math.cos(theta), 0, 0, math.sin(theta), 0, 0, 0, 1, 0, 0, 0, 1]).reshape(4, 3)
    global wa
    wa = array([v, w, w_pl]).reshape(3, 1)
    pa = numpy.dot(r_dt, wa) # returns xom, yom, theta, theta_pl
    return pa

# kinematic screw
def get_ks():
    mm = get_mm()
    tetha_pl = mm[3]
    xy_p = array([0, 0, 0, -math.sin(tetha_pl), xc+xp*math.cos(tetha_pl), xc, math.cos(tetha_pl), -yc+yp*math.sin(tetha_pl), -yc, 0, -1, -1, 0, 0, 0, 0, 0, 0]).reshape(6, 3)
    global wa
    ks = numpy.dot(xy_p, wa) # returns v_xc, v_yc, v_zc, o_xc, o_yc, o_zc
    return ks
    

def test():
#    print get_motor_speed(1)
    print get_ks()
    time.sleep(1)

#while True:
test()