
#
# Python code to push into the OGN APRS the delayed unencrypted PARS messages
#

import socket
import string
import sys
import os
import time
import os.path
import psutil
import signal
import atexit
import MySQLdb                          # the SQL data base routines^M
import json
import ogndecode
import argparse
from ctypes import *
from time import sleep                  # use the sleep function
from datetime import datetime, timedelta
from ogn.parser import parse
from parserfuncs import deg2dmslat, deg2dmslon, dao, alive
from ogntfuncs import *

#########################################################################


def shutdown(sock, prt=False):          # shutdown routine, close files and report on activity
                                        # shutdown before exit
    global numaprsmsg
    try:
        sock.shutdown(0)                # shutdown the connection
        sock.close()                    # close the connection file
    except Exception as e:
        print("Socket error...")
    conn.commit()                       # commit the DB updates
    conn.close()                        # close the database
    local_time = datetime.now()         # report date and time now
    now = datetime.utcnow()    		# get the date
    print("\n\n=================================================\nQueue: ", len(queue), now, "\n\n")
    i=1
    for e in queue:			# dump the entries on the queue
          etime=e['TIME']
          print (i, now-etime, "==>", etime, e['ID'], e['station'], e['hora'], e['rest'])
          if (prt):
          	print(json.dumps(e['DECODE'], skipkeys=True, indent=4))
          aprsmsg=genaprsmsg(e)	# gen the APRS message
          aprsmsg += " %ddly \n"%delta.seconds	# include information about the delay
          print("APRSMSG: ", e["NumDec"], aprsmsg)	# print for debugging
          rtn = config.SOCK_FILE.write(aprsmsg)	# send it to the APRS server
          i += 1			# one more to delete from table
          numaprsmsg += 1		# counter of published APRS msgs
    print("Shutdown now, Time now:", local_time, " Local time.")
    print("Number of records read: %d Trk status: %d Decodes: %d APRS msgs gen: %d Num Err Decodes %d \n" % (inputrec, numtrksta, numdecodes, numaprsmsg, numerrdeco))
    mem =  process.memory_info().rss  	# in bytes
    print("Memory available:", mem)
    if os.path.exists(config.DBpath+"DLYM2OGN.alive"):
                                        # delete the mark of being alive
        os.remove(config.DBpath+"DLYM2OGN.alive")
    return                              # job done

#########################################################################

#########################################################################
#########################################################################


def signal_term_handler(signal, frame):
    print('got SIGTERM ... shutdown orderly')
    shutdown(sock) 			# shutdown orderly
    sys.exit(0)


# ......................................................................#
signal.signal(signal.SIGTERM, signal_term_handler)
# ......................................................................#


def prttime(unixtime):
    # get the time from the timestamp
    tme = datetime.utcfromtimestamp(unixtime)
    return(tme.strftime("%H%M%S"))			# the time


#
########################################################################
def genaprsmsg(entry):					# format the reconstructed APRS message
            decode             =entry["DECODE"]
            ID                 =entry["ID"]
            station            =entry["station"]
            hora               =entry["hora"]
            resto               =entry["rest"]
            latitude           =decode["Lat"]
            longitude          =decode["Lon"]
            altitude           =decode["Alt"]
            course             =decode["Heading"]
            speed              =decode["Speed"]
            roclimb            =decode["RoC"]*3.28084
            RoT                =decode["RoT"]
            DOP                =decode["DOP"]
                                                        # swap 2nd and 3rd words in rest of message
            sp1=resto.find(' ')				# find the end of first word
            sp2=resto[sp1+1:].find(' ')+1+sp1  
            rest=resto[0:sp1]+' '+resto[sp2+1:]+' '+resto[sp1+1:sp2]

                                                        # build the APRS message
            lat = deg2dmslat(abs(latitude))
            if latitude > 0:
                        lat += 'N'
            else:
                        lat += 'S'
            lon = deg2dmslon(abs(longitude))
            if longitude > 0:
                        lon += 'E'
            else:
                        lon += 'W'
            
            ccc = "%03d" % int(course)
            sss = "%03d" % int(speed)
            daotxt="!W"+dao(latitude)+dao(longitude)+"!"	# the extended precision

            DOP=10+DOP
            HorPrec=int((DOP*2+5)/10 )
            if(HorPrec>63):
                HorPrec=63
            VerPrec=int((DOP*3+5)/10 )
            if(VerPrec>63): 
                VerPrec=63
            gpstxt="gps"+str(HorPrec)+"x"+str(VerPrec)

            aprsmsg = ID+">OGNTRK,OGNDELAY*,"+station+":/" + hora+lat+"/"+lon+"'"+ccc+"/"+sss+"/"
            if altitude > 0:
                        altitude=int(altitude*3.28084)		# convert ot feet
                        aprsmsg += "A=%06d" % altitude
            aprsmsg += " "+daotxt+" id06"+ID[3:]+" %+04dfpm " % (int(roclimb))+"%+04.1frot" % (float(RoT)) +rest+" "+gpstxt

            return(aprsmsg)
#
########################################################################
#
programver = 'V1.0'
print("\n\nStart DLYM2OGN "+programver)
print("===================")

print("Program Version:", time.ctime(os.path.getmtime(__file__)))
print("==========================================")
date = datetime.utcnow()         		# get the date
dte = date.strftime("%y%m%d")             # today's date
print("\nDate: ", date, "UTC on SERVER:", socket.gethostname(), "Process ID:", os.getpid())
date = datetime.now()                   # local time

# --------------------------------------#
#
# get the configuration data
#
# --------------------------------------#
import config                           # get the configuration data
if os.path.exists(config.DLYPIDfile):
    raise RuntimeError("DLY2APRS already running !!!")
    exit(-1)
#
import locale
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
APP         = "DLYM2OGN"		# the application name
SLEEP       = 10			# sleep 10 seconds in between calls to the APRS
DELAY       = config.DELAY		# 20 minutes delay
nerrors     = 0				# number of errors in *funcs found
day         = 0				# day of running
loopcount   = 0				# counter of loops
inputrec    = 0				# number of input records
numerr      = 0				# number of errors
numtrksta   = 0 			# number of tracker status records
numdecodes  = 0				# number of records decoded
numaprsmsg  = 0				# number of APRS messages generated
numerrdeco  = 0				# number of APRS messages generated
maxnerrs    = 100
queue       = []			# queue of pending messages
trackers    = {}			# list of seems trackers encoding
utrackers   = {}			# list of seems trackers non encoding
ognttable   = {}			# init the instance of the table
# --------------------------------------#
DBpath      = config.DBpath
DBhost      = config.DBhost
DBuser      = config.DBuser
DBpasswd    = config.DBpasswd
DBname      = config.DBname
# we force everything FALSE as we try to push to the APRS
SPIDER      = False
SPOT        = False
INREACH     = False
CAPTURS     = False
SKYLINE     = False
LT24        = False
OGNT        = False
# --------------------------------------#


parser = argparse.ArgumentParser(description="OGN Push to the OGN APRS the delayed tracks")
parser.add_argument('-p',  '--print',     required=False,
                    dest='prt',   action='store', default=False)
parser.add_argument('-dly', '--delay', required=False,
                    dest='dly',       action='store', default=-1)
parser.add_argument('-l', '--log', required=False,
                    dest='log',       action='store', default='/tmp/DLY.log')
args = parser.parse_args()
prt = args.prt				# print on|off
dly = args.dly				# delay in seconds, default config.DELAY
log = args.log				# name of the logfile
if (dly == -1):
   DELAY=config.DELAY
else:
   DELAY=int(dly)

# -----------------------------------------------------------------#
conn = MySQLdb.connect(host=DBhost, user=DBuser, passwd=DBpasswd, db=DBname)
curs = conn.cursor()               # set the cursor

print("Time now is: ", date, " Local time, using DELAY: ", DELAY)
print("MySQL: Database:", DBname, " at Host:", DBhost)
# --------------------------------------#
			# build the table from the TRKDEVICES DB table
ogntbuildtable(conn, ognttable, prt)

# --------------------------------------#

#----------------------dlym2ogn.py start-----------------------#


with open(config.DLYPIDfile, "w") as f:	# set the lock file  as the pid
    f.write(str(os.getpid()))
    f.close()
atexit.register(lambda: os.remove(config.DLYPIDfile))

logfile=open(log, "w")   	# set the log file
logfile.write(str(os.getpid())+' '+str(date)+'\n')
logfile.flush()
# create socket & connect to server
server=config.APRS_SERVER_HOST
server="aprs.glidernet.org"
server="glidern1.glidernet.org"
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((server, config.APRS_SERVER_PORT))
print("Socket sock connected to: ", server, ":", config.APRS_SERVER_PORT)

# logon to OGN APRS network
config.APRS_USER='DLY2APRS'
config.APRS_PASSCODE='32159'

login = 'user %s pass %s vers DLY2APRS %s filter %s' % (config.APRS_USER, config.APRS_PASSCODE, programver, " b/OGN* \n")
login=login.encode(encoding='utf-8', errors='strict')
sock.send(login)

# Make the connection to the server
sock_file = sock.makefile(mode='rw')    # make read/write as we need to send the keep_alive

config.SOCK = sock
config.SOCK_FILE = sock_file
print("APRS Version:", sock_file.readline())
sleep(2)
print("APRS Login request:", login)
print("APRS Login reply:  ", sock_file.readline())


# Initialise libfap.py for parsing returned lines
start_time = time.time()
local_time = datetime.now()
keepalive_count = 1
keepalive_time = time.time()
alive(config.DBpath+APP, first='yes')
#
#-----------------------------------------------------------------#
# Initialise API for DLYM2OGN
#-----------------------------------------------------------------#
#
now = datetime.utcnow()			# get the UTC timea
min5 = timedelta(seconds=300)		# 5 minutes ago
now = now-min5				# now less 5 minutes
# number of seconds until beginning of the day 1-1-1970
td = now-datetime(1970, 1, 1)
ts = int(td.total_seconds())		# Unix time - seconds from the epoch
ttime = now.strftime("%Y-%m-%dT%H:%M:%SZ")  # format required by 
# --------------------------------------#
from Keys import *
keyfile="keyfile.encrypt"		# name where it is the keys encrypted
keypriv="utils/keypriv.PEM"		# name of the private key file (PEM)

DK=[]					# decrypting keys 
if os.path.exists(keyfile):		# check for the encrypted keyfile
      privkey=getprivatekey(keypriv)	# get the private key
      decKey=getkeyfromencryptedfile(keyfile,privkey).decode('utf-8')
      if prt:
         print ("DKfile", decKey)
      DK=getkeys(DK,decKey)		# get the keys
      if prt:
         print (DK)
else:
      print ("ERROR: No key file found !!!")
      exit (-1)
# --------------------------------------#
day = now.day				# day of the month
process = psutil.Process(os.getpid())	# process info





try:

#----------------------dlym2ogn.py main loop-----------------------#
    while True:
        func='NONE'
        current_time = time.time()
        local_time = datetime.now()
        elapsed_time = current_time - keepalive_time    # time since last keep_alive
        if (current_time - keepalive_time) > 180:      	# keepalives every 3 mins
                                                        # and mark that we are still alive
            alive(config.DBpath+APP)			# mark that we are alive
            mem =  process.memory_info().rss  		# in bytes
            logfile.write(str(local_time)+' '+str(mem)+'\n')	# mark the time
            logfile.flush()				# write the records
            run_time = time.time() - start_time
            keepalive_time = current_time
            keepalive_count = keepalive_count + 1       # just a control

            try:					# lets send a message to the APRS for keep alive
                rtn = sock_file.write("#Python ogn aprspush App\n\n")
                sock_file.flush()		        # Make sure keepalive gets sent. If not flushed then buffered

            except Exception as e:
                print(( 'Something\'s wrong with socket write. Exception type is %s' % (repr(e))))
                now = datetime.utcnow()		        # get the UTC time
                print("UTC time is now: ", now, keepalive_count, run_time)

        now = datetime.utcnow()				# get the UTC time
                                                        # number of second until beginning of the epoch
        tt = int((now-datetime(1970, 1, 1)).total_seconds())
        if now.day != day:				# check if day has changed
            print("End of Day...")
            shutdown(sock)				# recycle
            exit(0)


        loopcount += 1			        	# we report a counter of calls to the interfaces


        sys.stdout.flush()				# flush the print messages
        if prt:
            print("In main loop. Count= ", inputrec)
        inputrec += 1
        try:
            packet_str = sock_file.readline() 		# Read packet string from socket

            if len(packet_str) > 0 and packet_str[0] != "#" and config.LogData:
                datafile.write(packet_str)		# log the data if requested
            if prt:
                print(packet_str)
        except socket.error:
            print("Socket error on readline")
            continue
        if prt:
            print(packet_str)
        # A zero length line should not be return if keepalives are being sent
        # A zero length line will only be returned after ~30m if keepalives are not sent
        if len(packet_str) == 0:
            numerr += 1				# increase error counter
            if numerr > maxnerrs:		# if too mane errors
                print("Read returns zero length string. Failure.  Orderly closeout", err)
                date = datetime.now()
                print("UTC now is: ", date)
                break
            else:
                sleep(5) 			# wait 5 seconds
                continue

        ix = packet_str.find('>')
        cc = packet_str[0:ix]
        packet_str = cc.upper()+packet_str[ix:]	# convert the ID to uppercase
        msg = {}

        					# if not a heartbeat from the server
        if len(packet_str) > 0 and packet_str[0] != "#":
#########################################################################################
						# deal with a normal APRS message
            s=packet_str
            ph=s.find(":>")
            hora=s[ph+2:ph+9]
            try:
               beacon=parse(s)  		# parse the APRS message
            except Exception as e:
               print("DLY: parse error >>>>", e, s, "<<<<\n")
               continue
						# check if is a OGN tracker status message
            if beacon["aprs_type"] == "status" and beacon["beacon_type"] == "tracker" and beacon["dstcall"] == "OGNTRK" and "comment" in beacon:
               comment=beacon['comment']	# get the comment where it is the data
            else:
               continue				# otherwise ignore it	
            #print("ORIGMSG: ", s)
            #print (beacon)
            sp=comment.find(' ')		# look for the first space
            txt=comment[0:sp]			# that is the text to decode
            rest=comment[sp:]			# save the rest: freq deviation, error bits, ... 
            ident = beacon['name']		# tracker ID
            station = beacon['receiver_name'] 	# station
            #print ("Txt:>>>", len(txt), txt, ":::>", sp, rest, ":::>", s, "\n")
            jstring="                   "
            if (len(txt) != 20):		# those are encoded tracker messages 
                status = beacon['comment']	# NO ... get the status message
                                                # and the station receiving that status report
                otime = beacon['reference_timestamp']	# get the time from the system
                if len(status) > 254:
                    status = status[0:254]
                #print ("Status report >>>>>>>>>>>:", ident, station, otime, status)
                inscmd = "insert into OGNTRKSTATUS values ('%s', '%s', '%s', '%s' )" % (ident, station, otime, status)
                try:
                    curs.execute(inscmd)
                except MySQLdb.Error as e:
                    try:
                        print(">>>MySQL1 Error [%d]: %s" % (
                            e.args[0], e.args[1]))
                    except IndexError:
                        print(">>>MySQL2 Error: %s" % str(e))
                    print(">>>MySQL3 error:",  numtrksta, inscmd)
                    print(">>>MySQL4 data :",  s)
                numtrksta += 1			# number of records saved
                ID = ident
                if not ID in utrackers:   	# did we see this tracker
                          utrackers[ID] = 1    	# init the counter
                else:
                          utrackers[ID] += 1   	# increase the counter

                continue			# nothing else to do

						# deal with the decoding
            if ident not in ognttable:		# if is not on the table that we are working on ???
               if prt:
               	  print("TRK:", ident, station, "<<<")
               continue				# nothing to do
            flarmid=ognttable[ident]		# just in case
            jstring=" " 
            if prt:
               print ("Decoding >>>>", jstring, ">>", txt, "<<", len(txt), ident, station, "<<<<")
            try:				# decode the encrypted message
                   #print(">>>:", DK, txt)
                   jstring=ogndecode.ogn_decode_func(txt, DK[0], DK[1], DK[2], DK[3])
                   if len(jstring) > 0:		# if valid ???
                      numdecodes += 1		# increase the counter
                      jstring=jstring[0:jstring.find('}')+1]
                      #print ("Return:>>>>", len(jstring), jstring)
                      decode=json.loads(jstring) # get the dict from the JSON string
                      #print ("DDD", decode)
                      ID=beacon["name"]		# tracker ID
                      station=beacon["receiver_name"] # station

                      now = datetime.utcnow()	# get the UTC time
     						# place it on the queue
                      qentry= { "NumDec": numdecodes, "TIME": now, "ID":ID, "station": station, "hora": hora, "rest": rest, "DECODE": decode}
                      queue.append(qentry)	# add the entry to the queue
                      if prt:
                         print("N#", numdecodes, len(queue), qentry, "<<<<")
                      if not ID in trackers:   	# did we see this tracker
                          trackers[ID] = 1    	# init the counter
                      else:
                          trackers[ID] += 1    	# increase the counter

            except Exception as e:		# catch the exception
                   errordet=""			# error messages
                   ee="%s"%e			# convert to string
                   p1=ee.find("(char ")		# find the (char xxx) string
                   if p1 != -1:			# if found ???
                        p2=ee.find(')') 	# look end of string
                        pos=ee[p1+6:p2] 	# get the char position
                        p=int(pos)		# convert to integeer
                        errordet=jstring[p-3:p+3] # extract the position
                   print ("DECODE Error:", e, ">>:", errordet, ":<<", ident, station, hora, jstring, txt)
                   numerrdeco += 1		# increse the counter
                   continue			# nothing else to do

						# check now if we need to publish delayed entries 
        nqueue=[]				# the new queue if we need to delete entries
        idx=0					# index to rebuild the table
        ddd=0
        for e in queue: 			# scan the queue for entries to push to the APRS
                etime=e["TIME"]			# get the time
                delta=(now - etime)		# get the time difference
                #print("Delta>>>", delta)
                dts=int(delta.total_seconds())	# time difference in seconds
                if (dts > DELAY): 		# if higher that DELAY ??
                    aprsmsg=genaprsmsg(e)	# gen the APRS message
                    aprsmsg += " %ddly \n"%delta.seconds	# include information about the delay
                    if prt:
                       print("APRSMSG: ", e["NumDec"], aprsmsg)	# print for debugginga
                    logfile.write(aprsmsg)	# log into file
                    rtn = config.SOCK_FILE.write(aprsmsg)	# send it to the APRS server
                    config.SOCK_FILE.flush()		        # Make sure gets sent. If not flushed then buffered
                    idx += 1			# one more to delete from table
                    numaprsmsg += 1		# counter of published APRS msgs
                else:
                    nqueue.append(e)		# keep that entry on the table
                    if ddd == 0:		# if first on the queue
                       ddd =dts			# remember that
                				# end of for loop
        if (idx > 0):				# if we found at least one entry
                queue=nqueue			# this is the new queue
                del nqueue 			# delete the old queue
        mem =  process.memory_info().rss  	# in bytes
        
        if prt or mem < 2*1024*1024 or (loopcount - int(loopcount/1000)*1000) == 0:        	# if less that 2 Mb 
               print("##MEM##>>>", numdecodes, len(queue), ddd, "<<<", process.memory_info().rss, ">>>")  # in bytes



 
#       sleep(SLEEP)				# sleep n seconds

#----------------------dlym2ogn.py end of main loop-----------------------#

#########################################################################################
except KeyboardInterrupt:
    print("Keyboard input received, end of program, shutdown")
    pass

shutdown(sock)					# shotdown tasks
logfile.close()
print ("   Encrypted messages",   trackers)	# report the encrypted messages
print ("NO Encrypted messages:", utrackers)	# report the non encrypte message, like trackers status or from non encrypting trackers
print("Exit now ...", nerrors)
exit(0)
