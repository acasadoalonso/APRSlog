#!/usr/bin/python
#
# Python code to show access to OGN Beacons
#
# Version for gathering all the records for the world

from datetime import datetime
from libfap import *
from ctypes import *
import socket
import time
import config
import string
#import ephem
import pytz
import sys
import os
import signal
from   parserfuncs import *                 # the ogn/ham parser functions
from   geopy.distance import vincenty       # use the Vincenty algorithm^M
#from   geopy.geocoders import GeoNames      # use the Nominatim as the geolocator^M
import MySQLdb                              # the SQL data base routines^M

#########################################################################
def shutdown(sock, datafile):               # shutdown routine, close files and report on activity
                                                                                # shutdown before exit
        libfap.fap_cleanup()                # close lifap in order to avoid memory leaks
        sock.shutdown(0)                    # shutdown the connection
        sock.close()                        # close the connection file
        datafile.close()                    # close the data file
        print 'Records read:',cin, ' DB records created: ',cout    # report number of records read and IDs discovered
        conn.commit()                   # commit the DB updates
        conn.close()                    # close the database
        local_time = datetime.now() # report date and time now
        print "Time now:", local_time, " Local time."
        return                          # job done

#########################################################################

#########################################################################
def alive(first='no'):

        if (first == 'yes'):
                alivefile = open (config.DBpath+"APRS.alive", 'w') # create a file just to mark that we are alive
        else:
                alivefile = open (config.DBpath+"APRS.alive", 'a') # append a file just to mark that we are alive
        local_time = datetime.now()
        alivetime = local_time.strftime("%y-%m-%d %H:%M:%S")
        alivefile.write(alivetime+"\n") # write the time as control
        alivefile.close()               # close the alive file
#########################################################################
#########################################################################

def signal_term_handler(signal, frame):
    print 'got SIGTERM ... shutdown orderly'
    libfap.fap_cleanup()                        # close libfap
    shutdown(sock, datafile ) # shutdown orderly
    sys.exit(0)

# ......................................................................#
signal.signal(signal.SIGTERM, signal_term_handler)
# ......................................................................#

#
########################################################################

cin   = 0                               # input record counter
cout  = 0                               # output file counter
i     = 0                               # loop counter
err   = 0

fsllo={'NONE  ' : 0.0}                  # station location longitude
fslla={'NONE  ' : 0.0}                  # station location latitude
fslal={'NONE  ' : 0.0}                  # station location altitude
fslod={'NONE  ' : (0.0, 0.0)}           # station location - tuple
fsmax={'NONE  ' : 0.0}                  # maximun coverage
fsalt={'NONE  ' : 0}                    # maximun altitude

# --------------------------------------#
DATA=True
RECV=True
DBhost   =config.DBhost
DBuser   =config.DBuser
DBpasswd =config.DBpasswd
DBname   =config.DBname
# --------------------------------------#
conn=MySQLdb.connect(host=DBhost, user=DBuser, passwd=DBpasswd, db=DBname)
curs=conn.cursor()                      # set the cursor
date=datetime.utcnow()         # get the date
dte=date.strftime("%y%m%d")             # today's date

#----------------------ogn_SilentWingsInterface.py start-----------------------

print "Start APRS logging  V1.0"
print "========================"
print "MySQL: Database:", DBname, " at Host:", DBhost
print "Date: ", date, "UTC on:", socket.gethostname()
date = datetime.now()
print "Time now is: ", date, " Local time"

prtreq =  sys.argv[1:]
if prtreq and prtreq[0] == 'prt':
    prt = True
else:
    prt = False

if prtreq and prtreq[0] == 'DATA':
    DATA = True
    RECV = False
elif prtreq and prtreq[0] == 'RECV':
    RECV = True
    DATA = False
else:
    RECV = True
    DATA = True

# create socket & connect to server
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((config.APRS_SERVER_HOST, config.APRS_SERVER_PORT))
print "Socket sock connected"

# logon to OGN APRS network

login = 'user %s pass %s vers APRS_LOG V1.0 %s'  % (config.APRS_USER, config.APRS_PASSCODE , config.APRS_FILTER_DETAILS)
sock.send(login)

# Make the connection to the server
sock_file = sock.makefile()

# Initialise libfap.py for parsing returned lines
print "libfap_init"
libfap.fap_init()
start_time = time.time()
local_time = datetime.now()
fl_date_time = local_time.strftime("%y%m%d")
OGN_DATA = config.DBpath + "APRS" + fl_date_time+'.log'
print "APRS data file is: ", OGN_DATA
datafile = open (OGN_DATA, 'a')
keepalive_count = 1
keepalive_time = time.time()
alive("yes")
#
#-----------------------------------------------------------------
# Initialise API for computing sunrise and sunset
#-----------------------------------------------------------------
#

date = datetime.now()

try:

    while True:
        current_time = time.time()
        local_time = datetime.now()
        if local_time.hour == 22:
                break
        elapsed_time = current_time - keepalive_time
        if (current_time - keepalive_time) > 180:        # keepalives every 3 mins
                try:
                        rtn = sock_file.write("#Python ognES App\n\n")
                        # Make sure keepalive gets sent. If not flushed then buffered
                        sock_file.flush()
                        datafile.flush()
                        alive()                                 # indicate that we are alive
                        run_time = time.time() - start_time
                        if prt:
                                print "Send keepalive no: ", keepalive_count, " After elapsed_time: ", int((current_time - keepalive_time)), " After runtime: ", int(run_time), " secs"
                        keepalive_time = current_time
                        keepalive_count = keepalive_count + 1
                except Exception, e:
                        print ('something\'s wrong with socket write. Exception type is %s' % (`e`))

        if prt:
                print "In main loop. Count= ", i
                i += 1
        try:
                # Read packet string from socket
                packet_str = sock_file.readline()

                if len(packet_str) > 0 and packet_str[0] <> "#" and config.LogData:
                        datafile.write(packet_str)

        except socket.error:
                print "Socket error on readline"
                continue
        # A zero length line should not be return if keepalives are being sent
        # A zero length line will only be returned after ~30m if keepalives are not sent
        if len(packet_str) == 0:
                err +=1
                if err > 9:
                        print "Read returns zero length string. Failure.  Orderly closeout"
                        date = datetime.now()
                        print "UTC now is: ", date
                        break
                else:
                        continue

        ix=packet_str.find('>')
        cc= packet_str[0:ix]
        packet_str=cc.upper()+packet_str[ix:]
	msg={}
	msg=parseraprs(packet_str, msg)
        if  len(packet_str) > 0 and packet_str[0] <> "#":

        	msg=parseraprs(packet_str, msg)
		print msg
                id=msg['id']                         # id
                longitude = msg['longitude']
                latitude  = msg['latitude']
                altitude  = msg['altitude']
                path      = msg['path']
                otime     = msg['otime']
                type      = msg['type']
                data=packet_str
                if prt:
                        print 'Packet returned is: ', packet_str
                        print 'Callsign is: ', callsign, 'DST CallSign:', dst_callsign, 'Dest: ', destination, 'header: ', header, "OTime:", otime
                cin += 1                                # one more file to create
                if path == 'TCPIP*':                    # handle the TCPIP
                        if longitude == -1 and latitude == -1:
                                continue                # wrong station
                        if not id in fslod :
                           fslla[id]=latitude           # save the location of the station
                           fsllo[id]=longitude          # save the location of the station
                           fslal[id]=altitude           # save the location of the station
                           fslod[id]=(latitude, longitude) # save the location of the station
                           fsmax[id]=0.0                # initial coverage zero
                           fsalt[id]=0                  # initial coverage zero
                        status=msg['status']
                        temp=msg['temp']
                        version=msg['version']
                        cpu=msg['cpu']
                        rf=msg['rf']
                        inscmd="insert into RECEIVERS values ('%s', %f,  %f,  %f, '%s', '%s', %f, %f, '%s', '%s')" %\
                                         (id, latitude, longitude, altitude, otime, version, cpu, temp, rf, status)
                        try:
                                        curs.execute(inscmd)
                        except MySQLdb.Error, e:
                                        try:
                                                print ">>>MySQL Error [%d]: %s" % (e.args[0], e.args[1])
                                        except IndexError:
                                                print ">>>MySQL Error: %s" % str(e)
                                        print ">>>MySQL error:", cout, inscmd
                                        print ">>>MySQL data :",  data
                        cout +=1
                        conn.commit()
                        continue
                if path == 'qAC':
                        print "qAC>>>:", data
                        continue                        # the case of the TCP IP as well
                if path == 'qAS' or path == 'RELAY*':                       # if std records
                        station=msg['station']
                else:
                        continue                        # nothing else to do
                #
                speed     = msg['speed']
                course    = msg['course']
                uniqueid  = msg['uniqueid']
                extpos    = msg['extpos']
                roclimb   = msg['roclimb']
                rot       = msg['rot']
                sensitivity= msg['sensitivity']
                gps       = msg['gps']
                hora      = msg['time']
                altim=altitude                          # the altitude in meters
                if altim > 15000 or altim < 0:
                        altim=0
                        alti='%05d' % altim             # convert it to an string
                dist=-1
                if station in fslod:                    # if we have the station yet
                        distance=vincenty((latitude, longitude), fslod[station]).km    # distance to the station
                        dist=distance
                        if distance > 300.0:
                            print "distcheck: ", distance, data
                if prt:
                        print 'Parsed data: POS: ', longitude, latitude, altitude,' Speed:',speed,' Course: ',course,' Path: ',path,' Type:', type
                        print "RoC", roclimb, "RoT", rot, "Sens", sensitivity, gps, uniqueid, dist, extpos, ":::"
                        # write the DB record

                if (DATA):
                        date=datetime.utcnow()         # get the date
                        dte=date.strftime("%y%m%d")             # today's date
                        addcmd="insert into OGNDATA values ('" +id+ "','" + dte+ "','" + hora+ "','" + station+ "'," + str(latitude)+ "," + str(longitude)+ "," + str(altim)+ "," + str(speed)+ "," + \
                        str(course)+ "," + str(roclimb)+ "," +str(rot) + "," +str(sensitivity) + \
                                        ",'" + gps+ "','" + uniqueid+ "'," + str(dist)+ ",'" + extpos+ "') ON DUPLICATE KEY UPDATE extpos = '!ZZZ!' "
                        try:
                                curs.execute(addcmd)
                        except MySQLdb.Error, e:
                                try:
                                        print ">>>MySQL Error [%d]: %s" % (e.args[0], e.args[1])
                                except IndexError:
                                                print ">>>MySQL Error: %s" % str(e)
                                print ">>>MySQL error:", cout, addcmd
                                print ">>>MySQL data :",  data
                        cout +=1
                        conn.commit()                   # commit the DB updates


except KeyboardInterrupt:
    print "Keyboard input received, ignore"
    pass

shutdown(sock, datafile)
print "Exit now ..."
exit(1)

