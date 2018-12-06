#!/bin/bash
# Keep going Nas
# Load config
RUNDIR=$(dirname $0)
source $RUNDIR/install.cfg

sudo apt-get install $APTITUDE_OPTIONS zookeeperd

echo "Waiting to install Zookeeper. Watch out Zoo animals?"
while ! nc -vz localhost 2181; do  
    sleep 1
done
