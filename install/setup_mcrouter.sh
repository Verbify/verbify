#!/bin/bash
if [ ! -d /etc/mcrouter ]; then
    mkdir -p /etc/mcrouter
fi

if [ ! -f /etc/mcrouter/global.conf ]; then
    cat > /etc/mcrouter/global.conf <<MCROUTER
{
  // route all valid prefixes to the local memcached
  "pools": {
    "local": {
      "servers": [
        "127.0.0.1:11211",
      ],
      "protocol": "ascii",
      "keep_routing_prefix": false,
    },
  },
  "named_handles": [
    {
      "name": "local-pool",
      "type": "PoolRoute",
      "pool": "local",
    },
  ],
  "route": {
    "type": "PrefixSelectorRoute",
    "policies": {
      "rend:": "local-pool",
      "page:": "local-pool",
      "pane:": "local-pool",
      "sr:": "local-pool",
      "account:": "local-pool",
      "link:": "local-pool",
      "comment:": "local-pool",
      "message:": "local-pool",
      "campaign:": "local-pool",
      "award:": "local-pool",
      "trophy:": "local-pool",
      "flair:": "local-pool",
      "friend:": "local-pool",
      "inboxcomment:": "local-pool",
      "inboxmessage:": "local-pool",
      "reportlink:": "local-pool",
      "reportcomment:": "local-pool",
      "reportsr:": "local-pool",
      "reportmessage:": "local-pool",
      "modinbox:": "local-pool",
      "otp:": "local-pool",
      "captcha:": "local-pool",
      "queuedvote:": "local-pool",
      "geoip:": "local-pool",
      "geopromo:": "local-pool",
      "srpromos:": "local-pool",
      "rising:": "local-pool",
      "srid:": "local-pool",
      "defaultsrs:": "local-pool",
      "featuredsrs:": "local-pool",
      "query:": "local-pool",
      "rel:": "local-pool",
      "srmember:": "local-pool",
      "srmemberrel:": "local-pool",
    },
    "wildcard": {
      "type": "PoolRoute",
      "pool": "local",
    },
  },
}
MCROUTER
fi

cat > /etc/default/mcrouter <<MCROUTER_DEFAULT

MCROUTER_FLAGS="-f /etc/mcrouter/global.conf -L /var/log/mcrouter/mcrouter.log -p 5050 -r /././ --stats-root=/var/mcrouter/stats"
MCROUTER_DEFAULT

echo "cool cool start networking or verbify-start" > /etc/init/mcrouter.override
service mcrouter restart