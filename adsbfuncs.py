#!/bin/python3
import urllib.request, urllib.error, urllib.parse
import json
from ctypes import *
from datetime import datetime, timedelta
import socket
import time
import string
import sys
import os
import signal
from geopy.distance import geodesic       # use the Vincenty algorithm^M
import hashlib
import hmac
import urllib.request, urllib.parse, urllib.error
import random
import config
from parserfuncs import deg2dmslat, deg2dmslon
from flarmfuncs import *

import psutil
MUT=False
#-------------------------------------------------------------------------------------------------------------------#
global _adsbregcache_
_adsbregcache_ = {}
_adsbreg_ = {}

def getadsbreg(icao):			    # get the registration and model from the ICAO ID
    global _adsbregcache_
    global _adsbreg_
    if len(_adsbreg_) == 0:	    # only import the table if need it
       import ADSBreg
       _adsbreg_ = ADSBreg.ADSBreg
    if icao in _adsbregcache_:		    # if ID on the table ???
       return (_adsbregcache_[icao])        # return model and registration
    else:
       if icao in _adsbreg_:
          _adsbregcache_[icao]=_adsbreg_[icao]
          return (_adsbregcache_[icao])        # return model and registration
    return False			    # return FALSE

def getsizeadsbcache():
    return (len(_adsbregcache_))

def adsbgetapidata(adsbfile): 	            # get the data from the API server
    r=open(adsbfile)			    # open the file generated by dump1090
 
    js=r.read()
    j_obj = json.loads(js)                  # convert to JSON
    r.close()				    # close the file now
    return j_obj                            # return the JSON object
#-------------------------------------------------------------------------------------------------------------------#

                                            # extract the data of the last know position from the JSON object
def adsbaddpos(tracks, adsbpos, ttime, adsbnow, prt=False):

    foundone = False
    for msg in tracks:
        if "flight" in msg:
            flg = msg['flight']
        else:
            continue
        aid = "ICA"+msg['hex'].upper()	    # aircraft ID
        ttt=adsbnow-msg['seen']		    # when the aircraft was seen
                                            # number of second until beginning of the day
        ts = int(ttt)       		    # Unix time - seconds from the epoch
        t=datetime.utcfromtimestamp(ts)
        #print ("TTT:", t, ts, (adsbnow-ts) , adsbnow, msg)
        if "lon" in msg:
            lon = msg['lon']
        else:
            continue
        if "lat" in msg:
            lat = msg['lat'] 		    # extract the longitude and latitude
        else:
            continue
        gps = "NO"
        extpos = "NO"
        roc=0
        rot=0
        dir=0
        spd=0
        if MUT:
           if "vert_rate" in msg:
                roc = msg['vert_rate']
           if "speed" in msg:
                spd = msg['speed']
           if "altitude" in msg:
                alt = msg["altitude"] 		# and the altitude
           else:
                continue
        else:
           if "baro_rate" in msg:		# rate of climb in fpm
                roc = msg['baro_rate']
           if "track_rate" in msg:
                rot = msg['track_rate']		# rate of turn in degrees per second
           if "gs" in msg:
                spd = msg['gs']			# ground speed in knots
           if "alt_baro" in msg:
                alt = msg["alt_baro"] 		# and the altitude in feet
           else:
                continue

        if "track" in msg:
                dir = msg['track']
        date = t.strftime("%y%m%d")
        tme  = t.strftime("%H%M%S")
        foundone = True

        vitlat = config.FLOGGER_LATITUDE
        vitlon = config.FLOGGER_LONGITUDE
        distance = geodesic((lat, lon), (vitlat, vitlon)).km            # distance to the station
        pos = {"ICAOID": aid,  "date": date, "time": tme, "Lat": lat, "Long": lon, "altitude": alt, "UnitID": aid,
               "dist": distance, "course": dir, "speed": spd, "roc": roc, "rot":rot, "GPS": gps, "extpos": extpos , "flight": flg }
        #print "SSS:", ts, ttime, pos
        if ts < ttime+3:		    # check if the data is from before
            continue		            # in that case nothing to do
        adsbpos['adsbpos'].append(pos)      # and store it on the dict
        if prt:
            print("adsbPOS :", round(lat, 4), round(lon, 4), alt, aid, round( distance, 4), ts,  date, tme, flg)

    return(foundone) 			    # indicate that we added an entry to the dict


#-------------------------------------------------------------------------------------------------------------------#


def adsbstoreitindb(datafix, curs, conn):   # store the fix into the database

    import MySQLdb                          # the SQL data base routines^M
    for fix in datafix['adsbpos']:	    # for each fix on the dict
        id = fix['ICAOID']		    # extract the information
        dte = fix['date']
        hora = fix['time']
        station = config.location_name
        latitude = fix['Lat']
        longitude = fix['Long']
        altitude = fix['altitude']
        speed = fix['speed']
        course = fix['course']
        roclimb = fix['roc']
        rot = fix['rot']
        sensitivity = 0
        gps = fix['GPS']
        uniqueid = str(fix["UnitID"])
        dist = fix['dist']
        extpos = fix['extpos']
        addcmd = "insert into OGNDATA values ('" + id + "','" + dte + "','" + hora + "','" + station + "'," + str(latitude) + "," + str(longitude) + "," + str(altitude) + "," + str(speed) + "," + \
            str(course) + "," + str(roclimb) + "," + str(rot) + "," + str(sensitivity) + \
            ",'" + gps + "','" + uniqueid + "'," + \
            str(dist) + ",'" + extpos + "', 'adsb' ) "
        try:				    # store it on the DDBB
            #print addcmd
            curs.execute(addcmd)
        except MySQLdb.Error as e:
            try:
                print(">>>MySQL Error [%d]: %s" % (e.args[0], e.args[1]))
            except IndexError:
                print(">>>MySQL Error: %s" % str(e))
                print(">>>MySQL error:", cout, addcmd)
                print(">>>MySQL data :",  data)
            return (False)                  # indicate that we have errors
    conn.commit()                           # commit the DB updates
    return(True)			    # indicate that we have success

#-------------------------------------------------------------------------------------------------------------------#


def adsbaprspush(datafix, conn, prt=False):

    for fix in datafix['adsbpos']:	    # for each fix on the dict
        id = fix['ICAOID']		    # extract the information
        dte = fix['date']
        hora = fix['time']
        station = config.location_name
        latitude = fix['Lat']
        longitude = fix['Long']
        altitude = fix['altitude']
        speed = fix['speed']
        course = fix['course']
        roclimb = fix['roc']
        rot = fix['rot']
        sensitivity = 0
        gps = fix['GPS']
        uniqueid = fix["UnitID"]
        uniqueid = '25'+uniqueid[3:]
        dist = fix['dist']
        extpos = fix['extpos']
        flight = fix['flight']
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
 
        aprsmsg = id+">OGADSB,qAS,"+config.ADSBname+":/" + \
            hora+'h'+lat+"\\"+lon+"^"+ccc+"/"+sss+"/"
        if altitude > 0:
            aprsmsg += "A=%06d" % int(altitude)
        aprsmsg += " id"+uniqueid+" %+04dfpm " % (int(roclimb))+" "+str(rot)+"rot fn"+flight+" "
        regmodel = getadsbreg(id[3:9])
        if regmodel:
           reg  =regmodel['Reg']
           model=regmodel['Model']
           aprsmsg += "reg"+reg+" model"+model+" \n"
        else:
           aprsmsg += " \n"
        print("APRSMSG: ", aprsmsg)
        rtn = config.SOCK_FILE.write(aprsmsg)
        config.SOCK_FILE.flush()
        if rtn == 0:
           print ("Error writing msg:", aprsmsg)

    return (True)

#-------------------------------------------------------------------------------------------------------------------#
#LEMD>OGNSDR,TCPIP*,qAC,GLIDERN2:/141436h4030.49NI00338.59W&/A=002280
#LEMD>OGNSDR,TCPIP*,qAC,GLIDERN2:>141436h v0.2.8.RPI-GPU CPU:0.6 RAM:710.8/972.2MB NTP:0.3ms/-5.5ppm +56.9C 2/2Acfts[1h] RF:+50-3.2ppm/+0.76dB/+47.4dB@10km[3859]

RPI = True

 
def adsbsetrec(sock, prt=False, store=False, aprspush=False):
        t    = datetime.utcnow()       		# get the date
        tme  = t.strftime("%H%M%S")
        aprsmsg=config.ADSBname+">OGNSDR,TCPIP*:/"+tme+"h"+config.ADSBloc+" \n"
        print("APRSMSG: ", aprsmsg)
        rtn = sock.write(aprsmsg)
        sock.flush()
        if rtn == 0:
           print ("Error writing msg:", aprsmsg)
        if RPI:
           from gpiozero import CPUTemperature
           tcpu   = CPUTemperature()
           tempcpu= tcpu.temperature
        else:
           tempcpu = 0.0
        cpuload =psutil.cpu_percent()/100
        memavail=psutil.virtual_memory().available/(1024*1024)
        memtot  =psutil.virtual_memory().total/(1024*1024)
        aprsmsg =config.ADSBname+">OGNSDR,TCPIP*:>"+tme+"h v0.2.8.ADSB CPU:"+str(cpuload)+" RAM:"+str(memavail)+"/"+str(memtot)+"MB NTP:0.4ms/-5.4ppm +"+str(tempcpu)+"C\n"
        print("APRSMSG: ", aprsmsg)
        rtn = sock.write(aprsmsg)
        sock.flush()

        return

# find all the fixes since TTIME . Scan all the adsb devices for new data
def adsbfindpos(ttime, conn, prt=False, store=False, aprspush=False):

    url = "http://"+config.ADSBhost+"/data.json"
    adsbfile = config.ADSBfile
    if not os.path.exists(adsbfile):
       now = datetime.utcnow()
                                        # number of second until beginning of the day of 1-1-1970
       return (ttime+1)			# return TTIME for next call

    adsbpos = {"adsbpos": []}		# init the dicta
    pos = adsbgetapidata(adsbfile)      # get the JSON data from the ADSB server
    if prt:
        print(json.dumps(pos, indent=4)) # convert JSON to dictionary
    adsbnow = pos['now']		# timestamp from the ADSB data
    tracks  = pos['aircraft']		# get the aircraft information 
                                        # get all the devices with ADSB
    found = adsbaddpos(tracks, adsbpos, ttime, adsbnow, prt=prt)  # find the gliders since TTIME
    if prt:
        print(adsbpos)			# print the data
    if store:
        adsbstoreitindb(adsbpos, curs, conn)	# and store it on the DDBB
    if aprspush:
        adsbaprspush(adsbpos, conn, prt=prt)	# and push it into the OGN APRS
    now = datetime.utcnow()
                                        # number of second until beginning of the day of 1-1-1970
    return (int(adsbnow))			# return TTIME for next call

#-------------------------------------------------------------------------------------------------------------------#
