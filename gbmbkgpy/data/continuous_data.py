import astropy.io.fits as fits
import numpy as np
import collections
import matplotlib.pyplot as plt

from gbmgeometry import PositionInterpolator, gbm_detector_list

import scipy.interpolate as interpolate

from gbmbkgpy.io.file_utils import file_existing_and_readable
from gbmbkgpy.io.downloading import download_data_file

import astropy.time as astro_time
import astropy.coordinates as coord
import math
import numpy as np
from scipy import interpolate
import os
from gbmbkgpy.io.package_data import get_path_of_data_dir, get_path_of_data_file, get_path_of_external_data_dir
from gbmbkgpy.utils.progress_bar import progress_bar
from gbmbkgpy.io.plotting.step_plots import step_plot, slice_disjoint, disjoint_patch_plot
from gbmgeometry import GBMTime

import pymap3d as pm
import datetime
from gbmbkgpy.io.downloading import download_lat_spacecraft


try:

    # see if we have mpi and/or are upalsing parallel

    from mpi4py import MPI
    if MPI.COMM_WORLD.Get_size() > 1: # need parallel capabilities
        using_mpi = True ###################33

        comm = MPI.COMM_WORLD
        rank = comm.Get_rank()
        size = comm.Get_size()

    else:

        using_mpi = False
except:

    using_mpi = False


class ContinuousData(object):

    def __init__(self, date, detector, data_type, rate_generator_DRM=None, use_SAA=True, clean_SAA=False):
        """
        Initalize the ContinousData Class, which contains the information about the time bins 
        and counts of the data.
        """
        self._data_type = data_type
        self._det = detector
        self._day = date
        self._use_SAA = use_SAA
        self._clean_SAA = clean_SAA
        self._rate_generator_DRM = rate_generator_DRM

        # Download data-file and poshist file if not existing:
        datafile_name = 'glg_{0}_{1}_{2}_v00.pha'.format(self._data_type, self._det, self._day)
        datafile_path = os.path.join(get_path_of_external_data_dir(), self._data_type, self._day, datafile_name)

        poshistfile_name = 'glg_{0}_all_{1}_v00.fit'.format('poshist', self._day)
        poshistfile_path = os.path.join(get_path_of_external_data_dir(), 'poshist', poshistfile_name)

        # If MPI is used only one rank should download the data; the others wait
        if using_mpi:
            if rank==0:
                if not file_existing_and_readable(datafile_path):
                    download_data_file(self._day, self._data_type, self._det)

                if not file_existing_and_readable(poshistfile_path):
                    download_data_file(self._day, 'poshist')
            comm.Barrier()
        else:
            if not file_existing_and_readable(datafile_path):
                download_data_file(self._day, self._data_type, self._det)

            if not file_existing_and_readable(poshistfile_path):
                download_data_file(self._day, 'poshist')

        # Save poshistfile_path for later usage
        self._pos_hist = poshistfile_path


        # Open the datafile of the CTIME/CSPEC data and read in all needed quantities
        with fits.open(datafile_path) as f:
            self._counts = f['SPECTRUM'].data['COUNTS']
            self._bin_start = f['SPECTRUM'].data['TIME']
            self._bin_stop = f['SPECTRUM'].data['ENDTIME']

            self._exposure = f['SPECTRUM'].data['EXPOSURE']

            self._ebins_start = f['EBOUNDS'].data['E_MIN']
            self._ebins_stop = f['EBOUNDS'].data['E_MAX']
            
        self._ebins_size = self._ebins_stop - self._ebins_start

        # Sometimes there are corrupt time bins where the time bin start = time bin stop
        # So we have to delete these times bins
        i = 0
        while i < len(self._bin_start):
            if self._bin_start[i] == self._bin_stop[i]:
                self._bin_start = np.delete(self._bin_start, [i])
                self._bin_stop = np.delete(self._bin_stop, [i])
                self._counts = np.delete(self._counts, [i], axis=0)
                self._exposure=np.delete(self._exposure, [i])
                print('Deleted empty time bin', i)
            else:
                i+=1
                
        # Sometimes the poshist file does not cover the whole time coverd by the CTIME/CSPEC file.
        # So we have to delete these time bins 


        # Get boundary for time interval covered by the poshist file
        with fits.open(poshistfile_path) as f:
            pos_times = f['GLAST POS HIST'].data['SCLK_UTC']
        min_time_pos = pos_times[0]
        max_time_pos = pos_times[-1]
        # check for all time bins if they are outside of this interval
        i=0
        counter=0
        while i<len(self._bin_start):
            if self._bin_start[i]<min_time_pos or self._bin_stop[i]>max_time_pos:
                self._bin_start = np.delete(self._bin_start, i)
                self._bin_stop = np.delete(self._bin_stop, i)
                self._counts = np.delete(self._counts, i, 0)
                self._exposure = np.delete(self._exposure, i)
                counter+=1
            else:
                i+=1

        # Print how many time bins were deleted
        if counter>0:
            print(str(counter) + ' time bins had to been deleted because they were outside of the time interval covered'
                                 'by the poshist file...')

        # Calculate and save some important quantities
        self._n_entries = len(self._bin_start)
        self._counts_combined = np.sum(self._counts, axis=1)
        self._counts_combined_mean = np.mean(self._counts_combined)
        self._counts_combined_rate = self._counts_combined / self.time_bin_length
        self._n_time_bins, self._n_channels = self._counts.shape

        # Calculate the MET time for the day
        day = self._day
        year = '20%s' % day[:2]
        month = day[2:-2]
        dd = day[-2:]
        day_at = astro_time.Time("%s-%s-%s" % (year, month, dd))
        self._day_met = GBMTime(day_at).met
        
    @property
    def day(self):
        return self._day

    @property
    def data_type(self):
        return self._data_type

    @property
    def ebins(self):
        return np.vstack((self._ebins_start, self._ebins_stop)).T

    @property
    def detector_id(self):

        return self._det[-1]

    @property
    def n_channels(self):

        return self._n_channels

    @property
    def n_time_bins(self):

        return self._n_time_bins

    @property
    def rates(self):
        return self._counts / self._exposure.reshape((self._n_entries, 1))

    @property
    def counts(self):
        return self._counts

    @property
    def counts_combined(self):
        return self._counts_combined

    @property
    def counts_combined_rate(self):
        return self._counts_combined_rate

    @property
    def exposure(self):
        return self._exposure

    @property
    def time_bin_start(self):
        return self._bin_start

    @property
    def time_bin_stop(self):
        return self._bin_stop

    @property
    def time_bins(self):
        return np.vstack((self._bin_start, self._bin_stop)).T

    @property
    def time_bin_length(self):
        return self._bin_stop - self._bin_start

    @property
    def mean_time(self):
        return np.mean(self.time_bins, axis=1)

    def _earth_rate_array(self):
        """
        Calculate the earth_rate_array for all interpolation times for which the geometry was calculated. This supports
        MPI to reduce the calculation time.
        To calculate the earth_rate_array the responses created on a grid in rate_gernerator_DRM are used. All points
        that are occulted by the earth are added, assuming a spectrum specified in rate_generator_DRM for the earth
        albedo.
        :return:
        """
        points = self._rate_generator_DRM.points
        earth_rates = self._rate_generator_DRM.earth_rate
        # get the earth direction at the interpolation times; zen angle from -90 to 90
        earth_pos_inter_times = []
        if using_mpi:
            # last rank has to cover one more index. Caused by the calculation of the Geometry for the last time
            # bin of the day
            if rank == size - 1:
                upper_index = self._times_upper_bound_index + 1
                print(upper_index)
            else:
                upper_index = self._times_upper_bound_index
            
            for i in range(self._times_lower_bound_index, upper_index):
                earth_pos_inter_times.append(
                    np.array([np.cos(self._earth_zen[i] * (np.pi / 180)) * np.cos(self._earth_az[i] * (np.pi / 180)),
                              np.cos(self._earth_zen[i] * (np.pi / 180)) * np.sin(self._earth_az[i] * (np.pi / 180)),
                              np.sin(self._earth_zen[i] * (np.pi / 180))]))
            self._earth_pos_inter_times = np.array(earth_pos_inter_times)
            earth_pos = np.array(earth_pos_inter_times) #
            # define the opening angle of the earth in degree
            opening_angle_earth = 67
            array_earth_rate = []

            det_earth_angle = []#
            #point_earth_angle_all_inter = [] #                                                                                                                                                                                                                                
            #point_base_rate_all_inter = [] # 
            for pos in self._earth_pos_inter_times:
                earth_rate = np.zeros_like(earth_rates[0])

                det = np.array([1,0,0])#
                det_earth_angle.append(np.arccos(np.dot(pos, det))*180/np.pi)#
                #point_earth_angle = [] #                                                                                                                                                                                                                                      
                #point_base_rate = [] #
                for i, pos_point in enumerate(points):
                    angle_earth = np.arccos(np.dot(pos, pos_point)) * (180 / np.pi)
                    #point_earth_angle.append(angle_earth)#
                    if angle_earth < opening_angle_earth:
                        B=0
                        earth_rate += earth_rates[i]*np.exp(B*angle_earth)#TODO RING EFFECT
                        #point_base_rate.append(earth_rates[i])# 
                    #else:#                                                                                                                                                                                                                                                    
                        #point_base_rate.append(np.zeros_like(earth_rates[i]))#
                array_earth_rate.append(earth_rate)
                #point_base_rate_all_inter.append(point_base_rate)#
                #point_earth_angle_all_inter.append(point_earth_angle)#
                
            array_earth_rate = np.array(array_earth_rate)
            det_earth_angle = np.array(det_earth_angle)#
            #point_earth_angle = np.array(point_earth_angle_all_inter)#                                                                                                                                                                                                  
            #point_base_rate = np.array(point_base_rate_all_inter)#
            #del point_earth_angle_all_inter, point_base_rate_all_inter, earth_pos_inter_times
            array_earth_rate_g = comm.gather(array_earth_rate, root=0)
            det_earth_angle_g = comm.gather(det_earth_angle, root=0)#
            earth_pos_g = comm.gather(earth_pos, root=0)#
            #point_earth_angle_g = comm.gather(point_earth_angle, root=0)
            #point_base_rate_g = comm.gather(point_base_rate, root=0)
            if rank == 0:
                array_earth_rate_g = np.concatenate(array_earth_rate_g)
                det_earth_angle_g = np.concatenate(det_earth_angle_g)
                earth_pos_g = np.concatenate(earth_pos_g)
                #point_earth_angle_g = np.concatenate(point_earth_angle_g)
                #point_base_rate_g = np.concatenate(point_base_rate_g)
            array_earth_rate = comm.bcast(array_earth_rate_g, root=0)
            det_earth_angle = comm.bcast(det_earth_angle_g, root=0)
            earth_pos = comm.bcast(earth_pos_g,root=0)#
            #point_earth_angle = comm.bcast(point_earth_angle_g, root=0)
            #point_base_rate = comm.bcast(point_base_rate_g, root=0)
            #del array_earth_rate_g, point_earth_angle_g, point_base_rate_g
        else:
            for i in range(0, len(self._earth_zen)):
                earth_pos_inter_times.append(
                    np.array([np.cos(self._earth_zen[i] * (np.pi / 180)) * np.cos(self._earth_az[i] * (np.pi / 180)),
                              np.cos(self._earth_zen[i] * (np.pi / 180)) * np.sin(self._earth_az[i] * (np.pi / 180)),
                              np.sin(self._earth_zen[i] * (np.pi / 180))]))
            self._earth_pos_inter_times = np.array(earth_pos_inter_times)
            # define the opening angle of the earth in degree
            opening_angle_earth = 67
            array_earth_rate = []
            #point_earth_angle_all_inter = [] #
            #point_base_rate_all_inter = [] #
            for pos in self._earth_pos_inter_times:
                earth_rate = np.zeros_like(earth_rates[0])
                #point_earth_angle = [] #
                #point_base_rate = [] #
                for i, pos_point in enumerate(points):
                    angle_earth = np.arccos(np.dot(pos, pos_point)) * (180 / np.pi)
                    #point_earth_angle.append(angle_earth)#
                    if angle_earth < opening_angle_earth:
                        #point_base_rate.append(earth_rates[i])#
                        earth_rate += earth_rates[i]
                    #else:#
                        #point_base_rate.append(np.zeros_like(earth_rates[i]))#
                array_earth_rate.append(earth_rate)
                #point_base_rate_all_inter.append(point_base_rate)#
                #point_earth_angle_all_inter.append(point_earth_angle)#
            #point_base_rate = point_base_rate_all_inter
            #point_earth_angle = point_earth_angle_all_inter
        array_earth_rate = np.array(array_earth_rate).T
        #point_earth_angle = np.array(point_earth_angle)#
        #if rank==0:
            #print('Earth pos')
            #print(earth_pos[:10])
            #print('earth_rate')
            #print(array_earth_rate[4][:10])
            #fig = plt.figure()
            #ax = fig.gca(projection='3d')
            #surf = ax.scatter(earth_pos[:,0],earth_pos[:,1],earth_pos[:,2], s=0.4, c=array_earth_rate[4], cmap='plasma')
            #ax.scatter(1,0,0,s=10,c='red')
            #fig.colorbar(surf)
            #fig.savefig('testing_B_{}.pdf'.format(B))
            #fig = plt.figure()
            #ax = fig.gca(projection='3d')
            #surf = ax.scatter(points[:,0],points[:,1],points[:,2], s=0.4, c=earth_rates[:,4], cmap='plasma')
            #fig.colorbar(surf)
            #fig.savefig('testing_2.pdf')
        #point_base_rate = np.array(point_base_rate)#
        #self._point_earth_angle_interpolator = interpolate.interp1d(self._sun_time, point_earth_angle, axis=0)#
        #self._point_base_rate_interpolator = interpolate.interp1d(self._sun_time, point_base_rate, axis=0)#
        self._earth_rate_interpolator = interpolate.interp1d(self._sun_time, array_earth_rate)
        #del point_base_rate, point_earth_angle, array_earth_rate
    def _cgb_rate_array(self):
        """
        Calculate the cgb_rate_array for all interpolation times for which the geometry was calculated. This supports
        MPI to reduce the calculation time.
        To calculate the cgb_rate_array the responses created on a grid in rate_gernerator_DRM are used. All points
        that are not occulted by the earth are added, assuming a spectrum specified in rate_generator_DRM for the cgb
        spectrum.
        :return:
        """
        points = self._rate_generator_DRM.points
        cgb_rates = self._rate_generator_DRM.cgb_rate
        # get the earth direction at the interpolation times; zen angle from -90 to 90
        earth_pos_inter_times = []
        if using_mpi:
            # last rank has to cover one more index. Caused by the calculation of the Geometry for the last time
            # bin of the day
            if rank == size - 1:
                upper_index = self._times_upper_bound_index + 1
            else:
                upper_index = self._times_upper_bound_index

            for i in range(self._times_lower_bound_index, upper_index):
                earth_pos_inter_times.append(
                    np.array([np.cos(self._earth_zen[i] * (np.pi / 180)) * np.cos(self._earth_az[i] * (np.pi / 180)),
                              np.cos(self._earth_zen[i] * (np.pi / 180)) * np.sin(self._earth_az[i] * (np.pi / 180)),
                              np.sin(self._earth_zen[i] * (np.pi / 180))]))
            self._earth_pos_inter_times = np.array(earth_pos_inter_times)
            # define the opening angle of the earth in degree
            opening_angle_earth = 67
            array_cgb_rate = []
            for pos in self._earth_pos_inter_times:
                cgb_rate = np.zeros_like(cgb_rates[0])
                for i, pos_point in enumerate(points):
                    angle_earth = np.arccos(np.dot(pos, pos_point)) * (180 / np.pi)
                    if angle_earth > opening_angle_earth:
                        cgb_rate += cgb_rates[i]
                array_cgb_rate.append(cgb_rate)
            array_cgb_rate = np.array(array_cgb_rate)

            array_cgb_rate_g = comm.gather(array_cgb_rate, root=0)
            if rank == 0:
                array_cgb_rate_g = np.concatenate(array_cgb_rate_g)
            array_cgb_rate = comm.bcast(array_cgb_rate_g, root=0)
        else:
            for i in range(0, len(self._earth_zen)):
                earth_pos_inter_times.append(
                    np.array([np.cos(self._earth_zen[i] * (np.pi / 180)) * np.cos(self._earth_az[i] * (np.pi / 180)),
                              np.cos(self._earth_zen[i] * (np.pi / 180)) * np.sin(self._earth_az[i] * (np.pi / 180)),
                              np.sin(self._earth_zen[i] * (np.pi / 180))]))
            self._earth_pos_inter_times = np.array(earth_pos_inter_times)
            # define the opening angle of the earth in degree
            opening_angle_earth = 67
            array_cgb_rate = []
            for pos in self._earth_pos_inter_times:
                cgb_rate = np.zeros_like(cgb_rates[0])
                for i, pos_point in enumerate(points):
                    angle_earth = np.arccos(np.dot(pos, pos_point)) * (180 / np.pi)
                    if angle_earth > opening_angle_earth:
                        cgb_rate += cgb_rates[i]
                array_cgb_rate.append(cgb_rate)
        self._array_cgb_rate = np.array(array_cgb_rate).T
        self._cgb_rate_interpolator = interpolate.interp1d(self._sun_time, self._array_cgb_rate)


    def cgb_rate_array(self, met):
        """
        Interpolation function for the CGB continuum rate in a certain Ebin
        :param met: times at which to interpolate
        :return: array with the CGB rates expected over whole day in a certain Ebin
        """

        return self._cgb_rate_interpolator(met)

    def earth_rate_array(self, met):
        """
        Interpolation function for the Earth continuum rate in a certain Ebin
        :param met: times at which to interpolate
        :return: array with the Earth rates expected over whole day in a certain Ebin
        """

        return self._earth_rate_interpolator(met)

    @property
    def cgb_rate_interpolation_time(self):
        return self._array_cgb_rate

    @property
    def earth_rate_interpolation_time(self):
        return self._array_earth_rate

    @property
    def earth_az_interpolation_time(self):
        return self._earth_az

    @property
    def earth_zen_interpolation_time(self):
        return self._earth_zen

    @property
    def earth_pos_interpolation_time(self):
        return self._earth_pos_inter_times

    @property
    def saa_slices(self):
        return self._saa_slices

    @property
    def rate_generator_DRM(self):
        return self._rate_generator_DRM

    #test
    @property
    def det_ra_icrs(self):
        return self._det_ra

    @property
    def det_dec_icrs(self):
        return self._det_dec

    @property
    def times_lower_bound_index(self):
        """
        :return: the lower bound index of the part of the interpolation list covered by this rank
        """
        return self._times_lower_bound_index

    @property
    def times_upper_bound_index(self):
        """
        :return: the upper bound index of the part of the interpolation list covered by this rank
        """
        return self._times_upper_bound_index

    
    #test
    def west(self, met):
        return self._west_interpolator(met)

    def ra(self, met):
        return self._det_ra_interpolator(met)
    def dec(self, met):
        return self._det_dec_interpolator(met)

    def phi_west(self, met):
        return self._phi_west_interpolator(met)

    def theta_west(self, met):
        return self._theta_west_interpolator(met)
    def earth_angle(self, met):
        return self._earth_angle_interpolator(met)


    def point_earth_angle(self, met):
        return self._point_earth_angle_interpolator(met)

    def point_base_rate(self, met):
        return self._point_base_rate_interpolator(met)

    @property
    def sun_pos_icrs(self):
        return self._sun_pos_icrs

    def point_earth_phi(self,met):
        return self._pointing_earth_frame_phi_interpolator(met)

    def point_earth_theta(self,met):
        return self._pointing_earth_frame_theta_interpolator(met) 

    def west_angle_interpolator_define(self):
        sc_pos = self.sc_pos
        sun_time = self.interpolation_time
        sc_pos_norm = []
        for pos in sc_pos:
            sc_pos_norm.append(pos/np.sqrt(pos[0]**2+pos[1]**2+pos[2]**2))
        sc_pos_norm=np.array(sc_pos_norm)
        west_vector_bin = np.array([sc_pos_norm[:,1],-sc_pos_norm[:,0],np.zeros(len(sc_pos_norm[:,0]))]).T
        west_vector_bin_norm = []
        for pos in west_vector_bin:
            west_vector_bin_norm.append(pos/np.sqrt(pos[0]**2+pos[1]**2+pos[2]**2))
        west_vector_bin_norm=np.array(west_vector_bin_norm)

        point_phi=self._pointing_earth_frame_phi
        point_theta=self._pointing_earth_frame_theta
        
        pointing_vector = np.array([np.cos(point_phi)*np.cos(point_theta), np.sin(point_phi)*np.cos(point_theta), np.sin(point_theta)]).T

        self._phi_west = np.arccos(west_vector_bin_norm[:,0]*pointing_vector[:,0]+west_vector_bin_norm[:,1]*pointing_vector[:,1]+west_vector_bin_norm[:,2]*pointing_vector[:,2])*180/np.pi

        self._west_angle_interpolator = interpolate.interp1d(self._sun_time, self._phi_west)


    def north_angle_interpolator_define(self):
        sc_pos = self.sc_pos
        sun_time = self.interpolation_time
        sc_pos_norm = []
        for pos in sc_pos:
            sc_pos_norm.append(pos/np.sqrt(pos[0]**2+pos[1]**2+pos[2]**2))
        sc_pos_norm=np.array(sc_pos_norm)
        north_vector_bin = np.array([np.zeros(len(sc_pos_norm[:,0])),np.zeros(len(sc_pos_norm[:,0])),sc_pos_norm[:,2]]).T
        north_vector_bin_norm = []
        for pos in north_vector_bin:
            north_vector_bin_norm.append(pos/np.sqrt(pos[0]**2+pos[1]**2+pos[2]**2))
        north_vector_bin_norm=np.array(north_vector_bin_norm)

        point_phi=self._pointing_earth_frame_phi
        point_theta=self._pointing_earth_frame_theta

        pointing_vector = np.array([np.cos(point_phi)*np.cos(point_theta), np.sin(point_phi)*np.cos(point_theta), np.sin(point_theta)]).T

        self._phi_north = np.arccos(north_vector_bin_norm[:,0]*pointing_vector[:,0]+north_vector_bin_norm[:,1]*pointing_vector[:,1]+north_vector_bin_norm[:,2]*pointing_vector[:,2])*180/np.pi

        self._north_angle_interpolator = interpolate.interp1d(self._sun_time, self._phi_north)

        
    def west_angle(self, met):
        return self._west_angle_interpolator(met)

    def north_angle(self, met):
        return self._north_angle_interpolator(met)

    def ned_east(self, met):
        return self._ned_east_interpolator(met)

    def ned_down(self, met):
        return self._ned_down_interpolator(met)


    def build_lat_spacecraft_lon(self, year, month, day, min_met, max_met):
        """This function reads a LAT-spacecraft file and stores the data in arrays of the form: lat_time, mc_b, mc_l.\n
        Input:\n
        readfile.lat_spacecraft ( week = WWW )\n
        Output:\n
        0 = time\n
        1 = mcilwain parameter B\n
        2 = mcilwain parameter L"""

        # read the file

        day = astro_time.Time("%s-%s-%s" %(year, month, day))

        gbm_time = GBMTime(day)

        mission_week = np.floor(gbm_time.mission_week.value)


        filename = 'lat_spacecraft_weekly_w%d_p202_v001.fits' % mission_week
        filepath = get_path_of_data_file('lat', filename)


        if not file_existing_and_readable(filepath):

            download_lat_spacecraft(mission_week)


        # lets check that this file has the right info

        week_before = False
        week_after = False

        with fits.open(filepath) as f:

            if (f['PRIMARY'].header['TSTART'] >= min_met):

                # we need to get week before

                week_before = True

                before_filename = 'lat_spacecraft_weekly_w%d_p202_v001.fits' % (mission_week - 1)
                before_filepath = get_path_of_data_file('lat', before_filename)

                if not file_existing_and_readable(before_filepath):
                    download_lat_spacecraft(mission_week - 1)


            if (f['PRIMARY'].header['TSTOP'] <= max_met):

                # we need to get week after

                week_after = True

                after_filename = 'lat_spacecraft_weekly_w%d_p202_v001.fits' % (mission_week + 1)
                after_filepath = get_path_of_data_file('lat', after_filename)

                if not file_existing_and_readable( after_filepath):
                    download_lat_spacecraft(mission_week + 1)


            # first lets get the primary file

            lat_time = np.mean( np.vstack( (f['SC_DATA'].data['START'],f['SC_DATA'].data['STOP'])),axis=0)
            lat_geo = f['SC_DATA'].data['LAT_GEO']
            lon_geo = f['SC_DATA'].data['LON_GEO']
            rad_geo = f['SC_DATA'].data['RAD_GEO']


        # if we need to append anything to make up for the
        # dates not being included in the files
        # do it here... thanks Fermi!
        if week_before:

            with fits.open(before_filepath) as f:

                lat_time_before = np.mean(np.vstack((f['SC_DATA'].data['START'], f['SC_DATA'].data['STOP'])), axis=0)
                lat_geo_before = f['SC_DATA'].data['LAT_GEO']
                lon_geo_before = f['SC_DATA'].data['LON_GEO']
                rad_geo_before = f['SC_DATA'].data['RAD_GEO']


            lat_geo = np.append(lat_geo_before, mc_b)
            lon_geo = np.append(lon_geo_before, mc_l)
            rad_geo = np.append(rad_geo_before, rad_geo)
            lat_time = np.append(lat_time_before, lat_time)

        if week_after:

            with fits.open(after_filepath) as f:
                lat_time_after = np.mean(np.vstack((f['SC_DATA'].data['START'], f['SC_DATA'].data['STOP'])), axis=0)
                lat_geo_after = f['SC_DATA'].data['LAT_GEO']
                lon_geo_after = f['SC_DATA'].data['LON_GEO']
                rad_geo_after = f['SC_DATA'].data['RAD_GEO']

            lon_geo = np.append(lon_geo, lon_geo_after)
            lat_geo = np.append(lat_geo, lat_geo_after)
            rad_geo = np.append(rad_geo, rad_geo_after)
            lat_time = np.append(lat_time, lat_time_after)

        """
        # save them
        #TODO: do we need use the mean here?
        self._mc_l = mc_l
        self._mc_b = mc_b
        self._mc_time = lat_time
        # interpolate them
        self._mc_b_interp = interpolate.interp1d(self._mc_time, self._mc_b)
        self._mc_l_interp = interpolate.interp1d(self._mc_time, self._mc_l)
        """
        #remove the self-variables for memory saving
        lon_geo_interp = interpolate.interp1d(lat_time, lon_geo)
        lat_geo_interp = interpolate.interp1d(lat_time, lat_geo)
        rad_geo_interp = interpolate.interp1d(lat_time, rad_geo)
        return lon_geo_interp, lat_geo_interp, rad_geo_interp

    @property
    def ebins_size(self):
        return self._ebins_size
        
    def _response_sum(self):
        """
        Calculate the cgb_rate_array for all interpolation times for which the geometry was calculated. This supports
        MPI to reduce the calculation time.
        To calculate the cgb_rate_array the responses created on a grid in rate_gernerator_DRM are used. All points
        that are not occulted by the earth are added, assuming a spectrum specified in rate_generator_DRM for the cgb
        spectrum.
        :return:
        """
        points = self._rate_generator_DRM.points
        responses = self._rate_generator_DRM.responses
        sr_points = 4 * np.pi / len(points)
        # get the earth direction at the interpolation times; zen angle from -90 to 90
        earth_pos_inter_times = []
        if using_mpi:
            # last rank has to cover one more index. Caused by the calculation of the Geometry for the last time
            # bin of the day
            if rank == size - 1:
                upper_index = self._times_upper_bound_index + 1
            else:
                upper_index = self._times_upper_bound_index

            for i in range(self._times_lower_bound_index, upper_index):
                earth_pos_inter_times.append(
                    np.array([np.cos(self._earth_zen[i] * (np.pi / 180)) * np.cos(self._earth_az[i] * (np.pi / 180)),
                              np.cos(self._earth_zen[i] * (np.pi / 180)) * np.sin(self._earth_az[i] * (np.pi / 180)),
                              np.sin(self._earth_zen[i] * (np.pi / 180))]))
            self._earth_pos_inter_times = np.array(earth_pos_inter_times)
            # define the opening angle of the earth in degree
            opening_angle_earth = 67
            array_cgb_response_sum = []
            array_earth_response_sum = []
            for pos in self._earth_pos_inter_times:
                cgb_response_time = np.zeros_like(responses[0])
                earth_response_time = np.zeros_like(responses[0])
                for i, pos_point in enumerate(points):
                    angle_earth = np.arccos(np.dot(pos, pos_point)) * (180 / np.pi)
                    if angle_earth > opening_angle_earth:
                        cgb_response_time += responses[i]
                    else:
                        earth_response_time += responses[i]
                array_cgb_response_sum.append(cgb_response_time)
                array_earth_response_sum.append(earth_response_time)
            array_cgb_response_sum = np.array(array_cgb_response_sum)
            array_earth_response_sum = np.array(array_earth_response_sum)
            array_cgb_response_sum_g = comm.gather(array_cgb_response_sum, root=0)
            array_earth_response_sum_g = comm.gather(array_earth_response_sum, root=0) 
            if rank == 0:
                array_cgb_response_sum_g = np.concatenate(array_cgb_response_sum_g)
                array_earth_response_sum_g = np.concatenate(array_earth_response_sum_g)
            array_cgb_response_sum = comm.bcast(array_cgb_response_sum_g, root=0)
            array_earth_response_sum = comm.bcast(array_earth_response_sum_g, root=0)
        else:
            for i in range(0, len(self._earth_zen)):
                earth_pos_inter_times.append(
                    np.array([np.cos(self._earth_zen[i] * (np.pi / 180)) * np.cos(self._earth_az[i] * (np.pi / 180)),
                              np.cos(self._earth_zen[i] * (np.pi / 180)) * np.sin(self._earth_az[i] * (np.pi / 180)),
                              np.sin(self._earth_zen[i] * (np.pi / 180))]))
            self._earth_pos_inter_times = np.array(earth_pos_inter_times)
            # define the opening angle of the earth in degree
            opening_angle_earth = 67
            array_cgb_response_sum = []
            array_earth_response_sum = []
            for pos in self._earth_pos_inter_times:
                cgb_response_time = np.zeros_like(responses[0])
                earth_response_time = np.zeros_like(responses[0])
                for i, pos_point in enumerate(points):
                    angle_earth = np.arccos(np.dot(pos, pos_point)) * (180 / np.pi)
                    if angle_earth > opening_angle_earth:
                        cgb_response_time += responses[i]
                    else:
                        earth_response_time += responses[i]
                array_cgb_response_sum.append(cgb_response_time)                                                                                                                                                 
                array_earth_response_sum.append(earth_response_time)
                
        self._array_cgb_response_sum = np.array(array_cgb_response_sum)*sr_points
        self._array_earth_response_sum = np.array(array_earth_response_sum)*sr_points

    @property
    def response_array_earth(self):
        return self._array_earth_response_sum


    @property
    def response_array_cgb(self):
        return self._array_cgb_response_sum

    @property
    def Ebin_source(self):
        return self._rate_generator_DRM.Ebin_in_edge
