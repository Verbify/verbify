#!/bin/bash

set -x
psql -h ${DB_HOST:-localhost} \
     -d ${DB_NAME:-verbify} \
     -U ${DB_USER:-verbify} \
     -p ${DB_PORT:-5432} \
     -F"\t" -A -t
