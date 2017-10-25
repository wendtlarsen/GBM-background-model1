#!/usr/bin python2.7

import os
import matplotlib.pyplot as plt
import numpy as np
import math
import pyfits
from numpy import linalg as LA
import ephem

class n0:
    azimuth = 45.8899994*2*math.pi/360.
    zenith = 20.5799999*2*math.pi/360.
    azimuthg = 45.8899994
    zenithg = 20.5799999

class n1:
    azimuth = 45.1100006*2*math.pi/360.
    zenith = 45.3100014*2*math.pi/360.
    azimuthg = 45.1100006
    zenithg = 45.3100014

class n2:
    azimuth = 58.4399986*2*math.pi/360.
    zenith = 90.2099991*2*math.pi/360.
    azimuthg = 58.4399986
    zenithg = 90.2099991

class n3:
    azimuth = 314.869995*2*math.pi/360.
    zenith = 45.2400017*2*math.pi/360.
    azimuthg = 314.869995
    zenithg = 45.2400017

class n4:
    azimuth = 303.149994*2*math.pi/360.
    zenith = 90.2699966*2*math.pi/360.
    azimuthg = 303.149994
    zenithg = 90.2699966

class n5:
    azimuth = 3.34999990*2*math.pi/360.
    zenith = 89.7900009*2*math.pi/360.
    azimuthg = 3.34999990
    zenithg = 89.7900009

class n6:
    azimuth = 224.929993*2*math.pi/360.
    zenith = 20.4300003*2*math.pi/360.
    azimuthg = 224.929993
    zenithg = 20.4300003

class n7:
    azimuth = 224.619995*2*math.pi/360.
    zenith = 46.1800003*2*math.pi/360.
    azimuthg = 224.619995
    zenithg = 46.1800003

class n8:
    azimuth = 236.610001*2*math.pi/360.
    zenith = 89.9700012*2*math.pi/360.
    azimuthg = 236.610001
    zenithg = 89.9700012

class n9:
    azimuth = 135.190002*2*math.pi/360.
    zenith = 45.5499992*2*math.pi/360.
    azimuthg = 135.190002
    zenithg = 45.5499992

class na:
    azimuth = 123.730003*2*math.pi/360.
    zenith = 90.4199982*2*math.pi/360.
    azimuthg = 123.730003
    zenithg = 90.4199982

class nb:
    azimuth = 183.740005*2*math.pi/360.
    zenith = 90.3199997*2*math.pi/360.
    azimuthg = 183.740005
    zenithg = 90.3199997

class b0:
    azimuth = math.acos(1)
    zenith = math.asin(1)
    azimuthg = 0.0
    zenithg = 90.0

class b1:
    azimuth = math.pi
    zenith = math.asin(1)
    azimuthg = 180.0
    zenithg = 90.0

def read_cspec(detector, day, seconds = 0):
    """This function reads a cspec file and stores the data in arrays of the form: echan[emin, emax], total_counts, echan_counts[echan], exptime, total_rate, echan_rate, cstart, cstop, gtstart, gtstop\n
    Input:\n
    read_ctime ( detector, day = YYMMDD, seconds = SSS )\n
    0 = energy channel interval\n
    1 = total number of counts\n
    2 = number of counts per energy channel\n
    3 = total count rate\n
    4 = count rate per energy channel\n
    5 = bin time interval[start, end]\n
    6 = good time interval[start, end]\n
    7 = time of exposure\n"""
    
    #read the file. Check if one wants to read a specific trigger file or a daily file
    if seconds == 0:
        filename = 'glg_cspec_' + str(detector) + '_' + str(day) + '_v00.pha'
    else:
        filename = 'glg_cspec_' + str(detector) + '_bn' + str(day) + str(seconds) + '_v00.pha'
    __dir__ = os.path.dirname(os.path.abspath(__file__))
    fits_path = os.path.join(os.path.dirname(__dir__), 'cspec/' + str(day))
    filepath = os.path.join(fits_path, str(filename))
    fits = pyfits.open(filepath)
    energy = fits[1].data
    spectrum = fits[2].data
    goodtime = fits[3].data
    fits.close()
    
    #extract the data
    emin = energy['E_MIN'] #lower limit of the energy channels
    emax = energy['E_MAX'] #upper limit of the energy channels
    echan = np.zeros((len(emin),2), float) #combine the energy limits of the energy channels in one matrix
    echan[:,0] = emin
    echan[:,1] = emax
    counts = spectrum['COUNTS']
    total_counts = np.sum(counts, axis=1) #total number of counts for each time intervall
    echan_counts = np.vstack(([counts[:,0].T], [counts[:,1].T], [counts[:,2].T], [counts[:,3].T], [counts[:,4].T], [counts[:,5].T], [counts[:,6].T], [counts[:,7].T], [counts[:,8].T], [counts[:,9].T], [counts[:,10].T], [counts[:,11].T], [counts[:,12].T], [counts[:,13].T], [counts[:,14].T], [counts[:,15].T], [counts[:,16].T], [counts[:,17].T], [counts[:,18].T], [counts[:,19].T], [counts[:,20].T], [counts[:,21].T], [counts[:,22].T], [counts[:,23].T], [counts[:,24].T], [counts[:,25].T], [counts[:,26].T], [counts[:,27].T], [counts[:,28].T], [counts[:,29].T], [counts[:,30].T], [counts[:,31].T], [counts[:,32].T], [counts[:,33].T], [counts[:,34].T], [counts[:,35].T], [counts[:,36].T], [counts[:,37].T], [counts[:,38].T], [counts[:,39].T], [counts[:,40].T], [counts[:,41].T], [counts[:,42].T], [counts[:,43].T], [counts[:,44].T], [counts[:,45].T], [counts[:,46].T], [counts[:,47].T], [counts[:,48].T], [counts[:,49].T], [counts[:,50].T], [counts[:,51].T], [counts[:,52].T], [counts[:,53].T], [counts[:,54].T], [counts[:,55].T], [counts[:,56].T], [counts[:,57].T], [counts[:,58].T], [counts[:,59].T], [counts[:,60].T], [counts[:,61].T], [counts[:,62].T], [counts[:,63].T], [counts[:,64].T], [counts[:,65].T], [counts[:,66].T], [counts[:,67].T], [counts[:,68].T], [counts[:,69].T], [counts[:,70].T], [counts[:,71].T], [counts[:,72].T], [counts[:,73].T], [counts[:,74].T], [counts[:,75].T], [counts[:,76].T], [counts[:,77].T], [counts[:,78].T], [counts[:,79].T], [counts[:,80].T], [counts[:,81].T], [counts[:,82].T], [counts[:,83].T], [counts[:,84].T], [counts[:,85].T], [counts[:,86].T], [counts[:,87].T], [counts[:,88].T], [counts[:,89].T], [counts[:,90].T], [counts[:,91].T], [counts[:,92].T], [counts[:,93].T], [counts[:,94].T], [counts[:,95].T], [counts[:,96].T], [counts[:,97].T], [counts[:,98].T], [counts[:,99].T], [counts[:,100].T], [counts[:,101].T], [counts[:,102].T], [counts[:,103].T], [counts[:,104].T], [counts[:,105].T], [counts[:,106].T], [counts[:,107].T], [counts[:,108].T], [counts[:,109].T], [counts[:,110].T], [counts[:,111].T], [counts[:,112].T], [counts[:,113].T], [counts[:,114].T], [counts[:,115].T], [counts[:,116].T], [counts[:,117].T], [counts[:,118].T], [counts[:,119].T], [counts[:,120].T], [counts[:,121].T], [counts[:,122].T], [counts[:,123].T], [counts[:,124].T], [counts[:,125].T], [counts[:,126].T], [counts[:,127].T])) #number of counts as a table with respect to the energy channel -> echan_counts[0] are the counts for the first energy channel
    exptime = spectrum['EXPOSURE'] #length of the time intervall
    total_rate = np.divide(total_counts, exptime) #total count rate for each time intervall
    echan_rate = np.divide(echan_counts, exptime) #count rate per time intervall for each energy channel
    cstart = spectrum['TIME'] #start time of the time intervall
    cstop = spectrum['ENDTIME'] #end time of the time intervall
    bin_time = np.zeros((len(cstart),2), float) #combine the time limits of the counting intervals in one matrix
    bin_time[:,0] = cstart
    bin_time[:,1] = cstop
    gtstart = goodtime['START'] #start time of data collecting times (exiting SAA)
    gtstop = goodtime['STOP'] #end time of data collecting times (entering SAA)
    #times are in Mission Elapsed Time (MET) seconds. See Fermi webside or read_poshist for more information.
    good_time = np.zeros((len(gtstart),2), float) #combine the time limits of the goodtime intervals in one matrix
    good_time[:,0] = gtstart
    good_time[:,1] = gtstop
    return echan, total_counts, echan_counts, total_rate, echan_rate, bin_time, good_time, exptime

day = 150926
detector = n0
cspec_data = read_cspec(detector.__name__, day)
echan = cspec_data[0]
total_counts = cspec_data[1]
echan_counts = cspec_data[2]
total_rate = cspec_data[3]
echan_rate = cspec_data[4]
bin_time = cspec_data[5]
good_time = cspec_data[6]
exptime = cspec_data[7]
