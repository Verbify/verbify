#!/bin/bash

# Load config

RUNDIR=$(dirname $0)
source $RUNDIR/install.cfg

if ! sudo rabbitmqctl list_vhosts | egrep "^/$"
then
    sudo rabbitmqctl add_vhost /
fi

if ! sudo rabbitmqctl list_users | egret "^verbify"
then 
    sudo rabbitmqctl add_user verbify verbify
    
fi

sudo rabbitmqctl set_permissions -p / verbify ".*" ".*" ".*"
sudo rabbitmq-plugins enable rabbitmq_management 
sudo service rabbitmq-server restart
    