#!/bin/bash
# Load confoig
RUNDIR=$(dirname $0) 
source $RUNDIR/install.cfg

# Install requirements
cat <<PACKAGES | xargs apt-get install $APTITUDE_OPTIONS
mcrouter
memcached
postgresql
postgresql-client
rabbitmq-server
haproxy
nginx
gunicorn
redis-server
PACKAGES

# Waiting
# Still waiting
echo "Waiting for services. Check the source for port meanings."
#1121 = memcache
# 5432 = postgrees
# 5672 = rabbitmq
for port in 11211 5432 5672; do
    while ! nc -vz localhost $port; do
        sleep 1
    done
done
