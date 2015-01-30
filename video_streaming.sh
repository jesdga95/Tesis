#!/bin/sh

# start video streaming
LD_LIBRARY_PATH=/usr/local/lib /usr/local/bin/mjpg_streamer -i "input_file.so -f /run/shm -n image.jpg" -o "output_http.so -w /usr/local/www"