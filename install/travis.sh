#!/bin/bash

# Load Config

RUNDIR=$(dirname $0)
source $RUNDIR/install.cfg

ENVIRONMENT=${1:-travis}
VERBIFY_CODE=${2:-$VERBIFY_SRC/verbify}

if [ ! -e $VERBIFY_CODE ]; then
    echo "Not Cool, Couldn't find source $VERBIFY_CODE, Sorry, Aborting"
    exit 1
fi

# S A N I T Y   C H E C K S

if [[ $EUID -ne 0 ]]; then 
    echo "Not Cool, Must be run with root powers"
    exit 1
fi

if [[ "amd64" != $(dpkg --print-architecture) ]]; then
    cat << END
ERROR? This host is running the $(dpkg --print-architecture) architecture
Because of the prebuilt stuff, installing Verbify is only supported for amd64
Sorry
END
    exit 1
fi
source /etc/lsb-release
if [ "$DISTRIB_ID" != "Ubuntu" -o "$DISTRIB_RELEASE" != "14.04" ]; then 
    echo "Sorry, only Ubuntu 14.04 is supported"
    exit 1
fi


$RUNDIR/install_apt.sh

$RUNDIR/install_cassandra.sh
$RUNDIR/install_zookeeper.sh


[ -x "$(which pip) "] || easy_install pip
pip install -U pip wheel setuptools coverage
pushd $VERBIFY_CODE/v1
sudo python setup.py develop
make
ln -sf example.ini test.ini
popd

if [ "$ENVIRONMENT" == "vagrant" ]; then
    $RUNDIR/install_services.sh
    service mcrouter stop
    $RUNDIR/setup_postgres.sh
    $RUNDIR/setup_cassandra.sh
    $RUNDIR/setup_rabbitmq.sh
fi

# DONE

cat <<CONCLUSION
Congratulations man. You have offically unoffically installed a base version of VIper
To run unit tests:

    cd src/verbify/v1
    nosetests
    
CONCLUSION
