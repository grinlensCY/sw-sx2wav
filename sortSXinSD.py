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
with open(fn, 'r', newline='') as csvfile:
    rows = csv.reader(csvfile, delimiter=',', skipinitialspace=True)
    last_day_list = []
    last_num_list = []
    last_ts_list = []
    # lastfn = ''
    last_num = None
    for row in rows:
        print(row)
        fntmp = row[0].split('/')[-1]
        fn = f"{srcdir}/{fntmp}"
        if fntmp.split('_')[1] == '0':
            if last_num is not None:
                last_day_list.append(f"{srcdir}/day{dayCnt}")
                last_num_list.append(last_num)
                last_ts_list.append(last_ts)
            dayCnt += 1
            dstdir = f"{srcdir}/day{dayCnt}"
            if not os.path.exists(dstdir):
                os.makedirs(dstdir)
            shutil.copy2(f"{srcdir}/ts_log.txt",dstdir)
        if os.path.exists(fn):
            dstdir = f"{srcdir}/day{dayCnt}"
            shutil.move(fn, dstdir)
            print(f'\tmove {fntmp} to {dstdir}')
        # lastfn = fn
        last_num = int(fntmp.split('_')[1])
        last_ts = int(row[-1])
    last_day_list.append(f"{srcdir}/day{dayCnt}")
    last_num_list.append(last_num)
    last_ts_list.append(last_ts)
tsDiff_dict = {}
for fn in os.listdir(srcdir):
    if fn.startswith('log') and fn.endswith('.sx'):
        tsDiff_dict[f"{srcdir}/{fn}"] = {}
        for i in range(len(last_day_list)):
            num = int(fn.split('_')[1])
            ts = int(fn.split('_')[2][:-3])
            if num == last_num_list[i]+1 and ts > last_ts_list[i]:
                tsDiff_dict[f"{srcdir}/{fn}"][f"{last_day_list[i]}"]= ts - last_ts_list[i]
for fn in tsDiff_dict.keys():
    minTsDiff = 1e9
    dstdir = ''
    for lastD in tsDiff_dict[fn].keys():
        if tsDiff_dict[fn][lastD] < minTsDiff:
            dstdir = lastD
    if dstdir:
        shutil.move(fn, dstdir)
        print(f'\tmove {fntmp} to {dstdir}')


config['srcdir'][os.path.basename(__file__)] = srcdir
rwConfig('w')