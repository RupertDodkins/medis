# -*- coding: utf-8 -*-

'''This script contains the functions for FITS file and raw image manipulations'''

import numpy as np
from glob import glob
import astropy.io.fits as pyfits
import re, os
# from matplotlib import pyplot as plt
# from matplotlib.ticker import MultipleLocator
import pickle as pickle
from medis.Detector.distribution import *
from medis.params import mp, cp
from medis.Utils.misc import dprint

def read_folder(wvlFrames_dir = '/Volumes/Data2/dodkins/FITS files/Wvl Frames (corrected) 26th March/',
                width = 147, height = 144, out_folder = '../FITS files/neb-20141021-cube.fits',
                savecube=True):
    """
    Created on Tue Nov 13 15:05:36 2012
    @author: stuart
    Problem from SunPy mailing list. Save a MASSIVE array to a fits file
    """
    dprint("This function has hardcoded file locations. Strongly consider revising")
    numbers = re.compile(r'(\d+)')
    def numericalSort(value):
        parts = numbers.split(value)
        parts[1::2] = list(map(int, parts[1::2]))
        return parts 

    #wvlFrames_dir = '/Volumes/Data2/dodkins/FITS files/Wvl Frames (corrected) 26th March/'
    
    files = sorted(glob(wvlFrames_dir+"*fits"), key=numericalSort)

    n = len(files)
     
    return files 

def read_image(filename = 'focalplane_1.fits', prob_map=True):
    #hdulist = pyfits.open(directory + filename)
    hdulist = pyfits.open(filename)
    header = hdulist[0].header
    scidata = hdulist[0].data

    xnum = np.shape(scidata)[0]
    ynum = np.shape(scidata)[1]

    if prob_map:
        correction_factor = 1/np.max(scidata) #* 10
        #print correction_factor
        prob_array = scidata * correction_factor
        #print prob_array, np.shape(prob_array)
        return prob_array
    
    else:
        return scidata*1., header

def add_header(self, fromfile = 'telescope_obj1.fits', tofile='telescope_obj_p0.fits'):
    os.chdir('/home/dodkins/')
    hdu = pyfits.open(fromfile)
    hdr = hdu[0].header
    if fromfile == tofile: print(fromfile == tofile)
    hdu = pyfits.open(tofile, mode='update')
    scidata = hdu[0].data
    pyfits.update(tofile, scidata, hdr,0)
    print(hdu[0].header)
    print('done')


def save_wf(wf, filename):
    with open(filename, 'wb') as handle:
        pickle.dump(wf, handle, protocol=pickle.HIGHEST_PROTOCOL)


def load_wf(filename):
    with open(filename, 'rb') as handle:
        wf = pickle.load(handle)
    return wf

#pyfits.update(outFile, scidata, header,0)
#print '%s created' % outFile

# def make_packet(basesDeg, phases, timestamp, Id, xCoord, yCoord):
# # def make_packet(loc,toa,p=80):
#     '''If used alone assumes 100% QE '''
#     packet = np.append(loc,[toa,p], axis=0)
#     # packet {'loc': loc, 'toa': toa, 'phase': p, 'bg', p/10}
#     return packet


def resize_image(image, newsize=(125,125), warn=True):
    if warn:
        print('Using interpolation to resample wavefront - may lead to uncertainties')
    import skimage.transform
    newimage = skimage.transform.resize(image, newsize)
    return newimage


def clipped_zoom(img, zoom_factor, **kwargs):
    from scipy.ndimage import zoom
    h, w = img.shape[:2]

    # For multichannel images we don't want to apply the zoom factor to the RGB
    # dimension, so instead we create a tuple of zoom factors, one per array
    # dimension, with 1's for any trailing dimensions after the width and height.
    zoom_tuple = (zoom_factor,) * 2 + (1,) * (img.ndim - 2)

    # Zooming out
    if zoom_factor < 1:

        # Bounding box of the zoomed-out image within the output array
        zh = int(np.round(h * zoom_factor))
        zw = int(np.round(w * zoom_factor))
        top = (h - zh) // 2
        left = (w - zw) // 2

        # Zero-padding
        out = np.zeros_like(img)
        out[top:top+zh, left:left+zw] = zoom(img, zoom_tuple, **kwargs)

    # Zooming in
    elif zoom_factor > 1:

        # Bounding box of the zoomed-in region within the input array
        zh = int(np.round(h / zoom_factor))
        zw = int(np.round(w / zoom_factor))
        top = (h - zh) // 2
        left = (w - zw) // 2
        from medis.Utils.plot_tools import quicklook_im
        out = zoom(img[top:top+zh, left:left+zw], zoom_tuple, **kwargs)
        # quicklook_im(out, logAmp=True)
        # `out` might still be slightly larger than `img` due to rounding, so
        # trim off any extra pixels at the edges
        trim_top = ((out.shape[0] - h) // 2)
        trim_left = ((out.shape[1] - w) // 2)
        # print top, zh, left, zw
        # print out.shape[0], trim_top, h, trim_left, w
        if trim_top < 0 or trim_left < 0:
            temp = np.zeros_like(img)
            temp[:out.shape[0],:out.shape[1]] = out
            out = temp
        else:
            out = out[trim_top:trim_top+h, trim_left:trim_left+w]
        # quicklook_im(out, logAmp=False)
    # If zoom_factor == 1, just return the input array
    else:
        out = img

    # import matplotlib.pyplot as plt
    # plt.hist(out.flatten(), bins =100, alpha =0.5)
    # plt.hist(img.flatten(), bins =100, alpha=0.5)
    # plt.show()

    print(np.sum(img), np.sum(out))
    # out = out*np.sum(img)/np.sum(out)
    # out = out*4
    return out


def get_MR_pdf():
    res_elements = 1000
    I = np.linspace(0.1, 200, res_elements)

    ratios = [2]#[0,0.5,1,2,7]
    for ratio in ratios:
        Is = 10
        pdf = MR(Is*ratio,Is,I)
        pdf = pdf/ np.sum(pdf)

    return pdf

# def plot_pix_time(cube, x=50, y=50):
#     plt.figure()
#     print cube[x][y], np.shape(cube[x][y])
#     hist, bins = np.histogram(cube[x][y], bins='auto')
#     #plt.xlabel('Time ms')
#     #plt.plot(bins[:-1], hist)


def saveFITS(image, name):
    header = pyfits.Header()
    header["PIXSIZE"] = (0.16, " spacing in meters")

    hdu = pyfits.PrimaryHDU(image, header=header)
    hdu.writeto(name)


def scale_image(filename, scalefactor):
    scidata, hdr = read_image(filename, prob_map=False)
    scidata = scidata*scalefactor
    pyfits.update(filename, scidata, hdr,0)

