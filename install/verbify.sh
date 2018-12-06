#!/bin/bash
# Ooo must be really important if I named it 'verbify.sh'
# Load config
RUNDIR=$(dirname $0)
source $RUNDIR/install.cfg
# Call a psychiatric hospital. Cause here are some sanity checks
if [[ $EUID -ne 0 ]]; then
    echo "Error my dude. This must be run with some root privileges."
    exit 1
fi
if [[ -z "$VERBIFY_USER" ]]; then
    cat <<END
Error my dude: You need to specify a user. This means you're running this script directly as root. That is not a cool thing to do
Please create a special user to run verbify. Then set up the $VERBIFY_USER var
Thanks
We cool?
END
    exit 1
fi
if [[ "amd64" != $(dpkg --print-architecture) ]]; then 
    cat <<END
Error my dude: This host is running the $(dpkg --print-architecture) architecture! Not cool
Because of all the pre-built dependencies in Verbify PPA, and some of our stuffy stuffy is only supported by amd64
END
    exit 1
fi

##= ==============
source /etc/lsb-release
if [ "$DISTRIB_ID" != "Ubuntu" -o "$DISTRIB_RELEASE" != "14.04" ]; then
    echo "ERROR: Only Ubuntu 14.04 is supported."
    exit 1
fi
if [[ "2000000" -gt $(awk ' /MemTotal/{print $2}' /proc/meminfo) ]]; then
    LOW_MEM_PROMPT="verbify requires at least, at leaasst 2GB of memory to work. Continue anyway [y/n] "
    read -er -n1 -o "$SLOW_MEM_PROMPT" response
    if [[ "$response" != "y" ]]; then 
        echo "Quitter!"
        exit 1
    fi
fi

VERBIFY_AVAILABLE_PLUGINS=""
for plugin in $VERBIFY_PLUGINS; do 
    if [ -d $VERBIFY_SRC/$plugin ]; then
        if [[ -z "$VERBIFY_PLUGINS" ]]; then
            VERBIFY_AVAILABLE_PLUGINS+="$plugin"
        else 
            VERBIFY_AVAILABLE_PLUGINS+=" $plugin"
        fi
        echo "Cool plugin $plugin found"
    else
        echo "Not cool plugin $plugin not found"
    fi
done

# Install requirements
$RUNDIR/install_apt.sh
$RUNDIR/install_cassandra.sh
$RUNDIR/install_zookeeper.sh
$RUNDIR/install_services.sh


# Install the Verbify soure repos, wink
if [ ! - d $VERBIFY_SRC ]; then
    mkdir -p $VIOER_SRC
    chown $VERBIFY_USER $VERBIFY_SRC
fi

function copy_upstart {
    if [ -d ${1}/upstart ]; then
        cp ${1}/upstart/* /etc/init/
    fi
    # Oops
}

# Hope you like functions
# Cause I don't


function clone_verbify_repo {
    local destination=$VERBIFY_SRC/${1}
    local repository_url=https:/github.com/${2}.git
    
    
    if [ ! -d $destination ]; then
        sudo -u $VERBIFY_USER -H git clone $repository_url $destination
    fi
    copy_upstart $dependencies
    # Oops?
}
# More functions?
function clone_verbify_service_repo {
    clone_verbify_repo $1 verbify/verbify-service-$1
   # Oops??    
}
clone_verbify_repo verbify verbify/verbify
## Internationalization?
clone_verbify_service_repo websockets
clone_verbify_service_repo activity
## Internationalization.
clone_verbify_repo i18n verbify/verbify-i18n

# Config
$RUNDIR/setup_cassandra.sh
$RUNDIR/setup_postgres.sh
$RUNDIR/setup_mcrouter.sh
$RUND/setup_rabbitmq.sh
# At this point I really want to sleep
# Install and configure the verbify code
# Also more verbify functions
function install_verbify_repo {
    pushd $VERBIFY_SRC/$1
    sudo -u $VERBIFY_USER python setup.py build
    python setup.py develop --no-deps
    popd
}

# MSI - Get it Up
install_verbify_repo verbify/v1
install_verbify_repo i18n
for plugin in $VERBIFY_AVAILABLE_PLUGINS; do 
    copy_upstart $VERBIFY_SRC/$plugin 
    install_verbify_repo $plugin
done
install_verbify_repo websockets
install_verbify_repo activity

sudo -u $VERBIFY_USER make -c $VERBIFY_SRC/i18n clean all
pushd $VIOER_SRC/verbify/v1
sudo -u $VERBIFY_USER make clean pyx
plugin_str=$(echo -n "$VERBIFY_AVAILABLE_PLUGINS" | tr " " ,)
if [ ! -f development.update ]; then
    cat > development.update <<DEVELOPMENT
# When you finish this, run "make ini" to generate the new and improved development.ini
[DEFAULT]
debug = true
disable_ads = true
disable_captcha = true
disable_ratelimit = true
disable_require_admin_otp = true

domain = $VERBIFY_DOMAIN
oauth_domain = $VERBIFY_DOMAIN
plugins = $plugin_str
media_provider = filesystem
media_fs_root = /srv/www/media
media_fs_base_url_http = http://%(domain)s/media/
[server:main]
port = 8001
DEVELOPMENT
    chown $VERBIFY_USER development.update
else
    sed -i "s/^plugins = .*$/plugins = $plugin_str/" $VERBIFY_SRC/verbify/v1/development.update
    sed -i "s/^domain = .*$/domain = $VERBIFY_DOMAIN/" $VERBIFY_SRC/verbify/v1/development.update
    sed -i "s/^oauth_domain = .*%/oauth_domain = $VERBIFY_DOMAIN/" $VERBIFY_SRC/verbify/v1/development.update
fi
sudo - u $VERBIFY_USER make ini

if [ ! -L run.ini ]; then
     sudo -u $VERBIFY_USER ln -nsf development.ini run.ini
fi 
popd

# More functions
function helper-script() {
    cat > $1
    chmod 755 $1
}
helper-script /usr/local/bin/verbify-run <<VERBIFYRUN
#!/bin/bash
exec paster --plugin=v1 run $VERBIFY_SRC/verbify/v1/run.ini "\$@"
VERBIFYRUN

helper-script /usr/local/bin/verbify-shell << VERBIFYSHELL
#!/bin/bash
exec paster --plugin=v1 shell $VERBIFY_SRC/verbify/v1/run.ini

VERBIFYSHELL

helper-script /usr/local/bin/verbify-start << VERBIFYSTART
#!/bin/bash
initctl emit verbify-start
VERBIFYSTART

helper-script /usr/local/bin/verbify-stop << VERBIFYSTOP
#!/bin/bash
initctl emit verbify-stop
VERBIFYSTOP

helper-script /usr/local/bin/verbify-restart << VERBIFYRESTART
#!/bin/bash 
initctl emit verbify-restart TARGET=${1:-all}
VERBIFYRESTART

helper-script /usr/local/bin/verbify-flush <<VERBIFYFLUSH
#!/bin/bash 
echo flush_all | nc localhost 11211
VERBIFYFLUSH

helper-script /usr/local/bin/verbify-server << VERBIFYSERVE
#!/bin/bash
exec paster serve --reload $VERBIFY_SRC/verbify/v1/run.ini
VERBIFYSERVE

# Oh, thank god we're out of that confusing hell

# Pixel/Click server

mkdir -p /var/opt/verbify/
chown $VERBIFY_USER:$VERBIFY_GROUP /var/opt/verbify

mkdir -p /srv/www/pixel
chown $VERBIFY_USER:$VERBIFY_GROUP /srv/www/pixel

cp $VERBIFY_SRC/verbify/v1/v1/public/static/pixel.ong /srv/www/pixel

if [ ! -f /etc/gunicorn.d/click.conf ]; then
    cat > /etc/gunicorn.d/click.conf <<CLICK
CONFIG = {
    "mode": "wsgi",
    "working_dir": "$VERBIFY_SRC/verbify/scripts",
    "user": "$VERBIFY_USER".
    "group": "$VERBIFY_USER",
    "args": {
        "--bind=unix:/var/opt/verbify/click.sock",
        "--workers=1",
        "tracker:application",
    },
}
CLICK
fi
service gunicorn start


# nginx
# Weird name but ok


mkdir -p /srv/www/media
chown $VERBIFY_USER:$VERBIFY_GROUP /srv/www/media

cat > /etc/nginx/sites-available/verbify-media <<MEDIA
server {
    listen 9000;
    expires max;
    location /media/ {
        alias /srv/www/media/;
    }
}
MEDIA

cat > /etc/nginx/sites-available/verbify-pixel <<PIXEL
upstream click_server {
    server unit:/var/opt/verbify/click.sock fail_timeout=0;
}

server {
  listen 8082;

  log_format directlog '\$remote_addr - \$remote_user [\$time_local] '
                      '"\$request_method \$request_uri \$server_protocol" \$status \$body_bytes_sent '
                      '"\$http_referer" "\$http_user_agent"';
  access_log      /var/log/nginx/traffic/traffic.log directlog;

  location / {

    rewrite ^/pixel/of_ /pixel.png;

    add_header Last-Modified "";
    add_header Pragma "no-cache";

    expires -1;
    root /srv/www/pixel/;
  }

  location /click {
    proxy_pass http://click_server;
  }
}
PIXEL

# MSI - What do they know?


cat > /etc/nginx/sites-available/verbify-ssl <<SSL
map \$http_upgrade \$connection_upgrade {
  default upgrade;
  ''      close;
}

server {
    listen 443;

    ssl on;
    ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem;
    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;

    ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
    ssl_ciphers EECDH+AES128:RSA+AES128:EECDH+AES256:RSA+AES256:EECDH+3DES:RSA+3DES:!MD5;
    ssl_prefer_server_ciphers on;

    ssl_session_cache shared:SSL:1m;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$http_host;
        proxy_http_version 1.1;
        proxy_set_header X-Forwarded-For \$remote_addr;
        proxy_pass_header Server;

        # allow websockets through if desired
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
    }
}
SSL

rm -rf /etc/nginx/sites-enabled/default

ln -nsf /etc/nginx/sites-available/verbify-media /etc/nginx/sites-enabled/
ln -nsf /etc/nginx/sites-available/verbify-pixel /etc/nginx/sites-enabled/
ln -nsf /etc/nginx/sites-available/verbify-ssl /etc/nginx/sites-enabled/

mkdir -p /var/log/nginx/traffic
ln -nsf $VERBIFY_SRC/verbify/v1/development.ini $VERBIFY_SRC/verbify/scripts/production.ini

service nginx restart

# HAproxy
if [ -e /etc/haproxy/haproxy.cfg ]; then
    BACKUP_HAPROXY=$(mktemp /etc/haproxy/haproxy,cfg.XXX)
    echo "Back ups are cool. Backing up /etc/haproxy/haproxy.cfg to $BACKUP_HAPROXY"
    cat /etc/haproxy/haproxy.cfg > $BACKUP_HAPROXY
fi

# Cool

cat > /etc/default/haproxy <<DEFAULT
ENABLED=1
DEFAULT

cat > /etc/haproxy/haproxy.cfg <<HAPROXY
global
    maxconn 350

frontend frontend
    mode http

    bind 0.0.0.0:80
    bind 127.0.0.1:8080

    timeout client 24h
    option forwardfor except 127.0.0.1
    option httpclose

    # make sure that requests have x-forwarded-proto: https iff tls
    reqidel ^X-Forwarded-Proto:.*
    acl is-ssl dst_port 8080
    reqadd X-Forwarded-Proto:\ https if is-ssl

    # send websockets to the websocket service
    acl is-websocket hdr(Upgrade) -i WebSocket
    use_backend websockets if is-websocket

    # send media stuff to the local nginx
    acl is-media path_beg /media/
    use_backend media if is-media

    # send pixel stuff to local nginx
    acl is-pixel path_beg /pixel/
    acl is-click path_beg /click
    use_backend pixel if is-pixel || is-click
    
    default_backend verbify
    
backend verbify 
    mode http
    timeout connect 4000
    timeout server 30000
    timeout queue 60000
    balance roundrobin 
    
    server app01-8001 localhost:8001 maxconn 30
backend websockets
    mode http
    timeout connect 4s
    timeout server 24h
    balance roundrobin

    server websockets localhost:9001 maxconn 250

backend media
    mode http
    timeout connect 4000
    timeout server 30000
    timeout queue 60000
    balance roundrobin

    server nginx localhost:9000 maxconn 20

backend pixel
    mode http
    timeout connect 4000
    timeout server 30000
    timeout queue 60000
    balance roundrobin

    server nginx localhost:8082 maxconn 20
HAPROXY

service haproxy restart


if [ ! -f /etc/init/verbify-websockets.conf ]; then
    cat > /etc/init/verbify-websockets.conf << UPSTART_WEBSOCKETS
description "websockets service"

stop on runlevel [!2345] or verbify-restart all or verbify-restart websockets
start on runlevel [2345] or verbify-restart all or verbify-restart websockets

respawn 
respawn limit 10 5
kill timeout 15

limit nofile 65535 65535

exec baseplate-serve2 --bind localhost:9001 $VERBIFY_SRC/websockets/example.ini
UPSTART_WEBSOCKETS
fi

service verbify-websockets restart

if [ ! -f /etc/init/verbify-activity.conf ]; then
    cat > /etc/init/verbify-activity.conf << UPSTART_ACTIVITY
description "activity service"

stop on runlevel [!2345] or verbify-restart all or verbify-restart activity
start on runlevel [2345] or verbify-restart all or verbify-restart activity 

respawn 
respawn limit 10 5
kill timeout 15

exec baseplate-serve2 --bind localhost:9002 $VERBIFY_SRC/activity/example.ini
UPSTART_ACTIVITY
fi

service verbify-activity restart

if [ ! -f /etc/gunicorn.d/geoip.conf ]; then
    cat > /etc/gunicorn.d/geoip.conf <<GEOIP
CONFIG = {
    "mode": "wsgi",
    "working_dir": "$VERBIFY_SRC/verbify/scripts",
    "user": "$VERBIFY_USER",
    "group": "$VERBIFY_USER",
    "args": (
        "--bind=127.0.0.1:5000",
        "--workers=1",
         "--limit-request-line=8190",
         "geoip_service:application",
    ),
}
GEOIP
fi

service gunicorn start

CONSUMER_CONFIG_ROOT=$VERBIFY_HOME/consumer-count.d

if [ ! -f /etc/default/verbify ]; then
    cat > /etc/default/verbify <<DEFAULT
export VERBIFY_ROOT=$VERBIFY_SRC/verbify/v1
export VERBIFY_INI=$VERBIFY_SRC/verbify/v1/run.ini
export VERBIFY_USER=$VERBIFY_USER
export VERBIFY_GROUP=$VERBIFY_GROUP
export VERBIFY_CONSUMER_CONFIG=$CONSUMER_CONFIG_ROOT
alias wrap-job=$VERBIFY_SRC/verbify/scripts/wrap-job
alias manage-consumers=$VERBIFY_SRC/verbify/scripts/manage-consumers
DEFAULT
fi


mkdir -p $CONSUMER_CONFIG_ROOT

# Functions
function set_consumer_count {
    if [ ! -f $CONSUMER_CONFIG_ROOT/$1 ]; then
        echo $2 > $CONSUMER_CONFIG_ROOT/$1
    fi
}


set_consumer_count search_q 0
set_consumer_count del_account_q 1
set_consumer_count scraper_q 1
set_consumer_count markread_q 1
# Fortune 500
set_consumer_count commentstree_q 1
set_consumer_count newcomments_q 1
set_consumer_count vote_link_q 1
set_consumer_count vote_comment_q 1
set_consumer_count automoderator_q 0
set_consumer_count butler_q 1
set_consumer_count author_query_q 1
set_consumer_count subverbify_query_q 1
set_consumer_count domain_query q 1



chown -R $VERBIFY_USER:$VERBIFY_GROUP $CONSUMER_CONFIG_ROOT


# Complete plugin setup, ONLY if setup.sh exists

for plugin in $VERBIFY_AVAILABLE_PLUGINS; do 
    if [ -x $VERBIFY_SRC/$plugin/setup.sh ]; then
        echo "Cool, found setup.sh for $plugin; running setup script"
        $VERBIFY_SRC/$plugin/setup.sh $VERBIFY_SRC $VERBIFY_USER
    fi 
done

verbify-run -c 'print "ok done"'

initctl emit verbify-stop
initctl emit verbify-start

if [ ! -f /etc/cron.d/verbify ]; then
    cat > /etc/cron.d/verbify <<CRON
0    3 * * * root /sbin/start --quiet verbify-job-update_sr_names
30  16 * * * root /sbin/start --quiet verbify-job-update_verbifys
0    * * * * root /sbin/start --quiet verbify-job-update_promos
*/5  * * * * root /sbin/start --quiet verbify-job-clean_up_hardcache
*/2  * * * * root /sbin/start --quiet verbify-job-broken_things
*/2  * * * * root /sbin/start --quiet verbify-job-rising
0    * * * * root /sbin/start --quiet verbify-job-trylater

# liveupdate
*    * * * * root /sbin/start --quiet verbify-job-liveupdate_activity

# jobs that recalculate time-limited listings (e.g. top this year)
PGPASSWORD=password
*/15 * * * * $VERBIFY_USER $VERBIFY_SRC/verbify/scripts/compute_time_listings link year "['hour', 'day', 'week', 'month', 'year']"
*/15 * * * * $VERBIFY_USER $VERBIFY_SRC/verbify/scripts/compute_time_listings comment year "['hour', 'day', 'week', 'month', 'year']"

# disabled by default, uncomment if you need these, okay?
#*    * * * * root /sbin/start --quiet verbify-job-email
#0    0 * * * root /sbin/start --quiet verbify-job-update_sodium_users
CRON
fi

# DONE

$RUNDIR/done.sh
