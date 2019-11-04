#!/bin/bash
alive=$"/nfs/OGN/SWdata/APRS.alive"
if [ ! -f $alive ]
then
                logger  -t $0 "APRS Log is not alive"
                pnum=$(pgrep -x -f "python3 /home/angel/src/APRSsrc/main/aprslog.py")
                if [ $? -eq 0 ] # if OGN repo interface is  not running
                then
                        sudo kill $pnum
                fi
#               restart OGN data collector
                bash /home/angel/src/APRSsrc/main/sh/aprslog.sh 
                logger -t $0 "APRS Log seems down, restarting"
                date >>/nfs/OGN/SWdata/.APRSrestart.log
else
                logger -t $0 "APRS Log is alive"
		rm $alive
fi

