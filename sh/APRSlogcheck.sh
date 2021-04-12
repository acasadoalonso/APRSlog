#!/bin/bash

if [ -z $CONFIGDIR ]
then 
     export CONFIGDIR=/etc/local
fi
DBuser=$(echo    `grep '^DBuser '   $CONFIGDIR/APRSconfig.ini` | sed 's/=//g' | sed 's/^DBuser //g')
DBpasswd=$(echo  `grep '^DBpasswd ' $CONFIGDIR/APRSconfig.ini` | sed 's/=//g' | sed 's/^DBpasswd //g' | sed 's/ //g' )
DBpath=$(echo    `grep '^DBpath '   $CONFIGDIR/APRSconfig.ini` | sed 's/=//g' | sed 's/^DBpath //g' | sed 's/ //g' )
pid=$(echo  `grep '^pid'            $CONFIGDIR/APRSconfig.ini` | sed 's/=//g' | sed 's/^pid//g')
alive=$DBpath"APRS"$(hostname)".alive"
if [ ! -f $alive ]
then
                logger  -t $0 "APRS Log is not alive"
                if [ -f $pid ] # if OGN repo interface is  not running
                then
                        pnum=$(cat $pid)
                        logger  -t $0 "APRS Log Killing process: "$pnum
                        sudo kill $pnum 
                fi
#               restart OGN data collector
                bash ~/src/APRSsrc/main/sh/APRSlog.sh 
                echo $(date)" - "$(hostname)  >>$DBpath/.APRSrestart.log
                sleep 10
                if [ -f $pid ] # if we have PID file
                then
                   logger -t $0 "APRS Log seems down, restarting: "$(cat $pid)
                else
                   logger -t $0 "APRS Log seems down, restarting, no PID yet "
                fi
else
		if [ ! -f $pid ]
		then
                	logger -t $0 "APRS NOPID yet Log is alive Process: "$alive
		else
                	logger -t $0 "APRS Log is alive Process: "$(cat $pid)" "$alive
		fi
		rm $alive
fi

