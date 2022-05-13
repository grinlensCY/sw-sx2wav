import csv
# import pickle
import soundfile as sf
import librosa
# import enum
import os
import time
# import subprocess
import numpy as np

# import sounddevice as sd
import scipy
from scipy import signal
import scipy.fft as fft
from scipy.integrate import simps, romb, trapz
# import cv2

# import colorcet as cc
# from PIL import Image
# import socket
import shutil
# import logging
# from sklearn.model_selection import train_test_split
import json
# from pyedflib import highlevel
import pandas as pd
import math
# from PyQt5.QtCore import Qt
# import padasip as pa
# import compileall
# # import filter_butterW_zeroPhase as bwfilt
# from scipy import signal
# import random
# # try to import from another subfolder of upper folder
import sys
# # sys.path.append("..")
# # import RR_autocorr_DTW.get_envelope_RR


import threading
import queue
from random import randint
# from sklearn.decomposition import PCA
# import utils_ as myutils
# import serial.tools.list_ports
import matplotlib
import matplotlib.pyplot as plt
chinese_font = matplotlib.font_manager.FontProperties(fname='C:\Windows\Fonts\mingliu.ttc')
matplotlib.rcParams['agg.path.chunksize'] = 10000
import matplotlib.widgets as mwidgets
import tkinter as tk
from tkinter import filedialog
from zipfile import ZipFile
# plt.switch_backend('agg')

colorlist = ['k', 'm', 'g', 'r', 'b', 'c', 'tab:brown', 'tab:olive', 
                 'tab:orange', 'xkcd:dark blue',[0.61568627, 0.7372549 , 0.88235294],'xkcd:dusty blue','tab:gray','xkcd:lime green','xkcd:beige',
                 'xkcd:brick red','xkcd:reddish orange']
markerlist = ['.','v','x','>','s','p','|']
lgdposList = ['upper left','lower left','lower right','upper right']

def bwfilter(data_in=None, sr=None, f_cut=None, N_filt=3, filtype='bandpass',
                    b_filt=None, a_filt=None, isfiltfilt=False, forback=False, iszi=True, zf=None,
                    ispltfreqResp=False,job=''):
        """apply butterworth filter with zero phase shift"""
        data_filtered = None
        next_zi = None
        if b_filt is None:
            nyq = sr/2
            wn = np.array(f_cut) if isinstance(f_cut,list) or isinstance(f_cut,tuple) else np.array([f_cut])
            if not wn[0] and wn[-1]>=nyq:
                print(f'bwfilter {job}:  wn{wn} is not valid!')
                return data_in,[],[],[]
            if np.max(wn) >= nyq and filtype == 'bandpass':
                # wn[np.argmax(wn)] = nyq*0.99
                wn = wn[0]
                filtype = 'highpass'
            if wn.size == 2 and not wn[0]:
                wn = wn[1]
                filtype = 'lowpass'
            elif wn.size == 2 and wn[-1]>=nyq:
                wn = wn[0]
                filtype = 'highpass'
            elif (filtype != 'bandpass' and filtype != 'bandstop') and wn.size == 2:
                wn = wn[0] if filtype == 'highpass' else wn[1]
            print((f'{job} bwfilter: sr{sr:.2f} wn{wn} type:{filtype} N={N_filt} '
                    f'isfiltfilt:{isfiltfilt} forback:{forback} iszi:{iszi}'))
            b_filt, a_filt = signal.butter(N_filt, wn/nyq, btype=filtype)
            next_zi = signal.lfilter_zi(b_filt, a_filt)
        if data_in is not None:
            if isfiltfilt:
                data_filtered = signal.filtfilt(b_filt, a_filt, data_in)
            elif forback:
                zi = signal.lfilter_zi(b_filt, a_filt)
                data_filtered,_ = signal.lfilter(b_filt, a_filt, data_in, zi=zi*data_in[0])
                data_filtered,_ = signal.lfilter(b_filt, a_filt, data_filtered[::-1], zi=zi*data_filtered[-1])
                data_filtered = data_filtered[::-1]
            elif not iszi:
                data_filtered = signal.lfilter(b_filt, a_filt, data_in)
            elif iszi and zf is not None:
                # print('w/ zf')
                data_filtered,next_zi = signal.lfilter(b_filt, a_filt, data_in, zi=zf)
            elif iszi:
                # print('w/0 zf')
                zi = signal.lfilter_zi(b_filt, a_filt)
                data_filtered,next_zi = signal.lfilter(b_filt, a_filt, data_in, zi=zi*data_in[0])
        # plot of freq response
        if ispltfreqResp:
            w_butter, h_butter = signal.freqz(b_filt, a_filt, fs=sr)
            fig_fr = plt.figure(figsize=(10,6))
            ax_fr = fig_fr.subplots(1,1)
            ax_fr_2 = ax_fr.twinx()
            ax_fr.plot(w_butter, 20*np.log10(abs(h_butter)),'b',label="gain")
            ax_fr_2.plot(w_butter, np.unwrap(np.angle(h_butter,deg=True)),'r',label="phase")
            ax_fr.grid(axis='both')
            ax_fr.legend()
            ax_fr_2.legend()
            # ax_fr.set_xlim((f_cut[0]/2,f_cut[1]*2))
            plt.show()
        return data_filtered, b_filt, a_filt, next_zi

def rwConfig(rw='r'):
    dir_config = os.path.dirname(__file__)
    # print('dir_config',dir_config,',',dir_config+'\\config_misc.json')
    configfn = dir_config+'\\config_misc.json' if dir_config else 'config_misc.json'
    if rw == 'r':
        with open(configfn, 'r', newline='', encoding='utf-8-sig') as jf:
            return json.loads(jf.read())
    else:
        with open(configfn,'w',encoding='utf-8-sig', newline='') as jout:
            json.dump(config, jout, indent=4, ensure_ascii=False)

def saveConfig(config):
    dir_config = os.path.dirname(__file__)
    configfn = dir_config+'\\config_misc.json' if dir_config else 'config_misc.json'
    with open(configfn, 'w', encoding='utf-8-sig', newline='') as jout:
            json.dump(config, jout, indent=4, ensure_ascii=False)

def hhmmss(sec=None, hms='',outType=0):
    if sec is not None:
        h, r = divmod(sec, 3600)
        m, r = divmod(r, 60)
        # s, _ = divmod(r, 1000)
        s = r
        if outType == 0:
            if h:
                # ans = f'{h}:{m:02d}:{s:.2f}'
                ans = f'{h:02.0f}:{m:02.0f}:{s:02.0f}'
            elif m:
                # ans = f'{m:02d}:{s:.2f}'
                ans = f'{m:02.0f}:{s:02.0f}'
            else:        
                ans = f'{s:02.0f}'
        elif outType == 1:   # for tag time slot in the exported tag file
            ans = f'{h:02.0f}:{m:02.0f}:{s:09.6f}'
        elif outType == 2:  # for update ti
            return h,m,s
        elif outType == 3:
            if h:
                # ans = f'{h}:{m:02d}:{s:.2f}'
                ans = f'{h:02.0f}:{m:02.0f}:{s:02.0f}'
            elif m:
                # ans = f'{m:02d}:{s:.2f}'
                ans = f'{m:02.0f}:{s:02.0f}'
            else:        
                ans = f'{s:02.0f}sec'
        # elif outType == 2:  # for Set_ti.setValidator
        #     if h:
        #         ans = f"^[0-{h}]{{1,1}}:[0-5]\\d{{1,1}}:[0-5]\\d{{1,1}}.\\d{{3,3}}$"
        #     elif m:
        #         m_10, r = divmod(m, 10)
        #         if m_10:
        #             ans = f"^0:[0-{m_10}]\\d{{1,1}}:[0-5]\\d{{1,1}}.\\d{{3,3}}$"
        #         else:
        #             ans = f"^0:0\\[0-{m}]:[0-5]\\d{{1,1}}.\\d{{3,3}}$"
        #     else:
        #         s_10, r = divmod(s, 10)
        #         if s_10:
        #             ans = f"^0:00:(({round(s_10)}[0-{round(r)}])|(0\\d{{1,1}})).\\d{{3,3}}$"
        #         else:
        #             ans = f"^0:00:0\\[0-{round(s)}].\\d{{3,3}}$"
    elif hms:
        tmp = hms.split(':')
        if len(tmp)==3:
            ans = float(tmp[-1])+60*float(tmp[-2])+60*60*float(tmp[-3])
        elif len(tmp)==2:
            ans = float(tmp[-1])+60*float(tmp[-2])
    return ans
    
config = rwConfig('r')

print('select file source')
root = tk.Tk()
root.withdraw()
srcdir = config['srcdir'][os.path.basename(__file__)]
fn = filedialog.askopenfilename(initialdir=srcdir,filetypes=[("SX",f"*ts_log.txt")])
if not fn:
    sys.exit()
srcdir = os.path.dirname(fn)
dayCnt = 0
lastTs = []
fnlog = []
with open(fn, 'r', newline='') as csvfile:
    rows = csv.reader(csvfile, delimiter=',', skipinitialspace=True)
    for row in rows:
        print(row)
        fntmp = row[0].split('/')[-1]
        fnlog.append(fntmp)
        fn = f"{srcdir}/{fntmp}"
        
        if fntmp.split('_')[1] == '0':
            if dayCnt:
                lastTs.append(lastinfo)
            dayCnt += 1
            dstdir = f"{srcdir}/day{dayCnt}"
            if not os.path.exists(dstdir):
                os.makedirs(dstdir)
            shutil.copy2(f"{srcdir}/ts_log.txt",dstdir)
            
        if os.path.exists(fn):
            dstdir = f"{srcdir}/day{dayCnt}"
            shutil.move(fn, dstdir)
            print(f'\tmove {fntmp} to {dstdir}')

        lastinfo = [dayCnt,fntmp.split('_')[1],int(row[2])]
    lastTs.append(lastinfo)
leftfns = [fn for fn in os.listdir(srcdir) if fn.endswith('.sx')]
for fn in leftfns:
    minTdiff = 1e5
    day = int(fn.split('_')[1])-1
    ts = int(fn[:-3].split('_')[2])
    dayCnt = None
    for tsinfo in lastTs:
        tDiff = ts-tsinfo[2]
        if tDiff>0 and tDiff < 50 and minTdiff > tDiff:
            minTdiff = tDiff
            dayCnt = tsinfo[0]
    if dayCnt is not None:
        dstdir = f"{srcdir}/day{dayCnt}"
        shutil.move(f"{srcdir}/{fn}", dstdir)
        print(f'\tmove {fn} to {dstdir}')



config['srcdir'][os.path.basename(__file__)] = srcdir
rwConfig('w')