import os,threading,time,json,shutil
import shutil
import file_driver as FD
from package_handler import PackageHandler
from WriteDataToFileThread import RecThread
import protocol as PRO
import tkinter as tk
from tkinter import filedialog
from zipfile import ZipFile

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
        # t0 = time.time()
        while not flag.wait(5):
            if self.data_retriever.thd_run_flag is not None:  print(self.strPkgSpd)
            # print(f'chkRecThd: elapsed time={time.time()-t0:.2f}sec')
            isRun = False
            if not self.config['onlylog']:
                isRun |= not self.recThd_audio.stopped()
                print('\nisRun',isRun,'self.recThd_audio.stopped()', self.recThd_audio.stopped())
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
        ts = float(os.path.basename(sx_fn)[:-3])/1000
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
            if self.bleaddr in self.srcdir:
                dstdir = (f"{self.srcdir}/"
                        f'{str_date}')
                userdir = f"{self.srcdir}/"
            else:
                dstdir = (f"{self.srcdir}/"
                            f'{self.bleaddr}/'
                            f'{str_date}')
                userdir = f"{self.srcdir}/{self.bleaddr}/"
        dstdir = dstdir.replace('/merged','')
        userdir = userdir.replace('/merged','')
        print(f'setRec: dstdir={dstdir}\nuserdir={userdir}')
        if not os.path.exists(dstdir):
            os.makedirs(dstdir)
        # if not os.path.exists(dstdir2):
        #     os.makedirs(dstdir2)
        return dstdir,wavfnkw_ts,userdir,dstdir2,userdir2

    def chk_files_format(self,sx_fn='',cnt=0, userdir_kw='', thisSXdict={}):
        self.srcdir = os.path.dirname(sx_fn)
        ts = float(os.path.basename(sx_fn)[:-3])/1000
        self.flag_ble_addr.clear()
        print(f'\nrecording time:{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))}')
        print('chk_files_format sx_fn: ', sx_fn)
        # fnstr = sx_fn.split("/")[-2:] if len(sx_fn.split("/"))>1 else sx_fn.split("\\")[-2:]
        # self.input = '_'.join(fnstr)
        if self.srcdir and (sx_fn.endswith('sx') or sx_fn.endswith('sxr')) :
            drv = FD.Driver(sx_fn)
            pkg_handler = PackageHandler(self)
            self.data_retriever = PRO.Protocol(drv,'sxFile',self.config['skipPkgCnt'])
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
            while not self.flag_checked_fileformat.wait(0.5):
                cnt+=1
                print('wait for receiving file format',cnt)
                if cnt>20:
                    input(f'quit {os.path.basename(sx_fn)}, having waited for format check too long time')
                    print(f'quit {os.path.basename(sx_fn)}, having waited for format check too long time'
                          ,file=open('log.txt','a',newline=''))
                    self.stop()
                    break
            cnt = 0
            while not self.flag_ble_addr.wait(0.5):
                cnt += 1
                print('wait for receiving ble addre',cnt)
                if cnt > 10:
                    input(f'ble addr of {os.path.basename(sx_fn)} is unknown!')
                    print(f'ble addr of {os.path.basename(sx_fn)} is unknown!'
                          ,file=open('log.txt','a',newline=''))
                    break
        if self.flag_checked_fileformat.is_set():
            print(f'format checked:{self.flag_checked_fileformat.is_set()}  '
                    f'4kHz:{self.flag_4kHz.is_set()}  dualmic:{self.flag_dualmic.is_set()}  '
                    f'BLE addr:{pkg_handler.bleaddr} '
                    f'acc sr:{self.datainfo["acc"]["sr"]} '
                    f'gyro sr:{self.datainfo["gyro"]["sr"]}')
            if pkg_handler.bleaddr is None:
               self.stop()
               return pkg_handler.bleaddr,'','',''
            if self.config['onlySelectedBle'] not in pkg_handler.bleaddr:
                print('onlySelectedBle not in pkg_handler.bleaddr')
                self.stop()
                return pkg_handler.bleaddr,'','',''
            if self.config['onlyChkFormat']:
                print('onlyChkFormat',self.config['onlyChkFormat'])
                self.stop()
                return pkg_handler.bleaddr,'','',''
            # self.datainfo['mic']['sr'] = 4000 if self.flag_4kHz.is_set() else 2000
            self.bleaddr = pkg_handler.bleaddr if self.flag_ble_addr.is_set() else "unknownBLE"
            self.datainfo['ble'] = self.bleaddr
            self.datainfo['dualmic'] = self.flag_dualmic.is_set()
            if thisSXdict:
                thisSXdict['imu_sr'] = self.datainfo["acc"]["sr"]
                thisSXdict['mic_sr'] = self.datainfo["mic"]["sr"]
                thisSXdict['dualmic'] = self.flag_dualmic.is_set()
                thisSXdict['ble'] = self.bleaddr
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
                return '','','',''
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
            self.data_retriever = PRO.Protocol(drv,'sxFile',self.config['skipPkgCnt'])
            self.data_retriever.set_sys_info_handler(pkg_handler)
            self.data_retriever.set_mic_data_handler(pkg_handler)
            self.data_retriever.set_imu_data_handler(pkg_handler)
            self.data_retriever.set_ecg_data_handler(pkg_handler)
            self.data_retriever.set_endingTX_callback(self.endingTX_callback)
        go = self.setRec(dstdir,wavfnkw_ts)
        if go:
            print('going to start Engine again for recording!')
            self.start()

    def setRec(self,dstdir='',wavfnkw_ts=''):
        if not self.thd_rec_flag.is_set():
            dstfn_prefix = f'{dstdir}/{wavfnkw_ts}'
            recT0 = time.mktime(time.strptime(wavfnkw_ts,"%Y-%m-%d-%H-%M-%S"))
            if os.path.exists(os.path.dirname(dstdir)):
                existfns = [fn for fn in os.listdir(os.path.dirname(dstdir)) if wavfnkw_ts in fn]
            else:
                existfns = ''
                os.makedirs(os.path.dirname(dstdir))
            if len(existfns):
                print(f'{dstfn_prefix} has existed!')
                # if self.config['overwrite']:
                print('going to overwrite it!')
                # else:
                #     print('going to skip it!')
                #     self.stop()
                #     return False
            if not self.config['onlylog']:
                self.recThd_audio = RecThread(self.datainfo['mic']['sr'],
                                            1, 0.04, dstfn_prefix, 'mic',
                                            self.datainfo['mic']['fullscale'],
                                            self.flag_dualmic.is_set(),recT0,config,self.ts_Hz)
                self.recThd_audio.start()
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
            self.thd_rec_flag.clear()
            if not self.config['onlylog']:
                self.recThd_audio.stop()
                self.recThd_audio.join(0.5)
                # print('self.recThd_audio ',self.recThd_audio.is_alive())
                self.recThd_audio = None
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

def findFileset(datainfo, config, kw='audio-main',srcdir='', loadall=True, onlyChkTS=False, sx_dict={}):
    root = tk.Tk()
    root.withdraw()

    srcdir = config['dirToloadFile'] if not srcdir else srcdir
    tfn = filedialog.askopenfilename(initialdir=sdir,filetypes=[("SX File",(f"*{kw}*.sxr",f"*{kw}*.sx",f"*{kw}*.zip"))])
    if not tfn:
        return ''
    srcdir = os.path.dirname(tfn)
    if loadall:
        fns = [f'{srcdir}/{fn}' for fn in os.listdir(srcdir)
                if fn.endswith('.sxr') or fn.endswith('.sx') or fn.endswith('.zip')]
        if not onlyChkTS:
            for fn in fns:
                if fn.endswith('zip'):
                    with ZipFile(fn) as myzip:
                        for zipfn in myzip.namelist():
                            if zipfn.endswith('sx') and not os.path.exists(f'{srcdir}\{zipfn.replace("zip","sx")}'):
                                print('going to upzip',zipfn)
                                # myzip.extract(zipfn,path=srcdir)
                                myzip.extractall(path=srcdir)
            fns = [f'{srcdir}/{fn}' for fn in os.listdir(srcdir)
                    if fn.endswith('.sxr') or fn.endswith('.sx')]
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
    fns.sort()
    print()
    user_srcdir = srcdir.split('\\')[-1]
    for fn in fns:
        ts = float(os.path.basename(fn)[:-3])/1000
        recTime = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))
        msg = (f'{os.path.basename(fn)}  recording start at:{recTime}  '
                f'file size:{os.path.getsize(fn)}=>{hhmmss(os.path.getsize(fn)/20000)}')
        print(msg)
        sx_dict[os.path.basename(fn)] = {'user_srcdir':user_srcdir,
                                            'recTime':recTime,
                                            'ble':'',
                                            'mic_sr':0,
                                            'imu_sr':0,
                                            'dualmic':False,
                                            'duration':os.path.getsize(fn)/20000,
                                            'duration_hhmmss':hhmmss(os.path.getsize(fn)/20000)}
    fn_log = f'{srcdir}/{time.strftime("%Y-%m-%d", time.localtime())}.log'
    with open(fn_log, 'w') as jout:
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
    cum_sxData = None
    cum_logdata = None
    new_sxfns = []
    new_userlist = []
    merged_sxfns = []
    cum_cnt = 0
    cum_duration = 0
    sxpool = os.path.dirname(sxfns[0])+'/merged' if not config['onlytst0'] else os.path.dirname(sxfns[0])
    mergelog_fn = f'{sxpool}/merge.log'
    if os.path.exists(mergelog_fn):
        with open(mergelog_fn,'r',newline='') as jf:
            mergelog = json.loads(jf.read())
    else:
        mergelog = {}
    if not os.path.exists(sxpool):
        os.makedirs(sxpool)
    for i,fn in enumerate(sxfns):
        basefn = os.path.basename(fn)
        logfn = fn.replace(".sxr",".log").replace(".sx",".log")
        print(f'\treading {basefn}')
        if os.path.exists(logfn):
            with open(logfn, 'r', newline='') as jf:
                log = json.loads(jf.read())
        else:
            new_sxfns.append(f'{sxpool}/{basefn}')
            if not config['onlytst0']:
                shutil.copy2(fn,new_sxfns[-1])
            new_userlist.append(userlist[i])
            continue
        
        if basefn in mergelog and mergelog[basefn]:
            continue
        else:
            mergelog[basefn] = False
        with open(fn, 'rb') as f:
            buf = f.read()

        if not last_stop_ts:    # first of sxfns
            first_sxfn = f'{sxpool}/{basefn}'
            if not config['onlytst0']:
                shutil.copy2(fn,first_sxfn)
            first_sxbasefn = basefn
            first_user = userlist[i]
            cum_sxData = buf
            cum_logdata = log
            new_sxfns.append(first_sxfn)
            new_userlist.append(userlist[i])
            cum_cnt = 1
            cum_duration += (log['stop_ts']-log['start_ts'])
            print(f'first sx/user: {first_sxbasefn} / {first_user}')
            # if first_sxfn.endswith('sxr'):
            #     shutil.copy2(first_sxfn,first_sxfn.replace(".sxr","_orig.sxr"))
            # else:
            #     shutil.copy2(first_sxfn,first_sxfn.replace(".sx","_orig.sx"))
            # shutil.copy2(logfn,logfn.replace(".log","_orig.log"))
            last_merged_dict[first_user] = [basefn]
        else:
            interval = log['start_ts'] - last_stop_ts
            if userlist[i] == first_user and interval <= 5000:  # the same user and interval < 5sec
                if config['onlytst0']:
                    continue
                merged_sxfns.append(basefn)
                last_merged_dict[first_user].append(basefn)
                cum_sxData += buf
                cum_logdata['stop_ts'] = log['stop_ts']
                if config["dirList_load_S3zip"]:
                    cum_logdata['evt'].extend(log['evt'])
                    cum_logdata['hr'].extend(log['hr'])
                    cum_logdata['fm'].extend(log['fm'])
                cum_cnt += 1
                cum_duration += (log['stop_ts']-log['start_ts'])
                cum_logdata['duration'] = cum_duration/1000
                if config['delSX'] and not config['dirList_load_S3zip']:
                    print('mergeSX: remove',fn,'of',userlist[i])
                    os.remove(fn)
                    os.remove(logfn)
                if (fn == sxfns[-1]
                        or (not os.path.exists(sxfns[i+1].replace(".sx",".log"))
                            and not os.path.exists(sxfns[i+1].replace(".sxr",".log")))):
                    print((f'merging {merged_sxfns} into\n\t{os.path.basename(first_sxfn)}'
                            f'({first_user}: {cum_cnt} files,{cum_duration/1000/60:.2f}min)'))
                    with open(first_sxfn, "wb") as f:
                        f.write(cum_sxData)
                    with open(first_sxfn.replace(".sxr",".log").replace(".sx",".log"), 'w', newline='') as jf:
                        json.dump(cum_logdata, jf, ensure_ascii=False)
                    sx_dict[first_sxbasefn]['duration'] = cum_duration/1000
                    merged_sxfns.append(first_sxbasefn)
                    for fn in merged_sxfns:
                        mergelog[fn] = True
            else:
                if cum_cnt > 1 and not config['onlytst0']:
                    print((f'merging {merged_sxfns} into\n\t{os.path.basename(first_sxfn)}'
                            f'({cum_cnt} files,{cum_duration/1000/60:.2f}min)'))
                    sx_dict[first_sxbasefn]['duration'] = cum_duration/1000
                    cum_logdata['duration'] = cum_duration/1000
                    with open(first_sxfn, "wb") as f:
                        f.write(cum_sxData)
                    with open(first_sxfn.replace(".sxr",".log").replace(".sx",".log"), 'w', newline='') as jf:
                        json.dump(cum_logdata, jf, ensure_ascii=False)
                merged_sxfns.append(first_sxbasefn)
                for sfn in merged_sxfns:
                    mergelog[sfn] = True
                merged_sxfns = []
                cum_duration = 0
                # == another first_sxfn  
                cum_cnt = 1
                first_sxfn = f'{sxpool}/{basefn}'
                if not config['onlytst0']:
                    shutil.copy2(fn,first_sxfn)
                first_sxbasefn = os.path.basename(fn)
                first_user = userlist[i]
                new_sxfns.append(first_sxfn)
                new_userlist.append(userlist[i])
                if config['onlytst0']:
                    continue
                cum_sxData = buf
                cum_logdata = log
                cum_duration += (log['stop_ts']-log['start_ts'])
                with open(first_sxfn.replace(".sxr",".log").replace(".sx",".log"), 'w', newline='') as jf:
                    json.dump(cum_logdata, jf, ensure_ascii=False)
                print(f'first sx/user: {os.path.basename(first_sxfn)} / {first_user}')
                last_merged_dict[first_user] = [basefn]
        last_stop_ts = log['stop_ts']
        with open(mergelog_fn,'w',newline='') as jf:
            json.dump(mergelog, jf, indent=4, ensure_ascii=False)
    return new_sxfns,new_userlist,sxpool
    

if __name__ == "__main__":
    import sys
    print('version: 20220116a')
    config = updateConfig()
    for key in config.keys():
        if key == 'fj_dir_kw' or key == 'dir_Export_fj' or ('//' not in key and 'dir' not in key):
            print(key,config[key])
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
            with open(fn_log, 'r', newline='') as jf:
                sxdict = json.loads(jf.read())
        fns,usersrcdirs = unzipS3(
                            config["dirList_load_S3zip"],config["dir_upzipS3"],config['ts_loadS3'],
                            config['overwrite'],config['onlyChkTS'],sx_dict=sxdict)
        # == if no zip fns found in unzipS3, process sx fns in dir_upzipS3 if they are also in sxdict
        if not len(fns):
            dir_upzipS3 = config["dir_upzipS3"].replace("\\","/")
            for fn in os.listdir(dir_upzipS3):
                if fn.endswith(".sx") and fn in sxdict:
                    fns.append(f'{dir_upzipS3}/{fn}')
                    usersrcdirs.append(sxdict[fn]['user_srcdir'])
    else:
        sdir = config['dirToloadFile']
        fns = findFileset(datainfo, config,kw=kw,srcdir=sdir,loadall=config['load_all_sx'],
                            onlyChkTS=config['onlyChkTS'],sx_dict=sxdict)
        usersrcdirs = [os.path.basename(os.path.dirname(fn)) for fn in fns]
        if len(fns):
            config['dirToloadFile'] = os.path.dirname(fns[0])
            updateConfig(config=config)
    if not config['onlyChkTS']:
        sxpool = ''
        if config['mergeNearby'] and len(fns)>1:
            fns,usersrcdirs,sxpool = mergeSX(fns,usersrcdirs,last_merged_dict,sxdict)
        [print('going to converting',fn) for fn in fns]
        if input('Enter:go  Others:quit '):
            sys.exit()
        stop_flag = threading.Event()
        engine = Engine(datainfo,config,stopped_flag=stop_flag)
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
                print(f'is writing! elapsed time: {time.time()-t0:.1f}sec')
            if bleaddr is None or not dstdir:
                continue
            ts = float(os.path.basename(fn)[:-3])/1000
            recTime = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))
            print(f'{fn} was converted!')
            datainfo['recTime'] = recTime
            datainfo['sxfn'] = os.path.basename(fn)
            if userdirkw:
                datainfo['user_srcdir'] = userdirkw

            wavdictfn = f'{userdir}/{os.path.basename(userdir)}_fileinfo.json'
            if os.path.exists(wavdictfn):
                with open(wavdictfn, 'r', newline='') as jf:
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
            with open(wavdictfn, 'w', newline='') as wavjson:
                json.dump(wavdict, wavjson, indent=4, ensure_ascii=False)

            if config['delSX']:
                os.remove(fn)
                print('remove sx',os.path.basename(fn))
            elif (config['moveSX'] and config['dirList_load_S3zip']) and bleaddr:
                sx_dstfn = f"{dstdir}/{os.path.basename(fn)}"
                if not os.path.exists(sx_dstfn):
                    print('move sx to',sx_dstfn)
                    shutil.move(fn,sx_dstfn)
                elif fn != sx_dstfn:
                    print(sx_dstfn,'exists! remove src!')
                    os.remove(fn)
                # for folder in os.listdir(config['dir_savSX']):
                #     if folder[-4:] == f"{bleaddr[-4:]}":
                #         dstdir = f"{config['dir_savSX']}\\{folder}\\raw"
                #         print('move sx to',dstdir)
                #         dstfn = f"{dstdir}\\{os.path.basename(fn)}"
                #         if not os.path.exists(dstfn):
                #             if not os.path.exists(dstdir):
                #                 os.makedirs(dstdir)
                #             shutil.move(fn,dstfn)
                #         else:
                #             print(dstfn,'exists! remove src!')
                #             os.remove(fn)
                #         break
            if (config["dirList_load_S3zip"]
                    and len(sxdict)
                    and userdirkw in last_merged_dict and os.path.basename(fn) not in last_merged_dict[userdirkw]
                    and (not config["onlyChkTS"] or not config["onlyChkFormat"]
                            or not config["onlylog"] or not config["onlyMovelog"])):
                with open(fn_log, 'w') as jout:
                    json.dump(sxdict, jout, indent=4, ensure_ascii=False)
        time.sleep(3)
        if not config['onlytst0'] and len(sxpool) and config['delmergedSX']:
            shutil.rmtree(sxpool)

    print('threading.active=',threading.active_count(),threading.enumerate())