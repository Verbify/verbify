#!/bin/bash
#Configure Cassandra

sed -i -e 's/-Xss180k/-Xss256k/g' /etc/cassandra/cassandra-env.sh

python <<END
import pycassa
sys = pycassa.SystemManager("localhost:9160")

if "verbify" not in sys.list_keyspaces():
    print "creating keyspace 'verbify'"
    sys.create_keyspace("verbify", "SimpleStrategy", {"replication_factor": "1"})
    print "done"

if "permacache" not in sys.get_keyspace_column_families("verbify"):
    print "creating column family 'permacache'"
    sys.create_column_family("verbify", "permacache")
    print "done"
END
