#!/bin/bash
# load configuration
RUNDIR=$(dirname $0)
source $RUNDIR/install.cfg

cat <<CONCLUSION
Whaaat?
Verbify is installed!
Woot
The application code is managed with 'upstart' to see what is already running running  
    
    sudo initctl list | grep verbify
    
Cron jobs start with 'verbify-job-" and processers start with
"verbify-consumer-". THe crons are managed by /etc/cron.d/verbify
You can restart all of the consumers by running
    
    sudo verbify-restart
Or you can go trigger happy and target a specific one

   sudo verbify-restart scraper_q
   
You can shut down or start up the code with 

 sudo verbify-stop
 sudo verbify-start
 
And if you and the caching are in an abusive relationship. You can 'flush' it out with 
 
 
  verbify-flush
  
Now that the core of verbify is installed, you may want to do some additional
steps:

* Ensure that $VERBIFY_DOMAIN resolves to this machine.

* To populate the database with test data, run:

    cd $VERBIFY_SRC/verbify
    verbify-run scripts/inject_test_data.py -c 'inject_test_data()'

* Manually run verbify-job-update_verbifys immediately after populating the db
  or adding your own subverbifys.
CONCLUSION
