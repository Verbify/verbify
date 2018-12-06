#!/bin/bash
# Load the Config
RUNDIR=$(dirname $0)
source $RUNDIR/install.cfg

apt-get update

echo deb http://debian.datastax.com/community stable main | \
    sudo tee $CASSANDRA_SOURCES_LIST
wget -qO- -L https://debian.datastax.com/debian/repo_key | \
    sudo apt-key add -

# Got steal some stuff from Reddit

apt-get install $APTITUDE_OPTIONS python-software-properties
apt-add-repository -y ppa:reddit/ppa

cat <<HERE > /etc/apt/preferences.d/reddit
Package: *
Pin: release o=LP-PPA-reddit
Pin-Priority: 600
HERE


apt-get update

apt-get remove $APTITUDE_OPTIONS $(dpkg-query  -W -f='${binary:Package}\n' | grep libmemcached | tr '\n' ' ')
apt-get autoremove $APTITUDE_OPTIONS

cat <<PACKAGES | xargs apt-get install $APTITUDE_OPTIONS
netcat-openbsd
git-core

python-dev
python-setuptools
python-routes
python-pylons
python-boto
python-tz
python-crypto
python-babel
python-numpy
python-dateutil
cython
python-sqlalchemy
python-beautifulsoup
python-chardet
python-psycopg2
python-pycassa
python-imaging
python-pycaptcha
python-pylibmc=1.2.2-1~trusty5
python-amqplib
python-bcrypt
python-snappy
python-snudown
python-l2cs
python-lxml
python-kazoo
python-stripe
python-tinycss2
python-unidecode
python-mock
python-yaml
python-httpagentparser

python-baseplate

python-flask
geoip-bin
geoip-database
python-geoip

nodejs
node-less
node-uglify
gettext
make
optipng
jpegoptim

libpcre3-dev

python-gevent
python-gevent-websocket
python-haigha

python-redis
python-pyramid
python-raven
PACKAGES
