# -*- coding: utf-8 -*-

# BCDI: tools for pre(post)-processing Bragg coherent X-ray diffraction imaging data
#   (c) 07/2017-06/2019 : CNRS UMR 7344 IM2NP
#       authors:
#         Jerome Carnis, jerome.carnis@esrf.fr

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.path import Path
from scipy.ndimage.measurements import center_of_mass
from scipy.interpolate import RegularGridInterpolator
import xrayutilities as xu
from operator import itemgetter
import fabio
import os
import sys
sys.path.append('D:/myscripts/bcdi/')
import bcdi.graph.graph_utils as gu
import bcdi.postprocessing.postprocessing_utils as pu
from bcdi.utils import image_registration as reg
import bcdi.utils.utilities as util


def align_diffpattern(reference_data, data, mask=None, method='registration', combining_method='rgi'):
    """
    Align two diffraction patterns based on the shift of the center of mass or based on dft registration.

    :param reference_data: the first 3D or 2D diffraction intensity array which will serve as a reference.
    :param data: the 3D or 2D diffraction intensity array to align.
    :param mask: the 3D or 2D mask corresponding to data
    :param method: 'center_of_mass' or 'registration'. For 'registration', see: Opt. Lett. 33, 156-158 (2008).
    :param combining_method: 'rgi' for RegularGridInterpolator or 'subpixel' for subpixel shift
    :return:
     - the shifted data
     - the shifted mask
    """
    if reference_data.ndim == 3:
        nbz, nby, nbx = reference_data.shape
        if reference_data.shape != data.shape:
            raise ValueError('reference_data and data do not have the same shape')

        if method is 'registration':
            shiftz, shifty, shiftx = reg.getimageregistration(abs(reference_data), abs(data), precision=100)
        elif method is 'center_of_mass':
            ref_piz, ref_piy, ref_pix = center_of_mass(abs(reference_data))
            piz, piy, pix = center_of_mass(abs(data))
            shiftz = ref_piz - piz
            shifty = ref_piy - piy
            shiftx = ref_pix - pix
        else:
            raise ValueError("Incorrect value for parameter 'method'")

        print('z shift', str('{:.2f}'.format(shiftz)), ', y shift',
              str('{:.2f}'.format(shifty)), ', x shift', str('{:.2f}'.format(shiftx)))
        if (shiftz == 0) and (shifty == 0) and (shiftx == 0):
            return data, mask

        if combining_method is 'rgi':
            # re-sample data on a new grid based on the shift
            old_z = np.arange(-nbz // 2, nbz // 2)
            old_y = np.arange(-nby // 2, nby // 2)
            old_x = np.arange(-nbx // 2, nbx // 2)
            myz, myy, myx = np.meshgrid(old_z, old_y, old_x, indexing='ij')
            new_z = myz - shiftz
            new_y = myy - shifty
            new_x = myx - shiftx
            del myx, myy, myz
            rgi = RegularGridInterpolator((old_z, old_y, old_x), data, method='linear', bounds_error=False,
                                          fill_value=0)
            data = rgi(np.concatenate((new_z.reshape((1, new_z.size)), new_y.reshape((1, new_z.size)),
                                       new_x.reshape((1, new_z.size)))).transpose())
            data = data.reshape((nbz, nby, nbx)).astype(reference_data.dtype)
            if mask is not None:
                rgi = RegularGridInterpolator((old_z, old_y, old_x), mask, method='linear', bounds_error=False,
                                              fill_value=0)
                mask = rgi(np.concatenate((new_z.reshape((1, new_z.size)), new_y.reshape((1, new_z.size)),
                                           new_x.reshape((1, new_z.size)))).transpose())
                mask = mask.reshape((nbz, nby, nbx)).astype(data.dtype)
                mask = np.rint(mask)  # mask is integer 0 or 1

        elif combining_method is 'subpixel':
            data = abs(reg.subpixel_shift(data, shiftz, shifty, shiftx))  # data is a real number (intensity)
            if mask is not None:
                mask = np.rint(abs(reg.subpixel_shift(mask, shiftz, shifty, shiftx)))  # mask is integer 0 or 1
        else:
            raise ValueError("Incorrect value for parameter 'combining_method'")

    elif reference_data.ndim == 2:
        nby, nbx = reference_data.shape
        if reference_data.shape != data.shape:
            raise ValueError('reference_data and data do not have the same shape')

        if method is 'registration':
            shifty, shiftx = reg.getimageregistration(abs(reference_data), abs(data), precision=100)
        elif method is 'center_of_mass':
            ref_piy, ref_pix = center_of_mass(abs(reference_data))
            piy, pix = center_of_mass(abs(data))
            shifty = ref_piy - piy
            shiftx = ref_pix - pix
        else:
            raise ValueError("Incorrect value for parameter 'method'")

        print('y shift', str('{:.2f}'.format(shifty)), ', x shift', str('{:.2f}'.format(shiftx)))
        if (shifty == 0) and (shiftx == 0):
            return data, mask

        if combining_method is 'rgi':
            # re-sample data on a new grid based on the shift
            old_y = np.arange(-nby // 2, nby // 2)
            old_x = np.arange(-nbx // 2, nbx // 2)
            myy, myx = np.meshgrid(old_y, old_x, indexing='ij')
            new_y = myy - shifty
            new_x = myx - shiftx
            del myx, myy
            rgi = RegularGridInterpolator((old_y, old_x), data, method='linear', bounds_error=False, fill_value=0)
            data = rgi(np.concatenate((new_y.reshape((1, new_y.size)), new_x.reshape((1, new_y.size)))).transpose())
            data = data.reshape((nby, nbx)).astype(reference_data.dtype)
            if mask is not None:
                rgi = RegularGridInterpolator((old_y, old_x), mask, method='linear', bounds_error=False, fill_value=0)
                mask = rgi(np.concatenate((new_y.reshape((1, new_y.size)), new_x.reshape((1, new_y.size)))).transpose())
                mask = mask.reshape((nby, nbx)).astype(data.dtype)
                mask = np.rint(mask)  # mask is integer 0 or 1

        elif combining_method is 'subpixel':
            data = abs(reg.subpixel_shift(data, shifty, shiftx))  # data is a real number (intensity)
            if mask is not None:
                mask = np.rint(abs(reg.subpixel_shift(mask, shifty, shiftx)))  # mask is integer 0 or 1
        else:
            raise ValueError("Incorrect value for parameter 'combining_method'")
    else:
        raise ValueError('Expect 2D or 3D arrays as input')
    return data, mask


def beamstop_correction(data, detector, setup, debugging=False):
    """
    Correct absorption from the beamstops during P10 forward CDI experiment.

    :param data: the 3D stack of 2D CDI images, shape = (nbz, nby, nbx) or 2D image of shape (nby, nbx)
    :param detector: the detector object: Class experiment_utils.Detector()
    :param setup: the experimental setup: Class SetupPreprocessing()
    :param debugging: set to True to see plots
    :return: the corrected data
    """
    energy = setup.energy
    print('Applying beamstop correction for the X-ray energy of {:d}eV'.format(int(energy)))

    if energy not in [8200, 8700, 10000]:
        print('no beam stop information for the X-ray energy of {:d}eV, defaulting to 8700 eV'.format(int(energy)))
        energy = 8700

    ndim = data.ndim
    if ndim == 3:
        pass
    elif ndim == 2:
        data = data[np.newaxis, :, :]
    else:
        raise ValueError('2D or 3D data expected')
    nbz, nby, nbx = data.shape

    directbeam_y = setup.direct_beam[0] - detector.roi[0]  # vertical
    directbeam_x = setup.direct_beam[1] - detector.roi[2]  # horizontal

    # at 8200eV, the transmission of 100um Si is 0.26273
    # at 8700eV, the transmission of 100um Si is 0.32478
    # at 10000eV, the transmission of 100um Si is 0.47337
    if energy == 8200:
        factor_large = 1 / 0.26273  # 5mm*5mm (100um thick) Si wafer
        factor_small = 1 / 0.26273  # 3mm*3mm (100um thick) Si wafer
        pixels_large = [-33, 35, -31, 36]  # boundaries of the large wafer relative to the direct beam (V x H)
        pixels_small = [-14, 14, -11, 16]  # boundaries of the small wafer relative to the direct beam (V x H)
    elif energy == 8700:
        factor_large = 1 / 0.32478  # 5mm*5mm (100um thick) Si wafer
        factor_small = 1 / 0.32478  # 3mm*3mm (100um thick) Si wafer
        pixels_large = [-33, 35, -31, 36]  # boundaries of the large wafer relative to the direct beam (V x H)
        pixels_small = [-14, 14, -11, 16]  # boundaries of the small wafer relative to the direct beam (V x H)
    else:  # 10000 eV
        factor_large = 2.1/0.47337  # 5mm*5mm (200um thick) Si wafer
        factor_small = 4.5/0.47337   # 3mm*3mm (300um thick) Si wafer
        pixels_large = [-36, 34, -34, 35]  # boundaries of the large wafer relative to the direct beam (V x H)
        pixels_small = [-21, 21, -21, 21]  # boundaries of the small wafer relative to the direct beam (V x H)

    # define boolean arrays for the large and the small square beam stops
    large_square = np.zeros((nby, nbx))
    large_square[directbeam_y + pixels_large[0]:directbeam_y + pixels_large[1],
                 directbeam_x + pixels_large[2]:directbeam_x + pixels_large[3]] = 1
    small_square = np.zeros((nby, nbx))
    small_square[directbeam_y + pixels_small[0]:directbeam_y + pixels_small[1],
                 directbeam_x + pixels_small[2]:directbeam_x + pixels_small[3]] = 1

    # define the boolean array for the border of the large square wafer (the border is 1 pixel wide)
    temp_array = np.zeros((nby, nbx))
    temp_array[directbeam_y + pixels_large[0] + 1:directbeam_y + pixels_large[1] - 1,
               directbeam_x + pixels_large[2] + 1:directbeam_x + pixels_large[3] - 1] = 1
    large_border = large_square - temp_array

    # define the boolean array for the border of the small square wafer (the border is 1 pixel wide)
    temp_array = np.zeros((nby, nbx))
    temp_array[directbeam_y + pixels_small[0] + 1:directbeam_y + pixels_small[1] - 1,
               directbeam_x + pixels_small[2] + 1:directbeam_x + pixels_small[3] - 1] = 1
    small_border = small_square - temp_array

    if debugging:
        gu.imshow_plot(data, sum_frames=True, sum_axis=0, vmin=0, vmax=11, plot_colorbar=True, scale='log',
                       title='data before absorption correction', is_orthogonal=False, reciprocal_space=True)

        gu.combined_plots(tuple_array=(large_square, small_square, large_border, small_border),
                          tuple_sum_frames=(False, False, False, False),
                          tuple_sum_axis=0, tuple_width_v=None, tuple_width_h=None, tuple_colorbar=False,
                          tuple_vmin=0, tuple_vmax=11, is_orthogonal=False, reciprocal_space=True,
                          tuple_title=('large_square', 'small_square', 'larger border', 'small border'),
                          tuple_scale=('linear', 'linear', 'linear', 'linear'))

    # absorption correction for the large and small square beam stops
    for idx in range(nbz):
        tempdata = data[idx, :, :]
        tempdata[np.nonzero(large_square)] = tempdata[np.nonzero(large_square)] * factor_large
        tempdata[np.nonzero(small_square)] = tempdata[np.nonzero(small_square)] * factor_small
        data[idx, :, :] = tempdata

    if debugging:
        gu.imshow_plot(data, sum_frames=True, sum_axis=0, vmin=0, vmax=11, plot_colorbar=True, scale='log',
                       title='data after absorption correction', is_orthogonal=False, reciprocal_space=True)

    # interpolation for the border of the large square wafer
    indices = np.argwhere(large_border == 1)
    data[np.nonzero(np.repeat(large_border[np.newaxis, :, :], nbz, axis=0))] = 0  # exclude border points
    for frame in range(nbz):  # loop over 2D images in the detector plane
        tempdata = data[frame, :, :]
        for idx in range(indices.shape[0]):
            pixrow = indices[idx, 0]
            pixcol = indices[idx, 1]
            counter = 9 - large_border[pixrow-1:pixrow+2, pixcol-1:pixcol+2].sum()  # number of pixels in a 3x3 window
            # which do not belong to the border
            tempdata[pixrow, pixcol] = tempdata[pixrow-1:pixrow+2, pixcol-1:pixcol+2].sum() / counter
        data[frame, :, :] = tempdata

    # interpolation for the border of the small square wafer
    indices = np.argwhere(small_border == 1)
    data[np.nonzero(np.repeat(small_border[np.newaxis, :, :], nbz, axis=0))] = 0  # exclude border points
    for frame in range(nbz):  # loop over 2D images in the detector plane
        tempdata = data[frame, :, :]
        for idx in range(indices.shape[0]):
            pixrow = indices[idx, 0]
            pixcol = indices[idx, 1]
            counter = 9 - small_border[pixrow-1:pixrow+2, pixcol-1:pixcol+2].sum()  # number of pixels in a 3x3 window
            # which do not belong to the border
            tempdata[pixrow, pixcol] = tempdata[pixrow-1:pixrow+2, pixcol-1:pixcol+2].sum() / counter
        data[frame, :, :] = tempdata

    if debugging:
        gu.imshow_plot(data, sum_frames=True, sum_axis=0, vmin=0, vmax=11, plot_colorbar=True, scale='log',
                       title='data after interpolating the border of beam stops',
                       is_orthogonal=False, reciprocal_space=True)
    return data


def bin_parameters(binning, nb_frames, params, debugging=True):
    """
    Select parameter values taking into account an eventual binning of the data along the rocking curve axis.

    :param binning: binning factor for the axis corresponding to the rocking curve
    :param nb_frames: number of frames of the rocking curve dimension
    :param params: list of parameters
    :param debugging: set to True to have printed parameters
    :return: parameters of the same length, taking into account binning
    """
    if binning == 1:  # nothing to do
        return params

    if debugging:
        print(params)

    nb_param = len(params)
    print(nb_param, 'motor parameters modified to take into account binning of the rocking curve axis')

    if (binning % 1) != 0:
        raise ValueError('Invalid binning value')
    else:
        for idx in range(len(params)):
            try:
                param_length = len(params[idx])
                if param_length != nb_frames:
                    raise ValueError('parameter ', idx, 'length', param_length, 'different from nb_frames', nb_frames)
            except TypeError:  # int or float
                params[idx] = np.repeat(params[idx], nb_frames)
            temp = params[idx]
            params[idx] = temp[::binning]

    if debugging:
        print(params)

    return params


def cartesian2polar(nb_pixels, pivot, offset_angle, debugging=False):
    """
    Find the corresponding polar coordinates of a cartesian 2D grid perpendicular to the rotation axis.

    :param nb_pixels: number of pixels of the axis of the squared grid
    :param pivot: position in pixels of the origin of the polar coordinates system
    :param offset_angle: reference angle for the angle wrapping
    :param debugging: True to see more plots
    :return: the corresponding 1D array of angular coordinates, 1D array of radial coordinates
    """

    z_interp, x_interp = np.meshgrid(np.linspace(-pivot, -pivot + nb_pixels, num=nb_pixels, endpoint=False),
                                     np.linspace(pivot - nb_pixels, pivot, num=nb_pixels, endpoint=False),
                                     indexing='ij')  # z_interp changes along rows, x_interp along columns
    # z_interp downstream, same direction as detector X rotated by +90deg
    # x_interp along outboard opposite to detector X

    # map these points to (cdi_angle, X), the measurement polar coordinates
    interp_angle = wrap(obj=np.arctan2(z_interp, -x_interp), start_angle=offset_angle * np.pi / 180,
                        range_angle=np.pi)  # in radians, located in the range [start_angle, start_angle+np.pi[

    sign_array = -1 * np.sign(np.cos(interp_angle)) * np.sign(x_interp)
    sign_array[x_interp == 0] = np.sign(z_interp[x_interp == 0]) * np.sign(interp_angle[x_interp == 0])

    interp_radius = np.multiply(sign_array, np.sqrt(x_interp ** 2 + z_interp ** 2))

    if debugging:
        gu.imshow_plot(interp_angle*180/np.pi, plot_colorbar=True, scale='linear',
                       labels=('Qx (z_interp)', 'Qy (x_interp)'), title='calculated polar angle for the 2D grid')

        gu.imshow_plot(sign_array, plot_colorbar=True, scale='linear',
                       labels=('Qx (z_interp)', 'Qy (x_interp)'), title='sign_array')

        gu.imshow_plot(interp_radius, plot_colorbar=True, scale='linear', labels=('Qx (z_interp)', 'Qy (x_interp)'),
                       title='calculated polar radius for the 2D grid')
    return interp_angle, interp_radius


def center_fft(data, mask, detector, frames_logical, centering='max', fft_option='crop_asymmetric_ZYX', **kwargs):
    """
    Center and crop/pad the dataset depending on user parameters

    :param data: the 3D data array
    :param mask: the 3D mask array
    :param detector: the detector object: Class experiment_utils.Detector()
    :param frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
     A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
    :param centering: centering option, 'max' or 'com'. It will be overridden if the kwarg 'fix_bragg' is provided.
    :param fft_option:
     - 'crop_sym_ZYX': crop the array for FFT requirements, Bragg peak centered
     - 'crop_asym_ZYX': crop the array for FFT requirements without centering the Brag peak
     - 'pad_sym_Z_crop_sym_YX': crop detector images (Bragg peak centered) and pad the rocking angle based on
       'pad_size' (Bragg peak centered)
     - 'pad_sym_Z_crop_asym_YX': pad rocking angle based on 'pad_size' (Bragg peak centered) and crop detector
       (Bragg peak non-centered)
     - 'pad_asym_Z_crop_sym_YX': crop detector images (Bragg peak centered), pad the rocking angle
       without centering the Brag peak
     - 'pad_asym_Z_crop_asym_YX': pad rocking angle and crop detector without centering the Bragg peak
     - 'pad_sym_Z': keep detector size and pad/center the rocking angle based on 'pad_size', Bragg peak centered
     - 'pad_asym_Z': keep detector size and pad the rocking angle without centering the Brag peak
     - 'pad_sym_ZYX': pad all dimensions based on 'pad_size', Brag peak centered
     - 'pad_asym_ZYX': pad all dimensions based on 'pad_size' without centering the Brag peak
     - 'skip': keep the full dataset or crop it to the size defined by fix_size
    :param kwargs:
     - 'fix_bragg' = user-defined position in pixels of the Bragg peak [z_bragg, y_bragg, x_bragg]
     - 'fix_size' = user defined output array size [zstart, zstop, ystart, ystop, xstart, xstop]
     - 'pad_size' = user defined output array size [nbz, nby, nbx]
     - 'q_values' = [qx, qz, qy], each component being a 1D array
    :return:
     - updated data, mask (and q_values if provided, [] otherwise)
     - pad_width = [z0, z1, y0, y1, x0, x1] number of pixels added at each end of the original data
     - updated frames_logical
    """
    if data.ndim != 3 or mask.ndim != 3:
        raise ValueError('data and mask should be 3D arrays')

    if data.shape != mask.shape:
        raise ValueError('Data and mask must have the same shape\n data is ', data.shape, ' while mask is ', mask.shape)

    for k in kwargs.keys():
        if k in ['fix_bragg']:
            fix_bragg = kwargs['fix_bragg']
        elif k in ['fix_size']:
            fix_size = kwargs['fix_size']
        elif k in ['pad_size']:
            pad_size = kwargs['pad_size']
        elif k in ['q_values']:
            q_values = kwargs['q_values']
        else:
            raise Exception("unknown keyword argument given: allowed is"
                            "'fix_bragg', 'fix_size', 'pad_size' and 'q_values'")
    try:
        fix_bragg
    except NameError:  # fix_bragg not declared
        fix_bragg = []
    try:
        fix_size
    except NameError:  # fix_size not declared
        fix_size = []
    try:
        pad_size
    except NameError:  # pad_size not declared
        pad_size = []
    try:
        q_values
        qx = q_values[0]  # axis=0, z downstream, qx in reciprocal space
        qz = q_values[1]  # axis=1, y vertical, qz in reciprocal space
        qy = q_values[2]  # axis=2, x outboard, qy in reciprocal space
    except NameError:  # q_values not declared
        q_values = []
        qx = []
        qy = []
        qz = []
    except IndexError:  # q_values empty
        q_values = []
        qx = []
        qy = []
        qz = []

    if centering == 'max':
        z0, y0, x0 = np.unravel_index(abs(data).argmax(), data.shape)
        print("Max at (qx, qz, qy): ", z0, y0, x0)
    elif centering == 'com':
        z0, y0, x0 = center_of_mass(data)
        print("Center of mass at (qx, qz, qy): ", z0, y0, x0)
    else:
        raise ValueError("Incorrect value for 'centering' parameter")

    if len(fix_bragg) != 0:
        if len(fix_bragg) != 3:
            raise ValueError('fix_bragg should be a list of 3 integers')
        z0, y0, x0 = fix_bragg
        print("Peak intensity position defined by user on the full detector: ", z0, y0, x0)
        y0 = (y0 - detector.roi[0]) / detector.binning[1]
        x0 = (x0 - detector.roi[2]) / detector.binning[2]
        print("Peak intensity position after considering detector ROI and binning in detector plane: ", z0, y0, x0)

    iz0, iy0, ix0 = int(round(z0)), int(round(y0)), int(round(x0))
    print('Data peak value = ', data[iz0, iy0, ix0])

    # Max symmetrical box around center of mass
    nbz, nby, nbx = np.shape(data)
    max_nz = abs(2 * min(iz0, nbz - iz0))
    max_ny = 2 * min(iy0, nby - iy0)
    max_nx = abs(2 * min(ix0, nbx - ix0))
    if fft_option != 'skip':
        print("Max symmetrical box (qx, qz, qy): ", max_nz, max_ny, max_nx)
    if max_nz == 0 or max_ny == 0 or max_nx == 0:
        print('Empty images or presence of hotpixel at the border, defaulting fft_option to "skip"!')
        fft_option = 'skip'

    # Crop/pad data to fulfill FFT size and user requirements
    if fft_option == 'crop_sym_ZYX':
        # crop rocking angle and detector, Bragg peak centered
        nz1, ny1, nx1 = smaller_primes((max_nz, max_ny, max_nx), maxprime=7, required_dividers=(2,))
        pad_width = np.zeros(6, dtype=int)

        data = data[iz0 - nz1 // 2:iz0 + nz1//2, iy0 - ny1//2:iy0 + ny1//2, ix0 - nx1//2:ix0 + nx1//2]
        mask = mask[iz0 - nz1 // 2:iz0 + nz1//2, iy0 - ny1//2:iy0 + ny1//2, ix0 - nx1//2:ix0 + nx1//2]
        print("FFT box (qx, qz, qy): ", data.shape)

        if (iz0 - nz1//2) > 0:  # if 0, the first frame is used
            frames_logical[0:iz0 - nz1 // 2] = 0
        if (iz0 + nz1 // 2) < nbz:  # if nbz, the last frame is used
            frames_logical[iz0 + nz1 // 2:] = 0

        if len(q_values) != 0:
            qx = qx[iz0 - nz1//2:iz0 + nz1//2]
            qy = qy[ix0 - nx1//2:ix0 + nx1//2]
            qz = qz[iy0 - ny1//2:iy0 + ny1//2]

    elif fft_option == 'crop_asym_ZYX':
        # crop rocking angle and detector without centering the Bragg peak
        nz1, ny1, nx1 = smaller_primes((nbz, nby, nbx), maxprime=7, required_dividers=(2,))
        pad_width = np.zeros(6, dtype=int)

        data = data[nbz//2 - nz1//2:nbz//2 + nz1//2, nby//2 - ny1//2:nby//2 + ny1//2,
                    nbx//2 - nx1//2:nbx//2 + nx1//2]
        mask = mask[nbz//2 - nz1//2:nbz//2 + nz1//2, nby//2 - ny1//2:nby//2 + ny1//2,
                    nbx//2 - nx1//2:nbx//2 + nx1//2]
        print("FFT box (qx, qz, qy): ", data.shape)

        if (nbz//2 - nz1//2) > 0:  # if 0, the first frame is used
            frames_logical[0:nbz//2 - nz1//2] = 0
        if (nbz//2 + nz1//2) < nbz:  # if nbz, the last frame is used
            frames_logical[nbz//2 + nz1 // 2:] = 0

        if len(q_values) != 0:
            qx = qx[nbz//2 - nz1//2:nbz//2 + nz1//2]
            qy = qy[nbx//2 - nx1//2:nbx//2 + nx1//2]
            qz = qz[nby//2 - ny1//2:nby//2 + ny1//2]

    elif fft_option == 'pad_sym_Z_crop_sym_YX':
        # pad rocking angle based on 'pad_size' (Bragg peak centered) and crop detector (Bragg peak centered)
        if len(pad_size) != 3:
            raise ValueError('pad_size should be a list of three elements')
        if pad_size[0] != higher_primes(pad_size[0], maxprime=7, required_dividers=(2,)):
            raise ValueError(pad_size[0], 'does not meet FFT requirements')
        ny1, nx1 = smaller_primes((max_ny, max_nx), maxprime=7, required_dividers=(2,))

        data = data[:, iy0 - ny1//2:iy0 + ny1//2, ix0 - nx1//2:ix0 + nx1//2]
        mask = mask[:, iy0 - ny1//2:iy0 + ny1//2, ix0 - nx1//2:ix0 + nx1//2]
        pad_width = np.array([int(min(pad_size[0]/2-iz0, pad_size[0]-nbz)),
                              int(min(pad_size[0]/2-nbz + iz0, pad_size[0]-nbz)),
                              0, 0, 0, 0], dtype=int)
        data = zero_pad(data, padding_width=pad_width, mask_flag=False)
        mask = zero_pad(mask, padding_width=pad_width, mask_flag=True)  # mask padded pixels
        print("FFT box (qx, qz, qy): ", data.shape)

        temp_frames = -1 * np.ones(data.shape[0])
        temp_frames[pad_width[0]:pad_width[0] + nbz] = frames_logical
        frames_logical = temp_frames

        if len(q_values) != 0:
            dqx = qx[1] - qx[0]
            qx0 = qx[0] - pad_width[0] * dqx
            qx = qx0 + np.arange(pad_size[0])*dqx
            qy = qy[ix0 - nx1 // 2:ix0 + nx1 // 2]
            qz = qz[iy0 - ny1 // 2:iy0 + ny1 // 2]

    elif fft_option == 'pad_sym_Z_crop_asym_YX':
        # pad rocking angle based on 'pad_size' (Bragg peak centered) and crop detector (Bragg peak non-centered)
        if len(pad_size) != 3:
            raise ValueError('pad_size should be a list of three elements')
        print("pad_size for 1st axis before binning: ", pad_size[0])
        if pad_size[0] != higher_primes(pad_size[0], maxprime=7, required_dividers=(2,)):
            raise ValueError(pad_size[0], 'does not meet FFT requirements')
        ny1, nx1 = smaller_primes((max_ny, max_nx), maxprime=7, required_dividers=(2,))

        data = data[:, nby//2 - ny1//2:nby//2 + ny1//2, nbx//2 - nx1//2:nbx//2 + nx1//2]
        mask = mask[:, nby//2 - ny1//2:nby//2 + ny1//2, nbx//2 - nx1//2:nbx//2 + nx1//2]
        pad_width = np.array([int(min(pad_size[0]/2-iz0, pad_size[0]-nbz)),
                              int(min(pad_size[0]/2-nbz + iz0, pad_size[0]-nbz)),
                              0, 0, 0, 0], dtype=int)
        data = zero_pad(data, padding_width=pad_width, mask_flag=False)
        mask = zero_pad(mask, padding_width=pad_width, mask_flag=True)  # mask padded pixels
        print("FFT box (qx, qz, qy): ", data.shape)

        temp_frames = -1 * np.ones(data.shape[0])
        temp_frames[pad_width[0]:pad_width[0] + nbz] = frames_logical
        frames_logical = temp_frames

        if len(q_values) != 0:
            dqx = qx[1] - qx[0]
            qx0 = qx[0] - pad_width[0] * dqx
            qx = qx0 + np.arange(pad_size[0])*dqx
            qy = qy[nbx//2 - nx1//2:nbx//2 + nx1//2]
            qz = qz[nby//2 - ny1//2:nby//2 + ny1//2]

    elif fft_option == 'pad_asym_Z_crop_sym_YX':
        # pad rocking angle without centering the Bragg peak and crop detector (Bragg peak centered)
        ny1, nx1 = smaller_primes((max_ny, max_nx), maxprime=7, required_dividers=(2,))
        nz1 = higher_primes(nbz, maxprime=7, required_dividers=(2,))

        data = data[:, iy0 - ny1//2:iy0 + ny1//2, ix0 - nx1//2:ix0 + nx1//2]
        mask = mask[:, iy0 - ny1//2:iy0 + ny1//2, ix0 - nx1//2:ix0 + nx1//2]
        pad_width = np.array([int((nz1 - nbz + ((nz1 - nbz) % 2)) / 2), int((nz1 - nbz + 1) / 2 - ((nz1 - nbz) % 2)),
                              0, 0, 0, 0], dtype=int)
        data = zero_pad(data, padding_width=pad_width, mask_flag=False)
        mask = zero_pad(mask, padding_width=pad_width, mask_flag=True)  # mask padded pixels
        print("FFT box (qx, qz, qy): ", data.shape)

        temp_frames = -1 * np.ones(data.shape[0])
        temp_frames[pad_width[0]:pad_width[0] + nbz] = frames_logical
        frames_logical = temp_frames

        if len(q_values) != 0:
            dqx = qx[1] - qx[0]
            qx0 = qx[0] - pad_width[0] * dqx
            qx = qx0 + np.arange(nz1)*dqx
            qy = qy[ix0 - nx1 // 2:ix0 + nx1 // 2]
            qz = qz[iy0 - ny1 // 2:iy0 + ny1 // 2]

    elif fft_option == 'pad_asym_Z_crop_asym_YX':
        # pad rocking angle and crop detector without centering the Bragg peak
        ny1, nx1 = smaller_primes((nby, nbx), maxprime=7, required_dividers=(2,))
        nz1 = higher_primes(nbz, maxprime=7, required_dividers=(2,))

        data = data[:, nby//2 - ny1//2:nby//2 + ny1//2, nbx//2 - nx1//2:nbx//2 + nx1//2]
        mask = mask[:, nby//2 - ny1//2:nby//2 + ny1//2, nbx//2 - nx1//2:nbx//2 + nx1//2]
        pad_width = np.array([int((nz1 - nbz + ((nz1 - nbz) % 2)) / 2), int((nz1 - nbz + 1) / 2 - ((nz1 - nbz) % 2)),
                              0, 0, 0, 0], dtype=int)
        data = zero_pad(data, padding_width=pad_width, mask_flag=False)
        mask = zero_pad(mask, padding_width=pad_width, mask_flag=True)  # mask padded pixels
        print("FFT box (qx, qz, qy): ", data.shape)

        temp_frames = -1 * np.ones(data.shape[0])
        temp_frames[pad_width[0]:pad_width[0] + nbz] = frames_logical
        frames_logical = temp_frames

        if len(q_values) != 0:
            dqx = qx[1] - qx[0]
            qx0 = qx[0] - pad_width[0] * dqx
            qx = qx0 + np.arange(nz1)*dqx
            qy = qy[nbx//2 - nx1//2:nbx//2 + nx1//2]
            qz = qz[nby//2 - ny1//2:nby//2 + ny1//2]

    elif fft_option == 'pad_sym_Z':
        # pad rocking angle based on 'pad_size'(Bragg peak centered) and keep detector size
        if len(pad_size) != 3:
            raise ValueError('pad_size should be a list of three elements')
        print("pad_size for 1st axis before binning: ", pad_size[0])
        if pad_size[0] != higher_primes(pad_size[0], maxprime=7, required_dividers=(2,)):
            raise ValueError(pad_size[0], 'does not meet FFT requirements')

        pad_width = np.array([int(min(pad_size[0]/2-iz0, pad_size[0]-nbz)),
                              int(min(pad_size[0]/2-nbz + iz0, pad_size[0]-nbz)),
                              0, 0, 0, 0], dtype=int)
        data = zero_pad(data, padding_width=pad_width, mask_flag=False)
        mask = zero_pad(mask, padding_width=pad_width, mask_flag=True)  # mask padded pixels
        print("FFT box (qx, qz, qy): ", data.shape)

        temp_frames = -1 * np.ones(data.shape[0])
        temp_frames[pad_width[0]:pad_width[0] + nbz] = frames_logical
        frames_logical = temp_frames

        if len(q_values) != 0:
            dqx = qx[1] - qx[0]
            qx0 = qx[0] - pad_width[0] * dqx
            qx = qx0 + np.arange(pad_size[0])*dqx

    elif fft_option == 'pad_asym_Z':
        # pad rocking angle without centering the Bragg peak, keep detector size
        nz1 = higher_primes(nbz, maxprime=7, required_dividers=(2,))

        pad_width = np.array([int((nz1-nbz+((nz1-nbz) % 2))/2), int((nz1-nbz+1)/2-((nz1-nbz) % 2)),
                              0, 0, 0, 0], dtype=int)
        data = zero_pad(data, padding_width=pad_width, mask_flag=False)
        mask = zero_pad(mask, padding_width=pad_width, mask_flag=True)  # mask padded pixels
        print("FFT box (qx, qz, qy): ", data.shape)

        temp_frames = -1 * np.ones(data.shape[0])
        temp_frames[pad_width[0]:pad_width[0] + nbz] = frames_logical
        frames_logical = temp_frames

        if len(q_values) != 0:
            dqx = qx[1] - qx[0]
            qx0 = qx[0] - pad_width[0] * dqx
            qx = qx0 + np.arange(nz1)*dqx

    elif fft_option == 'pad_sym_ZYX':
        # pad both dimensions based on 'pad_size' (Bragg peak centered)
        if len(pad_size) != 3:
            raise ValueError('pad_size should be a list of 3 integers')
        print("pad_size: ", pad_size)
        print("The 1st axis (stacking dimension) is padded before binning, detector plane after binning.")
        if pad_size[0] != higher_primes(pad_size[0], maxprime=7, required_dividers=(2,)):
            raise ValueError(pad_size[0], 'does not meet FFT requirements')
        if pad_size[1] != higher_primes(pad_size[1], maxprime=7, required_dividers=(2,)):
            raise ValueError(pad_size[1], 'does not meet FFT requirements')
        if pad_size[2] != higher_primes(pad_size[2], maxprime=7, required_dividers=(2,)):
            raise ValueError(pad_size[2], 'does not meet FFT requirements')

        pad_width = [int(min(pad_size[0]/2-iz0, pad_size[0]-nbz)), int(min(pad_size[0]/2-nbz + iz0, pad_size[0]-nbz)),
                     int(min(pad_size[1]/2-iy0, pad_size[1]-nby)), int(min(pad_size[1]/2-nby + iy0, pad_size[1]-nby)),
                     int(min(pad_size[2]/2-ix0, pad_size[2]-nbx)), int(min(pad_size[2]/2-nbx + ix0, pad_size[2]-nbx))]
        pad_width = np.array(list((map(lambda value: max(value, 0), pad_width))), dtype=int)  # remove negative numbers
        data = zero_pad(data, padding_width=pad_width, mask_flag=False)
        mask = zero_pad(mask, padding_width=pad_width, mask_flag=True)  # mask padded pixels
        print("FFT box (qx, qz, qy): ", data.shape)

        temp_frames = -1 * np.ones(data.shape[0])
        temp_frames[pad_width[0]:pad_width[0] + nbz] = frames_logical
        frames_logical = temp_frames

        if len(q_values) != 0:
            dqx = qx[1] - qx[0]
            dqy = qy[1] - qy[0]
            dqz = qz[1] - qz[0]
            qx0 = qx[0] - pad_width[0] * dqx
            qy0 = qy[0] - pad_width[2] * dqy
            qz0 = qz[0] - pad_width[1] * dqz
            qx = qx0 + np.arange(pad_size[0]) * dqx
            qy = qy0 + np.arange(pad_size[2]) * dqy
            qz = qz0 + np.arange(pad_size[1]) * dqz

    elif fft_option == 'pad_asym_ZYX':
        # pad both dimensions without centering the Bragg peak
        nz1, ny1, nx1 = [higher_primes(nbz, maxprime=7, required_dividers=(2,)),
                         higher_primes(nby, maxprime=7, required_dividers=(2,)),
                         higher_primes(nbx, maxprime=7, required_dividers=(2,))]

        pad_width = np.array(
            [int((nz1-nbz+((nz1-nbz) % 2))/2), int((nz1-nbz+1)/2-((nz1-nbz) % 2)),
             int((ny1-nby+((pad_size[1]-nby) % 2))/2), int((ny1-nby+1)/2-((ny1-nby) % 2)),
             int((nx1-nbx+((nx1-nbx) % 2))/2), int((nx1-nbx+1)/2-((nx1-nbx) % 2))])
        data = zero_pad(data, padding_width=pad_width, mask_flag=False)
        mask = zero_pad(mask, padding_width=pad_width, mask_flag=True)  # mask padded pixels

        temp_frames = -1 * np.ones(data.shape[0])
        temp_frames[pad_width[0]:pad_width[0] + nbz] = frames_logical
        frames_logical = temp_frames

        if len(q_values) != 0:
            dqx = qx[1] - qx[0]
            dqy = qy[1] - qy[0]
            dqz = qz[1] - qz[0]
            qx0 = qx[0] - pad_width[0] * dqx
            qy0 = qy[0] - pad_width[2] * dqy
            qz0 = qz[0] - pad_width[1] * dqz
            qx = qx0 + np.arange(nz1) * dqx
            qy = qy0 + np.arange(nx1) * dqy
            qz = qz0 + np.arange(ny1) * dqz

    elif fft_option == 'skip':
        # keep the full dataset or use 'fix_size' parameter
        pad_width = np.zeros(6, dtype=int)  # do nothing or crop the data, starting_frame should be 0
        if len(fix_size) == 6:
            # take binning into account
            print("fix_size defined by user on the full detector: ", z0, y0, x0)
            fix_size[2] = fix_size[2] / detector.binning[1]
            fix_size[3] = fix_size[3] / detector.binning[1]
            fix_size[4] = fix_size[4] / detector.binning[2]
            fix_size[5] = fix_size[5] / detector.binning[2]
            print("fix_size defined after considering binning in detector plane (no ROI): ", z0, y0, x0)
            # size of output array defined
            nbz, nby, nbx = np.shape(data)
            z_pan = fix_size[1] - fix_size[0]
            y_pan = fix_size[3] - fix_size[2]
            x_pan = fix_size[5] - fix_size[4]
            if z_pan > nbz or y_pan > nby or x_pan > nbx or fix_size[1] > nbz or fix_size[3] > nby or fix_size[5] > nbx:
                raise ValueError("Predefined fix_size uncorrect")
            else:
                data = data[fix_size[0]:fix_size[1], fix_size[2]:fix_size[3], fix_size[4]:fix_size[5]]
                mask = mask[fix_size[0]:fix_size[1], fix_size[2]:fix_size[3], fix_size[4]:fix_size[5]]

                if fix_size[0] > 0:  # if 0, the first frame is used
                    frames_logical[0:fix_size[0]] = 0
                if fix_size[1] < nbz:  # if nbz, the last frame is used
                    frames_logical[fix_size[1]:] = 0

                if len(q_values) != 0:
                    qx = qx[fix_size[0]:fix_size[1]]
                    qy = qy[fix_size[4]:fix_size[5]]
                    qz = qz[fix_size[2]:fix_size[3]]
    else:
        raise ValueError("Incorrect value for 'fft_option'")

    if len(q_values) != 0:
        q_values[0] = qx
        q_values[1] = qz
        q_values[2] = qy
    return data, mask, pad_width, q_values, frames_logical


def check_cdi_angle(data, mask, cdi_angle, frames_logical, debugging=False):
    """
    In forward CDI experiment, check if there is no overlap in the measurement angles, crop it otherwise. Flip the
    rotation direction to convert sample angles into detector angles.
     Update data, mask and frames_logical accordingly.

    :param data: 3D forward CDI dataset before gridding.
    :param mask: 3D mask
    :param cdi_angle: array of measurement sample angles in degrees
    :param frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
     A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
    :param debugging: True to have more printed comments
    :return: updated data, mask, detector cdi_angle, frames_logical
    """
    angular_step = cdi_angle[1]-cdi_angle[0]
    detector_angle = cdi_angle[0] - angular_step * np.arange(len(cdi_angle))  # flip the rotation axis in order to
    # compensate the rotation of the Ewald sphere due to sample rotation
    print('Reverse the rotation direction to compensate the rotation of the Ewald sphere')

    wrap_angle = wrap(obj=detector_angle, start_angle=detector_angle.min(), range_angle=180)
    for idx in range(len(wrap_angle)):
        duplicate = (wrap_angle[:idx] == wrap_angle[idx]).sum()  # will be different from 0 if duplicated
        frames_logical[idx] = frames_logical[idx] * (duplicate == 0)  # set frames_logical to 0 if duplicated angle

    if debugging:
        print('frames_logical after checking duplicated angles:\n', frames_logical)

    # find first duplicated angle
    try:
        index_duplicated = np.where(frames_logical == 0)[0][0]
        # change the angle by a negligeable amount to still be able to use it for interpolation
        if angular_step > 0:
            detector_angle[index_duplicated] = detector_angle[index_duplicated] - 0.0001
        else:
            detector_angle[index_duplicated] = detector_angle[index_duplicated] + 0.0001
        print('RegularGridInterpolator cannot take dupicated values: shifting frame', index_duplicated,
              'by 1/10000 degrees for the interpolation')

        frames_logical[index_duplicated] = 1
    except IndexError:  # no duplicated angle
        print('no duplicated angle')

    data = data[np.nonzero(frames_logical)[0], :, :]
    mask = mask[np.nonzero(frames_logical)[0], :, :]
    detector_angle = detector_angle[np.nonzero(frames_logical)]
    return data, mask, detector_angle, frames_logical


def check_pixels(data, mask, debugging=False):
    """
    Check for hot pixels in the data using the mean value and the variance.

    :param data: 3D diffraction data
    :param mask: 2D or 3D mask. Mask will summed along the first axis if a 3D array.
    :param debugging: set to True to see plots
    :type debugging: bool
    :return: the filtered 3D data and the updated 2D mask.
    """
    if data.ndim != 3:
        raise ValueError('Data should be a 3D array')

    nbz, nby, nbx = data.shape

    if mask.ndim == 3:  # 3D array
        print("Mask is a 3D array, summing it along axis 0")
        mask = mask.sum(axis=0)
        mask[np.nonzero(mask)] = 1

    if data[0, :, :].shape != mask.shape:
        raise ValueError('Data and mask must have the same shape\n data slice is ',
                         data[0, :, :].shape, ' while mask is ', mask.shape)

    meandata = data.mean(axis=0)  # 2D
    vardata = 1 / data.var(axis=0)  # 2D
    var_mean = vardata[vardata != np.inf].mean()
    vardata[meandata == 0] = var_mean  # pixels were data=0 (hence 1/variance=inf) are set to the mean of 1/var
    # we do not want to mask pixels where there was trully no intensity during the scan
    if debugging:
        gu.combined_plots(tuple_array=(meandata, vardata), tuple_sum_frames=(False, False), tuple_sum_axis=(0, 0),
                          tuple_width_v=(None, None), tuple_width_h=(None, None), tuple_colorbar=(True, True),
                          tuple_vmin=(0, 0), tuple_vmax=(1, np.nan), tuple_scale=('linear', 'linear'),
                          tuple_title=('mean(data) before masking', '1/var(data) before masking'),
                          reciprocal_space=True)
    # calculate the mean and 1/variance for a single photon event along the rocking curve
    min_count = 0.99  # pixels with only 1 photon count along the rocking curve.

    mean_threshold = min_count / nbz
    var_threshold = ((nbz - 1) * mean_threshold ** 2 + (min_count - mean_threshold) ** 2) * 1 / nbz

    temp_mask = np.zeros((nby, nbx))
    temp_mask[vardata == np.inf] = 1  # this includes hotpixels since zero intensity pixels were set to var_mean

    vardata[vardata == np.inf] = 0
    indices_badpixels = np.nonzero(vardata > 1 / var_threshold)
    mask[indices_badpixels] = 1  # mask is 2D
    mask[np.nonzero(temp_mask)] = 1  # update mask

    indices_badpixels = np.nonzero(mask)  # update indices
    for index in range(nbz):
        tempdata = data[index, :, :]
        tempdata[indices_badpixels] = 0  # numpy array is mutable hence data will be modified

    if debugging:
        meandata = data.mean(axis=0)
        vardata = 1 / data.var(axis=0)
        gu.combined_plots(tuple_array=(meandata, vardata), tuple_sum_frames=(False, False), tuple_sum_axis=(0, 0),
                          tuple_width_v=(None, None), tuple_width_h=(None, None), tuple_colorbar=(True, True),
                          tuple_vmin=(0, 0), tuple_vmax=(1, np.nan), tuple_scale=('linear', 'linear'),
                          tuple_title=('mean(data) after masking', '1/var(data) after masking'), reciprocal_space=True)
    print("check_pixels():", str(indices_badpixels[0].shape[0]), "badpixels were masked on a total of", str(nbx * nby))
    return data, mask


def create_logfile(setup, detector, scan_number, root_folder, filename):
    """
    Create the logfile used in gridmap().

    :param setup: the experimental setup: Class SetupPreprocessing()
    :param detector: the detector object: Class experiment_utils.Detector()
    :param scan_number: the scan number to load
    :param root_folder: the root directory of the experiment, where is the specfile/.fio file
    :param filename: the file name to load, or the path of 'alias_dict.txt' for SIXS
    :return: logfile
    """
    if setup.custom_scan:  # no log file in that case
        logfile = ''
        
    elif setup.beamline == 'CRISTAL':  # no specfile, load directly the dataset
        import h5py
        ccdfiletmp = os.path.join(detector.datadir + detector.template_imagefile % scan_number)
        logfile = h5py.File(ccdfiletmp, 'r')

    elif setup.beamline == 'P10':  # load .fio file
        logfile = root_folder + filename + '/' + filename + '.fio'

    elif setup.beamline == 'SIXS_2018':  # no specfile, load directly the dataset
        import bcdi.preprocessing.nxsReady as nxsReady

        logfile = nxsReady.DataSet(longname=detector.datadir + detector.template_imagefile % scan_number,
                                   shortname=detector.template_imagefile % scan_number, alias_dict=filename,
                                   scan="SBS")
    elif setup.beamline == 'SIXS_2019':  # no specfile, load directly the dataset
        import bcdi.preprocessing.ReadNxs3 as ReadNxs3

        logfile = ReadNxs3.DataSet(directory=detector.datadir, filename=detector.template_imagefile % scan_number,
                                   alias_dict=filename)

    elif setup.beamline == 'ID01':  # load spec file
        from silx.io.specfile import SpecFile
        logfile = SpecFile(root_folder + filename + '.spec')
        
    elif setup.beamline == 'NANOMAX':
        import hdf5plugin
        import h5py
        ccdfiletmp = os.path.join(detector.datadir + ('%06d.h5') % scan_number)
        logfile = h5py.File(ccdfiletmp, 'r')
        
    else:
        raise ValueError('Incorrect value for beamline parameter')

    return logfile


def ewald_curvature_saxs(cdi_angle, detector, setup, anticlockwise=True):
    """
    Correct the data for the curvature of Ewald sphere. Based on the CXI detector geometry convention:
     Laboratory frame: z downstream, y vertical up, x outboard
     Detector axes: Y vertical and X horizontal
     (detector Y is vertical down at out-of-plane angle=0, detector X is opposite to x at inplane angle=0)

    :param cdi_angle: 1D array of measurement angles in degrees
    :param detector: the detector object: Class experiment_utils.Detector()
    :param setup: the experimental setup: Class SetupPreprocessing()
    :param anticlockwise: True if the rotation is anticlockwise
    :return: qx, qz, qy values in the laboratory frame (downstream, vertical up, outboard).
     Each array has the shape: nb_pixel_x * nb_pixel_y * nb_angles
    """
    wavelength = setup.wavelength * 1e9  # convert to nm
    kin = np.asarray(setup.beam_direction)  # (1, 0 , 0) by default
    directbeam_y = (setup.direct_beam[0] - detector.roi[0]) / detector.binning[1]  # vertical
    directbeam_x = (setup.direct_beam[1] - detector.roi[2]) / detector.binning[2]  # horizontal
    nbz = len(cdi_angle)
    nby = int((detector.roi[1] - detector.roi[0]) / detector.binning[1])
    nbx = int((detector.roi[3] - detector.roi[2]) / detector.binning[2])
    pixelsize_x = detector.pixelsize_x * 1e9  # in nm, pixel size in the horizontal direction
    distance = setup.distance * 1e9  # in nm
    qz = np.zeros((nbz, nby, nbx))
    qy = np.zeros((nbz, nby, nbx))
    qx = np.zeros((nbz, nby, nbx))

    # calculate q values of the detector frame for each angular position and stack them
    for idx in range(len(cdi_angle)):
        angle = cdi_angle[idx] * np.pi / 180
        if not anticlockwise:
            rotation_matrix = np.array([[np.cos(angle), 0, -np.sin(angle)],
                                        [0, 1, 0],
                                        [np.sin(angle), 0, np.cos(angle)]])
        else:
            rotation_matrix = np.array([[np.cos(angle), 0, np.sin(angle)],
                                        [0, 1, 0],
                                        [-np.sin(angle), 0, np.cos(angle)]])

        myy, myx = np.meshgrid(np.linspace(-directbeam_y, -directbeam_y + nby, num=nby, endpoint=False),
                               np.linspace(-directbeam_x, -directbeam_x + nbx, num=nbx, endpoint=False),
                               indexing='ij')

        two_theta = np.arctan(myx * pixelsize_x / distance)
        alpha_f = np.arctan(np.divide(myy, np.sqrt((distance/pixelsize_x)**2 + np.power(myx, 2))))

        qlab0 = 2 * np.pi / wavelength * (np.cos(alpha_f) * np.cos(two_theta) - kin[0])  # along z* downstream
        qlab1 = 2 * np.pi / wavelength * (np.sin(alpha_f) - kin[1])  # along y* vertical up
        qlab2 = 2 * np.pi / wavelength * (np.cos(alpha_f) * np.sin(two_theta) - kin[2])  # along x* outboard

        qx[idx, :, :] = rotation_matrix[0, 0] * qlab0 + rotation_matrix[0, 1] * qlab1 + rotation_matrix[0, 2] * qlab2
        qz[idx, :, :] = rotation_matrix[1, 0] * qlab0 + rotation_matrix[1, 1] * qlab1 + rotation_matrix[1, 2] * qlab2
        qy[idx, :, :] = rotation_matrix[2, 0] * qlab0 + rotation_matrix[2, 1] * qlab1 + rotation_matrix[2, 2] * qlab2

    return qx, qz, qy


def find_bragg(data, peak_method):
    """
    Find the Bragg peak position in data based on the centering method.

    :param data: 2D or 3D array. If complex, Bragg peak position is calculated for abs(array)
    :param peak_method: 'max', 'com' or 'maxcom'. For 'maxcom', it uses method 'max' for the first axis and 'com'
     for the other axes.
    :return: the centered data
    """
    if peak_method != 'max' and peak_method != 'com' and peak_method != 'maxcom':
        raise ValueError('Incorrect value for "centering_method" parameter')

    if data.ndim == 2:
        z0 = 0
        if peak_method == 'max':
            y0, x0 = np.unravel_index(abs(data).argmax(), data.shape)
            print("Max at (y, x): ", y0, x0, ' Max = ', int(data[y0, x0]))
        else:  # 'com'
            y0, x0 = center_of_mass(data)
            print("Center of mass at (y, x): ", y0, x0, ' COM = ', int(data[int(y0), int(x0)]))
    elif data.ndim == 3:
        if peak_method == 'max':
            z0, y0, x0 = np.unravel_index(abs(data).argmax(), data.shape)
            print("Max at (z, y, x): ", z0, y0, x0, ' Max = ', int(data[z0, y0, x0]))
        elif peak_method == 'com':
            z0, y0, x0 = center_of_mass(data)
            print("Center of mass at (z, y, x): ", z0, y0, x0, ' COM = ', int(data[int(z0), int(y0), int(x0)]))
        else:
            z0, _, _ = np.unravel_index(abs(data).argmax(), data.shape)
            y0, x0 = center_of_mass(data[z0, :, :])
            print("MaxCom at (z, y, x): ", z0, y0, x0, ' Max = ', int(data[int(z0), int(y0), int(x0)]))
    else:
        raise ValueError('Data should be 2D or 3D')

    return z0, y0, x0


def grid_bcdi(logfile, scan_number, detector, setup, flatfield=None, hotpixels=None, orthogonalize=False, hxrd=None,
              normalize=False, debugging=False, **kwargs):
    """
    Load the Bragg CDI data, apply filters and concatenate it for phasing.

    :param logfile: file containing the information about the scan and image numbers (specfile, .fio...)
    :param scan_number: the scan number to load
    :param detector: the detector object: Class experiment_utils.Detector()
    :param setup: the experimental setup: Class SetupPreprocessing()
    :param flatfield: the 2D flatfield array
    :param hotpixels: the 2D hotpixels array. 1 for a hotpixel, 0 for normal pixels.
    :param orthogonalize: if True will interpolate the data and the mask on an orthogonal grid using xrayutilities
    :param hxrd: an initialized xrayutilities HXRD object used for the orthogonalization of the dataset
    :param normalize: set to True to normalize the diffracted intensity by the incident X-ray beam intensity
    :param debugging: set to True to see plots
    :param kwargs:
     - follow_bragg (bool): True when for energy scans the detector was also scanned to follow the Bragg peak
    :return:
     - the 3D data array (in an orthonormal frame or in the detector frame) and the 3D mask array
     - frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
       A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
     - the monitor values for normalization
    """
    for k in kwargs.keys():
        if k in ['follow_bragg']:
            follow_bragg = kwargs['follow_bragg']
        else:
            raise Exception("unknown keyword argument given: allowed is 'follow_bragg'")
    if setup.rocking_angle == 'energy':
        try:
            follow_bragg
        except NameError:
            raise TypeError("Parameter 'follow_bragg' not provided, defaulting to False")
    rawdata, rawmask, monitor, frames_logical = load_data(logfile=logfile, scan_number=scan_number, detector=detector,
                                                          setup=setup, flatfield=flatfield, hotpixels=hotpixels,
                                                          debugging=debugging)
    # normalize by the incident X-ray beam intensity
    if normalize:
        rawdata, monitor = normalize_dataset(array=rawdata, raw_monitor=monitor, frames_logical=frames_logical,
                                             norm_to_min=True, debugging=debugging)

    # bin data and mask in the detector plane if needed
    # binning in the stacking dimension is done at the very end of the data processing
    if (detector.binning[1] != 1) or (detector.binning[2] != 1):
        rawdata = pu.bin_data(rawdata, (1, detector.binning[1], detector.binning[2]), debugging=False)
        rawmask = pu.bin_data(rawmask, (1, detector.binning[1], detector.binning[2]), debugging=False)
        rawmask[np.nonzero(rawmask)] = 1

    if not orthogonalize:
        return [], rawdata, [], rawmask, [], frames_logical, monitor

    elif setup.is_orthogonal:
        # load q values, the data is already orthogonalized
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(title="Select the file containing QxQzQy",
                                               initialdir=detector.datadir, filetypes=[("NPZ", "*.npz")])
        npzfile = np.load(file_path)
        q_values = [npzfile['qx'], npzfile['qz'], npzfile['qy']]
        return q_values, [], rawdata, [], rawmask, frames_logical, monitor

    else:
        if setup.filtered_data:
            print('Trying to orthogonalize a filtered data, the corresponding detector ROI should be provided\n'
                  'otherwise q values will be wrong.')
        nbz, nby, nbx = rawdata.shape
        qx, qz, qy, frames_logical = \
            regrid(logfile=logfile, nb_frames=rawdata.shape[0], scan_number=scan_number, detector=detector,
                   setup=setup, hxrd=hxrd, frames_logical=frames_logical, follow_bragg=follow_bragg)
        # qx, qz, qy (downstrean, vertical up, outboard) arrays have the same shape as the data
        if setup.beamline == 'ID01':
            # below is specific to ID01 energy scans where frames are duplicated for undulator gap change
            if setup.rocking_angle == 'energy':  # frames need to be removed
                tempdata = np.zeros(((frames_logical != 0).sum(), nby, nbx))
                offset_frame = 0
                for idx in range(nbz):
                    if frames_logical[idx] != 0:  # use frame
                        tempdata[idx-offset_frame, :, :] = rawdata[idx, :, :]
                    else:  # average with the precedent frame
                        offset_frame = offset_frame + 1
                        tempdata[idx-offset_frame, :, :] = (tempdata[idx-offset_frame, :, :] + rawdata[idx, :, :])/2
                rawdata = tempdata
                rawmask = rawmask[0:rawdata.shape[0], :, :]  # truncate the mask to have the correct size

        gridder = xu.Gridder3D(nbz, nby, nbx)
        # convert mask to rectangular grid in reciprocal space
        gridder(qx, qz, qy, rawmask)
        mask = np.copy(gridder.data)
        # convert data to rectangular grid in reciprocal space
        gridder(qx, qz, qy, rawdata)  # qx downstream, qz vertical up, qy outboard

        q_values = [gridder.xaxis, gridder.yaxis, gridder.zaxis]  # qx downstream, qz vertical up, qy outboard
        fig, _, _ = gu.contour_slices(gridder.data, (gridder.xaxis, gridder.yaxis, gridder.zaxis), sum_frames=False,
                                      title='Regridded data',
                                      levels=np.linspace(0, int(np.log10(gridder.data.max())), 150, endpoint=False),
                                      plot_colorbar=True, scale='log', is_orthogonal=True, reciprocal_space=True)
        fig.savefig(detector.savedir + 'reciprocal_space_' + str(nbz) + '_' + str(nby) + '_' + str(nbx) + '_' + '.png')
        plt.close(fig)

        return q_values, rawdata, gridder.data, rawmask, mask, frames_logical, monitor


def grid_cylindrical(array, rotation_angle, direct_beam, interp_angle, interp_radius):
    """
    Interpolate a 3D array in cylindrical coordinated (tomographic dataset) onto cartesian coordinates.

    :param array: 3D array of intensities measured in the detector frame
    :param rotation_angle: array, rotation angle values for the rocking scan
    :param direct_beam: position in pixels of the rotation pivot in the direction perpendicular to the rotation axis
    :param interp_angle: 2D array, polar angles for the interpolation in a plane perpendicular to the rotation axis
    :param interp_radius: 2D array, polar radii for the interpolation in a plane perpendicular to the rotation axis
    :return: the 3D array interpolated onto the 3D cartesian grid
    """
    assert array.ndim == 3, 'a 3D array is expected'

    rotation_step = rotation_angle[1]-rotation_angle[0]
    if rotation_step < 0:
        # flip rotation_angle and the data accordingly, RegularGridInterpolator takes only increasing position vectors
        rotation_angle = np.flip(rotation_angle)
        array = np.flip(array, axis=0)

    _, nby, nbx = array.shape
    interp_size = interp_angle.size
    _, numx = interp_angle.shape  # data shape is (numx, numx) by construction
    interp_array = np.zeros((numx, nby, numx), dtype=array.dtype)
    for idx in range(nby):  # loop over 2D frames perpendicular to the rotation axis
        # position of the experimental data points
        rgi = RegularGridInterpolator((rotation_angle * np.pi / 180, np.arange(-direct_beam, -direct_beam + nbx, 1)),
                                      array[:, idx, :], method='linear', bounds_error=False,
                                      fill_value=np.nan)

        # interpolate the data onto the new points
        temp_array = rgi(np.concatenate((interp_angle.reshape((1, interp_size)),
                                         interp_radius.reshape((1, interp_size)))).transpose())
        temp_array = temp_array.reshape(interp_angle.shape).astype(array.dtype)

        # stack the 2D interpolated frame along the rotation axis, taking into account the flip of the
        # detector Y axis (pointing down) compare to the laboratory frame vertical axis (pointing up)
        interp_array[:, nby - (idx + 1), :] = temp_array
        sys.stdout.write('\rGridding progress: {:d}%'.format(int((idx+1)/nby*100)))
        sys.stdout.flush()
    print('')
    return interp_array


def gridmap(logfile, scan_number, detector, setup, flatfield=None, hotpixels=None, orthogonalize=False, hxrd=None,
            normalize=False, debugging=False, **kwargs):
    """
    Load the Bragg CDI data, apply filters and concatenate it for phasing.

    :param logfile: file containing the information about the scan and image numbers (specfile, .fio...)
    :param scan_number: the scan number to load
    :param detector: the detector object: Class experiment_utils.Detector()
    :param setup: the experimental setup: Class SetupPreprocessing()
    :param flatfield: the 2D flatfield array
    :param hotpixels: the 2D hotpixels array. 1 for a hotpixel, 0 for normal pixels.
    :param orthogonalize: if True will interpolate the data and the mask on an orthogonal grid using xrayutilities
    :param hxrd: an initialized xrayutilities HXRD object used for the orthogonalization of the dataset
    :param normalize: set to True to normalize the diffracted intensity by the incident X-ray beam intensity
    :param debugging: set to True to see plots
    :param kwargs:
     - follow_bragg (bool): True when for energy scans the detector was also scanned to follow the Bragg peak
    :return:
     - the 3D data array (in an orthonormal frame or in the detector frame) and the 3D mask array
     - frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
       A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
     - the monitor values for normalization
    """
    for k in kwargs.keys():
        if k in ['follow_bragg']:
            follow_bragg = kwargs['follow_bragg']
        else:
            raise Exception("unknown keyword argument given: allowed is 'follow_bragg'")
    if setup.rocking_angle == 'energy':
        try:
            follow_bragg
        except NameError:
            raise TypeError("Parameter 'follow_bragg' not provided, defaulting to False")
    rawdata, rawmask, monitor, frames_logical = load_data(logfile=logfile, scan_number=scan_number, detector=detector,
                                                          setup=setup, flatfield=flatfield, hotpixels=hotpixels,
                                                          debugging=debugging)

    print((rawdata < 0).sum(), ' negative data points set to 0')  # can happen when subtracting a background
    rawdata[rawdata < 0] = 0

    # normalize by the incident X-ray beam intensity
    if normalize:
        rawdata, monitor = normalize_dataset(array=rawdata, raw_monitor=monitor, frames_logical=frames_logical,
                                             norm_to_min=True, debugging=debugging)

    # bin data and mask in the detector plane if needed
    # binning in the stacking dimension is done at the very end of the data processing
    if (detector.binning[1] != 1) or (detector.binning[2] != 1):
        print('Binning the data')
        rawdata = pu.bin_data(rawdata, (1, detector.binning[1], detector.binning[2]), debugging=False)
        rawmask = pu.bin_data(rawmask, (1, detector.binning[1], detector.binning[2]), debugging=False)
        rawmask[np.nonzero(rawmask)] = 1

    if not orthogonalize:
        return [], rawdata, [], rawmask, [], frames_logical, monitor

    elif setup.is_orthogonal:
        # load q values, the data is already orthogonalized
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(title="Select the file containing QxQzQy",
                                               initialdir=detector.datadir, filetypes=[("NPZ", "*.npz")])
        npzfile = np.load(file_path)
        q_values = [npzfile['qx'], npzfile['qz'], npzfile['qy']]
        return q_values, [], rawdata, [], rawmask, frames_logical, monitor

    else:
        if setup.filtered_data:
            print('Trying to orthogonalize a filtered data, the corresponding detector ROI should be provided\n'
                  'otherwise q values will be wrong.')
        nbz, nby, nbx = rawdata.shape
        qx, qz, qy, frames_logical = \
            regrid(logfile=logfile, nb_frames=rawdata.shape[0], scan_number=scan_number, detector=detector,
                   setup=setup, hxrd=hxrd, frames_logical=frames_logical, follow_bragg=follow_bragg)

        if setup.beamline == 'ID01':
            # below is specific to ID01 energy scans where frames are duplicated for undulator gap change
            if setup.rocking_angle == 'energy':  # frames need to be removed
                tempdata = np.zeros(((frames_logical != 0).sum(), nby, nbx))
                offset_frame = 0
                for idx in range(nbz):
                    if frames_logical[idx] != 0:  # use frame
                        tempdata[idx-offset_frame, :, :] = rawdata[idx, :, :]
                    else:  # average with the precedent frame
                        offset_frame = offset_frame + 1
                        tempdata[idx-offset_frame, :, :] = (tempdata[idx-offset_frame, :, :] + rawdata[idx, :, :])/2
                rawdata = tempdata
                rawmask = rawmask[0:rawdata.shape[0], :, :]  # truncate the mask to have the correct size
                nbz = rawdata.shape[0]
        gridder = xu.Gridder3D(nbz, nby, nbx)
        # convert mask to rectangular grid in reciprocal space
        gridder(qx, qz, qy, rawmask)  # qx downstream, qz vertical up, qy outboard
        mask = np.copy(gridder.data)
        # convert data to rectangular grid in reciprocal space
        gridder(qx, qz, qy, rawdata)  # qx downstream, qz vertical up, qy outboard

        q_values = [gridder.xaxis, gridder.yaxis, gridder.zaxis]  # downstream, vertical up, outboard
        fig, _, _ = gu.contour_slices(gridder.data, (gridder.xaxis, gridder.yaxis, gridder.zaxis), sum_frames=False,
                                      title='Regridded data',
                                      levels=np.linspace(0, int(np.log10(gridder.data.max())), 150, endpoint=False),
                                      plot_colorbar=True, scale='log', is_orthogonal=True, reciprocal_space=True)
        fig.savefig(detector.savedir + 'reciprocal_space_' + str(nbz) + '_' + str(nby) + '_' + str(nbx) + '_' + '.png')
        plt.close(fig)

        return q_values, rawdata, gridder.data, rawmask, mask, frames_logical, monitor


def higher_primes(number, maxprime=13, required_dividers=(4,)):
    """
    Find the closest integer >=n (or list/array of integers), for which the largest prime divider is <=maxprime,
    and has to include some dividers. The default values for maxprime is the largest integer accepted
    by the clFFT library for OpenCL GPU FFT. Adapted from PyNX.

    :param number: the integer number
    :param maxprime: the largest prime factor acceptable
    :param required_dividers: a list of required dividers for the returned integer.
    :return: the integer (or list/array of integers) fulfilling the requirements
    """
    if (type(number) is list) or (type(number) is tuple) or (type(number) is np.ndarray):
        vn = []
        for i in number:
            limit = i
            assert (i > 1 and maxprime <= i)
            while try_smaller_primes(i, maxprime=maxprime, required_dividers=required_dividers) is False:
                i = i + 1
                if i == limit:
                    return limit
            vn.append(i)
        if type(number) is np.ndarray:
            return np.array(vn)
        return vn
    else:
        limit = number
        assert (number > 1 and maxprime <= number)
        while try_smaller_primes(number, maxprime=maxprime, required_dividers=required_dividers) is False:
            number = number + 1
            if number == limit:
                return limit
        return number


def init_qconversion(setup):
    """
    Initialize the qconv object from xrayutilities depending on the setup parameters
    The convention in xrayutilities is x downstream, z vertical up, y outboard.

    :param setup: the experimental setup: Class SetupPreprocessing()
    :return: qconv object and offsets for motors
    """
    beamline = setup.beamline
    offset_inplane = setup.offset_inplane
    beam_direction = setup.beam_direction

    if beamline == 'ID01':
        offsets = (0, 0, 0, offset_inplane, 0)  # eta chi phi nu del
        qconv = xu.experiment.QConversion(['y-', 'x+', 'z-'], ['z-', 'y-'], r_i=beam_direction)  # for ID01
        # 3S+2D goniometer (ID01 goniometer, sample: eta, chi, phi      detector: nu,del
        # the vector beam_direction is giving the direction of the primary beam
        # convention for coordinate system: x downstream; z upwards; y to the "outside" (right-handed)
    elif beamline == 'NANOMAX':
        offsets = (0, 0, offset_inplane, 0)  # theta phi gamma delta
        qconv = xu.experiment.QConversion(['y-', 'z-'], ['z-', 'y-'], r_i=beam_direction)  # for NANOMAX
        # 2S+2D goniometer (ID01 goniometer, sample: theta, phi      detector: gamma,delta
        # the vector beam_direction is giving the direction of the primary beam
        # convention for coordinate system: x downstream; z upwards; y to the "outside" (right-handed)    
    elif beamline == 'SIXS_2018' or beamline == 'SIXS_2019':
        offsets = (0, 0, 0, offset_inplane, 0)  # beta, mu, beta, gamma del
        qconv = xu.experiment.QConversion(['y-', 'z+'], ['y-', 'z+', 'y-'], r_i=beam_direction)  # for SIXS
        # 2S+3D goniometer (SIXS goniometer, sample: beta, mu     detector: beta, gamma, del
        # beta is below both sample and detector circles
        # the vector is giving the direction of the primary beam
        # convention for coordinate system: x downstream; z upwards; y to the "outside" (right-handed)
    elif beamline == 'CRISTAL':
        offsets = (0, offset_inplane, 0)  # komega, gamma, delta
        qconv = xu.experiment.QConversion(['y-'], ['z+', 'y-'], r_i=beam_direction)  # for CRISTAL
        # 1S+2D goniometer (CRISTAL goniometer, sample: mgomega    detector: gamma, delta
        # the vector is giving the direction of the primary beam
        # convention for coordinate system: x downstream; z upwards; y to the "outside" (right-handed)
    elif beamline == 'P10':
        offsets = (0, 0, 0, 0, offset_inplane, 0)  # mu, omega, chi, phi, gamma del
        qconv = xu.experiment.QConversion(['z+', 'y-', 'x+', 'z-'], ['z+', 'y-'], r_i=beam_direction)  # for P10
        # 4S+2D goniometer (P10 goniometer, sample: mu, omega, chi,phi   detector: gamma, delta
        # the vector is giving the direction of the primary beam
        # convention for coordinate system: x downstream; z upwards; y to the "outside" (right-handed)
    elif beamline == '34ID':
        offsets = (0, 0, 0, 0, offset_inplane, 0)
        # mu, phi (incident angle), chi, theta (inplane), delta (inplane), gamma (outofplane)
        qconv = xu.experiment.QConversion(['z+', 'y+', 'x+', 'z+'], ['z+', 'y-'], r_i=beam_direction)  # for 34ID
        # TODO: check the motor directions for mu and chi
        # 4S+2D goniometer (34ID goniometer, sample: mu, phi, chi, theta (inplane)   detector: delta (inplane), gamma
        # the vector is giving the direction of the primary beam
        # convention for coordinate system: x downstream; z upwards; y to the "outside" (right-handed)
    else:
        raise ValueError("Incorrect value for parameter 'beamline'")

    return qconv, offsets


def load_background(background_file):
    """
    Load a background file.

    :param background_file: the path of the background file
    :return: a 2D background
    """
    if background_file != "":
        background = np.load(background_file)
        npz_key = background.files
        background = background[npz_key[0]]
        if background.ndim != 2:
            raise ValueError('background should be a 2D array')
    else:
        background = None
    return background


def load_cdi_data(logfile, scan_number, detector, setup, flatfield=None, hotpixels=None, background=None,
                  normalize='skip', debugging=False, **kwargs):
    """
    Load the forward CDI data, apply filters and optionally regrid it for phasing.


    :param logfile: file containing the information about the scan and image numbers (specfile, .fio...)
    :param scan_number: the scan number to load
    :param detector: the detector object: Class experiment_utils.Detector()
    :param setup: the experimental setup: Class SetupPreprocessing()
    :param flatfield: the 2D flatfield array
    :param hotpixels: the 2D hotpixels array. 1 for a hotpixel, 0 for normal pixels.
    :param background: the 2D background array to subtract to the data
    :param normalize: 'skip' to skip, 'monitor'  to normalize by the default monitor, 'sum_roi' to normalize
     by the integrated intensity in a defined region of interest
    :param debugging:  set to True to see plots
    :parama kwargs:
     - 'photon_threshold' = float, photon threshold to apply before binning
    :return:
     - the 3D data array (in an orthonormal frame or in the detector frame) and the 3D mask array
     - frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
       A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
     - the monitor values for normalization
    """
    for k in kwargs.keys():
        if k in ['photon_threshold']:
            photon_threshold = kwargs['photon_threshold']
        else:
            raise Exception("unknown keyword argument given: allowed is 'photon_threshold'")
    try:
        photon_threshold
    except NameError:  # photon_threshold not declared
        photon_threshold = 0

    rawdata, rawmask, monitor, frames_logical = load_data(logfile=logfile, scan_number=scan_number, detector=detector,
                                                          setup=setup, flatfield=flatfield, hotpixels=hotpixels,
                                                          background=background, normalize=normalize,
                                                          debugging=debugging)

    print((rawdata < 0).sum(), ' negative data points masked')  # can happen when subtracting a background
    rawmask[rawdata < 0] = 1
    rawdata[rawdata < 0] = 0

    rawdata = beamstop_correction(data=rawdata, detector=detector, setup=setup, debugging=debugging)

    # normalize by the incident X-ray beam intensity
    if normalize == 'skip':
        print('Skip intensity normalization')
    else:
        print('Intensity normalization using ' + normalize)
        rawdata, monitor = normalize_dataset(array=rawdata, raw_monitor=monitor, frames_logical=frames_logical,
                                             norm_to_min=True, debugging=debugging)

    nbz, nby, nbx = rawdata.shape
    # pad the data to the shape defined by the ROI
    if detector.roi[1] - detector.roi[0] > nby or detector.roi[3] - detector.roi[2] > nbx:
        start = tuple([np.nan, min(0, detector.roi[0]), min(0, detector.roi[2])])
        print('Paddind the data to the shape defined by the ROI')
        rawdata = pu.crop_pad(array=rawdata, start=start, output_shape=(rawdata.shape[0],
                                                                        detector.roi[1] - detector.roi[0],
                                                                        detector.roi[3] - detector.roi[2]))
        rawmask = pu.crop_pad(array=rawmask, padwith_ones=True, start=start,
                              output_shape=(rawmask.shape[0], detector.roi[1] - detector.roi[0],
                                            detector.roi[3] - detector.roi[2]))

    # apply optional photon threshold before binning
    if photon_threshold != 0:
        rawmask[rawdata < photon_threshold] = 1
        rawdata[rawdata < photon_threshold] = 0
        print("Applying photon threshold before binning: < ", photon_threshold)

    # bin data and mask in the detector plane if needed
    # binning in the stacking dimension is done at the very end of the data processing
    if (detector.binning[1] != 1) or (detector.binning[2] != 1):
        print('Binning the data: detector vertical axis by', detector.binning[1],
              ', detector horizontal axis by', detector.binning[2])
        rawdata = pu.bin_data(rawdata, (1, detector.binning[1], detector.binning[2]), debugging=False)
        rawmask = pu.bin_data(rawmask, (1, detector.binning[1], detector.binning[2]), debugging=False)
        rawmask[np.nonzero(rawmask)] = 1

    return rawdata, rawmask, frames_logical, monitor


def load_cristal_data(logfile, detector, flatfield, hotpixels, background, normalize='monitor', debugging=False):
    """
    Load CRISTAL data, apply filters and concatenate it for phasing. The address of dataset and monitor in the h5 file
     may have to be modified.

    :param logfile: h5py File object of CRISTAL .nxs scan file
    :param detector: the detector object: Class experiment_utils.Detector()
    :param flatfield: the 2D flatfield array
    :param hotpixels: the 2D hotpixels array
    :param background: the 2D background array to subtract to the data
    :param normalize: 'monitor' to return the default monitor values, 'sum_roi' to return a monitor based on the
     integrated intensity in the region of interest defined by detector.sum_roi
     by the integrated intensity in a defined region of interest
    :param debugging: set to True to see plots
    :return:
     - the 3D data array in the detector frame and the 3D mask array
     - a logical array of length = initial frames number. A frame used will be set to True, a frame unused to False.
     - the monitor values for normalization
    """
    mask_2d = np.zeros((detector.nb_pixel_y, detector.nb_pixel_x))

    group_key = list(logfile.keys())[0]
    tmp_data = logfile['/' + group_key + '/scan_data/data_06'][:]

    nb_img = tmp_data.shape[0]
    data = np.zeros((nb_img, detector.roi[1] - detector.roi[0], detector.roi[3] - detector.roi[2]))
    if normalize == 'sum_roi':
        monitor = np.zeros(nb_img)
    else:
        monitor = logfile['/' + group_key + '/scan_data/data_04'][:]

    for idx in range(nb_img):
        ccdraw = tmp_data[idx, :, :]
        ccdraw = ccdraw - background
        ccdraw, mask_2d = remove_hotpixels(data=ccdraw, mask=mask_2d, hotpixels=hotpixels)
        if detector.name == "Maxipix":
            ccdraw, mask_2d = mask_maxipix(ccdraw, mask_2d)
        else:
            raise ValueError('Detector ', detector.name, 'not supported for CRISTAL')
        ccdraw = flatfield * ccdraw
        if normalize == 'sum_roi':
            monitor[idx] = util.sum_roi(array=ccdraw, roi=detector.sum_roi)
        ccdraw = ccdraw[detector.roi[0]:detector.roi[1], detector.roi[2]:detector.roi[3]]
        data[idx, :, :] = ccdraw

    mask_2d = mask_2d[detector.roi[0]:detector.roi[1], detector.roi[2]:detector.roi[3]]
    data, mask_2d = check_pixels(data=data, mask=mask_2d, debugging=debugging)
    mask3d = np.repeat(mask_2d[np.newaxis, :, :], nb_img, axis=0)
    mask3d[np.isnan(data)] = 1
    data[np.isnan(data)] = 0

    frames_logical = np.ones(nb_img)

    return data, mask3d, monitor, frames_logical


def load_custom_data(custom_images, custom_monitor, beamline, detector, flatfield, hotpixels, background,
                     debugging=False):
    """
    Load a dataset measured without a scan, such as a set of images measured in a macro.

    :param custom_images: the list of image numbers
    :param custom_monitor: list of monitor values for normalization
    :param beamline: supported beamlines: 'ID01', 'SIXS_2018', 'SIXS_2019', 'CRISTAL', 'P10', '34ID'
    :param detector: the detector object: Class experiment_utils.Detector()
    :param flatfield: the 2D flatfield array
    :param hotpixels: the 2D hotpixels array
    :param background: the 2D background array to subtract to the data
    :param debugging: set to True to see plots
    :return:
    """
    mask_2d = np.zeros((detector.nb_pixel_y, detector.nb_pixel_x))
    ccdfiletmp = os.path.join(detector.datadir, detector.template_imagefile)
    if len(custom_images) == 0:
        raise ValueError("No image number provided in 'custom_images'")

    if len(custom_images) > 1:
        nb_img = len(custom_images)
        stack = False
    else:  # the data is stacked into a single file
        npzfile = np.load(ccdfiletmp % custom_images[0])
        tmp_data = npzfile[list(npzfile.files)[0]]
        nb_img = tmp_data.shape[0]
        stack = True

    data = np.zeros((nb_img, detector.roi[1] - detector.roi[0], detector.roi[3] - detector.roi[2]))
    for idx in range(nb_img):
        if stack:
            ccdraw = tmp_data[idx, :, :]
        else:
            i = int(custom_images[idx])
            if beamline == 'ID01':
                e = fabio.open(ccdfiletmp % i)
                ccdraw = e.data
            else:
                raise ValueError("Custom scan implementation missing for this beamline")
        ccdraw = ccdraw - background
        ccdraw, mask_2d = remove_hotpixels(data=ccdraw, mask=mask_2d, hotpixels=hotpixels)
        if detector.name == "Eiger2M":
            ccdraw, mask_2d = mask_eiger(data=ccdraw, mask=mask_2d)
        elif detector.name == "Maxipix":
            ccdraw, mask_2d = mask_maxipix(data=ccdraw, mask=mask_2d)
        else:
            pass
        ccdraw = flatfield * ccdraw
        ccdraw = ccdraw[detector.roi[0]:detector.roi[1], detector.roi[2]:detector.roi[3]]
        data[idx, :, :] = ccdraw

    mask_2d = mask_2d[detector.roi[0]:detector.roi[1], detector.roi[2]:detector.roi[3]]
    data, mask_2d = check_pixels(data=data, mask=mask_2d, debugging=debugging)
    mask3d = np.repeat(mask_2d[np.newaxis, :, :], nb_img, axis=0)
    mask3d[np.isnan(data)] = 1
    data[np.isnan(data)] = 0

    frames_logical = np.ones(nb_img)

    return data, mask3d, custom_monitor, frames_logical


def load_data(logfile, scan_number, detector, setup, flatfield=None, hotpixels=None, background=None,
              normalize='monitor', debugging=False):
    """
    Load data, apply filters and concatenate it for phasing.

    :param logfile: file containing the information about the scan and image numbers (specfile, .fio...)
    :param scan_number: the scan number to load
    :param detector: the detector object: Class experiment_utils.Detector()
    :param setup: the experimental setup: Class SetupPreprocessing()
    :param flatfield: the 2D flatfield array
    :param hotpixels: the 2D hotpixels array. 1 for a hotpixel, 0 for normal pixels.
    :param background: the 2D background array to subtract to the data
    :param normalize: 'monitor' to return the default monitor values, 'sum_roi' to return a monitor based on the
     integrated intensity in the region of interest defined by detector.sum_roi
     by the integrated intensity in a defined region of interest
    :param debugging: set to True to see plots
    :return:
     - the 3D data array in the detector frame and the 3D mask array
     - the monitor values for normalization
     - frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
       A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
    """
    if flatfield is None:
        flatfield = np.ones((detector.nb_pixel_y, detector.nb_pixel_x))
    if hotpixels is None:
        hotpixels = np.zeros((detector.nb_pixel_y, detector.nb_pixel_x))
    if background is None:
        background = np.zeros((detector.nb_pixel_y, detector.nb_pixel_x))

    print('Detector size defined by the ROI (VxH):',
          detector.roi[1] - detector.roi[0], detector.roi[3] - detector.roi[2])
    print('Detector physical size (VxH):', detector.nb_pixel_y, detector.nb_pixel_x)
    if detector.roi[1]-detector.roi[0] > detector.nb_pixel_y or detector.roi[3]-detector.roi[2] > detector.nb_pixel_x:
        print('Data shape is limited by detector size, loaded data will be smaller than as defined by the ROI.')

    if setup.custom_scan and not setup.filtered_data:
        data, mask3d, monitor, frames_logical = load_custom_data(custom_images=setup.custom_images,
                                                                 custom_monitor=setup.custom_monitor,
                                                                 beamline=setup.beamline,
                                                                 detector=detector, flatfield=flatfield,
                                                                 hotpixels=hotpixels, background=background,
                                                                 debugging=debugging)
    elif setup.filtered_data:
        data, mask3d, monitor, frames_logical = load_filtered_data(detector=detector)

    elif setup.beamline == 'ID01':
        data, mask3d, monitor, frames_logical = load_id01_data(logfile=logfile, scan_number=scan_number,
                                                               detector=detector, flatfield=flatfield,
                                                               hotpixels=hotpixels, background=background,
                                                               normalize=normalize, debugging=debugging)
    elif setup.beamline == 'NANOMAX':
        data, mask3d, monitor, frames_logical = load_nanomax_data(logfile=logfile, detector=detector, 
                                                               mask_path=True, debugging=debugging) #logfile, detector, mask_path, debugging=False
        print(data.shape) #data, mask3d, 0, frames_logical
        
    elif setup.beamline == 'SIXS_2018' or setup.beamline == 'SIXS_2019':
        data, mask3d, monitor, frames_logical = load_sixs_data(logfile=logfile, beamline=setup.beamline,
                                                               detector=detector, flatfield=flatfield,
                                                               hotpixels=hotpixels, background=background,
                                                               normalize=normalize, debugging=debugging)
    elif setup.beamline == 'CRISTAL':
        data, mask3d, monitor, frames_logical = load_cristal_data(logfile=logfile, detector=detector,
                                                                  flatfield=flatfield, hotpixels=hotpixels,
                                                                  background=background, normalize=normalize,
                                                                  debugging=debugging)
    elif setup.beamline == 'P10':
        data, mask3d, monitor, frames_logical = load_p10_data(logfile=logfile, detector=detector, flatfield=flatfield,
                                                              hotpixels=hotpixels, background=background,
                                                              normalize=normalize, debugging=debugging)
    else:
        raise ValueError('Wrong value for "beamline" parameter')

    # remove indices where frames_logical=0
    nbz, nby, nbx = data.shape
    nb_frames = (frames_logical != 0).sum()
    # TODO: try to load data more efficiently memorywise
    newdata = np.zeros((nb_frames, nby, nbx))
    newmask = np.zeros((nb_frames, nby, nbx))
    # do not process the monitor here, it is done in normalize_dataset()

    nb_overlap = 0
    for idx in range(len(frames_logical)):
        if frames_logical[idx]:
            newdata[idx - nb_overlap, :, :] = data[idx, :, :]
            newmask[idx - nb_overlap, :, :] = mask3d[idx, :, :]
        else:
            nb_overlap = nb_overlap + 1

    return newdata, newmask, monitor, frames_logical


def load_filtered_data(detector):
    """
    Load a filtered dataset and the corresponding mask.

    :param detector: the detector object: Class experiment_utils.Detector()
    :return: the data and the mask array
    """
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(initialdir=detector.datadir, title="Select data file",
                                           filetypes=[("NPZ", "*.npz")])
    data = np.load(file_path)
    npz_key = data.files
    data = data[npz_key[0]]
    file_path = filedialog.askopenfilename(initialdir=detector.datadir, title="Select mask file",
                                           filetypes=[("NPZ", "*.npz")])
    mask = np.load(file_path)
    npz_key = mask.files
    mask = mask[npz_key[0]]

    monitor = np.ones(data.shape[0])
    frames_logical = np.ones(data.shape[0])

    return data, mask, monitor, frames_logical


def load_flatfield(flatfield_file):
    """
    Load a flatfield file.

    :param flatfield_file: the path of the flatfield file
    :return: a 2D flatfield
    """
    if flatfield_file != "":
        flatfield = np.load(flatfield_file)
        npz_key = flatfield.files
        flatfield = flatfield[npz_key[0]]
        if flatfield.ndim != 2:
            raise ValueError('flatfield should be a 2D array')
    else:
        flatfield = None
    return flatfield


def load_hotpixels(hotpixels_file):
    """
    Load a hotpixels file.

    :param hotpixels_file: the path of the hotpixels file
    :return: a 2D array of hotpixels (1 for hotpixel, 0 for normal pixel)
    """
    if hotpixels_file != "":
        hotpixels = np.load(hotpixels_file)
        npz_key = hotpixels.files
        hotpixels = hotpixels[npz_key[0]]
        if hotpixels.ndim == 3:
            hotpixels = hotpixels.sum(axis=0)
        if hotpixels.ndim != 2:
            raise ValueError('hotpixels should be a 2D array')
        hotpixels[np.nonzero(hotpixels)] = 1
    else:
        hotpixels = None
    return hotpixels


def load_id01_data(logfile, scan_number, detector, flatfield, hotpixels, background, normalize='monitor',
                   debugging=False):
    """
    Load ID01 data, apply filters and concatenate it for phasing.

    :param logfile: Silx SpecFile object containing the information about the scan and image numbers
    :param scan_number: the scan number to load
    :param detector: the detector object: Class experiment_utils.Detector()
    :param flatfield: the 2D flatfield array
    :param hotpixels: the 2D hotpixels array
    :param background: the 2D background array to subtract to the data
    :param normalize: 'monitor' to return the default monitor values, 'sum_roi' to return a monitor based on the
     integrated intensity in the region of interest defined by detector.sum_roi
     by the integrated intensity in a defined region of interest
    :param debugging: set to True to see plots
    :return:
     - the 3D data array in the detector frame and the 3D mask array
     - the monitor values for normalization
     - frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
       A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
    """
    mask_2d = np.zeros((detector.nb_pixel_y, detector.nb_pixel_x))

    labels = logfile[str(scan_number) + '.1'].labels  # motor scanned
    labels_data = logfile[str(scan_number) + '.1'].data  # motor scanned

    ccdfiletmp = os.path.join(detector.datadir, detector.template_imagefile)

    try:
        ccdn = labels_data[labels.index(detector.counter), :]
    except ValueError:
        try:
            print(detector.counter, "not in the list, trying 'ccd_n'")
            detector.counter = 'ccd_n'
            ccdn = labels_data[labels.index(detector.counter), :]
        except ValueError:
            raise ValueError(detector.counter, 'not in the list, the detector name may be wrong')

    nb_img = len(ccdn)
    data = np.zeros((nb_img, detector.roi[1] - detector.roi[0], detector.roi[3] - detector.roi[2]))
    if normalize == 'sum_roi':
        monitor = np.zeros(nb_img)
    else:
        try:
            monitor = labels_data[labels.index('exp1'), :]  # mon2 monitor at ID01
        except ValueError:
            try:
                monitor = labels_data[labels.index('mon2'), :]  # exp1 for old data at ID01
            except ValueError:  # no monitor data
                print('No available monitor data')
                monitor = np.ones(nb_img)

    for idx in range(nb_img):
        i = int(ccdn[idx])
        e = fabio.open(ccdfiletmp % i)
        ccdraw = e.data
        ccdraw = ccdraw - background
        ccdraw, mask_2d = remove_hotpixels(data=ccdraw, mask=mask_2d, hotpixels=hotpixels)
        if detector.name == "Eiger2M":
            ccdraw, mask_2d = mask_eiger(data=ccdraw, mask=mask_2d)
        elif detector.name == "Maxipix":
            ccdraw, mask_2d = mask_maxipix(data=ccdraw, mask=mask_2d)
        else:
            raise ValueError('Detector ', detector.name, 'not supported for ID01')
        ccdraw = flatfield * ccdraw
        if normalize == 'sum_roi':
            monitor[idx] = util.sum_roi(array=ccdraw, roi=detector.sum_roi)
        ccdraw = ccdraw[detector.roi[0]:detector.roi[1], detector.roi[2]:detector.roi[3]]
        data[idx, :, :] = ccdraw

    mask_2d = mask_2d[detector.roi[0]:detector.roi[1], detector.roi[2]:detector.roi[3]]
    data, mask_2d = check_pixels(data=data, mask=mask_2d, debugging=debugging)
    mask3d = np.repeat(mask_2d[np.newaxis, :, :], nb_img, axis=0)
    mask3d[np.isnan(data)] = 1
    data[np.isnan(data)] = 0

    frames_logical = np.ones(nb_img)

    return data, mask3d, monitor, frames_logical


def load_p10_data(logfile, detector, flatfield, hotpixels, background, normalize='monitor', debugging=False):
    """
    Load P10 data, apply filters and concatenate it for phasing.

    :param logfile: path of the . fio file containing the information about the scan
    :param detector: the detector object: Class experiment_utils.Detector()
    :param flatfield: the 2D flatfield array
    :param hotpixels: the 2D hotpixels array
    :param background: the 2D background array to subtract to the data
    :param normalize: 'monitor' to return the default monitor values, 'sum_roi' to return a monitor based on the
     integrated intensity in the region of interest defined by detector.sum_roi
     by the integrated intensity in a defined region of interest
    :param debugging: set to True to see plots
    :return:
     - the 3D data array in the detector frame and the 3D mask array
     - the monitor values for normalization
     - frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
       A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.

    """
    import hdf5plugin  # should be imported before h5py
    import h5py
    mask_2d = np.zeros((detector.nb_pixel_y, detector.nb_pixel_x))

    ccdfiletmp = os.path.join(detector.datadir, detector.template_imagefile)

    h5file = h5py.File(ccdfiletmp, 'r')
    nb_img = len(list(h5file['entry/data']))
    print('Number of points :', nb_img)
    data = np.zeros((nb_img, detector.roi[1] - detector.roi[0], detector.roi[3] - detector.roi[2]))
    if normalize == 'sum_roi':
        monitor = np.zeros(nb_img)
    else:
        fio = open(logfile, 'r')
        monitor = []
        fio_lines = fio.readlines()
        for line in fio_lines:
            this_line = line.strip()
            words = this_line.split()
            if 'Col' in words and ('ipetra' in words or 'curpetra' in words):
                # template = ' Col 6 ipetra DOUBLE\n' (2018) or ' Col 6 curpetra DOUBLE\n' (2019)
                index_monitor = int(words[1]) - 1  # python index starts at 0
            try:
                float(words[0])  # if this does not fail, we are reading data
                monitor.append(float(words[index_monitor]))
            except ValueError:  # first word is not a number, skip this line
                continue
        fio.close()
        monitor = np.asarray(monitor, dtype=float)

    is_series = detector.is_series
    for file_idx in range(nb_img):
        idx = 0
        series_data = []
        series_monitor = []
        if is_series:
            data_path = 'data_' + str('{:06d}'.format(file_idx+1))
        else:
            data_path = 'data_000001'
        while True:
            try:
                try:
                    tmp_data = h5file['entry']['data'][data_path][idx]
                except OSError:
                    raise OSError('hdf5plugin is not installed')
                tmp_data = tmp_data - background
                ccdraw, mask2d = remove_hotpixels(data=tmp_data, mask=mask_2d, hotpixels=hotpixels)
                if detector.name == "Eiger4M":
                    ccdraw, mask_2d = mask_eiger4m(data=ccdraw, mask=mask_2d)
                else:
                    raise ValueError('Detector ', detector.name, 'not supported for P10')
                ccdraw = flatfield * ccdraw
                if normalize == 'sum_roi':
                    temp_mon = util.sum_roi(array=ccdraw, roi=detector.sum_roi)
                    series_monitor.append(temp_mon)
                ccdraw = ccdraw[detector.roi[0]:detector.roi[1], detector.roi[2]:detector.roi[3]]
                series_data.append(ccdraw)
                if not is_series:
                    sys.stdout.write('\rLoading frame {:d}'.format(idx))
                    sys.stdout.flush()
                idx = idx + 1
            except ValueError:  # reached the end of the series
                break
        if is_series:
            data[file_idx, :, :] = np.asarray(series_data).sum(axis=0)
            if normalize == 'sum_roi':
                monitor[file_idx] = np.asarray(series_monitor).sum()
            sys.stdout.write('\rSeries: loading frame {:d}'.format(file_idx))
            sys.stdout.flush()
        else:
            data = np.asarray(series_data)
            if normalize == 'sum_roi':
                monitor = np.asarray(series_monitor)
            break
    print('')
    mask_2d = mask_2d[detector.roi[0]:detector.roi[1], detector.roi[2]:detector.roi[3]]
    data, mask_2d = check_pixels(data=data, mask=mask_2d, debugging=debugging)
    mask3d = np.repeat(mask_2d[np.newaxis, :, :], nb_img, axis=0)
    mask3d[np.isnan(data)] = 1
    data[np.isnan(data)] = 0

    frames_logical = np.ones(nb_img)
    print('Monitor min max mean:', monitor.min(), monitor.max(), monitor.mean())
    return data, mask3d, monitor, frames_logical


def load_sixs_data(logfile, beamline, detector, flatfield, hotpixels, background, normalize='monitor', debugging=False):
    """
    Load SIXS data, apply filters and concatenate it for phasing.

    :param logfile: nxsReady Dataset object of SIXS .nxs scan file
    :param beamline: SIXS_2019 or SIXS_2018
    :param detector: the detector object: Class experiment_utils.Detector()
    :param flatfield: the 2D flatfield array
    :param hotpixels: the 2D hotpixels array
    :param background: the 2D background array to subtract to the data
    :param normalize: 'monitor' to return the default monitor values, 'sum_roi' to return a monitor based on the
     integrated intensity in the region of interest defined by detector.sum_roi
     by the integrated intensity in a defined region of interest
    :param debugging: set to True to see plots
    :return:
     - the 3D data array in the detector frame and the 3D mask array
     - the monitor values for normalization
     - frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
       A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
    """

    if beamline == 'SIXS_2018':
        tmp_data = logfile.mfilm[:]
    else:
        try:
            tmp_data = logfile.mpx_image[:]
        except AttributeError:
            try:
                tmp_data = logfile.maxpix[:]
            except AttributeError:  # the alias dictionnary was probably not provided
                tmp_data = logfile.image[:]

    mask_2d = np.zeros((detector.nb_pixel_y, detector.nb_pixel_x))
    frames_logical = np.ones(tmp_data.shape[0])
    nb_img = tmp_data.shape[0]
    data = np.zeros((nb_img, detector.roi[1] - detector.roi[0], detector.roi[3] - detector.roi[2]))
    if normalize == 'sum_roi':
        monitor = np.zeros(nb_img)
    else:
        if beamline == 'SIXS_2018':
            monitor = logfile.imon1[:]
        else:
            try:
                monitor = logfile.imon0[:]
            except AttributeError:  # the alias dictionnary was probably not provided
                monitor = logfile.intensity[:]

    for idx in range(nb_img):
        ccdraw = tmp_data[idx, :, :]
        ccdraw = ccdraw - background
        ccdraw, mask_2d = remove_hotpixels(data=ccdraw, mask=mask_2d, hotpixels=hotpixels)
        if detector.name == "Maxipix":
            ccdraw, mask_2d = mask_maxipix(data=ccdraw, mask=mask_2d)
        else:
            raise ValueError('Detector ', detector.name, 'not supported for SIXS')
        ccdraw = flatfield * ccdraw
        if normalize == 'sum_roi':
            monitor[idx] = util.sum_roi(array=ccdraw, roi=detector.sum_roi)
        ccdraw = ccdraw[detector.roi[0]:detector.roi[1], detector.roi[2]:detector.roi[3]]
        data[idx, :, :] = ccdraw

    mask_2d = mask_2d[detector.roi[0]:detector.roi[1], detector.roi[2]:detector.roi[3]]
    data, mask_2d = check_pixels(data=data, mask=mask_2d, debugging=debugging)
    mask3d = np.repeat(mask_2d[np.newaxis, :, :], nb_img, axis=0)
    mask3d[np.isnan(data)] = 1
    data[np.isnan(data)] = 0
    return data, mask3d, monitor, frames_logical


def load_nanomax_data(logfile, detector, mask_path, debugging=False):
    """
    Load P10 data, apply filters and concatenate it for phasing.

    :param logfile: path of the . fio file containing the information about the scan
    :param detector: the detector object: Class experiment_utils.Detector()
    :param flatfield: the 2D flatfield array
    :param hotpixels: the 2D hotpixels array
    :param background: the 2D background array to subtract to the data
    :param normalize: 'monitor' to return the default monitor values, 'sum_roi' to return a monitor based on the
     integrated intensity in the region of interest defined by detector.sum_roi
     by the integrated intensity in a defined region of interest
    :param debugging: set to True to see plots
    :return:
     - the 3D data array in the detector frame and the 3D mask array
     - the monitor values for normalization
     - frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
       A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.

    """
    import hdf5plugin  # should be imported before h5py
    import h5py
    
    def read_masterh5_NanoMAX(logfile):
#        h5file = h5py.File(logfile,'r')
        command = str(logfile['entry']['description'][()])[3:-2] # Reading only useful symbols
        motor_positions = {
                # Detector positions
                "delta": logfile['entry']['snapshot']['delta'][()],
                "gamma": logfile['entry']['snapshot']['gamma'][()],           
                "gonphi": logfile['entry']['snapshot']['gonphi'][()],
                "gontheta": logfile['entry']['snapshot']['gontheta'][()],
                "radius": logfile['entry']['snapshot']['radius'][()],
                "energy": logfile['entry']['snapshot']['energy'][()]
                }
        scan_keys = list(logfile['entry']['measurement'].keys())
        
        # Check which motor was scanned
        if 'gonphi' in scan_keys:        
            scan_info = {'gonphi': logfile['entry']['measurement']['gonphi'][()]}  
        elif 'gontheta' in scan_keys:
            scan_info = {'gontheta': logfile['entry']['measurement']['gontheta'][()]}  
        return command, motor_positions, scan_info
    
    command, motor_positions, scan_info = read_masterh5_NanoMAX(logfile)
    nb_img = len(scan_info['gonphi'])
    print('Number of points :', nb_img)
     
    mask_path = '/home/dzhigd/work/projects/CsPbBr3_NC_BCDI_NanoMAX/data/merlin_mask_190222_14keV.h5'
    h5mask = h5py.File(mask_path,'r')
    mask_2d = h5mask['mask'][()]
    print('Mask is loaded!') 

    ccdfiletmp = os.path.join(detector.template_imagefile)    
    h5file = h5py.File(ccdfiletmp, 'r')    
    
    data = h5file['entry']['measurement']['Merlin']['data'][()]
    
    
#    data = data[:, detector.roi[1] - detector.roi[0], detector.roi[3] - detector.roi[2]]
#    mask_2d = mask_2d[detector.roi[0]:detector.roi[1], detector.roi[2]:detector.roi[3]]
#    data, mask_2d = check_pixels(data=data, mask=mask_2d, debugging=debugging)
    mask3d = np.repeat(mask_2d[np.newaxis, :, :], nb_img, axis=0)
    
    print(mask3d.shape)
    data = data*mask3d
    data = np.flip(data, axis = 1)    

# Test
#    data = np.rot90(data,axes=(1,2))

#    mask3d[np.isnan(data)] = 1
    data[np.isnan(data)] = 0
    
    frames_logical = np.ones(nb_img)
#    print('Monitor min max mean:', monitor.min(), monitor.max(), monitor.mean())
    return data, mask3d, 0, frames_logical


def mask_eiger(data, mask):
    """
    Mask data measured with an Eiger2M detector

    :param data: the 2D data to mask
    :param mask: the 2D mask to be updated
    :return: the masked data and the updated mask
    """
    if data.ndim != 2 or mask.ndim != 2:
        raise ValueError('Data and mask should be 2D arrays')

    if data.shape != mask.shape:
        raise ValueError('Data and mask must have the same shape\n data is ', data.shape, ' while mask is ', mask.shape)

    data[:, 255: 259] = 0
    data[:, 513: 517] = 0
    data[:, 771: 775] = 0
    data[0: 257, 72: 80] = 0
    data[255: 259, :] = 0
    data[511: 552, :0] = 0
    data[804: 809, :] = 0
    data[1061: 1102, :] = 0
    data[1355: 1359, :] = 0
    data[1611: 1652, :] = 0
    data[1905: 1909, :] = 0
    data[1248:1290, 478] = 0
    data[1214:1298, 481] = 0
    data[1649:1910, 620:628] = 0

    mask[:, 255: 259] = 1
    mask[:, 513: 517] = 1
    mask[:, 771: 775] = 1
    mask[0: 257, 72: 80] = 1
    mask[255: 259, :] = 1
    mask[511: 552, :] = 1
    mask[804: 809, :] = 1
    mask[1061: 1102, :] = 1
    mask[1355: 1359, :] = 1
    mask[1611: 1652, :] = 1
    mask[1905: 1909, :] = 1
    mask[1248:1290, 478] = 1
    mask[1214:1298, 481] = 1
    mask[1649:1910, 620:628] = 1
    return data, mask


def mask_eiger4m(data, mask):
    """
    Mask data measured with an Eiger4M detector

    :param data: the 2D data to mask
    :param mask: the 2D mask to be updated
    :return: the masked data and the updated mask
    """
    if data.ndim != 2 or mask.ndim != 2:
        raise ValueError('Data and mask should be 2D arrays')

    if data.shape != mask.shape:
        raise ValueError('Data and mask must have the same shape\n data is ', data.shape, ' while mask is ', mask.shape)

    data[:, 1030:1040] = 1
    data[514:551, :] = 1
    data[1065:1102, :] = 1
    data[1616:1653, :] = 1

    mask[:, 1030:1040] = 1
    mask[514:551, :] = 1
    mask[1065:1102, :] = 1
    mask[1616:1653, :] = 1
    return data, mask


def mask_maxipix(data, mask):
    """
    Mask data measured with a Maxipix detector

    :param data: the 2D data to mask
    :param mask: the 2D mask to be updated
    :return: the masked data and the updated mask
    """
    if data.ndim != 2 or mask.ndim != 2:
        raise ValueError('Data and mask should be 2D arrays')

    if data.shape != mask.shape:
        raise ValueError('Data and mask must have the same shape\n data is ', data.shape, ' while mask is ', mask.shape)

    data[:, 255:261] = 0
    data[255:261, :] = 0

    mask[:, 255:261] = 1
    mask[255:261, :] = 1
    return data, mask


def mean_filter(data, nb_neighbours, mask, min_count=3, interpolate='mask_isolated', debugging=False):
    """
    Mask or apply a mean filter if the empty pixel is surrounded by nb_neighbours or more pixels with at least
    min_count intensity per pixel.

    :param data: 2D array to be filtered
    :param nb_neighbours: minimum number of non-zero neighboring pixels for median filtering
    :param mask: 2D mask array
    :param min_count: minimum intensity in the neighboring pixels
    :param interpolate: based on 'nb_neighbours', if 'mask_isolated' will mask isolated pixels,
      if 'interp_isolated' will interpolate isolated pixels
    :param debugging: set to True to see plots
    :type debugging: bool
    :return: updated data and mask, number of pixels treated
    """
    threshold = min_count*nb_neighbours
    if data.ndim != 2 or mask.ndim != 2:
        raise ValueError('Data and mask should be 2D arrays')

    if debugging:
        gu.combined_plots(tuple_array=(data, mask), tuple_sum_frames=(False, False), tuple_sum_axis=(0, 0),
                          tuple_width_v=(None, None), tuple_width_h=(None, None), tuple_colorbar=(True, True),
                          tuple_vmin=(-1, 0), tuple_vmax=(np.nan, 1), tuple_scale=('log', 'linear'),
                          tuple_title=('Data before filtering', 'Mask before filtering'), reciprocal_space=True)
    zero_pixels = np.argwhere(data == 0)
    nb_pixels = 0
    for indx in range(zero_pixels.shape[0]):
        pixrow = zero_pixels[indx, 0]
        pixcol = zero_pixels[indx, 1]
        temp = data[pixrow-1:pixrow+2, pixcol-1:pixcol+2]
        if temp.size != 0 and temp.sum() > threshold and sum(sum(temp != 0)) >= nb_neighbours:
            # mask/interpolate if at least 3 photons in each neighboring pixels
            nb_pixels = nb_pixels + 1
            if interpolate == 'interp_isolated':
                value = temp.sum() / sum(sum(temp != 0))
                data[pixrow, pixcol] = value
                mask[pixrow, pixcol] = 0
            else:
                mask[pixrow, pixcol] = 1
    if interpolate == 'interp_isolated':
        print("Nb of filtered pixel: ", nb_pixels)
    else:
        print("Nb of masked pixel: ", nb_pixels)

    if debugging:
        gu.combined_plots(tuple_array=(data, mask), tuple_sum_frames=(False, False), tuple_sum_axis=(0, 0),
                          tuple_width_v=(None, None), tuple_width_h=(None, None), tuple_colorbar=(True, True),
                          tuple_vmin=(-1, 0), tuple_vmax=(np.nan, 1), tuple_scale=('log', 'linear'),
                          tuple_title=('Data after filtering', 'Mask after filtering'), reciprocal_space=True)
    return data, nb_pixels, mask

def motor_positions_nanomax(logfile,setup):
    import hdf5plugin
    import h5py
    
#    h5file = h5py.File(logfile,'r')
#        
    # Detector positions
    delta = logfile['entry']['snapshot']['delta'][()]
    gamma = logfile['entry']['snapshot']['gamma'][()],   
    if setup.rocking_angle == 'inplane':
        phi = logfile['entry']['measurement']['gonphi'][()]
        theta = logfile['entry']['snapshot']['gontheta'][()]
    else:
        phi = logfile['entry']['snapshot']['gonphi'][()]
        theta = logfile['entry']['measurement']['gontheta'][()]
    radius = logfile['entry']['snapshot']['radius'][()]
    energy = logfile['entry']['snapshot']['energy'][()]
    
    return delta, gamma, phi, theta, radius, energy

def motor_positions_34id(setup):
    """
    Load the scan data and extract motor positions.

    :param setup: the experimental setup: Class SetupPreprocessing()
    :return: (mu, tilt, chi, theta, delta, gamma) motor positions
    """
    if setup.rocking_angle != 'energy':
        raise ValueError('Only energy scan implemented for 34ID')

    if not setup.custom_scan:
        raise ValueError('Only custom_scan implemented for 34ID')
    else:
        mu = setup.custom_motors["mu"]
        tilt = setup.custom_motors["phi"]
        chi = setup.custom_motors["chi"]
        theta = setup.custom_motors["theta"]
        gamma = setup.custom_motors["gamma"]
        delta = setup.custom_motors["delta"]

    return mu, tilt, chi, theta, delta, gamma


def motor_positions_cristal(logfile, setup):
    """
    Load the scan data and extract motor positions.

    :param logfile: h5py File object of CRISTAL .nxs scan file
    :param setup: the experimental setup: Class SetupPreprocessing()
    :return: (mgomega, gamma, delta) motor positions
    """
    if setup.rocking_angle != 'outofplane':
        raise ValueError('Only out of plane rocking curve implemented for CRISTAL')

    if not setup.custom_scan:
        group_key = list(logfile.keys())[0]

        mgomega = logfile['/' + group_key + '/scan_data/actuator_1_1'][:] / 1e6  # mgomega is scanned

        delta = logfile['/' + group_key + '/CRISTAL/Diffractometer/I06-C-C07-EX-DIF-DELTA/position'][:]

        gamma = logfile['/' + group_key + '/CRISTAL/Diffractometer/I06-C-C07-EX-DIF-GAMMA/position'][:]
    else:
        mgomega = setup.custom_motors["mgomega"] / 1e6
        delta = setup.custom_motors["delta"]
        gamma = setup.custom_motors["gamma"]

    return mgomega, gamma, delta


def motor_positions_id01(frames_logical, logfile, scan_number, setup, follow_bragg=False):
    """
    Load the scan data and extract motor positions.

    :param follow_bragg: True when for energy scans the detector was also scanned to follow the Bragg peak
    :param frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
     A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
    :param logfile: Silx SpecFile object containing the information about the scan and image numbers
    :param scan_number: the scan number to load
    :param setup: the experimental setup: Class SetupPreprocessing()
    :return: (eta, chi, phi, nu, delta, energy) motor positions
    """
    energy = setup.energy  # will be overridden if setup.rocking_angle is 'energy'
    old_names = False
    if not setup.custom_scan:
        motor_names = logfile[str(scan_number) + '.1'].motor_names  # positioners
        motor_positions = logfile[str(scan_number) + '.1'].motor_positions  # positioners
        labels = logfile[str(scan_number) + '.1'].labels  # motor scanned
        labels_data = logfile[str(scan_number) + '.1'].data  # motor scanned

        try:
            nu = motor_positions[motor_names.index('nu')]  # positioner
        except ValueError:
            print("'nu' not in the list, trying 'Nu'")
            nu = motor_positions[motor_names.index('Nu')]  # positioner
            print('Defaulting to old ID01 motor names')
            old_names = True

        if follow_bragg:
            if not old_names:
                delta = list(labels_data[labels.index('del'), :])  # scanned
            else:
                delta = list(labels_data[labels.index('Delta'), :])  # scanned
        else:
            if not old_names:
                delta = motor_positions[motor_names.index('del')]  # positioner
            else:
                delta = motor_positions[motor_names.index('Delta')]  # positioner

        chi = 0

        if setup.rocking_angle == "outofplane":
            if not old_names:
                eta = labels_data[labels.index('eta'), :]
                phi = motor_positions[motor_names.index('phi')]
            else:
                eta = labels_data[labels.index('Eta'), :]
                phi = motor_positions[motor_names.index('Phi')]
        elif setup.rocking_angle == "inplane":
            if not old_names:
                phi = labels_data[labels.index('phi'), :]
                eta = motor_positions[motor_names.index('eta')]
            else:
                phi = labels_data[labels.index('Phi'), :]
                eta = motor_positions[motor_names.index('Eta')]
        elif setup.rocking_angle == "energy":
            raw_energy = list(labels_data[labels.index('energy'), :])  # in kev, scanned
            if not old_names:
                phi = motor_positions[motor_names.index('phi')]  # positioner
                eta = motor_positions[motor_names.index('eta')]  # positioner
            else:
                phi = motor_positions[motor_names.index('Phi')]  # positioner
                eta = motor_positions[motor_names.index('Eta')]  # positioner

            nb_overlap = 0
            energy = raw_energy[:]
            for idx in range(len(raw_energy) - 1):
                if raw_energy[idx + 1] == raw_energy[idx]:  # duplicate energy when undulator gap is changed
                    frames_logical[idx + 1] = 0
                    energy.pop(idx - nb_overlap)
                    if follow_bragg == 1:
                        delta.pop(idx - nb_overlap)
                    nb_overlap = nb_overlap + 1
            energy = np.array(energy) * 1000.0 - 6  # switch to eV, 6 eV of difference at ID01

        else:
            raise ValueError('Invalid rocking angle ', setup.rocking_angle, 'for ID01')

    else:
        eta = setup.custom_motors["eta"]
        chi = 0
        phi = setup.custom_motors["phi"]
        delta = setup.custom_motors["delta"]
        nu = setup.custom_motors["nu"]

    return eta, chi, phi, nu, delta, energy, frames_logical


def motor_positions_p10(logfile, setup):
    """
    Load the .fio file from the scan and extract motor positions for P10 6-circle difractometer setup.

    :param logfile: path of the . fio file containing the information about the scan
    :param setup: the experimental setup: Class SetupPreprocessing()
    :return: (om, phi, chi, mu, gamma, delta) motor positions
    """
    if not setup.custom_scan:
        fio = open(logfile, 'r')
        if setup.rocking_angle == "outofplane":
            om = []
        elif setup.rocking_angle == "inplane":
            phi = []
        else:
            raise ValueError('Wrong value for "rocking_angle" parameter')

        fio_lines = fio.readlines()
        for line in fio_lines:
            this_line = line.strip()
            words = this_line.split()

            if 'Col' in words and 'om' in words:  # om scanned, template = ' Col 0 om DOUBLE\n'
                index_om = int(words[1]) - 1  # python index starts at 0
            if 'om' in words and '=' in words and setup.rocking_angle == "inplane":  # om is a positioner
                om = float(words[2])

            if 'Col' in words and 'phi' in words:  # phi scanned, template = ' Col 0 phi DOUBLE\n'
                index_phi = int(words[1]) - 1  # python index starts at 0
            if 'phi' in words and '=' in words and setup.rocking_angle == "outofplane":  # phi is a positioner
                phi = float(words[2])

            if 'chi' in words and '=' in words:  # template for positioners: 'chi = 90.0\n'
                chi = float(words[2])
            if 'del' in words and '=' in words:  # template for positioners: 'del = 30.05\n'
                delta = float(words[2])
            if 'gam' in words and '=' in words:  # template for positioners: 'gam = 4.05\n'
                gamma = float(words[2])
            if 'mu' in words and '=' in words:  # template for positioners: 'mu = 0.0\n'
                mu = float(words[2])

            try:
                float(words[0])  # if this does not fail, we are reading data
                if setup.rocking_angle == "outofplane":
                    om.append(float(words[index_om]))
                else:  # phi
                    phi.append(float(words[index_phi]))
            except ValueError:  # first word is not a number, skip this line
                continue

        if setup.rocking_angle == "outofplane":
            om = np.asarray(om, dtype=float)
        else:  # phi
            phi = np.asarray(phi, dtype=float)

        fio.close()

    else:
        om = setup.custom_motors["om"]
        chi = setup.custom_motors["chi"]
        phi = setup.custom_motors["phi"]
        delta = setup.custom_motors["delta"]
        gamma = setup.custom_motors["gamma"]
        mu = setup.custom_motors["mu"]
    return om, phi, chi, mu, gamma, delta


def motor_positions_p10_saxs(logfile, setup):
    """
    Load the .fio file from the scan and extract motor positions for P10 SAXS setup.

    :param logfile: path of the . fio file containing the information about the scan
    :param setup: the experimental setup: Class SetupPreprocessing()
    :return: sprz or hprz motor positions
    """
    if not setup.custom_scan:
        fio = open(logfile, 'r')
        if setup.rocking_angle == "outofplane":
            raise ValueError('Out of plane rotation not implemented for P110 SAXS setup')
        elif setup.rocking_angle == "inplane":
            phi = []
        else:
            raise ValueError('Wrong value for "rocking_angle" parameter')

        fio_lines = fio.readlines()
        for line in fio_lines:
            this_line = line.strip()
            words = this_line.split()

            if 'Col' in words:
                if 'sprz' in words or 'hprz' in words:  # sprz or hprz (SAXS) scanned
                    # template = ' Col 0 sprz DOUBLE\n'
                    index_phi = int(words[1]) - 1  # python index starts at 0
                    print(words, '  Index Phi=', index_phi)
            try:
                float(words[0])  # if this does not fail, we are reading data
                phi.append(float(words[index_phi]))
            except ValueError:  # first word is not a number, skip this line
                continue
        phi = np.asarray(phi, dtype=float)
        fio.close()
    else:
        phi = setup.custom_motors["phi"]
    return phi


def motor_positions_sixs(logfile, frames_logical, setup):
    """
    Load the scan data and extract motor positions.

    :param logfile: nxsReady Dataset object of SIXS .nxs scan file
    :param frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
     A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
    :param setup: the experimental setup: Class SetupPreprocessing()
    :return: (beta, mgomega, gamma, delta) motor positions and updated frames_logical
    """
    if not setup.custom_scan:
        delta = logfile.delta[0]  # not scanned
        gamma = logfile.gamma[0]  # not scanned
        try:
            beta = logfile.basepitch[0]  # not scanned
        except AttributeError:  # data recorder changed after 11/03/2019
            try:
                beta = logfile.beta[0]  # not scanned
            except AttributeError:  # the alias dictionnary was probably not provided
                beta = logfile.pitch[0]  # not scanned

        temp_mu = logfile.mu[:]

        mu = np.zeros((frames_logical != 0).sum())  # first frame is duplicated for SIXS_2018
        nb_overlap = 0
        for idx in range(len(frames_logical)):
            if frames_logical[idx]:
                mu[idx - nb_overlap] = temp_mu[idx]
            else:
                nb_overlap = nb_overlap + 1
    else:
        beta = setup.custom_motors["beta"]
        delta = setup.custom_motors["delta"]
        gamma = setup.custom_motors["gamma"]
        mu = setup.custom_motors["mu"]
    return beta, mu, gamma, delta, frames_logical


def motor_values(frames_logical, logfile, scan_number, setup, follow_bragg=False):
    """
    Load the scan data and extract motor positions.

    :param follow_bragg: True when for energy scans the detector was also scanned to follow the Bragg peak
    :param frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
     A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
    :param logfile: file containing the information about the scan and image numbers (specfile, .fio...)
    :param scan_number: the scan number to load
    :param setup: the experimental setup: Class SetupPreprocessing()
    :return: (rocking angular step, grazing incidence angle, inplane detector angle, outofplane detector angle)
     corrected values
    """
    if setup.beamline == 'ID01': #eta, chi, phi, nu, delta, energy, frames_logical
        if setup.rocking_angle == 'outofplane':  # eta rocking curve
            tilt, _, _, inplane, outofplane, _, _ = \
                motor_positions_id01(frames_logical, logfile, scan_number, setup, follow_bragg=follow_bragg)
            grazing = 0
        elif setup.rocking_angle == 'inplane':  # phi rocking curve
            grazing, _, tilt, inplane, outofplane, _, _ = \
                motor_positions_id01(frames_logical, logfile, scan_number, setup, follow_bragg=follow_bragg)
        else:
            raise ValueError('Wrong value for "rocking_angle" parameter')
            
    elif setup.beamline == 'NANOMAX': #delta, gamma, phi, theta, radius, energy
        if setup.rocking_angle == 'outofplane':  # theta rocking curve
            outofplane, inplane, _, tilt, _, _ = \
                motor_positions_nanomax(logfile,setup)
            grazing = 0
        elif setup.rocking_angle == 'inplane':  # phi rocking curve
            outofplane, inplane, tilt, _, _, _ = \
                motor_positions_nanomax(logfile,setup)
        else:
            raise ValueError('Wrong value for "rocking_angle" parameter')

    elif setup.beamline == 'SIXS_2018' or setup.beamline == 'SIXS_2019':
        if setup.rocking_angle == 'inplane':  # mu rocking curve
            grazing, tilt, inplane, outofplane, _ = motor_positions_sixs(logfile, frames_logical, setup)
        else:
            raise ValueError('Out-of-plane rocking curve not implemented for SIXS')

    elif setup.beamline == 'CRISTAL':
        if setup.rocking_angle == 'outofplane':  # mgomega rocking curve
            tilt, inplane, outofplane = motor_positions_cristal(logfile, setup)
            grazing = 0
            inplane = inplane[0]
            outofplane = outofplane[0]
        else:
            raise ValueError('Inplane rocking curve not implemented for CRISTAL')

    elif setup.beamline == 'P10':
        if setup.rocking_angle == 'outofplane':  # om rocking curve
            tilt, _, _, _, inplane, outofplane = motor_positions_p10(logfile, setup)
            grazing = 0
        elif setup.rocking_angle == 'inplane':  # phi rocking curve
            grazing, tilt, _, _, inplane, outofplane = motor_positions_p10(logfile, setup)
        else:
            raise ValueError('Wrong value for "rocking_angle" parameter')
    else:
        raise ValueError('Wrong value for "beamline" parameter: beamline not supported')

    return tilt, grazing, inplane, outofplane


def normalize_dataset(array, raw_monitor, frames_logical, norm_to_min=True, debugging=False):
    """
    Normalize array using the monitor values.

    :param array: the 3D array to be normalized
    :param raw_monitor: the monitor values
    :param frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
     A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
    :param norm_to_min: normalize to min(monitor) instead of max(monitor), avoid multiplying the noise
    :type norm_to_min: bool
    :param debugging: set to True to see plots
    :type debugging: bool
    :return:
     - normalized dataset
     - updated monitor
     - a title for plotting
    """
    if norm_to_min:
        print('Data normalization by monitor.min()/monitor')
    else:
        print('Data normalization by monitor.max()/monitor')

    ndim = array.ndim
    if ndim != 3:
        raise ValueError('Array should be 3D')

    if debugging:
        gu.imshow_plot(array=array, sum_frames=True, sum_axis=1, vmin=0, scale='log', title='Data before normalization')
        print('frames_logical: length=', frames_logical.shape, 'value=\n', frames_logical)

    # crop/pad monitor depending on frames_logical array
    monitor = np.zeros((frames_logical != 0).sum())
    nb_overlap = 0
    nb_padded = 0
    for idx in range(len(frames_logical)):
        if frames_logical[idx] == -1:  # padded frame, no monitor value for this
            if norm_to_min:
                monitor[idx - nb_overlap] = raw_monitor.min()
            else:  # norm to max
                monitor[idx - nb_overlap] = raw_monitor.max()
            nb_padded = nb_padded + 1
        elif frames_logical[idx] == 1:
            monitor[idx - nb_overlap] = raw_monitor[idx-nb_padded]
        else:
            nb_overlap = nb_overlap + 1
    if nb_padded != 0:
        print('Monitor value set to 1 for ', nb_padded, ' frames padded')

    if norm_to_min:
        monitor = monitor.min() / monitor  # will divide higher intensities
    else:  # norm to max
        monitor = monitor.max() / monitor  # will multiply lower intensities

    nbz = array.shape[0]
    if len(monitor) != nbz:
        raise ValueError('The frame number and the monitor data length are different:'
                         ' Got ', nbz, 'frames but ', len(monitor), ' monitor values')

    for idx in range(nbz):
        array[idx, :, :] = array[idx, :, :] * monitor[idx]

    return array, monitor


def primes(number):
    """
    Returns the prime decomposition of n as a list. Adapted from PyNX.

    :param number: the integer to be decomposed
    :return: the list of prime dividers of number
    """
    if not isinstance(number, int):
        raise TypeError('Number should be an integer')

    list_primes = [1]
    assert (number > 0)
    i = 2
    while i * i <= number:
        while number % i == 0:
            list_primes.append(i)
            number //= i
        i += 1
    if number > 1:
        list_primes.append(number)
    return list_primes


def regrid(logfile, nb_frames, scan_number, detector, setup, hxrd, frames_logical=None, follow_bragg=False):
    """
    Load beamline motor positions and calculate q positions for orthogonalization.

    :param logfile: file containing the information about the scan and image numbers (specfile, .fio...)
    :param nb_frames: length of axis 0 in the 3D dataset. If the data was cropped or padded, it may be different
     from the length of frames_logical.
    :param scan_number: the scan number to load
    :param detector: the detector object: Class experiment_utils.Detector()
    :param setup: the experimental setup: Class SetupPreprocessing()
    :param hxrd: an initialized xrayutilities HXRD object used for the orthogonalization of the dataset
    :param frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
     A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
    :param follow_bragg: True when in energy scans the detector was also scanned to follow the Bragg peak
    :return:
     - qx, qz, qy components for the dataset
     - updated frames_logical
    """
    binning = detector.binning

    if frames_logical is None:  # retrieve the raw data length, then len(frames_logical) may be different from nb_frames
        if (setup.beamline == 'ID01') or (setup.beamline == 'SIXS_2018') or (setup.beamline == 'SIXS_2019'):
            _, _, _, frames_logical = load_data(logfile=logfile, scan_number=scan_number,
                                                detector=detector, setup=setup)
        else:  # frames_logical parameter not used yet for other beamlines
            pass

    if follow_bragg and setup.beamline != 'ID01':
        raise ValueError('"follow_bragg" option implemented only for ID01 beamline')

    if setup.beamline == 'ID01':
        eta, chi, phi, nu, delta, energy, frames_logical = \
            motor_positions_id01(frames_logical, logfile, scan_number, setup, follow_bragg=follow_bragg)
        chi = chi + setup.sample_offsets[0]
        phi = phi + setup.sample_offsets[1]
        eta = eta + setup.sample_offsets[2]
        if setup.rocking_angle == 'outofplane':  # eta rocking curve
            nb_steps = len(eta)
            tilt_angle = eta[1] - eta[0]

            if nb_steps < nb_frames:  # data has been padded, we suppose it is centered in z dimension
                pad_low = int((nb_frames - nb_steps + ((nb_frames - nb_steps) % 2)) / 2)
                pad_high = int((nb_frames - nb_steps + 1) / 2 - ((nb_frames - nb_steps) % 2))
                eta = np.concatenate((eta[0] + np.arange(-pad_low, 0, 1) * tilt_angle,
                                      eta,
                                      eta[-1] + np.arange(1, pad_high + 1, 1) * tilt_angle), axis=0)
            if nb_steps > nb_frames:  # data has been cropped, we suppose it is centered in z dimension
                eta = eta[(nb_steps - nb_frames) // 2: (nb_steps + nb_frames) // 2]

        elif setup.rocking_angle == 'inplane':  # phi rocking curve
            nb_steps = len(phi)
            tilt_angle = phi[1] - phi[0]

            if nb_steps < nb_frames:  # data has been padded, we suppose it is centered in z dimension
                pad_low = int((nb_frames - nb_steps + ((nb_frames - nb_steps) % 2)) / 2)
                pad_high = int((nb_frames - nb_steps + 1) / 2 - ((nb_frames - nb_steps) % 2))
                phi = np.concatenate((phi[0] + np.arange(-pad_low, 0, 1) * tilt_angle,
                                      phi,
                                      phi[-1] + np.arange(1, pad_high + 1, 1) * tilt_angle), axis=0)
            if nb_steps > nb_frames:  # data has been cropped, we suppose it is centered in z dimension
                phi = phi[(nb_steps - nb_frames) // 2: (nb_steps + nb_frames) // 2]

        elif setup.rocking_angle == 'energy':
            pass
        else:
            raise ValueError('Wrong value for "rocking_angle" parameter')

        eta, chi, phi, nu, delta, energy = bin_parameters(binning=binning[0], nb_frames=nb_frames,
                                                          params=[eta, chi, phi, nu, delta, energy])
        qx, qy, qz = hxrd.Ang2Q.area(eta, chi, phi, nu, delta, en=energy, delta=detector.offsets)
    
    elif setup.beamline == 'NANOMAX': #
        delta, gamma, phi, theta, radius, energy = \
            motor_positions_nanomax(logfile,setup)       
        phi = phi + setup.sample_offsets[0]
        theta = theta + setup.sample_offsets[1]
        if setup.rocking_angle == 'outofplane':  # theta rocking curve
            nb_steps = len(theta)
            tilt_angle = theta[1] - theta[0]

            if nb_steps < nb_frames:  # data has been padded, we suppose it is centered in z dimension
                pad_low = int((nb_frames - nb_steps + ((nb_frames - nb_steps) % 2)) / 2)
                pad_high = int((nb_frames - nb_steps + 1) / 2 - ((nb_frames - nb_steps) % 2))
                theta = np.concatenate((theta[0] + np.arange(-pad_low, 0, 1) * tilt_angle,
                                      theta,
                                      theta[-1] + np.arange(1, pad_high + 1, 1) * tilt_angle), axis=0)
            if nb_steps > nb_frames:  # data has been cropped, we suppose it is centered in z dimension
                theta = theta[(nb_steps - nb_frames) // 2: (nb_steps + nb_frames) // 2]

        elif setup.rocking_angle == 'inplane':  # phi rocking curve
            nb_steps = len(phi)
            tilt_angle = phi[1] - phi[0]

            if nb_steps < nb_frames:  # data has been padded, we suppose it is centered in z dimension
                pad_low = int((nb_frames - nb_steps + ((nb_frames - nb_steps) % 2)) / 2)
                pad_high = int((nb_frames - nb_steps + 1) / 2 - ((nb_frames - nb_steps) % 2))
                phi = np.concatenate((phi[0] + np.arange(-pad_low, 0, 1) * tilt_angle,
                                      phi,
                                      phi[-1] + np.arange(1, pad_high + 1, 1) * tilt_angle), axis=0)
            if nb_steps > nb_frames:  # data has been cropped, we suppose it is centered in z dimension
                phi = phi[(nb_steps - nb_frames) // 2: (nb_steps + nb_frames) // 2]

        elif setup.rocking_angle == 'energy':
            pass
        else:
            raise ValueError('Wrong value for "rocking_angle" parameter')

        delta, gamma, phi, theta, energy = bin_parameters(binning=binning[0], nb_frames=nb_frames,
                                                          params=[delta, gamma, phi, theta, energy])
        qx, qy, qz = hxrd.Ang2Q.area(theta, phi, gamma, delta, en=energy, delta=detector.offsets)

    elif setup.beamline == 'SIXS_2018' or setup.beamline == 'SIXS_2019':
        beta, mu, gamma, delta, frames_logical = motor_positions_sixs(logfile, frames_logical, setup)
        if setup.rocking_angle == 'inplane':  # mu rocking curve
            nb_steps = len(mu)
            tilt_angle = mu[1] - mu[0]

            if nb_steps < nb_frames:  # data has been padded, we suppose it is centered in z dimension
                pad_low = int((nb_frames - nb_steps + ((nb_frames - nb_steps) % 2)) / 2)
                pad_high = int((nb_frames - nb_steps + 1) / 2 - ((nb_frames - nb_steps) % 2))
                mu = np.concatenate((mu[0] + np.arange(-pad_low, 0, 1) * tilt_angle,
                                     mu,
                                     mu[-1] + np.arange(1, pad_high + 1, 1) * tilt_angle), axis=0)
            if nb_steps > nb_frames:  # data has been cropped, we suppose it is centered in z dimension
                mu = mu[(nb_steps - nb_frames) // 2: (nb_steps + nb_frames) // 2]

        else:
            raise ValueError('Out-of-plane rocking curve not implemented for SIXS')
        beta, mu, beta, gamma, delta = bin_parameters(binning=binning[0], nb_frames=nb_frames,
                                                      params=[beta, mu, beta, gamma, delta])
        qx, qy, qz = hxrd.Ang2Q.area(beta, mu, beta, gamma, delta, en=setup.energy, delta=detector.offsets)

    elif setup.beamline == 'CRISTAL':
        mgomega, gamma, delta = motor_positions_cristal(logfile, setup)
        mgomega = mgomega + setup.sample_offsets[2]
        if setup.rocking_angle == 'outofplane':  # mgomega rocking curve
            nb_steps = len(mgomega)
            tilt_angle = mgomega[1] - mgomega[0]

            if nb_steps < nb_frames:  # data has been padded, we suppose it is centered in z dimension
                pad_low = int((nb_frames - nb_steps + ((nb_frames - nb_steps) % 2)) / 2)
                pad_high = int((nb_frames - nb_steps + 1) / 2 - ((nb_frames - nb_steps) % 2))
                mgomega = np.concatenate((mgomega[0] + np.arange(-pad_low, 0, 1) * tilt_angle,
                                          mgomega,
                                          mgomega[-1] + np.arange(1, pad_high + 1, 1) * tilt_angle), axis=0)
            if nb_steps > nb_frames:  # data has been cropped, we suppose it is centered in z dimension
                mgomega = mgomega[(nb_steps - nb_frames) // 2: (nb_steps + nb_frames) // 2]

        else:
            raise ValueError('Inplane rocking curve not implemented for CRISTAL')
        mgomega, gamma, delta = bin_parameters(binning=binning[0], nb_frames=nb_frames, params=[mgomega, gamma, delta])
        qx, qy, qz = hxrd.Ang2Q.area(mgomega, gamma, delta, en=setup.energy, delta=detector.offsets)

    elif setup.beamline == 'P10':
        om, phi, chi, mu, gamma, delta = motor_positions_p10(logfile, setup)
        chi = chi + setup.sample_offsets[0]
        phi = phi + setup.sample_offsets[1]
        om = om + setup.sample_offsets[2]
        if setup.rocking_angle == 'outofplane':  # om rocking curve
            nb_steps = len(om)
            tilt_angle = om[1] - om[0]

            if nb_steps < nb_frames:  # data has been padded, we suppose it is centered in z dimension
                pad_low = int((nb_frames - nb_steps + ((nb_frames - nb_steps) % 2)) / 2)
                pad_high = int((nb_frames - nb_steps + 1) / 2 - ((nb_frames - nb_steps) % 2))
                om = np.concatenate((om[0] + np.arange(-pad_low, 0, 1) * tilt_angle,
                                     om,
                                     om[-1] + np.arange(1, pad_high + 1, 1) * tilt_angle), axis=0)
            if nb_steps > nb_frames:  # data has been cropped, we suppose it is centered in z dimension
                om = om[(nb_steps - nb_frames) // 2: (nb_steps + nb_frames) // 2]

        elif setup.rocking_angle == 'inplane':  # phi rocking curve
            nb_steps = len(phi)
            tilt_angle = phi[1] - phi[0]

            if nb_steps < nb_frames:  # data has been padded, we suppose it is centered in z dimension
                pad_low = int((nb_frames - nb_steps + ((nb_frames - nb_steps) % 2)) / 2)
                pad_high = int((nb_frames - nb_steps + 1) / 2 - ((nb_frames - nb_steps) % 2))
                phi = np.concatenate((phi[0] + np.arange(-pad_low, 0, 1) * tilt_angle,
                                      phi,
                                      phi[-1] + np.arange(1, pad_high + 1, 1) * tilt_angle), axis=0)
            if nb_steps > nb_frames:  # data has been cropped, we suppose it is centered in z dimension
                phi = phi[(nb_steps - nb_frames) // 2: (nb_steps + nb_frames) // 2]

        else:
            raise ValueError('Wrong value for "rocking_angle" parameter')
        mu, om, chi, phi, gamma, delta = bin_parameters(binning=binning[0], nb_frames=nb_frames,
                                                        params=[mu, om, chi, phi, gamma, delta])
        qx, qy, qz = hxrd.Ang2Q.area(mu, om, chi, phi, gamma, delta, en=setup.energy, delta=detector.offsets)

    elif setup.beamline == '34ID':
        mu, phi, chi, theta, delta, gamma = motor_positions_34id(setup)
        chi = chi + setup.sample_offsets[0]
        theta = theta + setup.sample_offsets[1]  # theta is the inplane rotation
        phi = phi + setup.sample_offsets[2]  # phi is the incident angle
        if setup.rocking_angle == 'outofplane':  # phi rocking curve
            nb_steps = len(phi)
            tilt_angle = phi[1] - phi[0]

            if nb_steps < nb_frames:  # data has been padded, we suppose it is centered in z dimension
                pad_low = int((nb_frames - nb_steps + ((nb_frames - nb_steps) % 2)) / 2)
                pad_high = int((nb_frames - nb_steps + 1) / 2 - ((nb_frames - nb_steps) % 2))
                phi = np.concatenate((phi[0] + np.arange(-pad_low, 0, 1) * tilt_angle,
                                      phi,
                                      phi[-1] + np.arange(1, pad_high + 1, 1) * tilt_angle), axis=0)
            if nb_steps > nb_frames:  # data has been cropped, we suppose it is centered in z dimension
                phi = phi[(nb_steps - nb_frames) // 2: (nb_steps + nb_frames) // 2]

        elif setup.rocking_angle == 'inplane':  # theta rocking curve
            nb_steps = len(theta)
            tilt_angle = theta[1] - theta[0]

            if nb_steps < nb_frames:  # data has been padded, we suppose it is centered in z dimension
                pad_low = int((nb_frames - nb_steps + ((nb_frames - nb_steps) % 2)) / 2)
                pad_high = int((nb_frames - nb_steps + 1) / 2 - ((nb_frames - nb_steps) % 2))
                theta = np.concatenate((theta[0] + np.arange(-pad_low, 0, 1) * tilt_angle,
                                        theta,
                                        theta[-1] + np.arange(1, pad_high + 1, 1) * tilt_angle), axis=0)
            if nb_steps > nb_frames:  # data has been cropped, we suppose it is centered in z dimension
                theta = theta[(nb_steps - nb_frames) // 2: (nb_steps + nb_frames) // 2]

        elif setup.rocking_angle == 'energy':
            pass

        else:
            raise ValueError('Wrong value for "rocking_angle" parameter')
        mu, phi, chi, theta, delta, gamma = bin_parameters(binning=binning[0], nb_frames=nb_frames,
                                                           params=[mu, phi, chi, theta, delta, gamma])
        qx, qy, qz = hxrd.Ang2Q.area(mu, phi, chi, theta, delta, gamma, en=setup.energy, delta=detector.offsets)

    else:
        raise ValueError('Wrong value for "beamline" parameter: beamline not supported')

    return qx, qz, qy, frames_logical


def regrid_cdi(data, mask, logfile, detector, setup, frames_logical, correct_curvature=False, debugging=False):
    """
    Interpolate forward CDI data from the cylindrical frame to the reciprocal frame in cartesian coordinates.
     Note that it is based on PetraIII P10 beamline (counterclockwise rotation, detector seen from the front).

    :param data: the 3D data, already binned in the detector frame
    :param mask: the corresponding 3D mask
    :param logfile: file containing the information about the scan and image numbers (specfile, .fio...)
    :param detector: the detector object: Class experiment_utils.Detector(). The detector orientation is supposed to
     follow the CXI convention: (z downstream, y vertical up, x outboard) Y opposite to y, X opposite to x
    :param setup: the experimental setup: Class SetupPreprocessing()
    :param frames_logical: array of initial length the number of measured frames. In case of padding the length changes.
     A frame whose index is set to 1 means that it is used, 0 means not used, -1 means padded (added) frame.
    :param correct_curvature: if True, will correct for the curvature of the Ewald sphere
    :param debugging: set to True to see plots
    :return: the data and mask interpolated in the laboratory frame, q values (downstream, vertical up, outboard)
    """

    if data.ndim != 3:
        raise ValueError('data is expected to be a 3D array')
    if mask.ndim != 3:
        raise ValueError('mask is expected to be a 3D array')
    if setup.beamline == 'P10':
        if setup.rocking_angle == 'inplane':
            cdi_angle = motor_positions_p10_saxs(logfile, setup)
        else:
            raise ValueError('out-of-plane rotation not yet implemented for forward CDI data')
    else:
        raise ValueError('Not yet implemented for beamlines other than P10')

    wavelength = setup.wavelength * 1e9  # convert to nm
    distance = setup.distance * 1e9  # convert to nm
    pixel_x = detector.pixelsize_x * 1e9  # convert to nm, binned pixel size in the horizontal direction
    pixel_y = detector.pixelsize_y * 1e9  # convert to nm, binned pixel size in the vertical direction
    lambdaz = wavelength * distance
    directbeam_y = int((setup.direct_beam[0] - detector.roi[0]) / detector.binning[1])  # vertical
    directbeam_x = int((setup.direct_beam[1] - detector.roi[2]) / detector.binning[2])  # horizontal
    print('\nDirect beam for the ROI and binning (y, x):', directbeam_y, directbeam_x)

    data, mask, cdi_angle, frames_logical = check_cdi_angle(data=data, mask=mask, cdi_angle=cdi_angle,
                                                            frames_logical=frames_logical, debugging=debugging)
    if debugging:
        print('\ncdi_angle', cdi_angle)
    nbz, nby, nbx = data.shape
    print('\nData shape after check_cdi_angle and before regridding:', nbz, nby, nbx)
    print('\nAngle range:', cdi_angle.min(), cdi_angle.max())

    # calculate the number of voxels available to accomodate the gridded data
    # directbeam_x and directbeam_y already are already taking into account the ROI and binning
    numx = 2 * max(directbeam_x, nbx - directbeam_x)  # number of interpolated voxels in the plane perpendicular
    # to the rotation axis. It will accomodate the full data range.
    numy = nby  # no change of the voxel numbers along the rotation axis
    print('\nData shape after regridding:', numx, numy, numx)

    # update the direct beam position due to an eventual padding along X
    if nbx-directbeam_x < directbeam_x:
        pivot = directbeam_x
    else:  # padding to the left along x, need to correct the pivot position
        pivot = nbx - directbeam_x

    if not correct_curvature:
        dqx = 2 * np.pi / lambdaz * pixel_x  # in 1/nm, downstream, pixel_x is the binned pixel size
        dqz = 2 * np.pi / lambdaz * pixel_y  # in 1/nm, vertical up, pixel_y is the binned pixel size
        dqy = 2 * np.pi / lambdaz * pixel_x  # in 1/nm, outboard, pixel_x is the binned pixel size

        # calculation of q based on P10 geometry
        qx = np.arange(-directbeam_x, -directbeam_x + numx, 1) * dqx
        # downstream, same direction as detector X rotated by +90deg
        qz = np.arange(directbeam_y-numy, directbeam_y, 1) * dqz  # vertical up opposite to detector Y
        qy = np.arange(directbeam_x-numx, directbeam_x, 1) * dqy  # outboard opposite to detector X
        print('q spacing for interpolation (z,y,x)=', str('{:.6f}'.format(dqx)), str('{:.6f}'.format(dqz)),
              str('{:.6f}'.format(dqy)), ' (1/nm)')

        # find the corresponding polar coordinates of a cartesian 2D grid perpendicular to the rotation axis
        interp_angle, interp_radius = cartesian2polar(nb_pixels=numx, pivot=pivot, offset_angle=cdi_angle.min(),
                                                      debugging=debugging)

        interp_data = grid_cylindrical(array=data, rotation_angle=cdi_angle, direct_beam=directbeam_x,
                                       interp_angle=interp_angle, interp_radius=interp_radius)

        interp_mask = grid_cylindrical(array=mask, rotation_angle=cdi_angle, direct_beam=directbeam_x,
                                       interp_angle=interp_angle, interp_radius=interp_radius)

        interp_mask[np.nonzero(interp_mask)] = 1

    else:
        import sys
        print('#TODO check Ewald sphere curvature correction')
        sys.exit()
        # TODO check Ewald sphere curvature correction
        from scipy.interpolate import griddata
        # calculate exact q values for each voxel of the 3D dataset
        old_qx, old_qz, old_qy = ewald_curvature_saxs(cdi_angle=cdi_angle, detector=detector, setup=setup)

        # create the grid for interpolation
        qx = np.linspace(old_qz.min(), old_qz.max(), numx, endpoint=False)  # z downstream
        qz = np.linspace(old_qy.min(), old_qy.max(), numy, endpoint=False)  # y vertical up
        qy = np.linspace(old_qx.min(), old_qx.max(), numx, endpoint=False)  # x outboard

        new_qx, new_qz, new_qy = np.meshgrid(qx, qz, qy, indexing='ij')

        # interpolate the data onto the new points using griddata (the original grid is not regular)
        interp_data = griddata(
            np.array([np.ndarray.flatten(old_qx), np.ndarray.flatten(old_qz), np.ndarray.flatten(old_qy)]).T,
            np.ndarray.flatten(data),
            np.array([np.ndarray.flatten(new_qx), np.ndarray.flatten(new_qz), np.ndarray.flatten(new_qy)]).T,
            method='linear', fill_value=np.nan)
        interp_data = interp_data.reshape((numx, numy, numx)).astype(data.dtype)

        # interpolate the mask onto the new points
        interp_mask = griddata(
            np.array([np.ndarray.flatten(old_qx), np.ndarray.flatten(old_qz), np.ndarray.flatten(old_qy)]).T,
            np.ndarray.flatten(mask),
            np.array([np.ndarray.flatten(new_qx), np.ndarray.flatten(new_qz), np.ndarray.flatten(new_qy)]).T,
            method='linear', fill_value=np.nan)
        interp_mask = interp_mask.reshape((numx, numy, numx)).astype(mask.dtype)

    # check for Nan
    interp_mask[np.isnan(interp_data)] = 1
    interp_data[np.isnan(interp_data)] = 0
    interp_mask[np.isnan(interp_mask)] = 1
    
    # apply the mask to the data
    interp_data[np.nonzero(interp_mask)] = 0

    # calculate the position in pixels of the origin of the reciprocal space
    pivot_z = int((setup.direct_beam[1] - detector.roi[2]) / detector.binning[2])
    # 90 degrees conter-clockwise rotation of detector X around qz, downstream
    pivot_y = int(numy - directbeam_y)  # detector Y vertical down, opposite to qz vertical up
    pivot_x = int(numx - directbeam_x)  # detector X inboard at P10, opposite to qy outboard
    print("\nOrigin of the reciprocal space  (Qx,Qz,Qy): " + str(pivot_z) + "," + str(pivot_y) + "," + str(pivot_x)
          + '\n')

    # plot the gridded data
    binning = detector.binning  # only used for figure name when saving
    # sample rotation around the vertical direction at P10: the effective binning in axis 0 is binning[2]
    fig, _, _ = gu.contour_slices(interp_data, (qx, qz, qy), sum_frames=True, title='Regridded data',
                                  levels=np.linspace(0, int(np.log10(interp_data.max())), 150, endpoint=False),
                                  plot_colorbar=True, scale='log', is_orthogonal=True, reciprocal_space=True)
    fig.text(0.55, 0.30, 'Origin of the reciprocal space (Qx,Qz,Qy):\n\n' +
             '     ({:d}, {:d}, {:d})'.format(pivot_z, pivot_y, pivot_x), size=14)
    fig.savefig(detector.savedir + 'reciprocal_space_' + str(numx)+'_' + str(numy) + '_' + str(numx) +
                '_' + str(binning[2]) + '_' + str(binning[1]) + '_' + str(binning[2]) + '.png')
    plt.close(fig)

    fig, _, _ = gu.contour_slices(interp_data, (qx, qz, qy), sum_frames=False, title='Regridded data - central slice',
                                  levels=np.linspace(0, int(np.log10(interp_data.max())), 150, endpoint=False),
                                  plot_colorbar=True, scale='log', is_orthogonal=True, reciprocal_space=True)
    fig.text(0.55, 0.30, 'Origin of the reciprocal space (Qx,Qz,Qy):\n\n' +
             '     ({:d}, {:d}, {:d})'.format(pivot_z, pivot_y, pivot_x), size=14)
    fig.savefig(detector.savedir + 'reciprocal_space_central_'+str(numx)+'_'+str(numy)+'_'+str(numx) +
                '_' + str(binning[2]) + '_' + str(binning[1]) + '_' + str(binning[2]) + '.png')
    plt.close(fig)

    fig, _, _ = gu.multislices_plot(interp_data, sum_frames=False, scale='log', plot_colorbar=True, vmin=0,
                                    title='Regridded data - pixels', is_orthogonal=True, reciprocal_space=True)
    fig.text(0.55, 0.30, 'Origin of the reciprocal space (Qx,Qz,Qy):\n\n' +
             '     ({:d}, {:d}, {:d})'.format(pivot_z, pivot_y, pivot_x), size=14)
    fig.savefig(detector.savedir + 'reciprocal_space_central_pix_' + str(numx) + '_' + str(numy) + '_' + str(
        numx) + '_' + str(binning[2]) + '_' + str(binning[1]) + '_' + str(binning[2]) + '.png')
    plt.close(fig)
    if debugging:
        gu.multislices_plot(interp_mask, sum_frames=False, scale='linear', plot_colorbar=True, vmin=0,
                            title='Regridded mask', is_orthogonal=True, reciprocal_space=True)

    return interp_data, interp_mask, [qx, qz, qy], frames_logical


def remove_hotpixels(data, mask, hotpixels=None):
    """
    Remove hot pixels from CCD frames and update the mask.

    :param data: 2D or 3D array
    :param hotpixels: 2D array of hotpixels. 1 for a hotpixel, 0 for normal pixels.
    :param mask: array of the same shape as data
    :return: the data without hotpixels and the updated mask
    """
    if hotpixels is None:
        hotpixels = np.zeros(data.shape)
    if hotpixels.ndim == 3:  # 3D array
        print('Hotpixels is a 3D array, summing along the first axis')
        hotpixels = hotpixels.sum(axis=0)
        hotpixels[np.nonzero(hotpixels)] = 1  # hotpixels should be a binary array

    if data.shape != mask.shape:
        raise ValueError('Data and mask must have the same shape\n data is ', data.shape, ' while mask is ', mask.shape)

    if data.ndim == 3:  # 3D array
        if data[0, :, :].shape != hotpixels.shape:
            raise ValueError('Data and hotpixels must have the same shape\n data is ',
                             data.shape, ' while hotpixels is ', hotpixels.shape)
        for idx in range(data.shape[0]):
            temp_data = data[idx, :, :]
            temp_mask = mask[idx, :, :]
            temp_data[hotpixels == 1] = 0  # numpy array is mutable hence data will be modified
            temp_mask[hotpixels == 1] = 1  # numpy array is mutable hence mask will be modified
    elif data.ndim == 2:  # 2D array
        if data.shape != hotpixels.shape:
            raise ValueError('Data and hotpixels must have the same shape\n data is ',
                             data.shape, ' while hotpixels is ', hotpixels.shape)
        data[hotpixels == 1] = 0
        mask[hotpixels == 1] = 1
    else:
        raise ValueError('2D or 3D data array expected, got ', data.ndim, 'D')
    return data, mask


def smaller_primes(number, maxprime=13, required_dividers=(4,)):
    """
    Find the closest integer <=n (or list/array of integers), for which the largest prime divider is <=maxprime,
    and has to include some dividers. The default values for maxprime is the largest integer accepted
    by the clFFT library for OpenCL GPU FFT. Adapted from PyNX.

    :param number: the integer number
    :param maxprime: the largest prime factor acceptable
    :param required_dividers: a list of required dividers for the returned integer.
    :return: the integer (or list/array of integers) fulfilling the requirements
    """
    if (type(number) is list) or (type(number) is tuple) or (type(number) is np.ndarray):
        vn = []
        for i in number:
            assert (i > 1 and maxprime <= i), "Number is < " + str(maxprime)
            while try_smaller_primes(i, maxprime=maxprime, required_dividers=required_dividers) is False:
                i = i - 1
                if i == 0:
                    return 0
            vn.append(i)
        if type(number) is np.ndarray:
            return np.array(vn)
        return vn
    else:
        assert (number > 1 and maxprime <= number), "Number is < " + str(maxprime)
        while try_smaller_primes(number, maxprime=maxprime, required_dividers=required_dividers) is False:
            number = number - 1
            if number == 0:
                return 0
        return number


def try_smaller_primes(number, maxprime=13, required_dividers=(4,)):
    """
    Check if the largest prime divider is <=maxprime, and optionally includes some dividers. Adapted from PyNX.

    :param number: the integer number for which the prime decomposition will be checked
    :param maxprime: the maximum acceptable prime number. This defaults to the largest integer accepted by the clFFT
        library for OpenCL GPU FFT.
    :param required_dividers: list of required dividers in the prime decomposition. If None, this check is skipped.
    :return: True if the conditions are met.
    """
    p = primes(number)
    if max(p) > maxprime:
        return False
    if required_dividers is not None:
        for k in required_dividers:
            if number % k != 0:
                return False
    return True


def update_aliens(key, pix, piy, original_data, original_mask, updated_data, updated_mask, figure, width, dim, idx,
                  vmax, vmin=0, invert_yaxis=False):
    """
    Update the plot while removing the parasitic diffraction intensity in 3D dataset

    :param key: the keyboard key which was pressed
    :param pix: the x value of the mouse pointer
    :param piy: the y value of the mouse pointer
    :param original_data: the 3D data array before masking aliens
    :param original_mask: the 3D mask array before masking aliens
    :param updated_data: the current 3D data array
    :param updated_mask: the current 3D mask array
    :param figure: the figure instance
    :param width: the half_width of the masking window
    :param dim: the axis currently under review (axis 0, 1 or 2)
    :param idx: the frame index in the current axis
    :param vmax: the higher boundary for the colorbar
    :param vmin: the lower boundary for the colorbar
    :param invert_yaxis: True to invert the y axis of imshow plots
    :return: updated data, mask and controls
    """
    if original_data.ndim != 3 or updated_data.ndim != 3 or original_mask.ndim != 3 or updated_mask.ndim != 3:
        raise ValueError('original_data, original_mask, updated_data and updated_mask should be 3D arrays')

    nbz, nby, nbx = original_data.shape
    stop_masking = False
    if dim not in [0, 1, 2]:
        raise ValueError('dim should be 0, 1 or 2')

    axs = figure.gca()
    xmin, xmax = axs.get_xlim()
    ymin, ymax = axs.get_ylim()
    if key == 'u':  # show next frame
        idx = idx + 1
        if dim == 0:
            if idx > nbz - 1:
                idx = 0
        elif dim == 1:
            if idx > nby - 1:
                idx = 0
        else:  # dim=2
            if idx > nbx - 1:
                idx = 0

    elif key == 'd':  # show previous frame
        idx = idx - 1
        if dim == 0:
            if idx < 0:
                idx = nbz - 1
        elif dim == 1:
            if idx < 0:
                idx = nby - 1
        else:  # dim=2
            if idx < 0:
                idx = nbx - 1

    elif key == 'up':
        width = width + 1

    elif key == 'down':
        width = width - 1
        if width < 0:
            width = 0

    elif key == 'right':  # increase colobar max
        vmax = vmax * 2

    elif key == 'left':  # reduce colobar max
        vmax = vmax / 2
        if vmax < 1:
            vmax = 1

    elif key == 'm':  # mask intensities
        if (piy - width) < 0:
            starty = 0
        else:
            starty = piy - width
        if (pix - width) < 0:
            startx = 0
        else:
            startx = pix - width
        if dim == 0:
            updated_data[idx, starty:piy + width + 1, startx:pix + width + 1] = 0
            updated_mask[idx, starty:piy + width + 1, startx:pix + width + 1] = 1
        elif dim == 1:
            updated_data[starty:piy + width + 1, idx, startx:pix + width + 1] = 0
            updated_mask[starty:piy + width + 1, idx, startx:pix + width + 1] = 1
        else:  # dim=2
            updated_data[starty:piy + width + 1, startx:pix + width + 1, idx] = 0
            updated_mask[starty:piy + width + 1, startx:pix + width + 1, idx] = 1

    elif key == 'b':  # back to measured intensities
        if (piy - width) < 0:
            starty = 0
        else:
            starty = piy - width
        if (pix - width) < 0:
            startx = 0
        else:
            startx = pix - width
        if dim == 0:
            updated_data[idx, starty:piy + width + 1, startx:pix + width + 1] = \
                original_data[idx, starty:piy + width + 1, startx:pix + width + 1]
            updated_mask[idx, starty:piy + width + 1, startx:pix + width + 1] = \
                original_mask[idx, starty:piy + width + 1, startx:pix + width + 1]

        elif dim == 1:
            updated_data[starty:piy + width + 1, idx, startx:pix + width + 1] = \
                original_data[starty:piy + width + 1, idx, startx:pix + width + 1]
            updated_mask[starty:piy + width + 1, idx, startx:pix + width + 1] = \
                original_mask[starty:piy + width + 1, idx, startx:pix + width + 1]
        else:  # dim=2
            updated_data[starty:piy + width + 1, startx:pix + width + 1, idx] = \
                original_data[starty:piy + width + 1, startx:pix + width + 1, idx]
            updated_mask[starty:piy + width + 1, startx:pix + width + 1, idx] = \
                original_mask[starty:piy + width + 1, startx:pix + width + 1, idx]

    elif key == 'p' or key == 'a':  # plot full image or restart masking
        if dim == 0:
            xmin, xmax = -0.5, nbx - 0.5
            if invert_yaxis:
                ymin, ymax = -0.5, nby - 0.5  # pointing up
            else:
                ymin, ymax = nby - 0.5, -0.5  # pointing down
        elif dim == 1:
            xmin, xmax = -0.5, nbx - 0.5
            ymin, ymax = nbz - 0.5, -0.5  # pointing down
        else:  # dim=2
            xmin, xmax = -0.5, nby - 0.5
            ymin, ymax = nbz - 0.5, -0.5  # pointing down
        if key == 'a':  # restart masking
            updated_data[:] = original_data[:]
            updated_mask[:] = original_mask[:]

    elif key == 'q':
        stop_masking = True

    else:
        return updated_data, updated_mask, width, vmax, idx, stop_masking

    axs.cla()
    if dim == 0:
        axs.imshow(updated_data[idx, :, ], vmin=vmin, vmax=vmax)
        axs.set_title("XY - Frame " + str(idx + 1) + "/" + str(nbz) + "\n"
                      "m mask ; b unmask ; q quit ; u next frame ; d previous frame\n"
                      "up larger ; down smaller ; right darker ; left brighter")
    elif dim == 1:
        axs.imshow(updated_data[:, idx, :], vmin=vmin, vmax=vmax)
        axs.set_title("XZ - Frame " + str(idx + 1) + "/" + str(nby) + "\n"
                      "m mask ; b unmask ; q quit ; u next frame ; d previous frame\n"
                      "up larger ; down smaller ; right darker ; left brighter")
    elif dim == 2:
        axs.imshow(updated_data[:, :, idx], vmin=vmin, vmax=vmax)
        axs.set_title("YZ - Frame " + str(idx + 1) + "/" + str(nbx) + "\n"
                      "m mask ; b unmask ; q quit ; u next frame ; d previous frame\n"
                      "up larger ; down smaller ; right darker ; left brighter")
    if invert_yaxis:
        axs.invert_yaxis()
    axs.set_xlim([xmin, xmax])
    axs.set_ylim([ymin, ymax])
    plt.draw()

    return updated_data, updated_mask, width, vmax, idx, stop_masking


def update_aliens_combined(key, pix, piy, original_data, original_mask, updated_data, updated_mask, axes, width, dim,
                           frame_index, vmax, vmin=0, invert_yaxis=False):
    """
    Update the plot while removing the parasitic diffraction intensity in 3D dataset

    :param key: the keyboard key which was pressed
    :param pix: the x value of the mouse pointer
    :param piy: the y value of the mouse pointer
    :param original_data: the 3D data array before masking aliens
    :param original_mask: the 3D mask array before masking aliens
    :param updated_data: the current 3D data array
    :param updated_mask: the current 3D mask array
    :param axes: tuple of the 4 axes instances in a plt.subplots(nrows=2, ncols=2)
    :param width: the half_width of the masking window
    :param dim: the axis currently under review (axis 0, 1 or 2)
    :param frame_index: list of 3 frame indices (one per axis)
    :param vmax: the higher boundary for the colorbar
    :param vmin: the lower boundary for the colorbar
    :param invert_yaxis: True to invert the y axis of imshow plots
    :return: updated data, mask and controls
    """
    if original_data.ndim != 3 or updated_data.ndim != 3 or original_mask.ndim != 3 or updated_mask.ndim != 3:
        raise ValueError('original_data, updated_data and updated_mask should be 3D arrays')

    nbz, nby, nbx = original_data.shape
    stop_masking = False
    if dim not in [0, 1, 2]:
        raise ValueError('dim should be 0, 1 or 2')

    xmin0, xmax0 = axes[0].get_xlim()
    ymin0, ymax0 = axes[0].get_ylim()
    xmin1, xmax1 = axes[1].get_xlim()
    ymin1, ymax1 = axes[1].get_ylim()
    xmin2, xmax2 = axes[2].get_xlim()
    ymin2, ymax2 = axes[2].get_ylim()

    if key == 'u':  # show next frame
        if dim == 0:
            frame_index[0] = frame_index[0] + 1
            if frame_index[0] > nbz - 1:
                frame_index[0] = 0
        elif dim == 1:
            frame_index[1] = frame_index[1] + 1
            if frame_index[1] > nby - 1:
                frame_index[1] = 0
        else:  # dim=2
            frame_index[2] = frame_index[2] + 1
            if frame_index[2] > nbx - 1:
                frame_index[2] = 0

    elif key == 'd':  # show previous frame
        if dim == 0:
            frame_index[0] = frame_index[0] - 1
            if frame_index[0] < 0:
                frame_index[0] = nbz - 1
        elif dim == 1:
            frame_index[1] = frame_index[1] - 1
            if frame_index[1] < 0:
                frame_index[1] = nby - 1
        else:  # dim=2
            frame_index[2] = frame_index[2] - 1
            if frame_index[2] < 0:
                frame_index[2] = nbx - 1

    elif key == 'up':
        width = width + 1

    elif key == 'down':
        width = width - 1
        if width < 0:
            width = 0

    elif key == 'right':  # increase colobar max
        vmax = vmax * 2

    elif key == 'left':  # reduce colobar max
        vmax = vmax / 2
        if vmax < 1:
            vmax = 1

    elif key == 'm':  # mask intensities
        if (piy - width) < 0:
            starty = 0
        else:
            starty = piy - width
        if (pix - width) < 0:
            startx = 0
        else:
            startx = pix - width
        if dim == 0:
            updated_data[frame_index[0], starty:piy + width + 1, startx:pix + width + 1] = 0
            updated_mask[frame_index[0], starty:piy + width + 1, startx:pix + width + 1] = 1
        elif dim == 1:
            updated_data[starty:piy + width + 1, frame_index[1], startx:pix + width + 1] = 0
            updated_mask[starty:piy + width + 1, frame_index[1], startx:pix + width + 1] = 1
        else:  # dim=2
            updated_data[starty:piy + width + 1, startx:pix + width + 1, frame_index[2]] = 0
            updated_mask[starty:piy + width + 1, startx:pix + width + 1, frame_index[2]] = 1

    elif key == 'b':  # back to measured intensities
        if (piy - width) < 0:
            starty = 0
        else:
            starty = piy - width
        if (pix - width) < 0:
            startx = 0
        else:
            startx = pix - width
        if dim == 0:
            updated_data[frame_index[0], starty:piy + width + 1, startx:pix + width + 1] = \
                original_data[frame_index[0], starty:piy + width + 1, startx:pix + width + 1]
            updated_mask[frame_index[0], starty:piy + width + 1, startx:pix + width + 1] = \
                original_mask[frame_index[0], starty:piy + width + 1, startx:pix + width + 1]
        elif dim == 1:
            updated_data[starty:piy + width + 1, frame_index[1], startx:pix + width + 1] = \
                original_data[starty:piy + width + 1, frame_index[1], startx:pix + width + 1]
            updated_mask[starty:piy + width + 1, frame_index[1], startx:pix + width + 1] = \
                original_mask[starty:piy + width + 1, frame_index[1], startx:pix + width + 1]
        else:  # dim=2
            updated_data[starty:piy + width + 1, startx:pix + width + 1, frame_index[2]] = \
                original_data[starty:piy + width + 1, startx:pix + width + 1, frame_index[2]]
            updated_mask[starty:piy + width + 1, startx:pix + width + 1, frame_index[2]] = \
                original_mask[starty:piy + width + 1, startx:pix + width + 1, frame_index[2]]

    elif key == 'p' or key == 'a':  # plot full image or restart masking
        xmin0, xmax0 = -0.5, nbx - 0.5
        if invert_yaxis:
            ymin0, ymax0 = -0.5, nby - 0.5  # pointing up
        else:
            ymin0, ymax0 = nby - 0.5, -0.5  # pointing down
        xmin1, xmax1 = -0.5, nbx - 0.5
        ymin1, ymax1 = nbz - 0.5, -0.5  # pointing down
        xmin2, xmax2 = -0.5, nby - 0.5
        ymin2, ymax2 = nbz - 0.5, -0.5  # pointing down
        if key == 'a':  # restart masking
            updated_data[:] = original_data[:]
            updated_mask[:] = original_mask[:]

    elif key == 'q':
        stop_masking = True

    else:
        return updated_data, updated_mask, width, vmax, frame_index, stop_masking

    axes[0].cla()
    axes[1].cla()
    axes[2].cla()
    axes[0].imshow(updated_data[frame_index[0], :, :], vmin=vmin, vmax=vmax)
    axes[1].imshow(updated_data[:, frame_index[1], :], vmin=vmin, vmax=vmax)
    axes[2].imshow(updated_data[:, :, frame_index[2]], vmin=vmin, vmax=vmax)
    axes[0].set_title("XY - Frame " + str(frame_index[0] + 1) + "/" + str(nbz))
    axes[0].axis('scaled')
    if invert_yaxis:
        axes[0].invert_yaxis()
    axes[0].set_xlim([xmin0, xmax0])
    axes[0].set_ylim([ymin0, ymax0])
    axes[1].set_title("XZ - Frame " + str(frame_index[1] + 1) + "/" + str(nby))
    axes[1].axis('scaled')
    axes[1].set_xlim([xmin1, xmax1])
    axes[1].set_ylim([ymin1, ymax1])
    axes[2].set_title("YZ - Frame " + str(frame_index[2] + 1) + "/" + str(nbx))
    axes[2].axis('scaled')
    axes[2].set_xlim([xmin2, xmax2])
    axes[2].set_ylim([ymin2, ymax2])
    plt.draw()

    return updated_data, updated_mask, width, vmax, frame_index, stop_masking


def update_aliens_2d(key, pix, piy, original_data, original_mask, updated_data, updated_mask, figure, width,
                     vmax, vmin=0, invert_yaxis=False):
    """
    Update the plot while removing the parasitic diffraction intensity in 2D dataset

    :param key: the keyboard key which was pressed
    :param pix: the x value of the mouse pointer
    :param piy: the y value of the mouse pointer
    :param original_data: the 2D data array before masking aliens
    :param original_mask: the 3D mask array before masking aliens
    :param updated_data: the current 2D data array
    :param updated_mask: the current 2D mask array
    :param figure: the figure instance
    :param width: the half_width of the masking window
    :param vmax: the higher boundary for the colorbar
    :param vmin: the lower boundary for the colorbar
    :param invert_yaxis: True to invert the y axis of imshow plots
    :return: updated data, mask and controls
    """
    if original_data.ndim != 2 or updated_data.ndim != 2 or original_mask.ndim != 2or updated_mask.ndim != 2:
        raise ValueError('original_data, updated_data and updated_mask should be 2D arrays')

    nby, nbx = original_data.shape
    stop_masking = False

    axs = figure.gca()
    xmin, xmax = axs.get_xlim()
    ymin, ymax = axs.get_ylim()

    if key == 'up':
        width = width + 1

    elif key == 'down':
        width = width - 1
        if width < 0:
            width = 0

    elif key == 'right':
        vmax = vmax * 2

    elif key == 'left':
        vmax = vmax / 2
        if vmax < 1:
            vmax = 1

    elif key == 'm':
        if (piy - width) < 0:
            starty = 0
        else:
            starty = piy - width
        if (pix - width) < 0:
            startx = 0
        else:
            startx = pix - width
        updated_data[starty:piy + width + 1, startx:pix + width + 1] = 0
        updated_mask[starty:piy + width + 1, startx:pix + width + 1] = 1

    elif key == 'b':
        if (piy - width) < 0:
            starty = 0
        else:
            starty = piy - width
        if (pix - width) < 0:
            startx = 0
        else:
            startx = pix - width
        updated_data[starty:piy + width + 1, startx:pix + width + 1] = \
            original_data[starty:piy + width + 1, startx:pix + width + 1]
        updated_mask[starty:piy + width + 1, startx:pix + width + 1] = \
            original_mask[starty:piy + width + 1, startx:pix + width + 1]

    elif key == 'p' or key == 'a':  # plot full image or restart masking
        xmin, xmax = -0.5, nbx - 0.5
        if invert_yaxis:
            ymin, ymax = -0.5, nby - 0.5  # pointing up
        else:
            ymin, ymax = nby - 0.5, -0.5  # pointing down
        if key == 'a':  # restart masking
            updated_data[:] = original_data[:]
            updated_mask[:] = original_mask[:]

    elif key == 'q':
        stop_masking = True

    else:
        return updated_data, updated_mask, width, vmax, stop_masking

    axs.cla()
    axs.imshow(updated_data, vmin=vmin, vmax=vmax)
    axs.set_title("m mask ; b unmask ; q quit ; u next frame ; d previous frame\n"
                  "up larger ; down smaller ; right darker ; left brighter")
    if invert_yaxis:
        axs.invert_yaxis()
    axs.set_xlim([xmin, xmax])
    axs.set_ylim([ymin, ymax])
    plt.draw()

    return updated_data, updated_mask, width, vmax, stop_masking


def update_background(key, distances, data, figure, flag_pause, xy, scale='log', xlim=None, ylim=None):
    """
    Define the background for a 1D reciprocal space dataset.

    :param key: the keyboard key which was pressed
    :param distances: x axis for data
    :param data: the 1D data before background subtraction
    :param figure: the figure instance
    :param flag_pause: set to 1 to stop registering vertices using mouse clicks
    :param xy: the list of vertices which defines a polygon to be masked
    :param scale: scale of data, 'linear' or 'log'
    :param xlim: x axis plot limits
    :param ylim: y axis plot limits
    :return: updated background and controls
    """
    if data.ndim != 1:
        raise ValueError('data is expected to be a 1D array')
    axs = figure.gca()
    if xlim is None:
        xmin, xmax = axs.get_xlim()
    else:
        xmin, xmax = xlim
    if ylim is None:
        ymin, ymax = axs.get_ylim()
    else:
        ymin, ymax = ylim

    stop_masking = False
    xy = sorted(xy, key=itemgetter(0))

    if key == 'b':  # remove the last selected background point
        xy.pop()

    elif key == 'a':  # restart background selection from the beginning
        xy = []
        print('restart background selection')

    elif key == 'p':  # plot background
        pass

    elif key == 'x':
        if not flag_pause:
            flag_pause = True
            print('pause for pan/zoom')
        else:
            flag_pause = False
            print('resume masking')

    elif key == 'q':
        stop_masking = True

    else:
        return flag_pause, xy, stop_masking

    background = np.asarray(xy)
    axs.cla()
    if len(xy) != 0:
        if scale == 'linear':
            axs.plot(distances, data, '.-r', background[:, 0], background[:, 1], 'b')
        else:
            axs.plot(distances, np.log10(data), '.-r',
                     background[:, 0], background[:, 1], 'b')  # background is in log scale directly
    else:  # restart background selection
        if scale == 'linear':
            axs.plot(distances, data, '.-r')
        else:
            axs.plot(distances, np.log10(data), '.-r')
    axs.set_xlim([xmin, xmax])
    axs.set_ylim([ymin, ymax])
    axs.set_xlabel('q (1/nm)')
    axs.set_ylabel('Angular average (A.U.)')
    axs.set_title("Click to select background points\nx to pause/resume for pan/zoom\n"
                  "a restart ; p plot background ; q quit")
    plt.draw()

    return flag_pause, xy, stop_masking


def update_mask(key, pix, piy, original_data, original_mask, updated_data, updated_mask, figure, flag_pause, points,
                xy, width, dim, vmax, vmin=0, masked_color=0.1, invert_yaxis=False):
    """
    Update the mask to remove parasitic diffraction intensity and hotpixels in 3D dataset.

    :param key: the keyboard key which was pressed
    :param pix: the x value of the mouse pointer
    :param piy: the y value of the mouse pointer
    :param original_data: the 3D data array before masking
    :param original_mask: the 3D mask array before masking
    :param updated_data: the current 3D data array
    :param updated_mask: the temporary 2D mask array with updated points
    :param figure: the figure instance
    :param flag_pause: set to 1 to stop registering vertices using mouse clicks
    :param points: list of all point coordinates: points=np.stack((x, y), axis=0).T with x=x.flatten() , y = y.flatten()
     given x,y=np.meshgrid(np.arange(nx), np.arange(ny))
    :param xy: the list of vertices which defines a polygon to be masked
    :param width: the half_width of the masking window
    :param dim: the axis currently under review (axis 0, 1 or 2)
    :param vmax: the higher boundary for the colorbar
    :param vmin: the lower boundary for the colorbar
    :param masked_color: the value that detector gaps should have in plots
    :param invert_yaxis: True to invert the y axis of imshow plots
    :return: updated data, mask and controls
    """
    if original_data.ndim != 3 or updated_data.ndim != 3 or original_mask.ndim != 3:
        raise ValueError('original_data, updated_data and original_mask should be 3D arrays')
    if updated_mask.ndim != 2:
        raise ValueError('updated_mask should be 2D arrays')

    nbz, nby, nbx = original_data.shape
    stop_masking = False
    if dim not in [0, 1, 2]:
        raise ValueError('dim should be 0, 1 or 2')

    axs = figure.gca()
    xmin, xmax = axs.get_xlim()
    ymin, ymax = axs.get_ylim()

    if key == 'up':
        width = width + 1

    elif key == 'down':
        width = width - 1
        if width < 0:
            width = 0

    elif key == 'right':
        vmax = vmax + 1

    elif key == 'left':
        vmax = vmax - 1
        if vmax < 1:
            vmax = 1

    elif key == 'm':
        if (piy - width) < 0:
            starty = 0
        else:
            starty = piy - width
        if (pix - width) < 0:
            startx = 0
        else:
            startx = pix - width
        updated_mask[starty:piy + width + 1, startx:pix + width + 1] = 1

    elif key == 'b':
        if (piy - width) < 0:
            starty = 0
        else:
            starty = piy - width
        if (pix - width) < 0:
            startx = 0
        else:
            startx = pix - width
        updated_mask[starty:piy + width + 1, startx:pix + width + 1] = 0
        if dim == 0:
            updated_data[:, starty:piy + width + 1, startx:pix + width + 1] = \
                original_data[:, starty:piy + width + 1, startx:pix + width + 1]
        elif dim == 1:
            updated_data[starty:piy + width + 1, :, startx:pix + width + 1] = \
                original_data[starty:piy + width + 1, :, startx:pix + width + 1]
        else:  # dim=2
            updated_data[starty:piy + width + 1, startx:pix + width + 1, :] = \
                original_data[starty:piy + width + 1, startx:pix + width + 1, :]

    elif key == 'a':  # restart mask from beginning
        updated_data[:] = original_data[:]
        xy = []
        print('Restart masking...')
        if dim == 0:
            updated_data[
                original_mask == 1] = masked_color / nbz  # masked pixels plotted with the value of masked_pixel
            updated_mask = np.zeros((nby, nbx))
            xmin, xmax = -0.5, nbx - 0.5
            if invert_yaxis:
                ymin, ymax = -0.5, nby - 0.5  # pointing up
            else:
                ymin, ymax = nby - 0.5, -0.5  # pointing down
        elif dim == 1:
            updated_data[
                original_mask == 1] = masked_color / nby  # masked pixels plotted with the value of masked_pixel
            updated_mask = np.zeros((nbz, nbx))
            xmin, xmax = -0.5, nbx - 0.5
            ymin, ymax = nbz - 0.5, -0.5  # pointing down
        else:  # dim=2
            updated_data[
                original_mask == 1] = masked_color / nbx  # masked pixels plotted with the value of masked_pixel
            updated_mask = np.zeros((nbz, nby))
            xmin, xmax = -0.5, nby - 0.5
            ymin, ymax = nbz - 0.5, -0.5  # pointing down

    elif key == 'p':  # plot full image
        if dim == 0:
            xmin, xmax = -0.5, nbx - 0.5
            if invert_yaxis:
                ymin, ymax = -0.5, nby - 0.5  # pointing up
            else:
                ymin, ymax = nby - 0.5, -0.5  # pointing down
        elif dim == 1:
            xmin, xmax = -0.5, nbx - 0.5
            ymin, ymax = nbz - 0.5, -0.5  # pointing down
        else:  # dim=2
            xmin, xmax = -0.5, nby - 0.5
            ymin, ymax = nbz - 0.5, -0.5  # pointing down
        if not flag_pause and len(xy) != 0:
            xy.append(xy[0])
            print(xy)
            if dim == 0:
                ind = Path(np.array(xy)).contains_points(points).reshape((nby, nbx))
            elif dim == 1:
                ind = Path(np.array(xy)).contains_points(points).reshape((nbz, nbx))
            else:  # dim=2
                ind = Path(np.array(xy)).contains_points(points).reshape((nbz, nby))
            updated_mask[ind] = 1
        xy = []  # allow to mask a different area

    elif key == 'r':
        xy = []

    elif key == 'x':
        if not flag_pause:
            flag_pause = True
            print('pause for pan/zoom')
        else:
            flag_pause = False
            print('resume masking')

    elif key == 'q':
        stop_masking = True

    else:
        return updated_data, updated_mask, flag_pause, xy, width, vmax, stop_masking

    array = updated_data.sum(axis=dim)  # updated_data is not modified
    array[updated_mask == 1] = masked_color

    axs.cla()
    axs.imshow(np.log10(abs(array)), vmin=vmin, vmax=vmax)
    if invert_yaxis:
        axs.invert_yaxis()
    axs.set_xlim([xmin, xmax])
    axs.set_ylim([ymin, ymax])
    axs.set_title('x to pause/resume masking for pan/zoom \n'
                  'p plot mask ; a restart ; click to select vertices\n'
                  "m mask ; b unmask ; q quit ; u next frame ; d previous frame\n"
                  "up larger ; down smaller ; right darker ; left brighter")
    plt.draw()

    return updated_data, updated_mask, flag_pause, xy, width, vmax, stop_masking


def update_mask_combined(key, pix, piy, original_data, original_mask, updated_data, updated_mask, axes, flag_pause,
                         points, xy, width, dim, click_dim, info_text, vmax, vmin=0, invert_yaxis=False):
    """
    Update the mask to remove parasitic diffraction intensity and hotpixels in 3D dataset.

    :param key: the keyboard key which was pressed
    :param pix: the x value of the mouse pointer
    :param piy: the y value of the mouse pointer
    :param original_data: the 3D data array before masking
    :param original_mask: the 3D mask array before masking
    :param updated_data: the current 3D data array
    :param updated_mask: the temporary 3D mask array with updated points
    :param axes: tuple of the 4 axes instances in a plt.subplots(nrows=2, ncols=2)
    :param flag_pause: set to 1 to stop registering vertices using mouse clicks
    :param points: list of all point coordinates: points=np.stack((x, y), axis=0).T with x=x.flatten() , y = y.flatten()
     given x,y=np.meshgrid(np.arange(nx), np.arange(ny))
    :param xy: the list of vertices which defines a polygon to be masked
    :param width: the half_width of the masking window
    :param dim: the axis currently under review (axis 0, 1 or 2)
    :param click_dim: the dimension (0, 1 or 2) here the selection of mask polygon vertices by clicking was performed
    :param info_text: text instance in the figure
    :param vmax: the higher boundary for the colorbar
    :param vmin: the lower boundary for the colorbar
    :param invert_yaxis: True to invert the y axis of imshow plots
    :return: updated data, mask and controls
    """
    if original_data.ndim != 3 or updated_data.ndim != 3 or original_mask.ndim != 3 or updated_mask.ndim != 3:
        raise ValueError('original_data, updated_data and original_mask should be 3D arrays')

    nbz, nby, nbx = original_data.shape
    stop_masking = False
    if dim not in [0, 1, 2]:
        raise ValueError('dim should be 0, 1 or 2')

    xmin0, xmax0 = axes[0].get_xlim()
    ymin0, ymax0 = axes[0].get_ylim()
    xmin1, xmax1 = axes[1].get_xlim()
    ymin1, ymax1 = axes[1].get_ylim()
    xmin2, xmax2 = axes[2].get_xlim()
    ymin2, ymax2 = axes[2].get_ylim()

    if key == 'up':
        width = width + 1

    elif key == 'down':
        width = width - 1
        if width < 0:
            width = 0

    elif key == 'right':
        vmax = vmax + 1

    elif key == 'left':
        vmax = vmax - 1
        if vmax < 1:
            vmax = 1

    elif key == 'm':
        if (piy - width) < 0:
            starty = 0
        else:
            starty = piy - width
        if (pix - width) < 0:
            startx = 0
        else:
            startx = pix - width
        if dim == 0:
            updated_mask[:, starty:piy + width + 1, startx:pix + width + 1] = 1
        elif dim == 1:
            updated_mask[starty:piy + width + 1, :, startx:pix + width + 1] = 1
        else:  # dim=2
            updated_mask[starty:piy + width + 1, startx:pix + width + 1, :] = 1

    elif key == 'b':
        if (piy - width) < 0:
            starty = 0
        else:
            starty = piy - width
        if (pix - width) < 0:
            startx = 0
        else:
            startx = pix - width
        if dim == 0:
            updated_mask[:, starty:piy + width + 1, startx:pix + width + 1] = 0
            updated_data[:, starty:piy + width + 1, startx:pix + width + 1] =\
                original_data[:, starty:piy + width + 1, startx:pix + width + 1]
        elif dim == 1:
            updated_mask[starty:piy + width + 1, :, startx:pix + width + 1] = 0
            updated_data[starty:piy + width + 1, :, startx:pix + width + 1] = \
                original_data[starty:piy + width + 1, :, startx:pix + width + 1]
        else:  # dim=2
            updated_mask[starty:piy + width + 1, startx:pix + width + 1, :] = 0
            updated_data[starty:piy + width + 1, startx:pix + width + 1, :] = \
                original_data[starty:piy + width + 1, startx:pix + width + 1, :]

    elif key == 'a':  # restart mask from beginning
        updated_data = np.copy(original_data)
        xy = []
        click_dim = None
        print('Restart masking...')
        xmin0, xmax0 = -0.5, nbx - 0.5
        if invert_yaxis:
            ymin0, ymax0 = -0.5, nby - 0.5  # pointing up
        else:
            ymin0, ymax0 = nby - 0.5, -0.5  # pointing down
        xmin1, xmax1 = -0.5, nbx - 0.5
        ymin1, ymax1 = nbz - 0.5, -0.5  # pointing down
        xmin2, xmax2 = -0.5, nby - 0.5
        ymin2, ymax2 = nbz - 0.5, -0.5  # pointing down

        updated_data[:] = original_data[:]
        updated_mask = np.zeros((nbz, nby, nbx))

    elif key == 'p':  # plot full image
        xmin0, xmax0 = -0.5, nbx - 0.5
        if invert_yaxis:
            ymin0, ymax0 = -0.5, nby - 0.5  # pointing up
        else:
            ymin0, ymax0 = nby - 0.5, -0.5  # pointing down
        xmin1, xmax1 = -0.5, nbx - 0.5
        ymin1, ymax1 = nbz - 0.5, -0.5  # pointing down
        xmin2, xmax2 = -0.5, nby - 0.5
        ymin2, ymax2 = nbz - 0.5, -0.5  # pointing down
        if not flag_pause and len(xy) != 0:
            xy.append(xy[0])
            print(xy)
            if click_dim == 0:
                ind = Path(np.array(xy)).contains_points(points).reshape((nby, nbx))
                temp_mask = np.zeros((nby, nbx))
                temp_mask[ind] = 1
                updated_mask[np.repeat(temp_mask[np.newaxis, :, :], repeats=nbz, axis=0) == 1] = 1
            elif click_dim == 1:
                ind = Path(np.array(xy)).contains_points(points).reshape((nbz, nbx))
                temp_mask = np.zeros((nbz, nbx))
                temp_mask[ind] = 1
                updated_mask[np.repeat(temp_mask[:, np.newaxis, :], repeats=nby, axis=1) == 1] = 1
            else:  # dim=2
                ind = Path(np.array(xy)).contains_points(points).reshape((nbz, nby))
                temp_mask = np.zeros((nbz, nby))
                temp_mask[ind] = 1
                updated_mask[np.repeat(temp_mask[:, :, np.newaxis], repeats=nbx, axis=2) == 1] = 1
        xy = []  # allow to mask a different area
        click_dim = None

    elif key == 'r':
        xy = []

    elif key == 'x':
        if not flag_pause:
            flag_pause = True
            print('pause for pan/zoom')
        else:
            flag_pause = False
            print('resume masking')

    elif key == 'q':
        stop_masking = True

    else:
        return updated_data, updated_mask, flag_pause, xy, width, vmax, click_dim, stop_masking

    updated_data[original_mask == 1] = 0
    updated_data[updated_mask == 1] = 0

    axes[0].cla()
    axes[1].cla()
    axes[2].cla()
    axes[0].imshow(np.log10(updated_data.sum(axis=0)), vmin=vmin, vmax=vmax)
    axes[1].imshow(np.log10(updated_data.sum(axis=1)), vmin=vmin, vmax=vmax)
    axes[2].imshow(np.log10(updated_data.sum(axis=2)), vmin=vmin, vmax=vmax)
    axes[0].set_title("XY")
    axes[0].axis('scaled')
    if invert_yaxis:
        axes[0].invert_yaxis()
    axes[0].set_xlim([xmin0, xmax0])
    axes[0].set_ylim([ymin0, ymax0])
    axes[1].set_title("XZ")
    axes[1].axis('scaled')
    axes[1].set_xlim([xmin1, xmax1])
    axes[1].set_ylim([ymin1, ymax1])
    axes[2].set_title("YZ")
    axes[2].axis('scaled')
    axes[2].set_xlim([xmin2, xmax2])
    axes[2].set_ylim([ymin2, ymax2])
    fig = plt.gcf()
    info_text.remove()
    if flag_pause:
        info_text = fig.text(0.6, 0.05, 'masking paused', size=16)
    else:
        info_text = fig.text(0.6, 0.05, 'masking enabled', size=16)
    plt.draw()

    return updated_data, updated_mask, flag_pause, xy, width, vmax, click_dim, stop_masking, info_text


def update_mask_2d(key, pix, piy, original_data, original_mask, updated_data, updated_mask, figure, flag_pause, points,
                   xy, width, vmax, vmin=0, masked_color=0.1, invert_yaxis=False):
    """
    Update the mask to remove parasitic diffraction intensity and hotpixels for 2d dataset.

    :param key: the keyboard key which was pressed
    :param pix: the x value of the mouse pointer
    :param piy: the y value of the mouse pointer
    :param original_data: the 2D data array before masking
    :param original_mask: the 2D mask array before masking
    :param updated_data: the current 2D data array
    :param updated_mask: the temporary 2D mask array with updated points
    :param figure: the figure instance
    :param flag_pause: set to 1 to stop registering vertices using mouse clicks
    :param points: list of all point coordinates: points=np.stack((x, y), axis=0).T with x=x.flatten() , y = y.flatten()
     given x,y=np.meshgrid(np.arange(nx), np.arange(ny))
    :param xy: the list of vertices which defines a polygon to be masked
    :param width: the half_width of the masking window
    :param vmax: the higher boundary for the colorbar
    :param vmin: the lower boundary for the colorbar
    :param masked_color: the value that detector gaps should have in plots
    :param invert_yaxis: True to invert the y axis of imshow plots
    :return: updated data, mask and controls
    """
    if original_data.ndim != 2 or updated_data.ndim != 2 or original_mask.ndim != 2 or updated_mask.ndim != 2:
        raise ValueError('original_data, updated_data, original_mask and updated_mask should be 2D arrays')

    nby, nbx = original_data.shape
    stop_masking = False

    axs = figure.gca()
    xmin, xmax = axs.get_xlim()
    ymin, ymax = axs.get_ylim()

    if key == 'up':
        width = width + 1

    elif key == 'down':
        width = width - 1
        if width < 0:
            width = 0

    elif key == 'right':
        vmax = vmax + 1
        updated_data[updated_mask == 1] = masked_color

    elif key == 'left':
        vmax = vmax - 1
        if vmax < 1:
            vmax = 1
        updated_data[updated_mask == 1] = masked_color

    elif key == 'm':
        if (piy - width) < 0:
            starty = 0
        else:
            starty = piy - width
        if (pix - width) < 0:
            startx = 0
        else:
            startx = pix - width
        updated_mask[starty:piy + width + 1, startx:pix + width + 1] = 1
        updated_data[updated_mask == 1] = masked_color

    elif key == 'b':
        if (piy - width) < 0:
            starty = 0
        else:
            starty = piy - width
        if (pix - width) < 0:
            startx = 0
        else:
            startx = pix - width
        updated_mask[starty:piy + width + 1, startx:pix + width + 1] = 0
        updated_data[updated_mask == 1] = masked_color

    elif key == 'a':  # restart mask from beginning
        updated_data = np.copy(original_data)
        xy = []
        print('restart masking')
        updated_data[
            original_mask == 1] = masked_color  # masked pixels plotted with the value of masked_pixel
        updated_mask = np.zeros((nby, nbx))
        xmin, xmax = -0.5, nbx - 0.5
        if invert_yaxis:
            ymin, ymax = -0.5, nby - 0.5  # pointing up
        else:
            ymin, ymax = nby - 0.5, -0.5  # pointing down

    elif key == 'p':  # plot full image
        xmin, xmax = -0.5, nbx - 0.5
        if invert_yaxis:
            ymin, ymax = -0.5, nby - 0.5  # pointing up
        else:
            ymin, ymax = nby - 0.5, -0.5  # pointing down
        if not flag_pause and len(xy) != 0:
            xy.append(xy[0])
            print(xy)
            ind = Path(np.array(xy)).contains_points(points).reshape((nby, nbx))
            updated_mask[ind] = 1

        updated_data[updated_mask == 1] = masked_color
        xy = []  # allow to mask a different area

    elif key == 'r':
        xy = []

    elif key == 'x':
        if not flag_pause:
            flag_pause = True
            print('pause for pan/zoom')
        else:
            flag_pause = False
            print('resume masking')

    elif key == 'q':
        stop_masking = True

    else:
        return updated_data, updated_mask, flag_pause, xy, width, vmax, stop_masking

    axs.cla()
    axs.imshow(np.log10(abs(updated_data)), vmin=vmin, vmax=vmax)
    if invert_yaxis:
        axs.invert_yaxis()
    axs.set_xlim([xmin, xmax])
    axs.set_ylim([ymin, ymax])
    axs.set_title('x to pause/resume masking for pan/zoom \n'
                  'p plot mask ; a restart ; click to select vertices\n'
                  "m mask ; b unmask ; q quit ; u next frame ; d previous frame\n"
                  "up larger ; down smaller ; right darker ; left brighter")
    plt.draw()

    return updated_data, updated_mask, flag_pause, xy, width, vmax, stop_masking


def wrap(obj, start_angle, range_angle):
    """
    Wrap obj between start_angle and (start_angle + range_angle)

    :param obj: number or array to be wrapped
    :param start_angle: start angle of the range
    :param range_angle: range
    :return: wrapped angle in [start_angle, start_angle+range[
    """
    obj = (obj - start_angle + range_angle) % range_angle + start_angle
    return obj


def zero_pad(array, padding_width=np.array([0, 0, 0, 0, 0, 0]), mask_flag=False, debugging=False):
    """
    Pad obj with zeros.

    :param array: 3D array to be padded
    :param padding_width: number of zero pixels to padd on each side
    :param mask_flag: set to True to pad with 1, False to pad with 0
    :type mask_flag: bool
    :param debugging: set to True to see plots
    :type debugging: bool
    :return: obj padded with zeros
    """
    if array.ndim != 3:
        raise ValueError('3D Array expected, got ', array.ndim, 'D')

    nbz, nby, nbx = array.shape
    padding_z0 = padding_width[0]
    padding_z1 = padding_width[1]
    padding_y0 = padding_width[2]
    padding_y1 = padding_width[3]
    padding_x0 = padding_width[4]
    padding_x1 = padding_width[5]
    if debugging:
        gu.multislices_plot(array=array, sum_frames=False, plot_colorbar=True, vmin=0, vmax=1,
                            title='Array before padding')

    if mask_flag:
        newobj = np.ones((nbz + padding_z0 + padding_z1, nby + padding_y0 + padding_y1, nbx + padding_x0 + padding_x1))
    else:
        newobj = np.zeros((nbz + padding_z0 + padding_z1, nby + padding_y0 + padding_y1, nbx + padding_x0 + padding_x1))
    newobj[padding_z0:padding_z0 + nbz, padding_y0:padding_y0 + nby, padding_x0:padding_x0 + nbx] = array
    if debugging:
        gu.multislices_plot(array=newobj, sum_frames=False, plot_colorbar=True, vmin=0, vmax=1,
                            title='Array after padding')
    return newobj


if __name__ == "__main__":
    print(smaller_primes(299, maxprime=7, required_dividers=(2,)))
