# -*- coding: utf-8 -*-

# BCDI: tools for pre(post)-processing Bragg coherent X-ray diffraction imaging data
#   (c) 07/2017-06/2019 : CNRS UMR 7344 IM2NP
#   (c) 07/2019-present : DESY PHOTON SCIENCE
#       authors:
#         Jerome Carnis, carnis_jerome@yahoo.fr

import hdf5plugin  # for P10 amd NANOMAX, should be imported before h5py or PyTables
import xrayutilities as xu
import numpy as np
import matplotlib.pyplot as plt
plt.switch_backend("Qt5Agg")  # "Qt5Agg" or "Qt4Agg" depending on the version of Qt installer, bug with Tk
import pathlib
import os
import scipy.signal  # for medfilt2d
from scipy.ndimage.measurements import center_of_mass
import sys
from scipy.io import savemat
import tkinter as tk
from tkinter import filedialog
import gc
sys.path.append('/home/dzhigd/Software/bcdi/')
import bcdi.graph.graph_utils as gu
import bcdi.experiment.experiment_utils as exp
import bcdi.postprocessing.postprocessing_utils as pu
import bcdi.preprocessing.preprocessing_utils as pru


helptext = """
Prepare experimental data for Bragg CDI phasing: crop/pad, center, mask, normalize and filter the data.

Beamlines currently supported: ESRF ID01, SOLEIL CRISTAL, SOLEIL SIXS, PETRAIII P10 and APS 34ID-C.

Output: data and mask as numpy .npz or Matlab .mat 3D arrays for phasing

File structure should be (e.g. scan 1):
specfile, hotpixels file and flatfield file in:    /rootdir/
data in:                                           /rootdir/S1/data/

output files saved in:   /rootdir/S1/pynxraw/ or /rootdir/S1/pynx/ depending on 'use_rawdata' option
"""

scans = [329]  # np.arange(404, 407+1, 3)  # list or array of scan numbers
root_folder = "/media/dzhigd/My Passport/DDzhigaev/Data/MAXIV/NanoMax/2020062408/raw/"
sample_name = "sample0609"  # "SN"  #
user_comment = ''  # string, should start with "_"
debug = False  # set to True to see plots
binning = (1, 1, 1)  # binning that will be used for phasing
# (stacking dimension, detector vertical axis, detector horizontal axis)
###########################
flag_interact = True  # True to interact with plots, False to close it automatically
background_plot = '0.5'  # in level of grey in [0,1], 0 being dark. For visual comfort during masking
###########################
centering = 'com'  # Bragg peak determination: 'max' or 'com', 'max' is better usually.
#  It will be overridden by 'fix_bragg' if not empty
fix_bragg = []  # fix the Bragg peak position [z_bragg, y_bragg, x_bragg] considering the full detector
# It is useful if hotpixels or intense aliens. Leave it [] otherwise.
###########################
fix_size = []  # crop the array to predefined size considering the full detector,
# leave it to [] otherwise [zstart, zstop, ystart, ystop, xstart, xstop]. ROI will be defaulted to []
###########################
center_fft = 'skip'
# 'crop_sym_ZYX','crop_asym_ZYX','pad_asym_Z_crop_sym_YX', 'pad_sym_Z_crop_asym_YX',
# 'pad_sym_Z', 'pad_asym_Z', 'pad_sym_ZYX','pad_asym_ZYX' or 'skip'
pad_size = []  # size after padding, e.g. [256, 512, 512]. Use this to pad the array.
# used in 'pad_sym_Z_crop_sym_YX', 'pad_sym_Z', 'pad_sym_ZYX'
###########################
normalize_flux = False  # will normalize the intensity by the default monitor.
###########################
mask_zero_event = False  # mask pixels where the sum along the rocking curve is zero - may be dead pixels
###########################
flag_medianfilter = 'skip'
# set to 'median' for applying med2filter [3,3]
# set to 'interp_isolated' to interpolate isolated empty pixels based on 'medfilt_order' parameter
# set to 'mask_isolated' it will mask isolated empty pixels
# set to 'skip' will skip filtering
medfilt_order = 8    # for custom median filter, number of pixels with intensity surrounding the empty pixel
###########################
reload_previous = False  # True to resume a previous masking (load data and mask)
###########################
use_rawdata = False  # False for using data gridded in laboratory frame/ True for using data in detector frame
save_to_mat = True  # True to save also in .mat format
save_to_vti = True  # save the orthogonalized diffraction pattern to VTK file
######################################
# define beamline related parameters #
######################################
beamline = 'NANOMAX'  # name of the beamline, used for data loading and normalization by monitor
# supported beamlines: 'ID01', 'SIXS_2018', 'SIXS_2019', 'CRISTAL', 'P10', '34ID', 'NanoMAX'
is_series = False  # specific to series measurement at P10

custom_scan = False  # set it to True for a stack of images acquired without scan, e.g. with ct in a macro, or when
# there is no spec/log file available
custom_images = [3]  # np.arange(11353, 11453, 1)  # list of image numbers for the custom_scan
custom_monitor = np.ones(51)  # monitor values for normalization for the custom_scan

rocking_angle = "inplane"  # "outofplane" or "inplane" or "energy"
follow_bragg = False  # only for energy scans, set to True if the detector was also scanned to follow the Bragg peak
specfile_name = ''
# .spec for ID01, .fio for P10, alias_dict.txt for SIXS_2018, not used for CRISTAL and SIXS_2019
# template for ID01: name of the spec file without '.spec'
# template for SIXS_2018: full path of the alias dictionnary, typically root_folder + 'alias_dict_2019.txt'
# template for SIXS_2019: ''
# template for P10: sample_name + '_%05d'
# template for CRISTAL: ''
# template for 34ID: ''
#############################################################
# define detector related parameters and region of interest #
#############################################################
detector = "Merlin"    # "Eiger2M", "Maxipix", "Eiger4M" or "Timepix"
# nb_pixel_y = 1614  # use for the data measured with 1 tile broken on the Eiger2M
x_bragg = 147  # horizontal pixel number of the Bragg peak, can be used for the definition of the ROI
y_bragg = 178  # vertical pixel number of the Bragg peak, can be used for the definition of the ROI
# roi_detector = [1202, 1610, x_bragg - 256, x_bragg + 256]  # HC3207  x_bragg = 430
#roi_detector = [0,514,0,514]
roi_detector = []
# roi_detector = [y_bragg - 168, y_bragg + 168, x_bragg - 140, x_bragg + 140]  # CH5309
# roi_detector = [552, 1064, x_bragg - 240, x_bragg + 240]  # P10 2018
# roi_detector = [y_bragg - 290, y_bragg + 350, x_bragg - 350, x_bragg + 350]  # PtRh Ar
# [Vstart, Vstop, Hstart, Hstop]
# leave it as [] to use the full detector. Use with center_fft='skip' if you want this exact size.
photon_threshold = 0  # data[data < photon_threshold] = 0
hotpixels_file = ''  # root_folder + 'hotpixels.npz'  #
flatfield_file = ''  # root_folder + "flatfield_maxipix_8kev.npz"  #
template_imagefile = 'scan_%06d_merlin.hdf5'
mask_path = '/home/dzhigd/work/projects/CsPbBr3_NC_BCDI_NanoMAX/data/merlin_mask_190222_14keV.h5'
# template for NANOMAX: 'scan_%06d_merlin.hdf5'
# template for ID01: 'data_mpx4_%05d.edf.gz' or 'align_eiger2M_%05d.edf.gz'
# template for SIXS_2018: 'align.spec_ascan_mu_%05d.nxs'
# template for SIXS_2019: 'spare_ascan_mu_%05d.nxs'
# template for Cristal: 'S%d.nxs'
# template for P10: '_master.h5'
# template for 34ID: 'Sample%dC_ES_data_51_256_256.npz'
################################################################################
# define parameters below if you want to orthogonalize the data before phasing #
################################################################################
sdd = 1.1  # in m, sample to detector distance in m, not important if you use raw data
energy = 9000  # x-ray energy in eV, not important if you use raw data
custom_motors = {"phi": 5.899999999999977, "theta": 0, "delta": 0, "gamma": 13.259982884960397}
# use this to declare motor positions if there is not log file
# example: {"eta": np.linspace(16.989, 18.989, num=100, endpoint=False), "phi": 0, "nu": -0.75, "delta": 36.65}
# NANOMAX:
# ID01: eta, phi, nu, delta
# CRISTAL: mgomega, gamma, delta
# P10: om, phi, chi, mu, gamma, delta
# SIXS: beta, mu, gamma, delta
# 34ID: mu, phi (incident angle), chi, theta (inplane), delta (inplane), gamma (outofplane)
#########################################################################
# parameters for xrayutilities to orthogonalize the data before phasing #
#########################################################################
# xrayutilities uses the xyz crystal frame: for incident angle = 0, x is downstream, y outboard, and z vertical up
beam_direction = (1, 0, 0)  # beam along z
sample_inplane = (0, 1, 0)  # sample inplane reference direction along the beam at 0 angles
sample_outofplane = (1, 0, 0)  # surface normal of the sample at 0 angles
offset_inplane = 0  # outer detector angle offset, not important if you use raw data
sample_offsets = (0, 0, 0)  # tuple of offsets in degree of the sample around z (downstream), y (vertical up) and x
# the sample offsets will be added to the motor values
cch1 = 514/2  # cch1 parameter from xrayutilities 2D detector calibration, detector roi is taken into account below
cch2 = 514/2  # cch2 parameter from xrayutilities 2D detector calibration, detector roi is taken into account below
detrot = 0  # detrot parameter from xrayutilities 2D detector calibration
tiltazimuth = 0  # tiltazimuth parameter from xrayutilities 2D detector calibration
tilt = 0  # tilt parameter from xrayutilities 2D detector calibration
##################################
# end of user-defined parameters #
##################################


def close_event(event):
    """
    This function handles closing events on plots.

    :return: nothing
    """
    print(event, 'Click on the figure instead of closing it!')
    sys.exit()


def on_click(event):
    """
    Function to interact with a plot, return the position of clicked pixel. If flag_pause==1 or
    if the mouse is out of plot axes, it will not register the click

    :param event: mouse click event
    :return: updated list of vertices which defines a polygon to be masked
    """
    global xy, flag_pause
    if not event.inaxes:
        return
    if not flag_pause:
        _x, _y = int(np.rint(event.xdata)), int(np.rint(event.ydata))
        xy.append([_x, _y])
    return


def press_key(event):
    """
    Interact with a plot for masking parasitic diffraction intensity or detector gaps

    :param event: button press event
    :return: updated data, mask and controls
    """
    global original_data, original_mask, data, mask, temp_mask, dim, idx, width, flag_aliens, flag_mask, flag_pause
    global xy, points, fig_mask, masked_color, max_colorbar

    try:
        if flag_aliens:
            data, mask, width, max_colorbar, idx, stop_masking = \
                pru.update_aliens(key=event.key, pix=int(np.rint(event.xdata)), piy=int(np.rint(event.ydata)),
                                  original_data=original_data, original_mask=original_mask, updated_data=data,
                                  updated_mask=mask, figure=fig_mask, width=width, dim=dim, idx=idx, vmin=0,
                                  vmax=max_colorbar, invert_yaxis=not use_rawdata)
        elif flag_mask:
            data, temp_mask, flag_pause, xy, width, max_colorbar, stop_masking = \
                pru.update_mask(key=event.key, pix=int(np.rint(event.xdata)), piy=int(np.rint(event.ydata)),
                                original_data=original_data, original_mask=mask, updated_data=data,
                                updated_mask=temp_mask, figure=fig_mask, flag_pause=flag_pause, points=points,
                                xy=xy, width=width, dim=dim, vmin=0, vmax=max_colorbar, masked_color=masked_color,
                                invert_yaxis=not use_rawdata)
        else:
            stop_masking = False

        if stop_masking:
            plt.close(fig_mask)

    except AttributeError:  # mouse pointer out of axes
        pass


#######################
# Initialize detector #
#######################
kwargs = dict()  # create dictionnary
try:
    kwargs['nb_pixel_x'] = nb_pixel_x  # fix to declare a known detector but with less pixels (e.g. one tile HS)
except NameError:  # nb_pixel_x not declared
    pass
try:
    kwargs['nb_pixel_y'] = nb_pixel_y  # fix to declare a known detector but with less pixels (e.g. one tile HS)
except NameError:  # nb_pixel_y not declared
    pass
try:
    kwargs['is_series'] = is_series
except NameError:  # is_series not declared
    pass

detector = exp.Detector(name=detector, datadir=root_folder, template_imagefile=template_imagefile, roi=roi_detector,
                        binning=binning, **kwargs)

####################
# Initialize setup #
####################
setup = exp.SetupPreprocessing(beamline=beamline, energy=energy, rocking_angle=rocking_angle, distance=sdd,
                               beam_direction=beam_direction, sample_inplane=sample_inplane,
                               sample_outofplane=sample_outofplane, offset_inplane=offset_inplane,
                               custom_scan=custom_scan, custom_images=custom_images, sample_offsets=sample_offsets,
                               custom_monitor=custom_monitor, custom_motors=custom_motors)

#############################################
# Initialize geometry for orthogonalization #
#############################################
if rocking_angle == "energy":
    use_rawdata = False  # you need to interpolate the data in QxQyQz for energy scans
    print("Energy scan: defaulting use_rawdata to False, the data will be interpolated using xrayutilities")
if not use_rawdata:
    qconv, offsets = pru.init_qconversion(setup)
    detector.offsets = offsets
    hxrd = xu.experiment.HXRD(sample_inplane, sample_outofplane, qconv=qconv)  # x downstream, y outboard, z vertical
    # first two arguments in HXRD are the inplane reference direction along the beam and surface normal of the sample
    cch1 = cch1 - detector.roi[0]  # take into account the roi if the image is cropped
    cch2 = cch2 - detector.roi[2]  # take into account the roi if the image is cropped
    hxrd.Ang2Q.init_area(setup.detector_ver, setup.detector_hor, cch1=cch1, cch2=cch2, Nch1=detector.roi[1] - detector.roi[0],
                         Nch2=detector.roi[3] - detector.roi[2], pwidth1=detector.pixelsize_y,
                         pwidth2=detector.pixelsize_x, distance=sdd, detrot=detrot, tiltazimuth=tiltazimuth, tilt=tilt)
    # first two arguments in init_area are the direction of the detector, checked for ID01 and SIXS

############################################
# Initialize values for callback functions #
############################################
flag_mask = False
flag_aliens = False
plt.rcParams["keymap.quit"] = ["ctrl+w", "cmd+w"]  # this one to avoid that q closes window (matplotlib default)
############################
# start looping over scans #
############################
root = tk.Tk()
root.withdraw()
try:
    len(scans)
except TypeError:  # a single number was provided, not a list
    scans = [scans]

if len(scans) > 1:
    if center_fft not in ['crop_asymmetric_ZYX', 'pad_Z', 'pad_asymmetric_ZYX']:
        center_fft = 'skip'
        # avoid croping the detector plane XY while centering the Bragg peak
        # otherwise outputs may have a different size, which will be problematic for combining or comparing them
if len(fix_size) != 0:
    print('"fix_size" parameter provided, roi_detector will be set to []')
    roi_detector = []

for scan_nb in range(len(scans)):
    plt.ion()

    comment = user_comment  # initialize comment
    if setup.beamline != 'P10':
        if setup.beamline == 'NANOMAX':
            homedir = root_folder + sample_name + '/'
            detector.datadir = homedir
            specfile = '%06d.h5'%scans[scan_nb]
            imagefile = detector.datadir+template_imagefile%scans[scan_nb]
            detector.template_imagefile = imagefile
        else:
            homedir = root_folder + sample_name + str(scans[scan_nb]) + '/'
            detector.datadir = homedir + "data/"
            specfile = specfile_name            
        
    else:
        specfile = specfile_name % scans[scan_nb]
        homedir = root_folder + specfile + '/'
        detector.datadir = homedir + 'e4m/'
        imagefile = specfile + template_imagefile
        detector.template_imagefile = imagefile

    if not use_rawdata:
        comment = comment + '_ortho'
        savedir = homedir + "pynx/"
        pathlib.Path(savedir).mkdir(parents=True, exist_ok=True)
    else:
        savedir = homedir + "pynxraw/"
        pathlib.Path(savedir).mkdir(parents=True, exist_ok=True)
    detector.savedir = savedir

    print('\nScan', scans[scan_nb])
    print('Setup: ', setup.beamline)
    print('Detector: ', detector.name)
    print('Pixel number (VxH): ', detector.nb_pixel_y, detector.nb_pixel_x)
    print('Detector ROI:', roi_detector)
    print('Horizontal pixel size with binning: ', detector.pixelsize_x, 'm')
    print('Vertical pixel size with binning: ', detector.pixelsize_y, 'm')
    print('Specfile: ', specfile)
    print('Scan type: ', setup.rocking_angle)

    if not use_rawdata:
        print('Output will be orthogonalized by xrayutilities')
        print('Energy:', setup.energy, 'ev')
        print('Sample to detector distance: ', setup.distance, 'm')
        plot_title = ['QzQx', 'QyQx', 'QyQz']
    else:
        print('Output will be non orthogonal, in the detector frame')
        plot_title = ['YZ', 'XZ', 'XY']

    if not fix_size:  # output_size not defined, default to actual size
        pass
    else:
        print("'fix_size' parameter provided, defaulting 'center_fft' to 'skip'")
        center_fft = 'skip'

    ####################################
    # Load data
    ####################################
    if reload_previous:  # resume previous masking
        print('Resuming previous masking')
        file_path = filedialog.askopenfilename(initialdir=homedir, title="Select data file",
                                               filetypes=[("NPZ", "*.npz")])
        data = np.load(file_path)
        npz_key = data.files
        data = data[npz_key[0]]
        file_path = filedialog.askopenfilename(initialdir=homedir, title="Select mask file",
                                               filetypes=[("NPZ", "*.npz")])
        mask = np.load(file_path)
        npz_key = mask.files
        mask = mask[npz_key[0]]
        try:
            file_path = filedialog.askopenfilename(initialdir=homedir, title="Select q values",
                                                   filetypes=[("NPZ", "*.npz")])
            reload_qvalues = np.load(file_path)
            q_values = [reload_qvalues['qx'], reload_qvalues['qz'], reload_qvalues['qy']]
        except FileNotFoundError:
            q_values = []  # cannot orthogonalize since we do not know the original array size
        center_fft = 'skip'  # we assume that crop/pad/centering was already performed
        frames_logical = np.ones(data.shape[0])  # we assume that all frames will be used
        fix_size = []  # we assume that crop/pad/centering was already performed
        normalize_flux = False  # we assume that normalization was already performed
        monitor = []  # we assume that normalization was already performed

        np.savez_compressed(savedir + 'S' + str(scans[scan_nb]) + '_pynx_previous' + comment, data=data)
        np.savez_compressed(savedir + 'S' + str(scans[scan_nb]) + '_maskpynx_previous', mask=mask)

    else:  # new masking process

        flatfield = pru.load_flatfield(flatfield_file)
        hotpix_array = pru.load_hotpixels(hotpixels_file)

        logfile = pru.create_logfile(setup=setup, detector=detector, scan_number=scans[scan_nb],
                                     root_folder=root_folder, filename=specfile)

        if use_rawdata:
            q_values, data, _, mask, _, frames_logical, monitor = \
                pru.gridmap(logfile=logfile, scan_number=scans[scan_nb], detector=detector, setup=setup,
                            flatfield=flatfield, hotpixels=hotpix_array, hxrd=None, follow_bragg=follow_bragg,
                            normalize=False, debugging=debug, orthogonalize=False)
        else:
            q_values, rawdata, data, _, mask, frames_logical, monitor = \
                pru.gridmap(logfile=logfile, scan_number=scans[scan_nb], detector=detector, setup=setup,
                            flatfield=flatfield, hotpixels=hotpix_array, hxrd=hxrd, follow_bragg=follow_bragg,
                            normalize=False, debugging=debug, orthogonalize=True)

            np.savez_compressed(savedir+'S'+str(scans[scan_nb])+'_data_before_masking_stack', data=rawdata)
            if save_to_mat:
                # save to .mat, the new order is x y z (outboard, vertical up, downstream)
                savemat(savedir+'S'+str(scans[scan_nb])+'_data_before_masking_stack.mat',
                        {'data': np.moveaxis(rawdata, [0, 1, 2], [-1, -2, -3])})
            del rawdata
            gc.collect()

    ##########################################
    # plot normalization by incident monitor #
    ##########################################
    nz, ny, nx = np.shape(data)
    print('Data shape:', nz, ny, nx)
    if normalize_flux:
        plt.ion()
        fig = gu.combined_plots(tuple_array=(monitor, data), tuple_sum_frames=(False, True),
                                tuple_sum_axis=(0, 1), tuple_width_v=None,
                                tuple_width_h=None, tuple_colorbar=(False, False),
                                tuple_vmin=(np.nan, 0), tuple_vmax=(np.nan, np.nan),
                                tuple_title=('monitor.min() / monitor', 'Data after normalization'),
                                tuple_scale=('linear', 'log'), xlabel=('Frame number', 'Frame number'),
                                ylabel=('Counts (a.u.)', 'Rocking dimension'),
                                is_orthogonal=not use_rawdata, reciprocal_space=True)

        fig.savefig(savedir + 'monitor_S' + str(scans[scan_nb]) + '_' + str(nz) + '_' + str(ny) + '_' +
                    str(nx) + '_' + str(binning[0]) + '_' + str(binning[1]) + '_' + str(binning[2]) + '.png')
        if flag_interact:
            cid = plt.connect('close_event', close_event)
            fig.waitforbuttonpress()
            plt.disconnect(cid)
        plt.close(fig)
        plt.ioff()
        comment = comment + '_norm'

    ########################
    # crop/pad/center data #
    ########################
    data, mask, pad_width, q_vector, frames_logical = \
        pru.center_fft(data=data, mask=mask, detector=detector, frames_logical=frames_logical, centering=centering,
                       fft_option=center_fft, pad_size=pad_size, fix_bragg=fix_bragg, fix_size=fix_size,
                       q_values=q_values)

    starting_frame = [pad_width[0], pad_width[2], pad_width[4]]  # no need to check padded frames
    print('Pad width:', pad_width)
    nz, ny, nx = data.shape
    print('Data size after cropping / padding:', nz, ny, nx)

    if mask_zero_event:
        # mask points when there is no intensity along the whole rocking curve - probably dead pixels
        for idx in range(nz):
            temp_mask = mask[idx, :, :]
            temp_mask[np.sum(data, axis=0) == 0] = 1  # enough, numpy array is mutable hence mask will be modified
        del temp_mask

    plt.ioff()

    ##############################
    # save the raw data and mask #
    ##############################
    fig, _, _ = gu.multislices_plot(data, sum_frames=True, scale='log', plot_colorbar=True, vmin=0,
                                    title='Data before aliens removal\n',
                                    is_orthogonal=not use_rawdata, reciprocal_space=True)
    plt.savefig(savedir + 'data_before_masking_sum_S' + str(scans[scan_nb]) + '_' + str(nz) + '_' + str(ny) + '_' +
                str(nx) + '_' + str(binning[0]) + '_' + str(binning[1]) + '_' + str(binning[2]) + '.png')
    if flag_interact:
        cid = plt.connect('close_event', close_event)
        fig.waitforbuttonpress()
        plt.disconnect(cid)
    plt.close(fig)

    piz, piy, pix = np.unravel_index(data.argmax(), data.shape)
    fig = gu.combined_plots((data[piz, :, :], data[:, piy, :], data[:, :, pix]), tuple_sum_frames=False,
                            tuple_sum_axis=0, tuple_width_v=None, tuple_width_h=None, tuple_colorbar=True,
                            tuple_vmin=0, tuple_vmax=np.nan, tuple_scale='log',
                            tuple_title=('data at max in xy', 'data at max in xz', 'data at max in yz'),
                            is_orthogonal=not use_rawdata, reciprocal_space=False)
    plt.savefig(savedir + 'data_before_masking_S' + str(scans[scan_nb]) + '_' + str(nz) + '_' + str(ny) + '_' +
                str(nx) + '_' + str(binning[0]) + '_' + str(binning[1]) + '_' + str(binning[2]) + '.png')
    if flag_interact:
        cid = plt.connect('close_event', close_event)
        fig.waitforbuttonpress()
        plt.disconnect(cid)
    plt.close(fig)

    fig, _, _ = gu.multislices_plot(mask, sum_frames=True, scale='linear', plot_colorbar=True, vmin=0,
                                    vmax=(nz, ny, nx), title='Mask before aliens removal\n',
                                    is_orthogonal=not use_rawdata, reciprocal_space=True)
    plt.savefig(savedir + 'mask_before_masking_S' + str(scans[scan_nb]) + '_' + str(nz) + '_' + str(ny) + '_' +
                str(nx) + '_' + str(binning[0]) + '_' + str(binning[1]) + '_' + str(binning[2]) + '.png')

    if flag_interact:
        cid = plt.connect('close_event', close_event)
        fig.waitforbuttonpress()
        plt.disconnect(cid)
    plt.close(fig)

    ###############################################
    # save the orthogonalized diffraction pattern #
    ###############################################
    if not use_rawdata and len(q_vector) != 0:
        qx = q_vector[0]
        qz = q_vector[1]
        qy = q_vector[2]

        if save_to_vti:
            # save diffraction pattern to vti
            nqx, nqz, nqy = data.shape  # in nexus z downstream, y vertical / in q z vertical, x downstream
            print('dqx, dqy, dqz = ', qx[1] - qx[0], qy[1] - qy[0], qz[1] - qz[0])
            # in nexus z downstream, y vertical / in q z vertical, x downstream
            qx0 = qx.min()
            dqx = (qx.max() - qx0) / nqx
            qy0 = qy.min()
            dqy = (qy.max() - qy0) / nqy
            qz0 = qz.min()
            dqz = (qz.max() - qz0) / nqz

            gu.save_to_vti(filename=os.path.join(savedir, "S"+str(scans[scan_nb])+"_ortho_int"+comment+".vti"),
                           voxel_size=(dqx, dqz, dqy), tuple_array=data, tuple_fieldnames='int', origin=(qx0, qz0, qy0))

    if flag_interact:

        #############################################
        # remove aliens
        #############################################
        nz, ny, nx = np.shape(data)
        width = 5
        max_colorbar = 5
        flag_aliens = True

        # in XY
        dim = 0
        fig_mask = plt.figure()
        fig_mask.canvas.mpl_disconnect(fig_mask.canvas.manager.key_press_handler_id)
        axs = fig_mask.gca()
        idx = starting_frame[0]
        original_data = np.copy(data)
        original_mask = np.copy(mask)
        plt.imshow(data[idx, :, :], vmin=0, vmax=max_colorbar)
        plt.title("XY - Frame " + str(idx+1) + "/" + str(nz) + "\n"
                  "m mask ; b unmask ; q quit ; u next frame ; d previous frame\n"
                  "up larger ; down smaller ; right darker ; left brighter")
        if not use_rawdata:
            axs.invert_yaxis()  # detector Y is vertical down
        plt.connect('key_press_event', press_key)
        fig_mask.set_facecolor(background_plot)
        plt.show()
        del dim, fig_mask, original_data, original_mask
        gc.collect()

        # in XZ
        dim = 1
        fig_mask = plt.figure()
        fig_mask.canvas.mpl_disconnect(fig_mask.canvas.manager.key_press_handler_id)
        idx = starting_frame[1]
        original_data = np.copy(data)
        original_mask = np.copy(mask)
        plt.imshow(data[:, idx, :], vmin=0, vmax=max_colorbar)
        plt.title("XZ - Frame " + str(idx+1) + "/" + str(ny) + "\n"
                  "m mask ; b unmask ; q quit ; u next frame ; d previous frame\n"
                  "up larger ; down smaller ; right darker ; left brighter")
        plt.connect('key_press_event', press_key)
        fig_mask.set_facecolor(background_plot)
        plt.show()
        del dim, fig_mask, original_data, original_mask
        gc.collect()

        # in YZ
        dim = 2
        fig_mask = plt.figure()
        fig_mask.canvas.mpl_disconnect(fig_mask.canvas.manager.key_press_handler_id)
        idx = starting_frame[2]
        original_data = np.copy(data)
        original_mask = np.copy(mask)
        plt.imshow(data[:, :, idx], vmin=0, vmax=max_colorbar)
        plt.title("YZ - Frame " + str(idx+1) + "/" + str(nx) + "\n"
                  "m mask ; b unmask ; q quit ; u next frame ; d previous frame\n"
                  "up larger ; down smaller ; right darker ; left brighter")
        plt.connect('key_press_event', press_key)
        fig_mask.set_facecolor(background_plot)
        plt.show()

        del dim, width, fig_mask, original_data, original_mask
        gc.collect()

        fig, _, _ = gu.multislices_plot(data, sum_frames=True, scale='log', plot_colorbar=True, vmin=0,
                                        title='Data after aliens removal\n',
                                        is_orthogonal=not use_rawdata, reciprocal_space=True)

        if flag_interact:
            cid = plt.connect('close_event', close_event)
            fig.waitforbuttonpress()
            plt.disconnect(cid)
        plt.close(fig)

        fig, _, _ = gu.multislices_plot(mask, sum_frames=True, scale='linear', plot_colorbar=True, vmin=0,
                                        vmax=(nz, ny, nx), title='Mask after aliens removal\n',
                                        is_orthogonal=not use_rawdata, reciprocal_space=True)

        if flag_interact:
            cid = plt.connect('close_event', close_event)
            fig.waitforbuttonpress()
            plt.disconnect(cid)
        plt.close(fig)

        #############################################
        # define mask
        #############################################
        masked_color = 0.1  # will appear as -1 on the plot
        width = 0
        max_colorbar = 5
        flag_aliens = False
        flag_mask = True
        flag_pause = False  # press x to pause for pan/zoom

        nz, ny, nx = np.shape(data)
        original_data = np.copy(data)

        # in XY
        dim = 0
        x, y = np.meshgrid(np.arange(nx), np.arange(ny))
        x, y = x.flatten(), y.flatten()
        points = np.stack((x, y), axis=0).T
        xy = []  # list of points for mask
        temp_mask = np.zeros((ny, nx))
        data[mask == 1] = masked_color / nz  # will appear as -1 on the plot
        print('Select vertices of mask. Press a to restart;p to plot; q to quit.')
        fig_mask = plt.figure()
        fig_mask.canvas.mpl_disconnect(fig_mask.canvas.manager.key_press_handler_id)
        axs = fig_mask.gca()
        plt.imshow(np.log10(abs(data.sum(axis=0))), vmin=0, vmax=max_colorbar)
        plt.title('x to pause/resume masking for pan/zoom \n'
                  'p plot mask ; a restart ; click to select vertices\n'
                  "m mask ; b unmask ; q quit ; u next frame ; d previous frame\n"
                  "up larger ; down smaller ; right darker ; left brighter")
        if not use_rawdata:
            axs.invert_yaxis()  # detector Y is vertical down
        plt.connect('key_press_event', press_key)
        plt.connect('button_press_event', on_click)
        fig_mask.set_facecolor(background_plot)
        plt.show()
        data = np.copy(original_data)

        for idx in range(nz):
            temp_array = mask[idx, :, :]
            temp_array[np.nonzero(temp_mask)] = 1  # enough, numpy array is mutable hence mask will be modified
        del temp_mask
        gc.collect()
        
        # in XZ
        dim = 1
        flag_pause = False  # press x to pause for pan/zoom
        x, y = np.meshgrid(np.arange(nx), np.arange(nz))
        x, y = x.flatten(), y.flatten()
        points = np.stack((x, y), axis=0).T
        xy = []  # list of points for mask
        temp_mask = np.zeros((nz, nx))
        data[mask == 1] = masked_color / ny  # will appear as -1 on the plot
        print('Select vertices of mask. Press a to restart;p to plot; q to quit.')
        fig_mask = plt.figure()
        fig_mask.canvas.mpl_disconnect(fig_mask.canvas.manager.key_press_handler_id)
        plt.imshow(np.log10(abs(data.sum(axis=1))), vmin=0, vmax=max_colorbar)
        plt.title('x to pause/resume masking for pan/zoom \n'
                  'p plot mask ; a restart ; click to select vertices\n'
                  "m mask ; b unmask ; q quit ; u next frame ; d previous frame\n"
                  "up larger ; down smaller ; right darker ; left brighter")
        plt.connect('key_press_event', press_key)
        plt.connect('button_press_event', on_click)
        fig_mask.set_facecolor(background_plot)
        plt.show()
        data = np.copy(original_data)

        for idx in range(ny):
            temp_array = mask[:, idx, :]
            temp_array[np.nonzero(temp_mask)] = 1  # enough, numpy array is mutable hence mask will be modified
        del temp_mask
        gc.collect()

        # in YZ
        dim = 2
        flag_pause = False  # press x to pause for pan/zoom
        x, y = np.meshgrid(np.arange(ny), np.arange(nz))
        x, y = x.flatten(), y.flatten()
        points = np.stack((x, y), axis=0).T
        xy = []  # list of points for mask
        temp_mask = np.zeros((nz, ny))
        data[mask == 1] = masked_color / nx  # will appear as -1 on the plot
        print('Select vertices of mask. Press a to restart;p to plot; q to quit.')
        fig_mask = plt.figure()
        fig_mask.canvas.mpl_disconnect(fig_mask.canvas.manager.key_press_handler_id)
        plt.imshow(np.log10(abs(data.sum(axis=2))), vmin=0, vmax=max_colorbar)
        plt.title('x to pause/resume masking for pan/zoom \n'
                  'p plot mask ; a restart ; click to select vertices\n'
                  "m mask ; b unmask ; q quit ; u next frame ; d previous frame\n"
                  "up larger ; down smaller ; right darker ; left brighter")
        plt.connect('key_press_event', press_key)
        plt.connect('button_press_event', on_click)
        fig_mask.set_facecolor(background_plot)
        plt.show()

        data = original_data

        for idx in range(nx):
            temp_array = mask[:, :, idx]
            temp_array[np.nonzero(temp_mask)] = 1  # enough, numpy array is mutable hence mask will be modified
        del temp_mask, dim, original_data, flag_pause
        gc.collect()

    data[mask == 1] = 0
    flag_mask = False

    #############################################
    # mask or median filter isolated empty pixels
    #############################################
    if flag_medianfilter == 'mask_isolated' or flag_medianfilter == 'interp_isolated':
        print("\nFiltering isolated pixels")
        nb_pix = 0
        for idx in range(pad_width[0], nz-pad_width[1]):  # filter only frames whith data (not padded)
            data[idx, :, :], numb_pix, mask[idx, :, :] = \
                pru.mean_filter(data=data[idx, :, :], nb_neighbours=medfilt_order, mask=mask[idx, :, :],
                                interpolate=flag_medianfilter, min_count=3, debugging=debug)
            nb_pix = nb_pix + numb_pix
            print("Processed image nb: ", idx)
        if flag_medianfilter == 'mask_isolated':
            print("Total number of masked isolated pixels: ", nb_pix)
        if flag_medianfilter == 'interp_isolated':
            print("Total number of interpolated isolated pixels: ", nb_pix)

    elif flag_medianfilter == 'median':  # apply median filter
        for idx in range(pad_width[0], nz-pad_width[1]):  # filter only frames whith data (not padded)
            data[idx, :, :] = scipy.signal.medfilt2d(data[idx, :, :], [3, 3])
        print("Applying median filtering")
    else:
        print("Skipping median filtering")

    #############################################
    # apply photon threshold
    #############################################
    if photon_threshold != 0:
        mask[data < photon_threshold] = 1
        data[data < photon_threshold] = 0
        print("Applying photon threshold < ", photon_threshold)

    #############################################
    # save prepared data and mask
    #############################################
    plt.ion()
    nz, ny, nx = np.shape(data)
    print('Data size after masking:', nz, ny, nx)
    comment = comment + "_" + str(nz) + "_" + str(ny) + "_" + str(nx)  # need these numbers to calculate the voxel size

    # check for Nan
    mask[np.isnan(data)] = 1
    data[np.isnan(data)] = 0
    mask[np.isnan(mask)] = 1
    # check for Inf
    mask[np.isinf(data)] = 1
    data[np.isinf(data)] = 0
    mask[np.isinf(mask)] = 1

    data[mask == 1] = 0

    ###################################
    # plot the prepared data and mask #
    ###################################
    z0, y0, x0 = center_of_mass(data)
    fig, _, _ = gu.multislices_plot(data, sum_frames=False, scale='log', plot_colorbar=True, vmin=0,
                                    title='Masked data', slice_position=[int(z0), int(y0), int(x0)],
                                    is_orthogonal=not use_rawdata, reciprocal_space=True)
    plt.savefig(savedir + 'middle_frame_S' + str(scans[scan_nb]) + '_' + str(nz) + '_' + str(ny) + '_' +
                str(nx) + '_' + str(binning[0]) + '_' + str(binning[1]) + '_' + str(binning[2]) + comment + '.png')
    if not flag_interact:
        plt.close(fig)

    fig, _, _ = gu.multislices_plot(data, sum_frames=True, scale='log', plot_colorbar=True, vmin=0, title='Masked data',
                                    is_orthogonal=not use_rawdata, reciprocal_space=True)
    plt.savefig(savedir + 'sum_S' + str(scans[scan_nb]) + '_' + str(nz) + '_' + str(ny) + '_' +
                str(nx) + '_' + str(binning[0]) + '_' + str(binning[1]) + '_' + str(binning[2]) + comment + '.png')
    if not flag_interact:
        plt.close(fig)

    fig, _, _ = gu.multislices_plot(mask, sum_frames=True, scale='linear', plot_colorbar=True, vmin=0,
                                    vmax=(nz, ny, nx), title='Mask', is_orthogonal=not use_rawdata,
                                    reciprocal_space=True)
    plt.savefig(savedir + 'mask_S' + str(scans[scan_nb]) + '_' + str(nz) + '_' + str(ny) + '_' +
                str(nx) + '_' + str(binning[0]) + '_' + str(binning[1]) + '_' + str(binning[2]) + comment + '.png')
    if not flag_interact:
        plt.close(fig)

    if detector.binning[0] != 1:
        ################################################################################################
        # bin the stacking axis if needed, the detector plane was already binned when loading the data #
        ################################################################################################
        data = pu.bin_data(data, (detector.binning[0], 1, 1), debugging=False)
        mask = pu.bin_data(mask, (detector.binning[0], 1, 1), debugging=False)
        mask[np.nonzero(mask)] = 1
        if not use_rawdata and len(q_vector) != 0:
            qx = qx[::binning[0]]  # along Z

        ############################
        # plot binned data and mask #
        ############################
        nz, ny, nx = data.shape
        print('Data size after binning the stacking dimension:', data.shape)
        comment = comment + "_" + str(nz) + "_" + str(ny) + "_" + str(nx)

        fig, _, _ = gu.multislices_plot(data, sum_frames=True, scale='log', plot_colorbar=True, vmin=0,
                                        title='Final data', is_orthogonal=not use_rawdata,
                                        reciprocal_space=True)
        plt.savefig(savedir + 'finalsum_S' + str(scans[scan_nb]) + '_' + str(nz) + '_' + str(ny) + '_' +
                    str(nx) + '_' + str(binning[0]) + '_' + str(binning[1]) + '_' + str(binning[2]) + comment + '.png')
        if not flag_interact:
            plt.close(fig)

        fig, _, _ = gu.multislices_plot(mask, sum_frames=True, scale='linear', plot_colorbar=True, vmin=0,
                                        vmax=(nz, ny, nx), title='Final mask',
                                        is_orthogonal=not use_rawdata, reciprocal_space=True)
        plt.savefig(savedir + 'finalmask_S' + str(scans[scan_nb]) + '_' + str(nz) + '_' + str(ny) + '_' +
                    str(nx) + '_' + str(binning[0]) + '_' + str(binning[1]) + '_' + str(binning[2]) + comment + '.png')
        if not flag_interact:
            plt.close(fig)

    ############################
    # save final data and mask #
    ############################
    comment = comment + '_' + str(detector.binning[0]) + '_' + str(detector.binning[1]) + '_' + str(detector.binning[2])
    if not use_rawdata and len(q_vector) != 0:
        np.savez_compressed(savedir + 'QxQzQy_S' + str(scans[scan_nb]) + comment,
                            qx=q_vector[0], qz=q_vector[1], qy=q_vector[2])
        if save_to_mat:
            savemat(savedir + 'S' + str(scans[scan_nb]) + '_qx.mat', {'qx': q_vector[0]})
            savemat(savedir + 'S' + str(scans[scan_nb]) + '_qy.mat', {'qy': q_vector[1]})
            savemat(savedir + 'S' + str(scans[scan_nb]) + '_qz.mat', {'qz': q_vector[2]})

        fig, _, _ = gu.contour_slices(data, (q_vector[0], q_vector[1], q_vector[2]), sum_frames=True,
                                      title='Final data', plot_colorbar=True, scale='log', is_orthogonal=True,
                                      levels=np.linspace(0, int(np.log10(data.max())), 150, endpoint=False),
                                      reciprocal_space=True)
        fig.savefig(detector.savedir + 'final_reciprocal_space_S' + str(scans[scan_nb]) + comment + '.png')
        plt.close(fig)

    print('\nsaving to directory:', savedir)
    np.savez_compressed(savedir + 'S' + str(scans[scan_nb]) + '_pynx' + comment, data=data)
    np.savez_compressed(savedir + 'S' + str(scans[scan_nb]) + '_maskpynx' + comment, mask=mask)

    if save_to_mat:
        # save to .mat, the new order is x y z (outboard, vertical up, downstream)
        savemat(savedir + 'S' + str(scans[scan_nb]) + '_data.mat',
                {'data': np.moveaxis(data.astype(np.float32), [0, 1, 2], [-1, -2, -3])})
        savemat(savedir + 'S' + str(scans[scan_nb]) + '_mask.mat',
                {'data': np.moveaxis(mask.astype(np.int8), [0, 1, 2], [-1, -2, -3])})

plt.ioff()
plt.show()
