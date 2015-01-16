#!/bin/sh

cd /run/shm
sudo rm -rf *
cd /home/pi
python script.py
