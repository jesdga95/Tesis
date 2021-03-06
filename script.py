import os, subprocess, glob, time, math, atexit
import cv2.cv as cv
import select as sel
import paramiko
import socket
import numpy
import Queue
import sys

from numpy import array, linalg
from operator import attrgetter
from SimpleCV import *
from threading import Thread

##
# main settings and variables
##

# define comm port for input-output sockets
port = 3033

# client ip
client_ip = None

# blob data
MAX_SIZE = 3600
MIN_SIZE = 20
reference_blob = None

# camera control
CAMERA_ANGLE = 90;
POSITION_TOLERANCE = 5;
camera_position = 0
scanning = False

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
j = None # robot jacobian
q_point = None # output

# secure shell configuration and commands
# configure usb0 ip and net mask
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print "Starting SSH connection with EV3."
ssh.connect('10.42.0.3', username='root', password='r00tme', timeout=10)

##
# ssh command utils
##

# side motors
def get_duty_command(speed, motor):
    return "echo " + speed + " > /sys/class/tacho-motor/tacho-motor" + motor + "/duty_cycle_sp"

def get_status_command(status, motor):
    return "echo " + status + " > /sys/class/tacho-motor/tacho-motor" + motor + "/run"

def get_led_command_left(red, green):
    return "echo " + red + " > /sys/class/leds/ev3\:red\:left/brightness; echo " + green + " > /sys/class/leds/ev3\:green\:left/brightness"

def get_led_command_right(red, green):
    return "echo " + red + " > /sys/class/leds/ev3\:red\:right/brightness; echo " + green + " > /sys/class/leds/ev3\:green\:right/brightness"

# movement utils
def get_camera_position():
    stdin, stdout, sterr = ssh.exec_command("cat /sys/class/tacho-motor/tacho-motor0/position")
    return int(stdout.read().strip())
    
def reset_camera_position():
    if (abs(get_camera_position() * - 1)) >= POSITION_TOLERANCE:
        camera_rotation = str(get_camera_position() * - 1)
        print "Correcting camera rotation: " + camera_rotation + " degrees"
        ssh.exec_command("echo 0 > /sys/class/tacho-motor/tacho-motor0/position; echo " + camera_rotation + " > /sys/class/tacho-motor/tacho-motor0/position_sp; echo 1 > /sys/class/tacho-motor/tacho-motor0/run")
        time.sleep(0.5)
        ssh.exec_command("echo 0 > /sys/class/tacho-motor/tacho-motor0/position")
        global camera_position
        camera_position = 0

def move_camera(step):
    value = get_camera_position() + step
    if value <= CAMERA_ANGLE and value >= -CAMERA_ANGLE:
        ssh.exec_command("echo " + str(value) + " > /sys/class/tacho-motor/tacho-motor0/position_sp; echo 1 > /sys/class/tacho-motor/tacho-motor0/run")
        time.sleep(0.5)

def get_motor_speed(motor): # in rad/s
    stdin, stdout, sterr = ssh.exec_command("cat /sys/class/tacho-motor/tacho-motor" + str(motor) + "/duty_cycle_sp")
    speed_percent = stdout.read().strip()
    direction = 1
    if int(speed_percent) < 0:
        speed_percent = str(-int(speed_percent))
    #speed = int(speed_percent) * 15.28 / 100
    #print speed
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
    
def transform_speed(speed): # to percent
    percent = speed * 100 / 15.28 # we asume linear behavior for the motor
    if percent > 100:
        percent = 100
    elif percent < -100:
        percent = -100
    return round(percent)

def move_forward(speed):
    ssh.exec_command(get_duty_command(str(-speed), "1") + ";" + get_duty_command(str(-speed), "2") + ";" + get_status_command("1", "1") + ";" + get_status_command("1", "2"))
                        
def move_backwards(speed):
    ssh.exec_command(get_duty_command(str(speed), "1") + ";" + get_duty_command(str(speed), "2") + ";" + get_status_command("1", "1") + ";" + get_status_command("1", "2"))
    
def move_right(speed):
    ssh.exec_command(get_duty_command(str(-speed), "1") + ";" + get_duty_command(str(speed), "2") + ";" + get_status_command("1", "1") + ";" + get_status_command("1", "2"))
    
def move_left(speed):
    ssh.exec_command(get_duty_command(str(speed), "1") + ";" + get_duty_command(str(-speed), "2") + ";" + get_status_command("1", "1") + ";" + get_status_command("1", "2"))
    
def stop_motors():
    ssh.exec_command(get_duty_command("0", "0") + ";" + get_duty_command("0", "1") + ";" + get_duty_command("0", "2")  + ";" + get_status_command("0", "0") + ";" + get_status_command("0", "1") + ";" + get_status_command("0", "2"))

def rotate_left():
    move_left(60)
    time.sleep(0.5)
    stop_motors()

##
# image processing utils
##

def get_sr(blob):
   x1 = blob.topLeftCorner()[0]
   y1 = blob.topLeftCorner()[1]
   x2 = blob.topRightCorner()[0]
   y2 = blob.topRightCorner()[1]
   x3 = blob.bottomLeftCorner()[0]
   y3 = blob.bottomLeftCorner()[1]
   x4 = blob.bottomRightCorner()[0]
   y4 = blob.bottomRightCorner()[1]
   
   return array([x1, y1, x2, y2, x3, y3, x4, y4]).reshape(8, 1)

def get_ls(blob):
   x1 = blob.topLeftCorner()[0]
   y1 = blob.topLeftCorner()[1]
   x2 = blob.topRightCorner()[0]
   y2 = blob.topRightCorner()[1]
   x3 = blob.bottomLeftCorner()[0]
   y3 = blob.bottomLeftCorner()[1]
   x4 = blob.bottomRightCorner()[0]
   y4 = blob.bottomRightCorner()[1]
   z1 = 6 * (1/float(x1));
   z1_inv = -1/z1;
   l1 = array([z1_inv, 0, x1/z1, x1*y1, -(1+pow(x1, 2)), y1, 0, z1_inv, y1/z1, 1+pow(y1, 2), -x1+y1, -x1]).reshape(2, 6)
   l2 = array([z1_inv, 0, x2/z1, x2*y2, -(1+pow(x2, 2)), y2, 0, z1_inv, y2/z1, 1+pow(y2, 2), -x2+y2, -x2]).reshape(2, 6)
   l3 = array([z1_inv, 0, x3/z1, x3*y3, -(1+pow(x3, 2)), y3, 0, z1_inv, y3/z1, 1+pow(y3, 2), -x3+y3, -x3]).reshape(2, 6)
   l4 = array([z1_inv, 0, x4/z1, x4*y4, -(1+pow(x4, 2)), y4, 0, z1_inv, y4/z1, 1+pow(y4, 2), -x4+y4, -x4]).reshape(2, 6)
   
   return array([l1, l2, l3, l4]).reshape(8, 6)
   
# speed relation
def get_vr():
    wr = get_motor_speed(2) # rad/s
    wl = get_motor_speed(1) # rad/s
    dr = array([r/2, r/2, r/l, -r/l]).reshape(2, 2)
    ws = array([wr, wl]).reshape(2, 1)
    vr = numpy.dot(dr, ws) # returns v, w
    return vr

# monocycle model
def get_mm():
    if q_point is None:
        vr = get_vr()
        v = vr[0]
        w = vr[1]
    else:
        v = q_point[0]
        w = q_point[1]
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
    global j
    j = array([0, 0, 0, -math.sin(tetha_pl), xc+xp*math.cos(tetha_pl), xc, math.cos(tetha_pl), -yc+yp*math.sin(tetha_pl), -yc, 0, -1, -1, 0, 0, 0, 0, 0, 0]).reshape(6, 3)
    ks = numpy.dot(j, wa) # returns v_xc, v_yc, v_zc, o_xc, o_yc, o_zc
    return ks

# find matching blob on the image
def find_matching_blob(image):
    red_distance = image.colorDistance(Color.RED).invert() / 16
    blobs = red_distance.findBlobs()
    matching_blob = None
    if blobs:
        squares = blobs.filter([b.isSquare(0.2, 0.2) for b in blobs])
        if squares:
            for square in squares:
                area = square.area()
                if area <= MAX_SIZE and area >= MIN_SIZE:
                    matching_blob = square
                    break
    return matching_blob

# process current image
def process_image(file):
    try:
        # current camera image
        current = Image(file)
        blob1 = find_matching_blob(current)

        # reference image
        global reference_blob
        if reference_blob is None:
            reference = Image('/home/pi/reference.jpg')
            reference_blob = find_matching_blob(reference)
        
        blob2 = reference_blob

        # run algorithm
        global camera_position
        if blob1 is not None and blob2 is not None:
            ls_sas = get_ls(blob2) + get_ls(blob1)
            lpl = 0.5 * linalg.pinv(ls_sas)
            ks = get_ks()
            e = numpy.dot(lpl, get_sr(blob2) - get_sr(blob1))
            e_point = -2 * e
            global q_point
            q_point = numpy.dot(linalg.pinv(numpy.dot(numpy.dot(lpl, ls_sas), j)), e_point)
            w_motors = numpy.dot(linalg.pinv(array([r/2, r/2, r/l, -r/l]).reshape(2, 2)), array([q_point[0], q_point[1]]).reshape(2, 1))
            if client_ip is not None:
                try:
                    s_send = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s_send.connect((client_ip, port))
                    s_send.send(str(w_motors[0])+";"+str(w_motors[1])+";"+str(w_pl))
                except socket.error:
                    pass
            left_difference = blob2.bottomLeftCorner()[0] - blob1.bottomLeftCorner()[0]
            right_difference = blob2.bottomRightCorner()[0] - blob1.bottomRightCorner()[0]
            if left_difference <= -40 and right_difference <= -40:
                move_right(20)
                time.sleep(0.2)
                stop_motors()
                reset_camera_position()
                time.sleep(0.5)
            elif left_difference >= 40 and right_difference >= 40:
                move_left(20)
                time.sleep(0.2)
                stop_motors()
                reset_camera_position()
                time.sleep(0.5)
            elif camera_position == 0:
                ssh.exec_command(get_duty_command(str(transform_speed(w_motors[1])), "1") + ";" + get_duty_command(str(transform_speed(w_motors[1])), "2") + ";" + get_status_command("1", "1") + ";" + get_status_command("1", "2"))                
                reset_camera_position()
            else:
                rotate_left()
        else:
            global scanning
            total_degrees = 80 - get_camera_position()
            if camera_position != 80 and not scanning:
                move_camera(total_degrees)
                camera_position = 80
                scanning = True
            else:
                camera_position -= 20
                move_camera(-20)
                if camera_position <= -80:
                    rotate_left()
                    scanning = False
            stop_motors()
            time.sleep(0.5)
                
                
    except:
        pass

class ProcessingThread(Thread):
    def __init__(self):
        super(ProcessingThread, self).__init__()
        self.running = True
        self.manual = False
 
    def stop(self):
        self.running = False

    def set_manual(self, manual):
        self.manual = manual;

    def is_manual(self):
       return self.manual
 
    def run(self):
        while self.running:
            file = "/run/shm/image.jpg"
            
            if not self.manual:                  
                if os.path.isfile(file):
                    # start processing on current image
                    process_image(file)
                else:
                    # left led red
                    ssh.exec_command(get_led_command_left("255", "0"))
                    print "No image found"
                    
                    # wait until raspistill command has created the image (5 second timeout)
                    for timeout in range (5):
                        if os.path.isfile(file):
                            ssh.exec_command(get_led_command_left("0", "255"))
                            break
                        time.sleep(1)

# start processing thread
print "Starting image processing thread."
t1 = ProcessingThread()
t1.start()

##
# socket management
##

# process socket input
def process_socket_input(value):
    if value.startswith('M'):
        if value == "M":
            # manual mode, right led amber
            ssh.exec_command(get_led_command_right("255", "255"))
            t1.set_manual(True)
            print "Manual mode enabled."
        else:
            if t1.is_manual():
                global camera_position
                if value == "MS":
                    stop_motors()
                elif value == "MF":
                    move_forward(70)
                elif value == "MB":
                    move_backwards(70)
                elif value == "MR":
                    move_right(70)
                elif value == "ML":
                    move_left(70)
                elif value == "MCR":
                    camera_position += 20
                    move_camera(20)
                elif value == "MCL":
                    camera_position -= 20
                    move_camera(-20)
            else:
                print "Manual mode needs to be enabled to perform this action: " + value
    elif value == "A":
        # automatic mode, right led green
        ssh.exec_command(get_led_command_right("0", "255"))
        t1.set_manual(False)
        print "Automatic mode enabled."
    else:
        # the received information is an IP, store it as the client ip
        print "Connected to client: " + value + "."
        global client_ip
        client_ip = value


class SocketThread(Thread):
    def __init__(self):
        super(SocketThread, self).__init__()
        self.running = True
        self.q = Queue.Queue()
 
    def add(self, data):
        self.q.put(data)
 
    def stop(self):
        self.running = False
 
    def run(self):
        q = self.q
        while self.running:
            try:
                # block for 1 second only:
                value = q.get(block=True, timeout=1)
                process_socket_input(value.strip())
            except Queue.Empty:
                sys.stdout.flush()
        if not q.empty():
            print "Elements left in the queue:"
            while not q.empty():
                print q.get()
                
# start socket thread
print "Starting socket thread."
t2 = SocketThread()
t2.start()

##
# cleanup after exit
##

def cleanup():
    # stop image processing thread
    print "Stopping image processing thread."
    t1.stop()
    t1.join()

    # stop socket thread
    print "Stopping socket thread."
    t2.stop()
    t2.join()
    
    # turn motors off
    stop_motors()

    # both leds red
    ssh.exec_command(get_led_command_left("255", "0") + ";" + get_led_command_right("255", "0"))

    # reset camera position
    reset_camera_position()

##
# initialization
##

def main():
    # both leds green
    ssh.exec_command(get_led_command_left("0", "255") + ";" + get_led_command_right("0", "255"))

    # define camera run mode
    ssh.exec_command("echo position > /sys/class/tacho-motor/tacho-motor0/run_mode; echo brake > /sys/class/tacho-motor/tacho-motor0/stop_mode; echo on > /sys/class/tacho-motor/tacho-motor0/regulation_mode; echo 300 > /sys/class/tacho-motor/tacho-motor0/ramp_up_sp; echo 300 > /sys/class/tacho-motor/tacho-motor0/ramp_down_sp; echo 500 > /sys/class/tacho-motor/tacho-motor0/pulses_per_second_sp")

    # reset camera position
    reset_camera_position()

    host = ''
    s_receive = socket.socket()
    s_receive.bind((host, port))
    print "Server listening on port {p}.".format(p=port)
    s_receive.listen(1)
    while True:
        try:
            client, addr = s_receive.accept()
            ready = sel.select([client,], [], [], 2)
            if ready[0]:
                data = client.recv(4096)
                t2.add(data)
        except KeyboardInterrupt:
            cleanup()
            break
        except socket.error, msg:
            print "Socket error %s" %msg
            break

if __name__ == "__main__":
    main()
