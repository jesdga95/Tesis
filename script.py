import os, subprocess, glob, time, atexit
import cv2.cv as cv
import select as sel
import paramiko
import socket
import Queue
import sys

from numpy import *
from operator import attrgetter
from SimpleCV import *
from threading import Thread

##
# main settings and variables
##

# define output status
STATUS_CONNECTED = "connected"

# define comm port for input-output sockets
port = 3033

# blob sizes
MAX_SIZE = 3600
MIN_SIZE = 20

# camera control
CAMERA_ANGLE = 90;
POSITION_TOLERANCE = 5;

# speeds
r = 1.5 # cm
L = 18 # cm
Wright = 0 # rad/s
Wleft = 0 # rad/s

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

def run_forward():
    ssh.exec_command(get_duty_command("-70", "1") + ";" + get_duty_command("-70", "2") + ";" + get_status_command("1", "1") + ";" + get_status_command("1", "2") + ";sleep 0.1;" + get_duty_command("0", "0") + ";" + get_duty_command("0", "1") + ";" + get_duty_command("0", "2")  + ";" + get_status_command("0", "0") + ";" + get_status_command("0", "1") + ";" + get_status_command("0", "2"))

# camera utils
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
        
def move_camera(step):
    value = get_camera_position() + step
    if value <= CAMERA_ANGLE and value >= -CAMERA_ANGLE:
        ssh.exec_command("echo " + str(value) + " > /sys/class/tacho-motor/tacho-motor0/position_sp; echo 1 > /sys/class/tacho-motor/tacho-motor0/run")
        time.sleep(0.5)

##
# image processing utils
##

def sr_matrix(blob):
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

# find matching blob on the image
def find_matching_blob(image):
    red_distance = image.colorDistance(Color.RED).invert() / 16
    blobs = red_distance.findBlobs()
    squares = blobs.filter([b.isSquare(0.2, 0.2) for b in blobs])
    matching_blob = None
    if squares:
        for square in squares:
            area = square.area()
            if area <= MAX_SIZE and area >= MIN_SIZE:
                matching_blob = square
                # draw red circles on the corners
                #redcircle = DrawingLayer((red_distance.width, red_distance.height))
                #redcircle.circle(square.bottomLeftCorner(), 5, color = Color.RED)
                #redcircle.circle(square.bottomRightCorner(), 5, color = Color.RED)
                #redcircle.circle(square.topLeftCorner(), 5, color = Color.RED)
                #redcircle.circle(square.topRightCorner(), 5, color = Color.RED)
                #red_distance.addDrawingLayer(redcircle)
                #red_distance.applyLayers()
                #red_distance.show()
                break
    return matching_blob

# process current image
def process_image(file):
    if True:
    #try:
        # current camera image
        current = Image(file)
    
        # reference image
        reference = Image('/home/pi/reference.jpg')
        
        blob1 = find_matching_blob(current)
        blob2 = find_matching_blob(reference)     
    
        # measure X distance between reference image and current camera image corners
        if blob1 is not None and blob2 is not None:
              #print sr_matrix(blob1)
              print sr_matrix(blob2)
              if abs(blob2.bottomLeftCorner()[0] - blob1.bottomLeftCorner()[0]) >= 5 and abs(blob2.bottomRightCorner()[0] - blob1.bottomRightCorner()[0]) >= 5 and abs(blob2.topRightCorner()[0] - blob1.topRightCorner()[0]) >= 5 and abs(blob2.topLeftCorner()[0] - blob1.topLeftCorner()[0]) >= 5:
                  run_forward()
    #except:
        #pass

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
                if value == "MS":
                    ssh.exec_command(get_duty_command("0", "0") + ";" + get_duty_command("0", "1") + ";" + get_duty_command("0", "2")  + ";" + get_status_command("0", "0") + ";" + get_status_command("0", "1") + ";" + get_status_command("0", "2"))
                elif value == "MF":
                    ssh.exec_command(get_duty_command("-70", "1") + ";" + get_duty_command("-70", "2") + ";" + get_status_command("1", "1") + ";" + get_status_command("1", "2"))
                elif value == "MB":
                    ssh.exec_command(get_duty_command("70", "1") + ";" + get_duty_command("70", "2") + ";" + get_status_command("1", "1") + ";" + get_status_command("1", "2"))
                elif value == "MR":
                    ssh.exec_command(get_duty_command("-70", "1") + ";" + get_duty_command("70", "2") + ";" + get_status_command("1", "1") + ";" + get_status_command("1", "2"))
                elif value == "ML":
                    ssh.exec_command(get_duty_command("70", "1") + ";" + get_duty_command("-70", "2") + ";" + get_status_command("1", "1") + ";" + get_status_command("1", "2"))
                elif value == "MCR":
                    move_camera(20)
                elif value == "MCL":
                    move_camera(-20)
            else:
                print "Manual mode needs to be enabled to perform this action: " + value
    elif value == "A":
        # automatic mode, right led green
        ssh.exec_command(get_led_command_right("0", "255"))
        t1.set_manual(False)
        print "Automatic mode enabled."
    else:
        # setup connection on the received local IP
        try:
            s_send = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s_send.connect((value, port))
            print "Connected to client: " + value + "."
            s_send.send(STATUS_CONNECTED)
        except socket.error:
            pass


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
    # both leds red
    ssh.exec_command(get_led_command_left("255", "0") + ";" + get_led_command_right("255", "0"))

    # reset camera position
    reset_camera_position()

    # stop image processing thread
    print "Stopping image processing thread."
    t1.stop()
    t1.join()

    # stop socket thread
    print "Stopping socket thread."
    t2.stop()
    t2.join()

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