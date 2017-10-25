#!/usr/bin python2.7

import os
import matplotlib.pyplot as plt
import numpy as np
import math
import pyfits
from numpy import linalg as LA
import ephem
from work_module import calculate
from work_module import detector
from work_module import readfile
calc = calculate()
det = detector()
rf = readfile()

import scipy.optimize as optimization

#docstrings of the different self-made classes within the self-made module
#cdoc = calc.__doc__
#ddoc = det.__doc__
#rdoc = rf.__doc__

day = 150926
detector = det.n5

#angle between the sun and the detector
calc_sun_ang = calc.sun_ang(detector, day)
sun_ang = calc_sun_ang[0]
sat_time = calc_sun_ang[1]

#angle between the earth and the detector
earth_ang = calc.earth_ang(detector, day)[0]

#counts in the detector during that day
ctime = rf.ctime(detector, day)
counts = ctime[1]
rate = ctime[3]
bin_time = ctime[5]
count_time = np.array((bin_time[:,0] + bin_time[:,1])/2)

#periodical function corresponding to the orbital behaviour -> reference day is 150926, periodical shift per day is approximately 0.199*math.pi
ysin = np.sin((2*math.pi*np.arange(len(count_time)))/(5715*len(count_time)/len(sat_time)) + (0.7 + (day - 150926)*0.199)*math.pi)

#constant function corresponding to the diffuse y-ray background
ycon = np.ones(len(count_time))

#convertion to daytime in 24h
daytime_sun = (sat_time - sat_time[0] + 5)/3600.
daytime_counts = (count_time - sat_time[0] + 5)/3600.




x0 = np.array([240., 20., 1., 1.])#, 1., 1., 1.])
sigma = np.array((counts+1)**(0.5))

#print len(sigma), len(daytime_counts), len(counts), len(sun_ang)

def func(x, a, b, c, d):#, b, c, d):
    return a + b*np.sin((2*math.pi*x)/c + d)# + b*sun_ang + c*earth_ang + d*ysin

print optimization.curve_fit(func, daytime_counts, counts, x0, sigma)

#mittelwert = np.sum(counts)/len(counts)

#print mittelwert

a = optimization.curve_fit(func, daytime_counts, counts, x0, sigma)[0][0]
b = optimization.curve_fit(func, daytime_counts, counts, x0, sigma)[0][1]
c = optimization.curve_fit(func, daytime_counts, counts, x0, sigma)[0][2]
d = optimization.curve_fit(func, daytime_counts, counts, x0, sigma)[0][3]



fig, ax1 = plt.subplots()

#add two independent y-axes
#ax2 = ax1.twinx()
#ax3 = ax1.twinx()
#axes = [ax1, ax3]#, ax3]

#Make some space on the right side for the extra y-axis
#fig.subplots_adjust(right=0.75)

# Move the last y-axis spine over to the right by 20% of the width of the axes
#axes[-1].spines['right'].set_position(('axes', 1.2))

# To make the border of the right-most axis visible, we need to turn the frame on. This hides the other plots, however, so we need to turn its fill off.
#axes[-1].set_frame_on(True)
#axes[-1].patch.set_visible(False)

plot1 = ax1.plot(daytime_counts, counts, 'b-', label = 'Counts')#daytime_sun, earth_ang, 'r-')
#plot2 = ax2.plot(daytime_sun, sun_ang, 'y-', label = 'Sun angle')
#plot3 = ax2.plot(daytime_sun, earth_ang, 'r-', label = 'Earth angle')
plot4 = ax1.plot(daytime_counts, func(daytime_counts, a, b, c, d), 'r-', label = 'Orbital period')
#plot5 = ax1.plot(daytime_counts, a*ycon, 'b--', label = 'Constant background')

plots = plot1 + plot4# + plot5# + plot4 + plot5
labels = [l.get_label() for l in plots]
ax1.legend(plots, labels, loc=1)

ax1.grid()

ax1.set_xlabel('Time of day in 24h')
ax1.set_ylabel('Number of counts')
#ax2.set_ylabel('Angle in degrees')
#ax3.set_ylabel('Number')

#ax1.set_xlim([0, 24.1])
#ax1.set_ylim([0, 550])
#ax2.set_xlim([0, 24.1])
#ax2.set_ylim([0, 360])
#ax3.set_xlim([0, 24.1])
#ax3.set_ylim([-1.5, 1.5])

plt.title('Counts and angles of the ' + detector.__name__ + '-detector on the 26th Sept 2015')

#plt.axis([0, 24.1, 0, 500])

#plt.legend()

plt.show() 


