'''Example Code for conducting SDI with MKIDs'''

import os
import matplotlib as mpl
import numpy as np
mpl.use("Qt5Agg")
import matplotlib.pylab as plt
import copy as copy
import pickle as pickle
from medis.params import mp, ap, iop
from medis.Utils.plot_tools import quicklook_im, view_datacube
from medis.Utils.misc import dprint
import master

metric_name = __file__.split('/')[-1].split('.')[0]
metric_vals = [0.01, 0.04, 0.16]

master.set_field_params()
master.set_mkid_params()

iop.set_testdir(f'FirstPrincipleSim/{metric_name}')
iop.set_atmosdata('190823')
iop.set_aberdata('Palomar256')

print(ap.numframes)

comps = False

def adapt_dp_master(dp_master, metric_vals, metric_name='g_sig'):
    with open(dp_master, 'rb') as handle:
        dp = pickle.load(handle)
    metric_orig = getattr(mp,metric_name)#0.04
    QE_mean_orig = mp.g_mean
    iop.device_params = iop.device_params[:-4] + '_'+metric_name
    new_dp = copy.copy(dp)
    # quicklook_im(dp.QE_map)
    for metric_val in metric_vals:
        dprint((np.std(dp.QE_map), QE_mean_orig))
        new_dp.QE_map = (dp.QE_map - QE_mean_orig)*metric_val/metric_orig + QE_mean_orig
        new_dp.QE_map[dp.QE_map == 0] = 0
        new_dp.QE_map[new_dp.QE_map < 0] = 0
        dprint(np.std(new_dp.QE_map))
        iop.device_params = iop.device_params.split('_'+metric_name)[0] + f'_{metric_name}={metric_val}.pkl'
        dprint((iop.device_params, metric_val))
        # quicklook_im(new_dp.QE_map)
        plt.hist(new_dp.QE_map.flatten())
        plt.show(block=True)
        with open(iop.device_params, 'wb') as handle:
            pickle.dump(new_dp, handle, protocol=pickle.HIGHEST_PROTOCOL)

if __name__ == '__main__':
    if not os.path.exists(f'{iop.device_params[:-4]}_{metric_name}={metric_vals[0]}.pkl'):
        adapt_dp_master(master.dp, metric_vals, 'g_sig')
    stackcubes, dps = master.get_stackcubes(metric_vals, metric_name, comps=comps)
    # plt.show(block=True)
    master.eval_performance(stackcubes, dps, metric_vals, comps=comps)