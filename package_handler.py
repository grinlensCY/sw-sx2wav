import time
import threading
import math
import numpy as np

import queue

from WriteDataToFileThread import RecThread

protocol=None

class PackageHandler:
    def __init__(self,engine):
        self.acc_pkg_cnt=0
        self.gyro_pkg_cnt=0
        self.mag_pkg_cnt=0
        self.quat_pkg_cnt=0

        self.ecg_sq_pkg_cnt=0
        self.ecg_hr_pkg_cnt=0
        self.ecg_raw_pkg_cnt=0

        self.mic_pkg_cnt=0

        self.pre_ts=0
        self.pre_ts_pkg = 0

        self.recCnt = 0
        # self.sys_v=0
        self.sys_t=0
        self.is_usb_pwr=False

        self.engine = engine
        self.bleaddr = None
    
    def prepare_statistic_output(self):
        if(self.pre_ts==0):
            self.pre_ts=time.time()
            self.t0 = time.time()

        curr_ts=time.time()
        diff_ts=curr_ts-self.pre_ts
        if(diff_ts>3):
            msg = f'elapsed time: {(curr_ts-self.t0)/60:.1f}mins\n'
            msg+="imu: {0:2.2f},{1:2.2f},{2:2.2f},{3:2.2f}; ".format(self.acc_pkg_cnt/diff_ts,self.gyro_pkg_cnt/diff_ts,self.mag_pkg_cnt/diff_ts,self.quat_pkg_cnt/diff_ts)
            msg+="ecg: {0:2.2f},{1:2.2f},{2:2.2f}; ".format(self.ecg_sq_pkg_cnt/diff_ts,self.ecg_hr_pkg_cnt/diff_ts,self.ecg_raw_pkg_cnt/diff_ts)
            msg+="mic: {0:2.1f}pkg/sec".format(self.mic_pkg_cnt/diff_ts)
            msg+="\ntemperature: {0:2.1f}, ".format(self.sys_t)
            msg+="is powered by usb: "+str(self.is_usb_pwr)
            # if not round(curr_ts-self.t0,0)%60:
            #     print(msg, file=open(f'./pkgspd.txt', 'a'))
            self.engine.strPkgSpd = msg

            self.acc_pkg_cnt=0
            self.gyro_pkg_cnt=0
            self.mag_pkg_cnt=0
            self.quat_pkg_cnt=0
            self.ecg_sq_pkg_cnt=0
            self.ecg_hr_pkg_cnt=0
            self.ecg_raw_pkg_cnt=0
            self.mic_pkg_cnt=0
            self.pre_ts=curr_ts
    
    def handle_sys_info_pkg(self,dat):
        ''' (timestamp, firmware ver, hardware ver, battery level 0~100, temperature in degree, ble addr) '''
        # print('get sys info')
        # print(dat[0:5])
        # print(dat[5].hex())#ble addr
        # self.sys_v=dat[3]
        self.sys_t=dat[4]
        self.is_usb_pwr=dat[6]
        self.engine.sysinfo = dat
        if not self.engine.flag_ble_addr.is_set():
            tmp = dat[5].hex()
            addr = ''
            for c in range(-2,-len(tmp)-1,-2):
                addr += f'{tmp[c]}{tmp[c+1]}:' if c!=-len(tmp)else tmp[c]+tmp[c+1]
            print('BLE addr:',addr.upper(),addr.replace(':','').upper())
            self.bleaddr = addr.replace(':','').upper()
            self.engine.flag_ble_addr.set()
        if self.engine.thd_rec_flag.is_set():
            self.engine.recThd_sysinfo.addData([dat[0],dat[3],dat[4]])
            # print('get from decorder',dat[0])

    def handle_dual_mic_pkg(self,dat):
        if not self.engine.flag_checked_fileformat.is_set():
            self.engine.flag_dualmic.set()
            if len(dat[1]) == 64:
                self.engine.flag_4kHz.set()
                print('dualmic: 4kHz, pkg size=',len(dat[1]),'bleaddr=',self.bleaddr)
            else:
                self.engine.flag_4kHz.clear()
                print('dualmic: not 4kHz, pkg size=', len(dat[1]),'bleaddr=',self.bleaddr)
            self.engine.flag_checked_fileformat.set()
        # q.put_nowait(dat)

        self.mic_pkg_cnt+=1
        self.prepare_statistic_output()
        # == rec
        if self.engine.thd_rec_flag.is_set():
            # print('\ndual dual')
            self.engine.recThd_audio.addData(dat)
            # print('mic_pkg',np.array(dat[:5]).shape)
    
    def handle_mic_pkg(self,dat):
        if not self.engine.flag_checked_fileformat.is_set():
            self.engine.flag_dualmic.clear()
            if len(dat[1]) == 64:
                self.engine.flag_4kHz.set()
                print('multimic: 4kHz, pkg size=', len(dat[1]),'bleaddr=',self.bleaddr)
            else:
                self.engine.flag_4kHz.clear()
                print('multimic: not 4kHz, pkg size=', len(dat[1]),'bleaddr=',self.bleaddr)
            self.engine.flag_checked_fileformat.set()
        # q.put_nowait(dat)

        self.mic_pkg_cnt+=1
        self.prepare_statistic_output()
        # == rec
        if self.engine.thd_rec_flag.is_set():
            self.engine.recThd_audio.addData(dat)
            # print('mic_pkg',np.array(dat[:5]).shape)

    def handle_ecg_raw_pkg(self,dat):
        if self.engine.thd_rec_flag.is_set():
            self.engine.recThd_ecg.addData([dat[0],dat[1]], ch=0)

        self.ecg_raw_pkg_cnt+=1
        self.prepare_statistic_output()

    def handle_ecg_heart_rate_pkg(self,dat):
        pass

    def handle_ecg_signal_quality_pkg(self,dat):
        pass

    def handle_imu_acc_pkg(self,dat):
        self.acc_pkg_cnt+=1
        self.prepare_statistic_output()
        if self.engine.thd_rec_flag.is_set():
            self.engine.recThd_acc.addData([dat[0],dat[2]], ch=dat[1])

    def handle_imu_gyro_pkg(self,dat):
        self.gyro_pkg_cnt+=1
        self.prepare_statistic_output()
        if self.engine.thd_rec_flag.is_set():
            # print('add ts data in gryo rec',dat[0])
            self.engine.recThd_gyro.addData([dat[0],dat[2]], ch=dat[1])            

    def handle_imu_mag_pkg(self,dat):
        self.mag_pkg_cnt+=1
        self.prepare_statistic_output()
        if self.engine.thd_rec_flag.is_set():
            self.engine.recThd_mag.addData([dat[0],dat[2]], ch=dat[1])

    def handle_imu_quaternion_pkg(self,dat):
        self.quat_pkg_cnt+=1
        self.prepare_statistic_output()
        if self.engine.thd_rec_flag.is_set():
            self.engine.recThd_quaternion.addData([dat[0],dat[2]], ch=dat[1])

    def calc_sr(self, name='', idx=2, dat=None):
        if self.pre_ts_pkg == 0:
            self.pre_ts_pkg = dat[0]
            self.quat_pkg_cnt = len(dat[idx])
        else:
            sr = self.quat_pkg_cnt / ((dat[0]-self.pre_ts_pkg)*4e-6)
            print(f'{name} sr={sr:.3f}Hz  data_len={self.quat_pkg_cnt}')
            self.pre_ts_pkg = dat[0]
            self.quat_pkg_cnt = len(dat[idx])

#===================================================================================

