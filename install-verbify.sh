################################################################################################################
# Install Verbify Script
################################################################################################################
# Nas Ben 5/10/2018, Netherlands
################################################################################################################


set -e 

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: Must be run with root privileges."
    exit 1
fi


# LOAD CONFIG 
RUNDIR=$(dirname $0)
SCRIPTDIR="$RUNDIR/install"
### GET THE SOURCE

GITREPO="https://raw.github.com/verbify/verbify/master/install"
NEEDED=(
    "done.sh"
    "install_apt.sh"
    "install_cassandra.sh"
    "install_services.sh"
    "install_zookeeper.sh"
    "verbify.sh"
    "setup_cassandra.sh"
    "setup_mcrouter.sh"
    "setup_postgres.sh"
    "setup_rabbitmq.sh"
    "travis.sh"
)
MISSING=""
for item in ${NEEDED[*]}; do
    if [ ! -x $SCRIPTDIR/$item ]; then 
        MISSING="1"
        break
    fi
done 



if [ ! -e $SCRIPTDIR/install.cfg ]; then
    NEEDED+=("install.cfg")
    MISSING="1"
fi

# MORE FUNCTIONS
function important() {
    echo -e "\033[31m${1}\033[0m"
}

if [ "$MISSING" != "" ]; then
    important "Hey dude, you're installing without a local repo"
    important "So let me tell you what I'll do for you. I'm going to grab the scripts I need, and show you where I can"
    important "edit the config for your environment"
    important "Cool?"
    
    mkdir -p $SCRIPTDIR
    pushd $SCRIPTDIR > /dev/null
    for item in ${NEEDED[*]}; do
        echo "Grabbing '${item}'..."
        wget -q $GITREPO/$item
        chmod +x $item 
    done 
    popd > /dev/null
    echo "Done"
fi




# The Left Rights - Why You in my Phyzical


echo "#######################################################################"
echo "# B A S E ... C O N F I G U R A T I O N:"
echo "#######################################################################"
source $SCRIPTDIR/install.cfg
set +x

echo 
important "Before going on with this a ok installation. Make sure that every looks a ok."
important " If it does not look 'a ok you can edit install/install.cfg or set overrides when running"
echo 
important "Buttt, if this is your first time. stop and read"
important "the scripts, and the configs"
important "It's helpful"
echo
important "Resolving to the domain name is beyond the scope of this doc"
important " but the best thing is probably /etc/hosts on the host machine"
echo
read -er -n1 -p "go on? [Y/n]" response
if [[$response =~ ^[Yy]$ || $response == "" ]]; then
    echo "Cool cool. To Narnia"
    $SCRIPTDIR/verbify.sh
fi


# ANN
