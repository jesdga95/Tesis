#!/bin/sh

# build initial camera command, add -cfx 128:128 for gray scale
# shutdown timer, timelapse, burst mode, nopreview, dimensions, no thumbnail
raspistill -t 0 -tl 0 -bm -n -o /run/shm/image.jpg -w 320 -h 240 -th 0:0:0