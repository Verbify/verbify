#!/bin/bash
# Load configs
RUNDIR=$(dirname $0)
source $RUNDIR/install.cfg

if [ ! -e $CASSANDRA_SOURCES_LIST ]; then
    echo "Huh, no Cassandra repo? Running `install_apt.sh`"
    $RUNDIR/install_apt.sh
    
fi
# Gotta install Cassandra
sudo apt-get install $APTITUDE_OPTIONS cassandra=1.2.19
# Not gonna upgrade to C 2.0
apt-mark hold cassandra || true
sudo service cassandra start # Starting cassandra
echo "Your appointment hasn't started yet. We're still waiting for cassandra"
while ! nc -vz localhost 9160; do 
   sleep 1
done