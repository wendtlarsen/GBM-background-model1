import matplotlib

matplotlib.use('Agg')
# imports
from gbmbkgpy.data.continuous_data import Data
from gbmbkgpy.data.external_prop import ExternalProps
from gbmbkgpy.modeling.model import Model
from gbmbkgpy.fitting.background_like import BackgroundLike
from gbmbkgpy.utils.saa_calc import SAA_calc
from gbmbkgpy.utils.geometry_calc import Geometry
from gbmbkgpy.utils.response_precalculation import Response_Precalculation
from gbmbkgpy.io.downloading import download_files
from gbmbkgpy.minimizer.multinest_minimizer import MultiNestFit
from gbmbkgpy.io.plotting.plot import Plotter
from gbmbkgpy.modeling.setup_sources import Setup
from gbmbkgpy.modeling.albedo_cgb import Albedo_CGB_fixed, Albedo_CGB_free
from config import *

import numpy as np

from datetime import datetime

from mpi4py import MPI

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

start = datetime.now()


def print_progress(text):
    """
    Helper function that prints the input text only with rank 0
    """
    if rank == 0:
        print(text)


####################### Setup parameters ###############################
date = general_dict['dates']
detector = general_dict['detector']
data_type = general_dict['data_type']
# List with all echans you want to use
echan_list = general_dict['echan_list']  # has to be  List! One entry is also possible

############################# Data ######################################

# download files with rank=0; all other ranks have to wait!
print_progress('Download data...')
if rank == 0:
    for d in date:
        download_files(data_type, detector, d)
    wait = True
else:
    wait = None
wait = comm.bcast(wait, root=0)
print_progress('Done')
# Create the data object for the wanted day and detector

print_progress('Prepare data...')
data = Data(date, detector, data_type, echan_list)
print_progress('Done')

# Create external properties object (for McIlwain L-parameter)
print_progress('Download and prepare external properties...')
ep = ExternalProps(date)
print_progress('Done')

############################# Model ########################################

################## Response precalculation ################

# Create a Response precalculation object, that precalculates the responses on a spherical grid arount the detector.
# These calculations use the full DRM's and thus include sat. scattering and partial loss of energy by the photons.
Ngrid = response_dict['Ngrid']
print_progress('Precalculate responses for {} points on sphere around detector...'.format(Ngrid))
resp = Response_Precalculation(detector, date, echan_list, Ngrid=Ngrid, data_type=data_type)
print_progress('Done')

################## SAA precalculation ######################

######### SAA options ###########
# Use time after SAA? If no give the time which should be deleted after every SAA in s. If use_SAA=False no SAA sources
# are build
time_after_SAA = saa_dict['time_after_SAA']
# Want to use separated time intervals that are shorter than 1000 seconds?
short_time_intervals = saa_dict['short_time_intervals']
################################

# Build the SAA object
if time_after_SAA is not None:
    print_progress('Precalculate SAA times and SAA mask. {} seconds after every SAA exit are excluded from fit...')
else:
    print_progress('Precalculate SAA times and SAA mask...')
saa_calc = SAA_calc(data, time_after_SAA=time_after_SAA, short_time_intervals=short_time_intervals)
print_progress('Done')

################### Geometry precalculation ##################

########## Geom options ###########

# For how many times during the day do you want to calculate the geometry? In between a linear interpolation is used.
n_bins_to_calculate = geom_dict['n_bins_to_calculate']
###################################
print_progress('Precalculate geometry for {} times during the day...'.format(n_bins_to_calculate))
geom = Geometry(data, detector, date, n_bins_to_calculate)
print_progress('Done')

##################### Setup Sources ##########################

# Create all individual sources and add them to a list

########## Setup options ###########

# Use SAA?
use_SAA = setup_dict['use_SAA']
# Use CosmicRay source?
use_CR = setup_dict['use_CR']
# Use EarthAlbedo source?
use_Earth = setup_dict['use_Earth']
# Use CGB source?
use_CGB = setup_dict['use_CGB']
# Which PS should be included (given as list of names)
ps_list = setup_dict['ps_list']
# Which of these PS should have a free pl spectrum?
fix_ps = setup_dict['fix_ps']
# Fix the spectrum of the earth albedo?
fix_earth = setup_dict['fix_earth']
# Fix the spectrum of the CGB?
fix_cgb = setup_dict['fix_cgb']

assert (fix_earth and fix_cgb) or (not fix_earth and not fix_cgb), 'At the moment albeod and cgb spectrum have to be either both fixed or both free'

########### Albedo-CGB Object ###########
if fix_earth:
    albedo_cgb_obj = Albedo_CGB_fixed(resp, geom)
else:
    albedo_cgb_obj = Albedo_CGB_free(resp, geom)

print_progress('Create Source list...')

source_list = Setup(data, saa_calc, ep, geom, echan_list=echan_list, response_object=resp, albedo_cgb_object=albedo_cgb_obj,
                    use_SAA=use_SAA, use_CR=use_CR, use_Earth=use_Earth, use_CGB=use_CGB, point_source_list=ps_list,
                    fix_ps=fix_ps, fix_Earth=fix_earth, fix_CGB=fix_cgb)

print_progress('Done')

###################### Setup Model #############################
print_progress('Build model with source_list...')
model = Model(*source_list)
print_progress('Done')

##################### Prior bounds #############################

######## Define bounds for all sources ###############

# SAA: Amplitude and decay constant
saa_bounds = bounds_dict['saa_bound']

# CR: Constant and McIlwain normalization
cr_bounds = bounds_dict['cr_bound']

# Amplitude of PS spectrum
ps_fixed_bound = bounds_dict['ps_fixed_bound']
ps_free_bound = bounds_dict['ps_free_bound']
# If earth spectrum is fixed only the normalization, otherwise C, index1, index2 and E_break
if fix_earth:
    earth_bound = bounds_dict['earth_fixed_bound']
else:
    earth_bound = bounds_dict['earth_free_bound']

# If cgb spectrum is fixed only the normalization, otherwise C, index1, index2 and E_break
if fix_cgb:
    cgb_bound = bounds_dict['cgb_fixed_bound']
else:
    cgb_bound = bounds_dict['cgb_free_bound']

######## Define gaussian parameter for all sources ###############

# SAA: Amplitude and decay constant
saa_gaussian = gaussian_dict['saa_bound']

# CR: Constant and McIlwain normalization
cr_gaussian = gaussian_dict['cr_bound']

# Amplitude of PS spectrum
ps_fixed_gaussian = gaussian_dict['ps_fixed_bound']
ps_free_gaussian = gaussian_dict['ps_free_bound']
# If earth spectrum is fixed only the normalization, otherwise C, index1, index2 and E_break
if fix_earth:
    earth_gaussian = gaussian_dict['earth_fixed_bound']
else:
    earth_gaussian = gaussian_dict['earth_free_bound']

# If cgb spectrum is fixed only the normalization, otherwise C, index1, index2 and E_break
if fix_cgb:
    cgb_gaussian = gaussian_dict['cgb_fixed_bound']
else:
    cgb_gaussian = gaussian_dict['cgb_free_bound']

#######################################

parameter_bounds = []

# Echan individual sources
for i in echan_list:
    if use_SAA:
        for j in range(saa_calc.num_saa):
            parameter_bounds.append(saa_bounds)

        # If fitting only one day add additional 'SAA' decay to account for leftover excitation
        if len(date) == 1:
            parameter_bounds.append(saa_bounds)

    if use_CR:
        parameter_bounds.append(cr_bounds)
# Global sources for all echans
for i, ps in enumerate(ps_list):
    if fix_ps[i]:
        parameter_bounds.append(ps_fixed_bound)
    else:
        parameter_bounds.append(ps_free_bound)

parameter_bounds.append(earth_bound)
parameter_bounds.append(cgb_bound)

# Concatenate this
parameter_bounds = np.concatenate(parameter_bounds)

# Add bounds to the parameters for multinest
model.set_parameter_bounds(parameter_bounds)

gaussian_parameter_bounds = []

# Echan individual sources
for i in echan_list:
    if use_SAA:
        for j in range(saa_calc.num_saa):
            gaussian_parameter_bounds.append(saa_gaussian)

        # If fitting only one day add additional 'SAA' decay to account for leftover excitation
        if len(date) == 1:
            gaussian_parameter_bounds.append(saa_gaussian)

    if use_CR:
        gaussian_parameter_bounds.append(cr_gaussian)
# Global sources for all echans
for i, ps in enumerate(ps_list):
    if fix_ps[i]:
        gaussian_parameter_bounds.append(ps_fixed_gaussian)
    else:
        gaussian_parameter_bounds.append(ps_free_gaussian)

gaussian_parameter_bounds.append(earth_gaussian)
gaussian_parameter_bounds.append(cgb_gaussian)

# Concatenate this
gaussian_parameter_bounds = np.concatenate(gaussian_parameter_bounds)

# Add bounds to the parameters for multinest
model.set_parameter_gaussian(gaussian_parameter_bounds)
################################## Backgroundlike Class #################################

# Class that calcualtes the likelihood
print_progress('Create BackgroundLike class that conects model and data...')
background_like = BackgroundLike(data, model, saa_calc, echan_list)
print_progress('Done')

################################## Fitting ###############################################

############# Multinest options ##############

# Number of live points for mulitnest?
num_live_points = multi_dict['num_live_points']

# const_efficiency_mode of mulitnest?
const_efficiency_mode = multi_dict['constant_efficiency_mode']

#############################################

# Instantiate Multinest Fit
mn_fit = MultiNestFit(background_like, model.parameters)
# Fit with multinest and define the number of live points one wants to use
mn_fit.minimize_multinest(n_live_points=num_live_points, const_efficiency_mode=const_efficiency_mode)

# Plot Marginals
mn_fit.plot_marginals()

# Multinest Output dir
output_dir = mn_fit.output_dir

################################# Plotting ################################################

############## Plot options #################
# Choose a bin width to bin the data
bin_width = plot_dict['bin_width']

# Change time to seconds from midnight?
change_time = plot_dict['change_time']

# Show Residuals?
show_residuals = plot_dict['show_residuals']

# Show data?
show_data = plot_dict['show_data']

# Plot best fit of individual sources?
plot_sources = plot_dict['plot_sources']

# Display the GRB trigger time? What times and names? Time in '20:57:03.000' format.
show_grb_trigger = plot_dict['show_grb_trigger']
times_mark = plot_dict['times_mark']
names_mark = plot_dict['names_mark']

# Create PPC plots?
ppc = plot_dict['ppc']

# Time range for plot (as tuple, e.g. (5000,35000))
xlim = plot_dict['xlim']

# Count rates range for plot (as tuple, e.g. (0,60))
ylim = plot_dict['ylim']

# Should the legend be outside of the plot?
legend_outside = plot_dict['legend_outside']

print_progress('Create Plotter object...')
# Create Plotter object that creates the plots
plotter = Plotter(data, model, saa_calc, echan_list)
print_progress('Done')

# Create one plot for every echan and save it
for index, echan in enumerate(echan_list):
    print_progress('Create Plots for echan {} ...'.format(echan))
    residual_plot = plotter.display_model(index, min_bin_width=bin_width, show_residuals=show_residuals,
                                          show_data=show_data, plot_sources=plot_sources,
                                          show_grb_trigger=show_grb_trigger, change_time=change_time, ppc=ppc,
                                          result_dir=output_dir, xlim=xlim, ylim=ylim, legend_outside=legend_outside)
    if rank == 0:
        residual_plot.savefig(output_dir + 'residual_plot_{}_det_{}_echan_{}_bin_width_{}.pdf'.format(
            date, detector, echan, bin_width), dpi=300)
plotter._plot_data(output_dir + 'data_for_plots.hdf5', output_dir, echan_list)
print_progress('Done')
# Print the duration of the script
print('Whole calculation took: {}'.format(datetime.now() - start))
