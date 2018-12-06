#!/usr/bin/env bash
install/install_services.sh

pushd v1
python setup.py develop
make pyx
ln -sf example.ini test.ini
popd

# Configure
install/setup_cassandra.sh
