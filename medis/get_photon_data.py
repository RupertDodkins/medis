"""Top level code that takes a atmosphere phase map and propagates a wavefront through the system"""

import os
import numpy as np
import traceback
import multiprocessing
import glob
import random
import pickle as pickle
import time
from proper_mod import prop_run
from medis.Utils.plot_tools import quicklook_im, view_datacube, loop_frames
from medis.Utils.misc import dprint
from medis.params import ap,cp,tp,mp,sp,iop,dp
import medis.Detector.mkid_artefacts as MKIDs
import medis.Detector.H2RG as H2RG
import medis.Detector.pipeline as pipe
import medis.Detector.readout as read
import medis.Telescope.aberrations as aber
import medis.Atmosphere.atmos as atmos

def gen_timeseries(inqueue, photon_table_queue, outqueue, conf_obj_tup):
    """
    generates observation sequence by calling optics_propagate in time series

    It is the time loop wrapper for optics_propagate
    this is where the observation sequence is generated (timeseries of observations by the detector)
    thus, where the detector observes the wavefront created by optics_propagate (for MKIDs, the probability distribution)

    :param inqueue: time index for parallelization (used by multiprocess)
    :param photon_table_queue: photon table (list of photon packets) in the multiprocessing format
    :param spectralcube_queue: series of intensity images (spectral image cube) in the multiprocessing format
    :param conf_obj_tup:
    :return:
    """
    (tp,ap,sp,iop,cp,mp) = conf_obj_tup

    try:

        if tp.detector == 'MKIDs':
            with open(iop.device_params, 'rb') as handle:
                dp = pickle.load(handle)

        start = time.time()

        for it, t in enumerate(iter(inqueue.get, sentinel)):

            kwargs = {'iter': t, 'params': [ap, tp, iop, sp]}
            _, save_E_fields = prop_run('medis.Telescope.optics_propagate', 1, ap.grid_size, PASSVALUE=kwargs,
                                                   VERBOSE=False, PHASE_OFFSET=1)

            for o in range(len(ap.contrast) + 1):
                outqueue.put((t, save_E_fields[:, :, o]))

        now = time.time()
        elapsed = float(now - start) / 60.
        each_iter = float(elapsed) / (it + 1)

        print('***********************************')
        dprint(f'{elapsed:.2f} minutes elapsed, each time step took {each_iter:.2f} minutes') #* ap.numframes/sp.num_processes TODO change to log #

    except Exception as e:
        traceback.print_exc()
        # raise e
        pass

def update_realtime_save():
    iop.realtime_save = f"{iop.realtime_save.split('.')[0][:-4]}{str(ap.startframe).zfill(4)}.pkl"

def initialize_telescope():
    iop.makedir()  # make the directories at this point in case the user doesn't want to keep changing params.py

    print('Creating New MEDIS Simulation')
    print('********** Taking Obs Data ***********')

    try:
        multiprocessing.set_start_method('spawn')
    except RuntimeError:
        pass

    # initialize atmosphere
    print("Atmosdir = %s " % iop.atmosdir)
    if tp.use_atmos and not os.path.exists(f'{iop.atmosdir}/{cp.model}'):
        atmos.generate_maps()

    # initialize telescope
    if (tp.aber_params['QuasiStatic'] is True) and glob.glob(iop.aberdir + 'quasi/*.fits') == []:
        aber.generate_maps(tp.f_lens)
        if tp.aber_params['NCPA']:
            aber.generate_maps(tp.f_lens, 'NCPA', 'lens')

    # if tp.servo_error:
    #     aber.createObjMapsEmpty()

    aber.initialize_CPA_meas()

    if tp.active_null:
        aber.initialize_NCPA_meas()

    # initialize MKIDs
    if tp.detector == 'MKIDs' and not os.path.isfile(iop.device_params):
        MKIDs.initialize()

    if ap.companion is False:
        ap.contrast = []

    if sp.save_locs is None:
        sp.save_locs = []
    if 'final' not in sp.save_locs:
        sp.save_locs = np.append(sp.save_locs, 'final')
        sp.gui_map_type = np.append(sp.gui_map_type, 'amp')

def applymkideffects(spectralcube, t):
    spectrallist = read.get_packets(spectralcube, t, dp, mp)
    # packets = read.get_packets(save_E_fields, t, dp, mp)
    spectralcube = MKIDs.makecube(spectrallist, mp.array_size)

    # if sp.save_obs:
    #     command = read.get_obs_command(spectrallist, t)
    # #     photon_table_queue.put(command)

    return spectralcube

def realtime_stream(EfieldsThread, e_fields_sequence, inqueue, outqueue):
    for t in range(ap.startframe, ap.numframes):
        dprint(t)
        inqueue.put(t)

        for o in range(len(ap.contrast) + 1):
            qt, save_E_fields = outqueue.get()
            spectralcube = np.abs(save_E_fields[-1]) ** 2

            if tp.detector == 'MKIDs':
                spectralcube = applymkideffects(spectralcube, t)

            gui_images = np.zeros_like(save_E_fields, dtype=np.float)
            phase_ind = sp.gui_map_type == 'phase'
            amp_ind = sp.gui_map_type == 'amp'
            gui_images[phase_ind] = np.angle(save_E_fields[phase_ind], deg=False)
            gui_images[amp_ind] = np.absolute(save_E_fields[amp_ind])

            e_fields_sequence[qt, :, :, o] = save_E_fields

            if o == EfieldsThread.fields_ob:
                EfieldsThread.newSample.emit(gui_images)
                EfieldsThread.sct.newSample.emit((qt, spectralcube))

        if sp.play_gui is False:
            ap.startframe = qt
            update_realtime_save()
            read.save_rt(iop.realtime_save, e_fields_sequence[:qt])
            sp.play_gui = True
            run_medis(EfieldsThread)
            dprint((tp.use_ao, sp.play_gui))
            return

    return e_fields_sequence

sentinel = None
def postfacto(e_fields_sequence, inqueue, outqueue):
    for t in range(ap.startframe, ap.numframes):
        dprint(t)
        inqueue.put(t)

    for i in range(sp.num_processes):
        # Send the sentinal to tell Simulation to end
        inqueue.put(sentinel)

    for t in range(ap.numframes):
        qt, save_E_fields = outqueue.get()
        spectralcube = np.abs(save_E_fields[-1, :, ]) ** 2

        if tp.detector == 'MKIDs':
            spectralcube = applymkideffects(spectralcube, t)

        save_E_fields[-1] = spectralcube
        e_fields_sequence[qt - ap.startframe] = save_E_fields

    return e_fields_sequence

def run_medis(EfieldsThread=None, realtime=False, plot=False):

    if EfieldsThread is not None:
        realtime = True

    # If complete savefile exists use that
    check = read.check_exists_obs_sequence(plot)
    if check:
        if iop.obs_seq[-3:] == '.h5':
            obs_sequence = read.open_obs_sequence_hdf5(iop.obs_seq)
        else:
            obs_sequence = read.open_obs_sequence(iop.obs_seq)

        return obs_sequence

    # Start the clock
    begin = time.time()

    initialize_telescope()

    # Initialise the fields
    e_fields_sequence = np.zeros((ap.numframes, len(sp.save_locs),
                                  ap.nwsamp, 1 + len(ap.contrast),
                                  ap.grid_size, ap.grid_size), dtype=np.complex64)

    # if tp.detector == 'MKIDs':
    #     obs_sequence = np.zeros((ap.numframes, ap.w_bins, mp.array_size[1], mp.array_size[0]))
    # else:
    #     obs_sequence = np.zeros((ap.numframes, ap.w_bins, ap.grid_size, ap.grid_size))

    update_realtime_save()
    dprint((iop.realtime_save, os.path.exists(iop.realtime_save)))
    if ap.startframe != 0 and os.path.exists(iop.realtime_save):
        print(iop.realtime_save, 'iop.realtimesave')
        # obs_sequence[:ap.startframe], e_fields_sequence[:ap.startframe] = read.open_rt_save(iop.realtime_save, ap.startframe)
        e_fields_sequence[:ap.startframe] = read.open_rt_save(iop.realtime_save, ap.startframe)

    inqueue = multiprocessing.Queue()
    outqueue = multiprocessing.Queue()
    photon_table_queue = multiprocessing.Queue()
    jobs = []

    # if sp.save_obs and tp.detector == 'MKIDs':
    #     proc = multiprocessing.Process(target=read.handle_output, args=(photon_table_queue, iop.obsfile))
    #     proc.start()

    for i in range(sp.num_processes):
        p = multiprocessing.Process(target=gen_timeseries, args=(inqueue, photon_table_queue, outqueue,
                                                                 (tp,ap,sp,iop,cp,mp)))
        jobs.append(p)
        p.start()

    if realtime:
        e_fields_sequence = realtime_stream(EfieldsThread, e_fields_sequence, inqueue, outqueue)
    else:
        e_fields_sequence = postfacto(e_fields_sequence, inqueue, outqueue)

    for i, p in enumerate(jobs):
        p.join()

    photon_table_queue.put(None)
    outqueue.put(None)

    print('MEDIS Data Run Completed')
    finish = time.time()
    if sp.timing is True:
        print(f'Time elapsed: {(finish-begin)/60:.2f} minutes')
    print('**************************************')
    print(f"Shape of e_fields_sequence = {np.shape(e_fields_sequence)}")

    read.save_fields(e_fields_sequence, fields_file=iop.fields)

    return e_fields_sequence

if __name__ == '__main__':
    sp.timing = True
    run_medis()