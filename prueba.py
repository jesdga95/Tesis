#from numpy import *
import os, subprocess, time
import paramiko

#l1 = array([1, 1, 2, 2, 3, 3, 4, 4, 6, 8, 0, 3]).reshape(2, 6)
#l2 = array([3, 8, 9, 4, 7, 1, 3, 0, 8, 5, 5, 1]).reshape(2, 6)
#l3
#l4
#print array([x1, y1, x2, y2, x3, y3, x4, y4]).reshape(8, 1)
#print array([l1, l2]).reshape(4, 6)
#print pow(3, 2)
#print 1/float(134)

CAMERA_ANGLE = 70;
POSITION_TOLERANCE = 5;

# secure shell configuration and commands
# configure usb0 ip and net mask
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print "Starting SSH connection with EV3."
ssh.connect('10.42.0.3', username='root', password='r00tme', timeout=10)

ssh.exec_command("echo position > /sys/class/tacho-motor/tacho-motor0/run_mode; echo brake > /sys/class/tacho-motor/tacho-motor0/stop_mode; echo on > /sys/class/tacho-motor/tacho-motor0/regulation_mode; echo 300 > /sys/class/tacho-motor/tacho-motor0/ramp_up_sp; echo 300 > /sys/class/tacho-motor/tacho-motor0/ramp_down_sp; echo 500 > /sys/class/tacho-motor/tacho-motor0/pulses_per_second_sp")

def get_camera_position():
    stdin, stdout, sterr = ssh.exec_command("cat /sys/class/tacho-motor/tacho-motor0/position")
    return int(stdout.read().strip())

def reset_camera_position():
    if (abs(get_camera_position() * - 1)) >= POSITION_TOLERANCE:
        camera_rotation = str(get_camera_position() * - 1)
        print "Correcting camera rotation: " + camera_rotation + " degrees"
        ssh.exec_command("echo 0 > /sys/class/tacho-motor/tacho-motor0/position; echo " + camera_rotation + " > /sys/class/tacho-motor/tacho-motor0/position_sp; echo 1 > /sys/class/tacho-motor/tacho-motor0/run")
        time.sleep(2)
        ssh.exec_command("echo 0 > /sys/class/tacho-motor/tacho-motor0/position")

def move_camera(step):
    value = get_camera_position() + step
    if value <= CAMERA_ANGLE and value >= -CAMERA_ANGLE:
        ssh.exec_command("echo 0 > /sys/class/tacho-motor/tacho-motor0/position; echo " + str(value) + " > /sys/class/tacho-motor/tacho-motor0/position_sp; echo 1 > /sys/class/tacho-motor/tacho-motor0/run")
        sleep(2)

reset_camera_position()
time.sleep(2)
ssh.exec_command("echo 0 > /sys/class/tacho-motor/tacho-motor0/position")
move_camera(60)
move_camera(-120)
move_camera(100)
reset_camera_position()