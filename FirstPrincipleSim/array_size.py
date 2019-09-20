'''Example Code for conducting SDI with MKIDs'''

import os
import matplotlib as mpl
import numpy as np
mpl.use("Qt5Agg")
import matplotlib.pylab as plt
import copy as copy
import pickle as pickle
import medis.get_photon_data as gpd
from medis.params import mp, ap, iop, tp, sp
from medis.Utils.plot_tools import quicklook_im, view_datacube
from medis.Utils.misc import dprint
from medis.Utils.rawImageIO import clipped_zoom
import medis.Detector.mkid_artefacts as MKIDs
import master

metric_name = __file__.split('/')[-1].split('.')[0]
metric_vals = np.array([[100,100],[150,150],[200,200]])

master.set_field_params()
master.set_mkid_params()

iop.set_testdir(f'FirstPrincipleSim/{metric_name}')
iop.set_atmosdata('190823')
iop.set_aberdata('Palomar512')

print(ap.numframes)

comps = True

def adapt_dp_master():
    if not os.path.exists(iop.testdir):
        os.mkdir(iop.testdir)
    with open(master.dp, 'rb') as handle:
        dp = pickle.load(handle)
    metric_orig = getattr(mp,metric_name)#0.04
    iop.device_params = iop.device_params[:-4] + '_'+metric_name
    quicklook_im(dp.QE_map)
    for metric_val in metric_vals:
        dprint((np.std(dp.QE_map), metric_val))
        mp.array_size = np.array(metric_val)
        iop.device_params = iop.device_params.split('_'+metric_name)[0] + f'_{metric_name}={metric_val}.pkl'
        new_dp = MKIDs.initialize()
        dprint((iop.device_params, metric_val))
        quicklook_im(new_dp.QE_map)
        plt.hist(new_dp.QE_map.flatten())
        plt.show(block=True)
        new_dp.lod = int((metric_val[0]/metric_orig[0])*mp.lod)
        dprint(new_dp.lod)
        new_dp.platescale = mp.platescale * metric_orig[0]/metric_val[0]
        new_dp.array_size = metric_val
        with open(iop.device_params, 'wb') as handle:
            pickle.dump(new_dp, handle, protocol=pickle.HIGHEST_PROTOCOL)

def form():
    if not os.path.exists(f'{iop.device_params[:-4]}_{metric_name}={metric_vals[0]}.pkl'):
        adapt_dp_master()
    # stackcubes, dps = get_stackcubes(metric_vals, metric_name, comps=comps, plot=True)
    # master.eval_performance(stackcubes, dps, metric_vals, comps=comps)

    comps_ = [True, False]
    pca_products = []
    for comps in comps_:
        stackcubes, dps = master.get_stackcubes(metric_vals, metric_name, comps=comps, plot=False)
        pca_products.append(master.pca_stackcubes(stackcubes, dps, comps))

    maps = pca_products[0]
    rad_samps = pca_products[1][1]
    conts = pca_products[1][4]

    master.combo_performance(maps, rad_samps, conts, metric_vals)

if __name__ == '__main__':
    form()

    # comps = False
    # stackcubes, dps = master.get_stackcubes(metric_vals, metric_name, comps=comps)
    # master.eval_performance(stackcubes, dps, metric_vals, comps=comps)