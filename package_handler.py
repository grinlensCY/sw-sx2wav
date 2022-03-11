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
        self.cumm_accpkgCnt = 0
        self.accpkg_step_sec = 20/104

        self.acc_sr_list = []
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
            msg = (f'\nelapsed time: {(curr_ts-self.t0)/60:.1f}mins  processed:{self.cumm_accpkgCnt*self.accpkg_step_sec/60:.1f}mins  '
                    f'speed=processed/elapsed={self.cumm_accpkgCnt*self.accpkg_step_sec/(curr_ts-self.t0):.1f}\n')
            msg+="imu: {0:2.2f},{1:2.2f},{2:2.2f},{3:2.2f}; ".format(self.acc_pkg_cnt/diff_ts,self.gyro_pkg_cnt/diff_ts,self.mag_pkg_cnt/diff_ts,self.quat_pkg_cnt/diff_ts)
            msg+="ecg: {0:2.2f},{1:2.2f},{2:2.2f}; ".format(self.ecg_sq_pkg_cnt/diff_ts,self.ecg_hr_pkg_cnt/diff_ts,self.ecg_raw_pkg_cnt/diff_ts)
            msg+="mic: {0:2.1f}pkg/sec".format(self.mic_pkg_cnt/diff_ts)
            msg+="\ntemperature: {0:2.1f}, ".format(self.sys_t)
            msg+="powered by usb/qi: "+str(self.is_usb_pwr)
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
        ''' 
        [0]timestamp,               [1]firmware ver,    [2]hardware ver,    [3]battery level(%),
        [4]temperature(degreeC),    [5]ble addr,        [6]charging    ,    [7]Bat vol(mV),
        [8]imu_temperature(degC)
        '''
        self.is_usb_pwr=dat[6]
        self.engine.sysinfo = []
        for d in dat:
            self.engine.sysinfo.append(d)
        self.sys_t = dat[8] if dat[8] is not None else dat[4]
        # self.engine.sysinfo[4] = self.sys_t
        if not self.engine.flag_ble_addr.is_set():
            tmp = dat[5].hex()
            addr = ''
            for c in range(-2,-len(tmp)-1,-2):
                addr += f'{tmp[c]}{tmp[c+1]}:' if c!=-len(tmp)else tmp[c]+tmp[c+1]
            print('BLE addr:',addr.upper(),addr.replace(':','').upper())
            print(f'FW ver:{hex(dat[1])}\tHW ver:{hex(dat[2])}')
            # if dat[2] >= 32:
            #     self.engine.datainfo['acc']['sr'] = 104
            #     self.engine.datainfo['gyro']['sr'] = 104
            self.bleaddr = addr.replace(':','').upper()
            self.engine.flag_ble_addr.set()
        if self.engine.thd_rec_flag.is_set():
            # self.engine.recThd_sysinfo.addData([dat[0],dat[3],self.engine.sysinfo[4],dat[7]])
            tmp = self.engine.sysinfo.copy()
            tmp[5] = tmp[5].hex()
            self.engine.recThd_sysinfo.addData(tmp)

    def handle_dual_mic_pkg(self,dat):
        if not self.engine.flag_mic_sr_checked.is_set():
            self.engine.flag_dualmic.set()
            if len(dat[1]) == 64:
                self.engine.flag_4kHz.set()
                self.engine.datainfo['mic']['sr'] = 4000
                print('dualmic: 4kHz, pkg size=',len(dat[1]),'bleaddr=',self.bleaddr)
            else:
                self.engine.flag_4kHz.clear()
                self.engine.datainfo['mic']['sr'] = 2000
                print('dualmic: not 4kHz, pkg size=', len(dat[1]),'bleaddr=',self.bleaddr)
            self.engine.flag_mic_sr_checked.set()
        if self.engine.flag_mic_sr_checked.is_set() and self.engine.flag_imu_sr_checked.is_set():
            self.engine.flag_checked_fileformat.set()
        # q.put_nowait(dat)

        self.mic_pkg_cnt+=1
        self.prepare_statistic_output()
        # == rec
        if self.engine.thd_rec_flag.is_set() and not self.engine.config['onlylog']:
            # print('\ndual dual')
            self.engine.recThd_audio.addData(dat)
            # print('mic_pkg',np.array(dat[:5]).shape)
    
    def handle_mic_pkg(self,dat):
        if not self.engine.flag_mic_sr_checked.is_set():
            self.engine.flag_dualmic.clear()
            if len(dat[1]) == 64:
                self.engine.flag_4kHz.set()
                self.engine.datainfo['mic']['sr'] = 4000
                print('multimic: 4kHz, pkg size=', len(dat[1]),'bleaddr=',self.bleaddr)
            else:
                self.engine.flag_4kHz.clear()
                self.engine.datainfo['mic']['sr'] = 2000
                print('multimic: not 4kHz, pkg size=', len(dat[1]),'bleaddr=',self.bleaddr)
            self.engine.flag_mic_sr_checked.set()
        if self.engine.flag_mic_sr_checked.is_set() and self.engine.flag_imu_sr_checked.is_set():
            self.engine.flag_checked_fileformat.set()
        # q.put_nowait(dat)

        self.mic_pkg_cnt+=1
        self.prepare_statistic_output()
        # == rec
        if self.engine.thd_rec_flag.is_set() and not self.engine.config['onlylog']:
            self.engine.recThd_audio.addData(dat)
            # print('mic_pkg',np.array(dat[:5]).shape)

    def handle_ecg_raw_pkg(self,dat):
        if self.engine.thd_rec_flag.is_set() and not self.engine.config['onlylog']:
            self.engine.recThd_ecg.addData([dat[0],dat[1]], ch=0)

        self.ecg_raw_pkg_cnt+=1
        self.prepare_statistic_output()

    def handle_ecg_heart_rate_pkg(self,dat):
        pass

    def handle_ecg_signal_quality_pkg(self,dat):
        pass

    def handle_imu_acc_pkg(self,dat):
        self.acc_pkg_cnt+=1
        self.cumm_accpkgCnt += 1
        self.prepare_statistic_output()
        if self.engine.thd_rec_flag.is_set() and not self.engine.config['onlylog']:
            self.engine.recThd_acc.addData([dat[0],dat[2]], ch=dat[1])
        
        # print('self.engine.flag_imu_sr_checked.is_set()',self.engine.flag_imu_sr_checked.is_set(),len(self.acc_sr_list))
        
        if not self.engine.flag_imu_sr_checked.is_set() and len(self.acc_sr_list) < 6:
            sr = self.calc_sr('acc', 2, dat)
            if sr is not None:
                self.acc_sr_list.append(sr)
            if len(self.acc_sr_list) == 5:
                updated_sr = np.round(np.median(self.acc_sr_list)+0.0001,2)
                self.accpkg_step_sec = self.pkg_len/updated_sr
                for key in ['acc','gyro','mag','quaternion']:
                    self.engine.datainfo[key]['sr'] = updated_sr
                self.engine.flag_imu_sr_checked.set()
                print('\nPackageHandler: imu sr was confirmed!',self.engine.datainfo[key]['sr'],'Hz')
        if self.engine.flag_mic_sr_checked.is_set() and self.engine.flag_imu_sr_checked.is_set():
            self.engine.flag_checked_fileformat.set()

    def handle_imu_gyro_pkg(self,dat):
        self.gyro_pkg_cnt+=1
        self.prepare_statistic_output()
        if self.engine.thd_rec_flag.is_set() and not self.engine.config['onlylog']:
            # print('add ts data in gryo rec',dat[0])
            self.engine.recThd_gyro.addData([dat[0],dat[2]], ch=dat[1])            

    def handle_imu_mag_pkg(self,dat):
        self.mag_pkg_cnt+=1
        self.prepare_statistic_output()
        if self.engine.thd_rec_flag.is_set() and not self.engine.config['onlylog']:
            self.engine.recThd_mag.addData([dat[0],dat[2]], ch=dat[1])

    def handle_imu_quaternion_pkg(self,dat):
        self.quat_pkg_cnt+=1
        self.prepare_statistic_output()
        if self.engine.thd_rec_flag.is_set() and not self.engine.config['onlylog']:
            self.engine.recThd_quaternion.addData([dat[0],dat[2]], ch=dat[1])

    def calc_sr(self, name='', idx=2, dat=None):
        if self.pre_ts_pkg == 0:
            self.pre_ts_pkg = dat[0]
            self.pkg_len = len(dat[idx])
            sr = None
        else:
            sr = self.pkg_len / ((dat[0]-self.pre_ts_pkg)/self.engine.ts_Hz)
            if sr > 230:
                print(f'PackageHandler: {name} sr={sr:.2f}Hz > 230 --> update ts_Hz {self.engine.ts_Hz} ==> 32768')
                self.engine.ts_Hz = 32768
                sr = self.pkg_len / ((dat[0]-self.pre_ts_pkg)/self.engine.ts_Hz)
            if sr <= 90:
                print(f'PackageHandler: {name} data_len={self.pkg_len} sr={sr:.2f}Hz <= 90Hz ==> pkgloss?')
                time.sleep(0.3)
                sr = None
                # if len(self.acc_sr_list):
                #     print(f'PackageHandler: {name} ')
                #     if 102 < np.mean(self.acc_sr_list) < 106:
                #         sr = 104
                #     elif 190 < np.mean(self.acc_sr_list) < 220:
                #         sr = 208
                #     else:
                #         sr = None
                # else:
                #     sr = None
            self.pre_ts_pkg = dat[0]
            self.pkg_len = len(dat[idx])
            if self.pkg_len != 20 and self.pkg_len != 32 and self.pkg_len != 64:
                sr = None
            print(f'PackageHandler: {name} sr={sr}Hz  data_len={self.pkg_len}')
        return sr

#===================================================================================

