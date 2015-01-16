#!/bin/sh

# keep attempting until service has started
string="failed"
while true
do
    if sudo service isc-dhcp-server start | grep -q "$string"; then
        echo "could not start service."
        sleep 5
    else
        echo "service started."
        break
    fi
done
