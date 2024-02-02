import os,threading,time,json,shutil,csv
import shutil
import file_driver as FD
import signal
from package_handler import PackageHandler
from WriteDataToFileThread import RecThread
from WriteDataToFileThread6ch import RecThread as RecThread6ch
import protocol as PRO
import protocol_6ch as PRO6ch
import tkinter as tk
from tkinter import filedialog
from zipfile import ZipFile

from serialdb import SerialDB

class Engine:
    def __init__(self,datainfo=None, config=None, stopped_flag=None):
        self.datainfo = datainfo

        self.config = config
        self.ts_Hz = 250000

        self.thd_rec_flag = threading.Event()
        self.stopped_flag = stopped_flag

        self.reset()

        self.data_retriever = None
        self.recThd_audio = None
        self.recThd_acc = None
        self.recThd_ecg = None
        self.recThd_gyro = None
        self.recThd_mag = None
        self.recThd_quaternion = None
        self.recThd_sysinfo = None
        # self.recT0 = None
        self.input = ''
        self.flag_stop_ChkRecThd = threading.Event()
        self.flag_checked_fileformat = threading.Event()
        self.flag_imu_sr_checked = threading.Event()
        self.flag_mic_sr_checked = threading.Event()
        self.flag_4kHz = threading.Event()
        self.flag_dualmic = threading.Event()
        self.flag_ble_addr = threading.Event()
        self.strPkgSpd = ''
        self.bleaddr = None
        self.srcdir = ''
        self.thd_ChkRecThd = None

        self.keyfn = ''

    def start(self):
        print('engine start')
        self.data_retriever.start()
        self.flag_stop_ChkRecThd.clear()
        self.thd_ChkRecThd = threading.Thread(target=self.chkRecThd, args=(self.flag_stop_ChkRecThd,),
                                                  name='thd_ChkRecThd')
        self.thd_ChkRecThd.start()

    def reset(self):
        self.input = ''

    def depose(self):
        self.stop()

    def stop(self):        
        if self.thd_rec_flag.is_set():
            self.setRec()
        
        print('--stop thd_ChkRecThd')
        self.flag_stop_ChkRecThd.set()
        if self.thd_ChkRecThd is not None and self.thd_ChkRecThd.is_alive():
            time.sleep(3)
            print('main self.thd_ChkRecThd.is_alive',self.thd_ChkRecThd.is_alive())
            self.thd_ChkRecThd = None

        print('--stop data_retriever')
        if(self.data_retriever is not None):
            self.data_retriever.stop()
            self.data_retriever=None
        
        self.reset()
        self.stopped_flag.set()

        print('engine stop')
    
    def chkRecThd(self, flag):
        print('start to ChkRecThd')
        t0 = time.time()
        while not flag.wait(5):
            if self.data_retriever.thd_run_flag is not None:  print(self.strPkgSpd)
            # print(f'chkRecThd: elapsed time={time.time()-t0:.2f}sec')
            isRun = False
            if self.recThd_audio is not None and not self.config['onlylog']:
                isRun |= not self.recThd_audio.stopped()
                print('\nisRun',isRun)
                elapsedT = time.time()-t0
                speed = self.recThd_audio.processedT/elapsedT
                print((f'self.recThd_audio.stopped() {self.recThd_audio.stopped()}\n'
                        f'elapsed time={elapsedT/60:.1f}mins  '
                        f'processed={self.recThd_audio.processedT/60:.1f}mins  '
                        f'speed={speed:.1f}  '
                        f'progress={self.recThd_audio.processedT/self.duration:.1%}  '
                        f'processing Time_remaining= {(self.duration-self.recThd_audio.processedT)/speed/60:.1f}mins'))
                if not self.config['onlyChkpkgloss']:
                    isRun |= not self.recThd_acc.stopped()
                    print(isRun,'self.recThd_acc.stopped()', self.recThd_acc.stopped())
                    # isRun |= not self.recThd_ecg.stopped()
                    # print(isRun,'self.recThd_ecg.stopped()', self.recThd_ecg.stopped())
                    isRun |= not self.recThd_gyro.stopped()
                    print(isRun,'self.recThd_gyro.stopped()', self.recThd_gyro.stopped())
                    isRun |= not self.recThd_mag.stopped()
                    print(isRun,'self.recThd_mag.stopped()', self.recThd_mag.stopped())
                    isRun |= not self.recThd_quaternion.stopped()
                    print(isRun,'self.recThd_quaternion.stopped()', self.recThd_quaternion.stopped())
            isRun |= not self.recThd_sysinfo.stopped()
            print(isRun,'self.recThd_sysinfo.stopped()', self.recThd_sysinfo.stopped())
            if not isRun:
                flag.set()
                break
        self.stop()

    def updateConfig(self,config):
        self.config = config

    def getDstdir(self,sx_fn,userdir_kw):
        ts = self.getTsOfFn(sx_fn,ms=False)     # float(os.path.basename(sx_fn)[:-3])/1000
        wavfnkw_ts = f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))}'
        str_date = time.strftime("%Y-%m-%d", time.localtime(ts))

        dstdir = ''
        dstdir2 = ''
        userdir2 = ''
        if userdir_kw in self.config['fj_dir_kw']:
            dstdir =  f"{self.config['dir_Export_fj']}/{self.bleaddr}/{str_date}"
            userdir = f"{self.config['dir_Export_fj']}/{self.bleaddr}"
        elif self.config['dir_Export'] == self.config['dir_savSX']:
            for folder in os.listdir(self.config['dir_Export']):
                # if folder[-4:] == f"{self.bleaddr[-4:]}" or folder == userdir_kw or len(self.config['dirList_load_S3zip']):
                if folder == userdir_kw:
                    dstdir =  f"{self.config['dir_savSX']}/{folder}/{str_date}"
                    userdir = f"{self.config['dir_savSX']}/{folder}"
                    break
            if not dstdir and len(self.config['dirList_load_S3zip']):
                dstdir =  f"{self.config['dir_savSX']}/{userdir_kw}/{str_date}"
                userdir = f"{self.config['dir_savSX']}/{userdir_kw}"

        if not dstdir:  # if can't find any folder matching the ble address or no assigned dir_Export
            str_bleaddr_2 = ""
            if self.bleaddr:
                for i,s in enumerate(self.bleaddr):
                    if i%2: continue
                    str_bleaddr_2 += self.bleaddr[i:i+2]+'_' if i!=10 else self.bleaddr[i:i+2]
                if self.bleaddr in self.srcdir or str_bleaddr_2 in self.srcdir:
                    # if int(str_date[:4]) < 2020:
                    #     dstdir = f"{self.srcdir}"
                    dstdir = (f"{self.srcdir}/"
                            f'{str_date}')
                    userdir = f"{self.srcdir}/"
                else:
                    dstdir = (f"{self.srcdir}/"
                                f'{self.bleaddr}/'
                                f'{str_date}')
                    userdir = f"{self.srcdir}/{self.bleaddr}/"
            else:
                srcdir = os.path.dirname(sx_fn)
                dstdir = (f"{srcdir}/"
                            f'{str_date}')
                userdir = f"{srcdir}/"
        dstdir = dstdir.replace('/merged','')
        userdir = userdir.replace('/merged','')
        print(f'setRec: dstdir={dstdir}\nuserdir={userdir}')
        if not os.path.exists(dstdir):
            os.makedirs(dstdir)
        # if not os.path.exists(dstdir2):
        #     os.makedirs(dstdir2)
        return dstdir,wavfnkw_ts,userdir,dstdir2,userdir2

    def chk_files_format(self,sx_fn='',cnt=0, userdir_kw='', thisSXdict={}):
        self.duration = thisSXdict['duration']
        self.srcdir = os.path.dirname(sx_fn)
        ts = self.getTsOfFn(sx_fn,ms=False)
        self.flag_ble_addr.clear()
        print(f'\nrecording time:{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))}')
        print('chk_files_format sx_fn: ', sx_fn)
        # fnstr = sx_fn.split("/")[-2:] if len(sx_fn.split("/"))>1 else sx_fn.split("\\")[-2:]
        # self.input = '_'.join(fnstr)
        if self.srcdir and (sx_fn.endswith('sx') or sx_fn.endswith('sxr')):
            self.keyfn = f"{sx_fn[:-4]}_keyiv.txt" if '.sxr' in sx_fn else ''
            if os.path.exists(self.keyfn):
                print(f"keyiv file:{self.keyfn} exists!")
                with open(self.keyfn,'r') as f:
                    tmp = f.readline()
                self.key = tmp.split(',')[0]
                self.iv = tmp.split(',')[1]
            else:
                print(f"keyiv file:{self.keyfn} does NOT exist!")
                self.key = self.config['key']
                self.iv = self.config['iv']
                self.keyfn = None
                if not self.key and sx_fn.endswith('sxr'):
                    ble = input('sxr needs key! keyin BLEmac in XX:XX:XX:XX:XX:XX or XX.....XX Enter:default key  others:mac :')
                    if ble:
                        db = SerialDB('./db/dut_20231213.db')
                        res = db.get_key_qrcode(ble=ble)
                        if res:
                            tmp = res.split(',')
                            self.key = tmp[1]
                            self.iv = tmp[2]
            drv = FD.Driver(sx_fn)
            pkg_handler = PackageHandler(self)
            # self.data_retriever = PRO.Protocol(drv,'sxFile',self.config['skipPkgCnt'],key=self.key,iv=self.iv)
            self.data_retriever = (PRO.Protocol(drv,'sxFile',self.config['skipPkgCnt'],key=self.key,iv=self.iv)
                                    if not self.config['6ch']
                                    else PRO6ch.Protocol(drv,'sxFile',self.config['skipPkgCnt'],key=self.key,iv=self.iv))
            self.data_retriever.set_sys_info_handler(pkg_handler)
            self.data_retriever.set_mic_data_handler(pkg_handler)
            self.data_retriever.set_imu_data_handler(pkg_handler)
            self.data_retriever.set_ecg_data_handler(pkg_handler)
            self.data_retriever.set_endingTX_callback(self.endingTX_callback)
            self.data_retriever.start()
            self.flag_checked_fileformat.clear()
            self.flag_imu_sr_checked.clear()
            self.flag_mic_sr_checked.clear()
            cnt = 0
            while not self.flag_checked_fileformat.wait(1):
                cnt+=1
                print('\nwait for receiving file format',cnt,'\n')
                if cnt>20:
                    self.stop()
                    print(f'quit {os.path.basename(sx_fn)}, having waited for format check too long time'
                        ,file=open('log.txt','a',newline='', encoding='utf-8-sig'))
                    break
            cnt = 0
            while not self.flag_ble_addr.wait(0.5):
                cnt += 1
                print('wait for receiving ble addre',cnt)
                if cnt > 10:
                    input(f'ble addr of {os.path.basename(sx_fn)} is unknown! any key to go on')
                    print(f'ble addr of {os.path.basename(sx_fn)} is unknown!'
                          ,file=open('log.txt','a',newline='', encoding='utf-8-sig'))
                    break
        if self.flag_checked_fileformat.is_set():
            print(f'format checked:{self.flag_checked_fileformat.is_set()}  '
                    f'4kHz:{self.flag_4kHz.is_set()}  dualmic:{self.flag_dualmic.is_set()}  '
                    f'BLE addr:{pkg_handler.bleaddr} ')
            if not self.flag_imu_sr_checked.is_set():
                self.config['onlylog'] = 10
                print('\nimu_sr is NOT confirmed ==> force to be onlylog mode!\n')
            else:            
                print(f'acc sr:{self.datainfo["acc"]["sr"]} '
                        f'gyro sr:{self.datainfo["gyro"]["sr"]}')
            if pkg_handler.bleaddr is None:
               self.stop()
               return pkg_handler.bleaddr,'','','','','',''
            if self.config['onlySelectedBle'] not in pkg_handler.bleaddr:
                print('onlySelectedBle not in pkg_handler.bleaddr')
                self.stop()
                return pkg_handler.bleaddr,'','','','','',''
            if self.config['onlyChkFormat']:
                print('onlyChkFormat',self.config['onlyChkFormat'])
                self.stop()
                return pkg_handler.bleaddr,'','','','','',''
            # self.datainfo['mic']['sr'] = 4000 if self.flag_4kHz.is_set() else 2000
            self.bleaddr = pkg_handler.bleaddr if self.flag_ble_addr.is_set() else "unknownBLE"
            self.datainfo['ble'] = self.bleaddr
            self.datainfo['dualmic'] = self.flag_dualmic.is_set()
            if thisSXdict:
                thisSXdict['imu_sr'] = self.datainfo["acc"]["sr"]
                thisSXdict['mic_sr'] = self.datainfo["mic"]["sr"]
                thisSXdict['dualmic'] = self.flag_dualmic.is_set()
                thisSXdict['ble'] = self.bleaddr
            if self.data_retriever is not None:
                self.data_retriever.stop()
            # == handle log and sx file
            # self.srcdir = os.path.dirname(sx_fn)
            dstdir,wavfnkw_ts,userdir,dstdir2,userdir2 = self.getDstdir(sx_fn,userdir_kw)
            # = log
            log_srcfn = sx_fn.replace("sxr","log").replace("sx","log")
            log_dstfn = f'{dstdir}/{wavfnkw_ts}.log'
            if os.path.exists(log_srcfn) and not os.path.exists(log_dstfn):
                print('move log to',log_dstfn)
                # shutil.move(log_srcfn,log_dstfn)
            elif os.path.exists(log_srcfn) and os.path.exists(log_dstfn):
                print(f'{log_dstfn} exists. Removing {log_srcfn}.') 
                # if self.config['overwrite']:
                os.remove(log_dstfn)
                print('overwrite', log_dstfn)
            if os.path.exists(log_srcfn):
                shutil.move(log_srcfn,log_dstfn)
                # else:
                #     os.remove(log_srcfn)
            if self.config['onlyMovelog']:
                print('onlyMovelog ==> Stop!')
                self.stop()
                return '','','','','','',''
            self.set_files_source(reset=False,sx_fn=sx_fn, wavfnkw_ts=wavfnkw_ts, dstdir=dstdir)
            # self.stop()
            return self.bleaddr, dstdir, userdir, self.flag_dualmic.is_set(), dstdir2, userdir2, wavfnkw_ts
        else:
            return '','','','','','',''

    def set_files_source(self,reset=True,sx_fn='',wavfnkw_ts='',dstdir=''):
        if reset: self.stop()
        # self.srcdir = os.path.dirname(sx_fn)
        print('sx_fn: ', sx_fn)
        fnstr = sx_fn.split("/")[-2:] if len(sx_fn.split("/"))>1 else sx_fn.split("\\")[-2:]
        self.input = '_'.join(fnstr)
        if self.srcdir and (sx_fn.endswith('sx') or sx_fn.endswith('sxr')):
            drv = FD.Driver(sx_fn)
            pkg_handler = PackageHandler(self)
            # self.data_retriever = PRO.Protocol(drv,'sxFile',self.config['skipPkgCnt'],key=self.key,iv=self.iv)
            self.data_retriever = (PRO.Protocol(drv,'sxFile',self.config['skipPkgCnt'],key=self.key,iv=self.iv)
                                    if not self.config['6ch']
                                    else PRO6ch.Protocol(drv,'sxFile',self.config['skipPkgCnt'],key=self.key,iv=self.iv))
            self.data_retriever.set_sys_info_handler(pkg_handler)
            self.data_retriever.set_mic_data_handler(pkg_handler)
            self.data_retriever.set_imu_data_handler(pkg_handler)
            self.data_retriever.set_ecg_data_handler(pkg_handler)
            self.data_retriever.set_endingTX_callback(self.endingTX_callback)
            if self.keyfn and not os.path.exists(self.keyfn) and self.config['key']:
                with open(self.keyfn,'w',newline='') as f:
                    f.write(f"{self.config['key']},{self.config['iv']}")
                print('write key/iv in',self.keyfn)
            # sys.exit()

        go = self.setRec(dstdir,wavfnkw_ts)
        if go:
            print('going to start Engine again for recording!')
            self.start()

    def setRec(self,dstdir='',wavfnkw_ts=''):
        if not self.thd_rec_flag.is_set():
            dstfn_prefix = f'{dstdir}/{wavfnkw_ts}'
            recT0 = time.mktime(time.strptime(wavfnkw_ts,"%Y-%m-%d-%H-%M-%S"))
            # if os.path.exists(os.path.dirname(dstdir)):
            if os.path.exists(dstdir):
                existfns = [fn for fn in os.listdir(dstdir) if wavfnkw_ts in fn]
            else:
                existfns = ''
                os.makedirs(os.path.dirname(dstdir))

            print(f"setRec: wavfnkw_ts={wavfnkw_ts}")
            print(f"setRec: dstdir={dstdir}")
            print(f"setRec: existfns={existfns}")
            # existfns = [fn for fn in os.listdir(os.path.dirname(dstdir)) if wavfnkw_ts in fn]
            print(f"setRec: dstfn_prefix={dstfn_prefix}")
            if len(existfns):
                print(f'{existfns[0]} exists!')
                # if self.config['overwrite']:
                print('going to overwrite it!')
                [os.remove(f"{dstdir}/{fn}") for fn in existfns if fn.endswith('.wav')]

                # else:
                #     print('going to skip it!')
                #     self.stop()
                #     return False
            if not self.config['onlylog']:
                if self.config['6ch']:
                    self.recThd_audio = RecThread6ch(self.datainfo['mic']['sr'],
                                            1, 0.04, dstfn_prefix, 'mic',
                                            self.datainfo['mic']['fullscale'],recT0,self.config,self.ts_Hz)
                else:
                    self.recThd_audio = RecThread(self.datainfo['mic']['sr'],
                                            1, 0.04, dstfn_prefix, 'mic',
                                            self.datainfo['mic']['fullscale'],
                                            self.flag_dualmic.is_set(),recT0,config,self.ts_Hz)
                self.recThd_audio.start()
                if not self.config['onlyChkpkgloss']:
                    self.recThd_acc = RecThread(int(self.datainfo['acc']['sr']),
                                                4, 0.04, dstfn_prefix,'acc',
                                                self.datainfo['acc']['fullscale'],
                                                self.flag_dualmic.is_set(),recT0,config,self.ts_Hz)
                    self.recThd_acc.start()
                    # self.recThd_ecg = RecThread(self.datainfo['ecg']['sr'],
                    #                             2, 0.01, dstfn_prefix, 'ecg',
                    #                             self.datainfo['ecg']['fullscale'],config,self.ts_Hz)
                    # self.recThd_ecg.start()
                    self.recThd_gyro = RecThread(int(self.datainfo['gyro']['sr']),
                                                4, 0.04, dstfn_prefix, 'gyro',
                                                self.datainfo['gyro']['fullscale'],
                                                self.flag_dualmic.is_set(),recT0,config,self.ts_Hz)
                    self.recThd_gyro.start()
                    self.recThd_mag = RecThread(int(self.datainfo['mag']['sr']),
                                                4, 0.04, dstfn_prefix, 'mag',
                                                self.datainfo['mag']['fullscale'],
                                                self.flag_dualmic.is_set(),recT0,config,self.ts_Hz)
                    self.recThd_mag.start()
                    self.recThd_quaternion = RecThread(int(self.datainfo['quaternion']['sr']),
                                                    5, 0.04, dstfn_prefix, 'quaternion',
                                                    self.datainfo['quaternion']['fullscale'],
                                                self.flag_dualmic.is_set(),recT0,config,self.ts_Hz)
                    self.recThd_quaternion.start()
            self.recThd_sysinfo = RecThread(1,
                                            3, 0.09, dstfn_prefix, 'sysinfo',
                                            1,recT0=recT0,config=config,ts_Hz=self.ts_Hz)
            self.recThd_sysinfo.start()
            self.thd_rec_flag.set()
            return True
        else:
            print('stop rec')
            self.thd_rec_flag.clear()
            if not self.config['onlylog']:
                self.recThd_audio.stop()
                self.recThd_audio.join(0.5)
                # print('self.recThd_audio ',self.recThd_audio.is_alive())
                self.recThd_audio = None
                if not self.config['onlyChkpkgloss']:
                    self.recThd_acc.stop()
                    self.recThd_acc.join(0.5)
                    # print('self.recThd_acc ',self.recThd_acc.is_alive())
                    self.recThd_acc = None
                    # self.recThd_ecg.stop()
                    # self.recThd_ecg.join(0.5)
                    # # print('self.recThd_ecg ',self.recThd_ecg.is_alive())
                    # self.recThd_ecg = None
                    self.recThd_gyro.stop()
                    self.recThd_gyro.join(0.5)
                    # print('self.recThd_gyro ',self.recThd_gyro.is_alive())
                    self.recThd_gyro = None
                    self.recThd_mag.stop()
                    self.recThd_mag.join(0.5)
                    # print('self.recThd_mag ',self.recThd_mag.is_alive())
                    self.recThd_mag = None
                    self.recThd_quaternion.stop()
                    self.recThd_quaternion.join(0.5)
                    # print('self.recThd_quaternion ',self.recThd_quaternion.is_alive())
                    self.recThd_quaternion = None
            self.recThd_sysinfo.stop()
            self.recThd_sysinfo.join(0.5)
            self.recThd_sysinfo = None
            # self.recT0 = None
    
    def endingTX_callback(self):
        print('stop data_retriever')
        self.data_retriever.stop()
    
    def getTsOfFn(self,fn,ti=0,ms=True):
        bn = os.path.basename(fn)
        bn_split = bn.split('_')
        if bn.startswith('FILE'):
            return int(bn[4:-3])
        elif bn.startswith('log') and len(bn_split)==2:    # log_00000035.sx
            return ti
        elif bn.startswith('dev') or bn.startswith('log'):  # dev0_20_1646953956142.sx  log_0_xxxxx.sx
            if ms:
                return float(bn_split[-1][:-3])
            else:
                return float(bn_split[-1][:-3])/1000
        else:   # 1646693225364.sx or .sxr
            idx = len(bn.split('.')[-1])+1
            if ms:
                return float(bn[:-idx])
            else:
                return float(bn[:-idx])/1000


def updateConfig(engine=None, config=None):
    if config:
        with open(f"{os.path.join(os.path.dirname(__file__),'config.json')}", 'w', encoding='utf-8-sig') as jout:
            json.dump(config, jout, indent=4, ensure_ascii=False)
    else:
        with open(f"{os.path.join(os.path.dirname(__file__),'config.json')}", 'r', encoding='utf-8-sig') as reader:
            config = json.loads(reader.read())
        if engine is not None:
            engine.updateConfig(config)
        print('update config')
        return config

def hhmmss(sec):
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f'{h:02.0f}:{m:02.0f}:{s:02.0f}'

def getTsOfFn(fn,ti=0,ms=True):
    bn = os.path.basename(fn)
    bn_split = bn.split('_')
    if bn.startswith('FILE'):
        return int(bn[4:-3])
    elif bn.startswith('log') and len(bn_split)==2:    # log_00000035.sx
        return ti
    elif bn.startswith('dev') or bn.startswith('log'):  # dev0_20_1646953956142.sx  log_0_xxxxx.sx
        if ms:
            return float(bn_split[-1][:-3])
        else:
            return float(bn_split[-1][:-3])/1000
    elif bn.endswith('.zip') and len(bn) > 20:  # DA_EE_30_CB_E4_8C-1694675778197.zip  by rawdata_recorder APP
        if ms:
            return float(bn.split('-')[-1][:-4])
        else:
            return float(bn.split('-')[-1][:-4])/1000
    else:   # 1646693225364.sx or .sxr
        idx = len(bn.split('.')[-1])+1
        if ms:
            return float(bn[:-idx])
        else:
            return float(bn[:-idx])/1000

def findFileset(datainfo, config, kw='audio-main',srcdir='', loadall=True, onlyChkTS=False, sx_dict={}):
    root = tk.Tk()
    root.withdraw()

    srcdir = config['dirToloadFile'][0] if not srcdir else srcdir
    
    tfn = filedialog.askopenfilename(initialdir=sdir,filetypes=[("SX File",(f"*{kw}*.sxr",f"*{kw}*.sx",f"*{kw}*.zip"))])
    if not tfn:
        return ''
    srcdir = os.path.dirname(tfn)
    ts_range = [0,0]
    if len(config["ts_loadS3"]):
        ts_range[0] = time.mktime(time.strptime(f'{config["ts_loadS3"][0]}', "%Y%m%d"))*1000
        if config["ts_loadS3"][1] < config["ts_loadS3"][0]:
            config["ts_loadS3"][1] = config["ts_loadS3"][0]+1
        try:
            ts_range[1] = time.mktime(time.strptime(f'{config["ts_loadS3"][1]+1}', "%Y%m%d"))*1000
        except ValueError:
            ts_range[1] = (config["ts_loadS3"][1]+1-config["ts_loadS3"][0])*60*60*24*1000+ts_range[0]
    if len(config['ts_range_sx']):
        ts_range[0] = ts_range[0] if config['ts_range_sx'][0] == -1 else max(ts_range[0],config['ts_range_sx'][0])
        ts_range[1] = time.time()*1000 if config['ts_range_sx'][-1] == -1 or not ts_range[1] else min(ts_range[1],config['ts_range_sx'][-1])
    print('updated ts_range',ts_range)
    if loadall:
        fns_list = [f'{srcdir}/{fn}' for fn in os.listdir(srcdir)
                if fn.endswith('.sxr') or fn.endswith('.sx') or (fn.endswith('.zip') and len(fn)>13)]
        skip_list = []
        # if not onlyChkTS:
        for fn in fns_list:
            ts = getTsOfFn(fn,ms=False)
            fsize = os.path.getsize(fn)
            basefn = os.path.basename(fn)
            fsizepermin = 38000 if config['6ch'] else 20000
            if ts:
                recTime = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))
                msg = (f'{basefn}  recording start at:{recTime}  '
                        f'file size:{os.path.getsize(fn)}=>{hhmmss(fsize/fsizepermin)}')
            else:
                recTime = 'SD_card_unknown'
                msg = (f'{basefn}  recording start at:{recTime}  '
                        f'file size:{os.path.getsize(fn)}=>{hhmmss(fsize/fsizepermin)}')
            if fsize < 1600:     # < 5sec
                msg += f"  ==>duration < 5sec==>quit!"
                print(msg)
                skip_list.append(basefn)
                continue
            print(msg)
            if (ts_range[0] != 0 and ts_range[1] != 0) and recTime != 'SD_card_unknown':
                # fnidx = basefn.find('.')
                # ts = int(basefn[:fnidx])
                # ts_range[1] = max(ts, ts_range[1])
                ts_range_str = [time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts_range[0]/1000)),
                                time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts_range[1]/1000))]
                if ts*1000 < ts_range[0] or ts*1000 > ts_range[1]:
                    print(f"\tis beyond specified range {ts_range}={ts_range_str} ==> skip it")
                    skip_list.append(basefn)
                    continue
            if not config['onlytst0'] and fn.endswith('zip'):
                try:
                    with ZipFile(fn) as myzip:
                        for zipfn in myzip.namelist():
                            if zipfn.endswith('sx') and not os.path.exists(f'{srcdir}\{zipfn.replace("zip","sx")}'):
                                print('going to upzip',zipfn)
                                # myzip.extract(zipfn,path=srcdir)
                                myzip.extractall(path=srcdir)
                except:
                    print('error in unzip --> skipe')
                    continue
        fns = [f'{srcdir}/{fn}' for fn in os.listdir(srcdir)
                if ((fn.endswith('.sxr') or fn.endswith('.sx')) and fn not in skip_list)]
        if os.path.basename(fns[0]).startswith('log_'):
            fns.sort(key=lambda x:int(os.path.basename(x).split('_')[1]))
        else:
            fns.sort(key=lambda x:os.path.basename(x).split('_')[-1])
        if config['delzip']:
            for fn in fns_list:
                if fn.endswith('.zip'):
                    os.remove(fn)
    else:
        if tfn.endswith('zip'):
            with ZipFile(tfn) as myzip:
                for zipfn in myzip.namelist():
                    if zipfn.endswith('sx') and not os.path.exists(f'{srcdir}\{zipfn.replace("zip","sx")}'):
                        print('going to upzip',zipfn)
                        # myzip.extract(zipfn,path=srcdir)
                        myzip.extractall(path=srcdir)
        fns = [tfn.replace(".zip",".sx")]
        datainfo['user_srcdir'] = srcdir.split('\\')[-1]
        datainfo['sxfn'] = tfn
    print('final list is ...')
    user_srcdir = os.path.basename(srcdir) #srcdir.split('\\')[-1]
    for fn in fns:
        ts = getTsOfFn(fn,ms=False)     #float(os.path.basename(fn)[:-3])/1000
        basefn = os.path.basename(fn)
        if ts:
            recTime = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))
            msg = (f'{basefn}  recording start at:{recTime}  '
                    f'file size:{os.path.getsize(fn)}=>{hhmmss(os.path.getsize(fn)/20000)}')
        else:
            recTime = 'SD_card_unknown'
            msg = (f'{basefn}  recording start at:{recTime}  '
                    f'file size:{os.path.getsize(fn)}=>{hhmmss(os.path.getsize(fn)/20000)}')
        print(msg)
        sx_dict[basefn] = {'user_srcdir':user_srcdir,
                            'recTime':recTime,
                            'ble':'',
                            'mic_sr':0,
                            'imu_sr':0,
                            'dualmic':False,
                            'duration':os.path.getsize(fn)/20000,
                            'duration_hhmmss':hhmmss(os.path.getsize(fn)/20000)}
    fn_log = f'{srcdir}/{time.strftime("%Y-%m-%d", time.localtime())}.log'
    with open(fn_log, 'w', newline='', encoding='utf-8-sig') as jout:
        json.dump(sxdict, jout, indent=4, ensure_ascii=False)
    if len(fns) == 1:
        datainfo['recTime'] = recTime
        datainfo['sxfn'] = fns[0]
        datainfo['user_srcdir'] = srcdir.split('\\')[-1]
    print()
    return fns

def unzipS3(srcList,dst,tsRange,overwrite,onlyChkTS,sx_dict):
    ti = time.mktime(time.strptime(f'{tsRange[0]}', "%Y%m%d"))*1000
    try:
        tf = time.mktime(time.strptime(f'{tsRange[1]+1}', "%Y%m%d"))*1000
    except ValueError:
        tf = (tsRange[1]+1-tsRange[0])*60*60*24*1000+ti
    sx_list = []
    usrsrcdir_list = []
    for srcdir in srcList:
        user_srcdir = os.path.basename(srcdir)
        print('check',srcdir,'\nuser dir:',user_srcdir)
        fns = [f'{srcdir}/{fn}' for fn in os.listdir(srcdir)
                if fn.endswith('.zip')
                    and len(fn) == 17
                    and ti <= float(fn[:-3]) <= tf]
        for fn in fns:
            ts = float(os.path.basename(fn)[:-3])/1000
            recTime = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))
            print('going to upzip',fn,'\n\tsize',os.stat(fn).st_size>>10,'KB\trec time:',recTime)
            if os.stat(fn).st_size>>10 < 200:
                print('\tto small to process it')
                continue
            with ZipFile(fn) as myzip:
                for zipfn in myzip.namelist():
                    if not zipfn.endswith('sx'):
                        continue
                    # ts = float(zipfn[:-3])/1000
                    # recTime = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))
                    filesize = myzip.getinfo(zipfn).file_size
                    msg = (f'{zipfn}>> size:{filesize>>10}KB')
                    if myzip.getinfo(zipfn).file_size>>10 < 200:
                        print(f'{msg}: filesize is too small!')
                        continue
                    if zipfn in sx_dict:
                        msg += ' has been in converted list!'
                        if not overwrite:
                            print(f'{msg} ==> skip')
                            continue
                    else:
                        sx_dict[zipfn] = {'user_srcdir':user_srcdir,
                                            'recTime':recTime,
                                            'ble':'',
                                            'mic_sr':0,
                                            'imu_sr':0,
                                            'dualmic':False,
                                            'duration':0}
                        print(msg)
                    if not onlyChkTS:
                        if (zipfn.endswith('sx')
                                and (not os.path.exists(f'{dst}/{zipfn}')
                                        or overwrite
                                        or not os.path.exists(f'{dst}/{zipfn}'.replace('.sx','log')))):
                            print(f'\tgoing to upzip to {dst} ')
                            # myzip.extract(zipfn,path=dst)
                            myzip.extractall(path=dst)
                        else:
                            print(zipfn,'exists?',os.path.exists(f'{dst}/{zipfn}'),'recording time:',recTime)
                        sx_list.append(f'{dst}/{zipfn}')
                        usrsrcdir_list.append(user_srcdir)
    if len(sx_list) == 1:
        datainfo['recTime'] = recTime
        datainfo['sxfn'] = sx_list[0]
        datainfo['user_srcdir'] = user_srcdir
    return sx_list,usrsrcdir_list

def mergeSX(sxfns,userlist,last_merged_dict,sx_dict):
    global config
    if len(sxfns) < 2:
        return sxfns
    last_stop_ts = 0
    first_sxfn = None
    first_user = None
    first_sx_keyfn = None
    cum_sxData = None
    cum_logdata = None
    new_sxfns = []
    new_userlist = []
    merged_sxfns = []
    cum_cnt = 0
    cum_duration = 0
    sxpool = os.path.dirname(sxfns[0])+'/merged' if not config['onlytst0'] else os.path.dirname(sxfns[0])
    # mergelog_fn = f'{sxpool}/merge.log'
    # if os.path.exists(mergelog_fn):
    #     with open(mergelog_fn,'r',newline='',encoding='utf-8-sig') as jf:
    #         mergelog = json.loads(jf.read())
    # else:
    #     mergelog = {}
    if not os.path.exists(sxpool):
        os.makedirs(sxpool)

    ts_log_fn = f"{os.path.dirname(sxfns[0])}/ts_log.txt"
    tslog = {}
    if os.path.exists(ts_log_fn):
        print('\nfound ts_log.txt!')
        with open(ts_log_fn, 'r', newline='') as csvfile:
            rows = csv.reader(csvfile, delimiter=',', skipinitialspace=True)
            for row in rows:
                basefn = os.path.basename(row[0])
                tslog[f"{basefn}"] = {'start_ts':int(row[1]),'stop_ts':int(row[2])}

    if input('start merging? Enter:go  Others:quit  '):
        shutil.rmtree(sxpool)
        sys.exit()
    for i,fn in enumerate(sxfns):
        basefn = os.path.basename(fn)
        logfn = fn.replace(".sxr",".log").replace(".sx",".log")
        mustMerge = basefn.startswith('log') or basefn.startswith('dev')
        print(f'\treading {basefn} mustMerge={mustMerge}')
        if tslog != {}:
            if basefn in tslog.keys():
                log = tslog[basefn]
            else:
                log = {'start_ts':getTsOfFn(sxfns[i-1])}
        elif os.path.exists(logfn):
            with open(logfn, 'r', newline='',encoding='utf-8-sig') as jf:
                log = json.loads(jf.read())
        # elif not mustMerge:
        #     new_sxfns.append(f'{sxpool}/{basefn}')
        #     if not config['onlytst0']:
        #         shutil.copy2(fn,new_sxfns[-1])
        #     new_userlist.append(userlist[i])
        #     continue
        else:
            log = {'start_ts':getTsOfFn(fn)}
        
        # if basefn in mergelog and mergelog[basefn]:
        #     continue
        # else:
        # mergelog[basefn] = False
        with open(fn, 'rb') as f:
            buf = f.read()

        if not last_stop_ts:    # first of sxfns
            first_sxfn = f'{sxpool}/{basefn}'
            if not config['onlytst0']:
                shutil.copy2(fn,first_sxfn)
                keyfn = f"{fn[:-4]}_keyiv.txt" if basefn.endswith('sxr') else ""
                if os.path.exists(keyfn):
                    shutil.copy2(keyfn, f"{first_sxfn[:-4]}_keyiv.txt")
            first_sxbasefn = basefn
            first_user = userlist[i]
            cum_sxData = buf
            cum_logdata = log
            new_sxfns.append(first_sxfn)
            new_userlist.append(userlist[i])
            cum_cnt = 1
            if 'stop_ts' not in log.keys():
                log['stop_ts'] = log['start_ts'] + os.path.getsize(fn)/20000*1000
                cum_logdata['stop_ts'] = log['stop_ts']
            cum_duration += (log['stop_ts']-log['start_ts'])
            print((f"first sx/user: {first_sxbasefn} / {first_user}  duration={(log['stop_ts']-log['start_ts'])/1000:.1f}  "
                    f"cum_duration={cum_duration/1000:.1f}"))
            # if first_sxfn.endswith('sxr'):
            #     shutil.copy2(first_sxfn,first_sxfn.replace(".sxr","_orig.sxr"))
            # else:
            #     shutil.copy2(first_sxfn,first_sxfn.replace(".sx","_orig.sx"))
            # shutil.copy2(logfn,logfn.replace(".log","_orig.log"))
            last_merged_dict[first_user] = [basefn]

            if config['delSX'] and not config['dirList_load_S3zip']:
                    print('mergeSX: remove',fn,'of',userlist[i])
                    os.remove(fn)
                    if os.path.exists(logfn):
                        os.remove(logfn)
        else:
            interval = log['start_ts'] - last_stop_ts
            print(f"\t\t\tinterval = {interval/1000:.1f}sec")
            if userlist[i] == first_user and ((mustMerge and interval <= 180000) or interval <= config['maxMergeInterval_ms']):  # the same user and interval < 5sec
            # if userlist[i] == first_user and interval <= 50000:  # the same user and interval < 5sec
                if config['onlytst0']:
                    continue
                merged_sxfns.append(basefn)
                last_merged_dict[first_user].append(basefn)
                cum_sxData += buf
                if config["dirList_load_S3zip"]:
                    cum_logdata['evt'].extend(log['evt'])
                    cum_logdata['hr'].extend(log['hr'])
                    cum_logdata['fm'].extend(log['fm'])
                cum_cnt += 1
                if 'stop_ts' in log.keys():
                    cum_logdata['stop_ts'] = log['stop_ts']
                else:
                    log['stop_ts'] = log['start_ts'] + os.path.getsize(fn)/20000*1000
                    cum_logdata['stop_ts'] = log['stop_ts']
                cum_duration += (log['stop_ts']-log['start_ts'])
                cum_logdata['duration'] = cum_duration/1000
                if config['delSX'] and not config['dirList_load_S3zip']:
                    print('mergeSX: remove',fn,'of',userlist[i])
                    os.remove(fn)
                    if os.path.exists(logfn):
                        os.remove(logfn)
                if (fn == sxfns[-1]
                        or (not mustMerge and 'stop_ts' not in log.keys())):
                    print((f'\n\tmerging {merged_sxfns} \n\t\tinto  {os.path.basename(first_sxfn)}'
                            f'({first_user}: {cum_cnt} files,{cum_duration/1000/60:.2f}min)\n'))
                    with open(first_sxfn, "wb") as f:
                        f.write(cum_sxData)
                    with open(first_sxfn.replace(".sxr",".log").replace(".sx",".log"), 'w', newline='', encoding='utf-8-sig') as jf:
                        json.dump(cum_logdata, jf, ensure_ascii=False)
                    sx_dict[first_sxbasefn]['duration'] = cum_duration/1000
                    merged_sxfns.append(first_sxbasefn)
            else:
                if cum_cnt > 1 and not config['onlytst0']:
                    print((f'merging {merged_sxfns} into\n\t{os.path.basename(first_sxfn)}'
                            f'({cum_cnt} files,{cum_duration/1000/60:.2f}min)'))
                    sx_dict[first_sxbasefn]['duration'] = cum_duration/1000
                    cum_logdata['duration'] = cum_duration/1000
                    with open(first_sxfn, "wb") as f:
                        f.write(cum_sxData)
                    with open(first_sxfn.replace(".sxr",".log").replace(".sx",".log"), 'w', newline='', encoding='utf-8-sig') as jf:
                        json.dump(cum_logdata, jf, ensure_ascii=False)
                merged_sxfns.append(first_sxbasefn)
                # for sfn in merged_sxfns:
                #     mergelog[sfn] = True
                merged_sxfns = []
                cum_duration = 0
                # == another first_sxfn  
                cum_cnt = 1
                first_sxfn = f'{sxpool}/{basefn}'
                if not config['onlytst0']:
                    shutil.copy2(fn,first_sxfn)
                    keyfn = f"{fn[:-4]}_keyiv.txt" if basefn.endswith('sxr') else ""
                    if os.path.exists(keyfn):
                        shutil.copy2(keyfn, f"{first_sxfn[:-4]}_keyiv.txt")
                first_sxbasefn = os.path.basename(fn)
                first_user = userlist[i]
                new_sxfns.append(first_sxfn)
                new_userlist.append(userlist[i])
                if config['onlytst0']:
                    continue
                cum_sxData = buf
                if 'stop_ts' in log.keys():
                    cum_logdata['stop_ts'] = log['stop_ts']
                else:
                    log['stop_ts'] = log['start_ts'] + os.path.getsize(fn)/20000*1000
                    cum_logdata['stop_ts'] = log['stop_ts']
                cum_logdata = log
                cum_duration += (log['stop_ts']-log['start_ts'])
                with open(first_sxfn.replace(".sxr",".log").replace(".sx",".log"), 'w', newline='', encoding='utf-8-sig') as jf:
                    json.dump(cum_logdata, jf, ensure_ascii=False)
                print((f"first sx/user: {os.path.basename(first_sxfn)} / {first_user}  duration={(log['stop_ts']-log['start_ts'])/1000:.1f}  "
                        f"cum_duration={cum_duration/1000:.1f}"))
                last_merged_dict[first_user] = [basefn]
        last_stop_ts = log['stop_ts']
        # with open(mergelog_fn,'w',newline='', encoding='utf-8-sig') as jf:
        #     json.dump(mergelog, jf, indent=4, ensure_ascii=False)
        print(f"going to converting {len(merged_sxfns)} merged files!")
    return new_sxfns,new_userlist,sxpool
    

if __name__ == "__main__":
    import sys

    def signal_handler(sig, frame):
        global engine
        engine.stop()

    signal.signal(signal.SIGINT, signal_handler)

    print('version: 20240202a')
    config = updateConfig()
    for key in config.keys():
        if key != 'default' and (key == 'fj_dir_kw' or key == 'dir_Export_fj' or ('//' not in key and 'dir' not in key)):
            if key in config['default'].keys() and config[key] != config['default'][key]:
                print(f"{key} {config[key]} ===> not default={config['default'][key]}")
                # time.sleep(2)
            # else:
            #     print(f"{key} {config[key]}")
        elif key.startswith("dirList_load_S3zip"):
            for item in config[key]:
                print(item)
    if input('Are all parameters correct? Enter:contiune others:exit '):
        sys.exit()
    datainfo = {'mic':{'fullscale':32768.0, 'sr':4000},
                'ecg':{'fullscale':2000.0, 'sr':512},
                'acc':{'fullscale':4.0, 'sr':112.5/2},
                'gyro':{'fullscale':4.0, 'sr':112.5/2},
                'mag':{'fullscale':4900.0, 'sr':112.5/2},
                'quaternion':{'fullscale':1.0, 'sr':112.5/2},
                'ble':'',
                'dualmic':False,
                'user_srcdir':'',
                'recTime':'',
                'sxfn':'',
                'duration':0}
    kw = ''
    sxdict = {}
    usersrcdirs = []
    last_merged_dict = {}
    fns = []
    if config["dirList_load_S3zip"]:    # auto run mode, process files in s3
        fn_log = os.path.join(os.path.dirname(__file__),'s3filelog.json')
        if os.path.exists(fn_log):
            with open(fn_log, 'r', newline='',encoding='utf-8-sig') as jf:
                sxdict = json.loads(jf.read())
        fns,usersrcdirs = unzipS3(
                            config["dirList_load_S3zip"],config["dir_upzipS3"],config["ts_loadS3"],
                            config['overwrite'],config['onlyChkTS'],sx_dict=sxdict)
        # == if no zip fns found in unzipS3, process sx fns in dir_upzipS3 if they are also in sxdict
        if not len(fns):
            dir_upzipS3 = config["dir_upzipS3"].replace("\\","/")
            for fn in os.listdir(dir_upzipS3):
                if fn.endswith(".sx") and fn in sxdict:
                    fns.append(f'{dir_upzipS3}/{fn}')
                    usersrcdirs.append(sxdict[fn]['user_srcdir'])
    else:
        print('select dir')
        [print(i,path) for i,path in enumerate(config['dirToloadFile'])]
        o = input('which? ')
        if not o and o != 0:
            sys.exit()
        sdir = config['dirToloadFile'][int(o)]
        fns = findFileset(datainfo, config,kw=kw,srcdir=sdir,loadall=config['load_all_sx'],
                            onlyChkTS=config['onlyChkTS'],sx_dict=sxdict)
        usersrcdirs = [os.path.basename(os.path.dirname(fn)) for fn in fns]
        if len(fns):
            thisdir = os.path.dirname(os.path.dirname(fns[0]))
            if not len([path for path in config['dirToloadFile'] if thisdir in path]) and 'compilation/IRB' not in thisdir:
                if not input(f"append {thisdir} to dirToloadFile?  "):
                    config['dirToloadFile'].append(thisdir)
            if len(config['dirToloadFile']) > 16:
                del config['dirToloadFile'][0]
            updateConfig(config=config)
    if not config['onlyChkTS']:
        sxpool = ''
        if config['mergeNearby'] and len(fns)>1:
            fns,usersrcdirs,sxpool = mergeSX(fns,usersrcdirs,last_merged_dict,sxdict)
        [print('going to converting',fn) for fn in fns]
        stop_flag = threading.Event()
        engine = Engine(datainfo,config,stopped_flag=stop_flag)
        if config['onlyMerge'] or (config['prompt_convert'] and input('Enter:go  Others:quit ')):
            for fn in fns:
                dstdir,wavfnkw_ts,userdir,dstdir2,userdir2 = engine.getDstdir(fn,'')
                if config['moveSX'] or config['onlyMerge']:
                    sx_dstfn = f"{dstdir}/{os.path.basename(fn)}"
                    if not os.path.exists(sx_dstfn):
                        print('move sx to',sx_dstfn)
                        shutil.move(fn,sx_dstfn)
                    elif fn != sx_dstfn:
                        print(sx_dstfn,'exists! remove src!')
                        os.remove(fn)
            if config['delmergedSX']:
                shutil.rmtree(sxpool)
            sys.exit()
        
        t0 = time.time()
        for i,fn in enumerate(fns):
            if os.path.getsize(fn)/20000 < 20:
                print(fn,'data duration maybe less than 20sec --> skip!\n')
                os.remove(fn)
                logfn = fn.replace('sxr','log').replace('sx','log')
                if os.path.exists(logfn):
                    os.remove(logfn)
                continue
            stop_flag.clear()
            userdirkw = usersrcdirs[i] if len(usersrcdirs) else ''
            thisdict = sxdict[os.path.basename(fn)] if len(sxdict) else {}
            # self.bleaddr, dstdir, userdir, self.flag_dualmic.is_set()
            bleaddr,dstdir,userdir,isdualmic,dstdir2,userdir2,wavfnkw_ts = engine.chk_files_format(sx_fn=fn,
                                                            cnt=i+1,userdir_kw=userdirkw,thisSXdict=thisdict)
            while not stop_flag.wait(2.5):
                print(f'is writing!')    # elapsed time: {time.time()-t0:.1f}sec')
            if bleaddr is None or not dstdir:
                continue
            ts = getTsOfFn(fn,ms=False)     #float(os.path.basename(fn)[:-3])/1000
            if not ts:
                recTime = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))
                # msg = (f'{os.path.basename(fn)}  recording start at:{recTime}  '
                #         f'file size:{os.path.getsize(fn)}=>{hhmmss(os.path.getsize(fn)/20000)}')
            else:
                recTime = 'SD_card_unknown'
                # msg = (f'{os.path.basename(fn)}  recording start at:{recTime}  '
                #         f'file size:{os.path.getsize(fn)}=>{hhmmss(os.path.getsize(fn)/20000)}')

            print(f'{fn} was converted!')
            datainfo['recTime'] = recTime
            datainfo['sxfn'] = os.path.basename(fn)
            if userdirkw:
                datainfo['user_srcdir'] = userdirkw

            wavdictfn = f'{userdir}/{os.path.basename(userdir)}_fileinfo.json'
            if os.path.exists(wavdictfn):
                with open(wavdictfn, 'r', newline='',encoding='utf-8-sig') as jf:
                    wavdict = json.loads(jf.read())
            else:
                wavdict = {}
            wavdict[recTime] = {'ble': bleaddr,
                                'micsr': datainfo["mic"]["sr"],
                                'imusr': datainfo["acc"]["sr"],
                                'dualmic':isdualmic,
                                'sxfn': datainfo['sxfn'],
                                'duration': sxdict[datainfo['sxfn']]['duration'],
                                'duration_hhmmss': sxdict[datainfo['sxfn']]['duration_hhmmss']}
            with open(wavdictfn, 'w', newline='', encoding='utf-8-sig') as wavjson:
                json.dump(wavdict, wavjson, indent=4, ensure_ascii=False)

            if config['moveSX']:
                sx_dstfn = f"{dstdir}/{os.path.basename(fn)}"
                if not os.path.exists(sx_dstfn):
                    print('move sx to',sx_dstfn)
                    shutil.move(fn,sx_dstfn)
                elif fn != sx_dstfn:
                    print(sx_dstfn,'exists! remove src!')
                    os.remove(fn)
                keyfn = f"{dstdir}/{os.path.basename(engine.keyfn)}" if engine.keyfn else ''
                if engine.keyfn and not os.path.exists(keyfn):
                    print(f"move keyfn to {dstdir}")
                    shutil.copy2(engine.keyfn, dstdir)

            if config['delSX'] and os.path.exists(fn):
                os.remove(fn)
                print('remove sx',os.path.basename(fn))

            if (config["dirList_load_S3zip"]
                    and len(sxdict)
                    and userdirkw in last_merged_dict and os.path.basename(fn) not in last_merged_dict[userdirkw]
                    and (not config["onlyChkTS"] or not config["onlyChkFormat"]
                            or not config["onlylog"] or not config["onlyMovelog"])):
                with open(fn_log, 'w', encoding='utf-8-sig') as jout:
                    json.dump(sxdict, jout, indent=4, ensure_ascii=False)
        time.sleep(3)
        if not config['onlytst0'] and len(sxpool) and config['delmergedSX']:
            shutil.rmtree(sxpool)

    print('threading.active=',threading.active_count(),threading.enumerate())