import os,threading,time,json
import shutil
import file_driver as FD
from package_handler import PackageHandler
from WriteDataToFileThread import RecThread
import protocol as PRO
import tkinter as tk
from tkinter import filedialog
from zipfile import ZipFile

class Engine:
    def __init__(self,datainfo=None, config=None, stopped_flag=None, filecnt=0):
        self.datainfo = datainfo

        self.config = config

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
        self.flag_4kHz = threading.Event()
        self.flag_dualmic = threading.Event()
        self.flag_ble_addr = threading.Event()
        self.strPkgSpd = ''
        self.filecnt=filecnt
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
        while not flag.wait(3):
            if self.data_retriever.thd_run_flag is not None:  print(self.strPkgSpd)
            # print(f'chkRecThd: elapsed time={time.time()-t0:.2f}sec')
            isRun = False
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

    def chk_files_format(self,f_name='',srcdir='',cnt=0):
        srcdir = os.path.dirname(f_name)
        ts = float(os.path.basename(f_name)[:-3])/1000
        self.flag_ble_addr.clear()
        print(f'\nrecording time:{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))}')
        print('f_name: ', f_name)
        # fnstr = f_name.split("/")[-2:] if len(f_name.split("/"))>1 else f_name.split("\\")[-2:]
        # self.input = '_'.join(fnstr)
        if srcdir and f_name.endswith('sx'):
            drv = FD.Driver(f_name)
            pkg_handler = PackageHandler(self)
            self.data_retriever = PRO.Protocol(drv,'sxFile')
            self.data_retriever.set_sys_info_handler(pkg_handler)
            self.data_retriever.set_mic_data_handler(pkg_handler)
            self.data_retriever.set_imu_data_handler(pkg_handler)
            self.data_retriever.set_ecg_data_handler(pkg_handler)
            self.data_retriever.set_endingTX_callback(self.endingTX_callback)
            self.data_retriever.start()
            self.flag_checked_fileformat.clear()
            cnt = 0
            while not self.flag_checked_fileformat.wait(0.5):
                cnt+=1
                print('wait for receiving file format',cnt)
                if cnt>10:
                    input(f'quit {os.path.basename(f_name)}, having waited for format check too long time')
                    print(f'quit {os.path.basename(f_name)}, having waited for format check too long time'
                          ,file=open('log.txt','a',newline=''))
                    self.stop()
                    break
            cnt = 0
            while not self.flag_ble_addr.wait(0.5):
                cnt += 1
                print('wait for receiving ble addre',cnt)
                if cnt > 10:
                    input(f'ble addr of {os.path.basename(f_name)} is unknown!')
                    print(f'ble addr of {os.path.basename(f_name)} is unknown!'
                          ,file=open('log.txt','a',newline=''))
                    break
        if self.flag_checked_fileformat.is_set():
            print(f'format checked:{self.flag_checked_fileformat.is_set()}  '
                    f'4kHz:{self.flag_4kHz.is_set()}  dualmic:{self.flag_dualmic.is_set()}  '
                    f'BLE addr:{pkg_handler.bleaddr}')
            if pkg_handler.bleaddr is None:
               self.stop() 
            if self.config['onlySelectedBle'] not in pkg_handler.bleaddr:
                print('onlySelectedBle not in pkg_handler.bleaddr')
                self.stop()
            if self.config['onlyChkFormat']:
                print('onlyChkFormat',self.config['onlyChkFormat'])
                self.stop()
                return pkg_handler.bleaddr,'',''
            self.datainfo['mic']['sr'] = 4000 if self.flag_4kHz.is_set() else 2000
            self.bleaddr = pkg_handler.bleaddr if self.flag_ble_addr.is_set() else "unknownBLE"
            self.data_retriever.stop()
            # == handle log and sx file
            self.srcdir = os.path.dirname(f_name)
            dstdir,fnkw_ts,userdir = self.getDstdir(f_name)
            # = log
            log_srcfn = f_name.replace("sx","log")
            log_dstfn = f'{dstdir}/{fnkw_ts}.log'
            if os.path.exists(log_srcfn) and not os.path.exists(log_dstfn):
                print('move log to',log_dstfn)
                shutil.move(log_srcfn,log_dstfn)
            elif os.path.exists(log_srcfn) and os.path.exists(log_dstfn):
                print(f'{log_dstfn} exists. Removing {log_srcfn}.') 
                if self.config['overwrite']:
                    os.remove(log_dstfn)
                    print('overwrite', log_dstfn)
                    shutil.move(log_srcfn,log_dstfn)
                else:
                    os.remove(log_srcfn)
            # # = sx
            # if (self.config['moveSX'] or self.config['dirList_load_S3zip']):
            #     sx_dstfn = f"{dstdir}/{os.path.basename(f_name)}"
            #     if not os.path.exists(sx_dstfn):
            #         print('move sx to',sx_dstfn)
            #         shutil.move(f_name,sx_dstfn)
            #     else:
            #         print(sx_dstfn,'exists! remove src!')
            #         os.remove(f_name)
            if self.config['onlyMovelog']:
                print('onlyMovelog ==> Stop!')
                self.stop()
                return '','',''
            engine.set_files_source(reset=False,f_name=f_name, fnkw_ts=fnkw_ts, dstdir=dstdir)
            return self.bleaddr, dstdir, userdir
        else:
            return '','',''
    
    def getDstdir(self,f_name):
        ts = float(os.path.basename(f_name)[:-3])/1000
        fnkw_ts = f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))}'
        str_date = time.strftime("%Y-%m-%d", time.localtime(ts))
        dstdir = ''
        if self.config['dir_Export']:
            if self.config['dir_Export'] == self.config['dir_savSX']:
                for folder in os.listdir(self.config['dir_Export']):
                    if folder[-4:] == f"{self.bleaddr[-4:]}":
                        dstdir =  f"{config['dir_savSX']}/{folder}/{str_date}"
                        userdir = f"{config['dir_savSX']}/{folder}"
                        break
            else:
                dstdir = os.path.dirname(f_name)
                userdir = ''
        if not dstdir:  # if can't find any folder matching the ble address or no assigned dir_Export
            dstdir = (f"{self.srcdir}/"
                        f'{self.bleaddr}/'
                        f'{str_date}/')
            userdir = ''
        print(f'setRec: dstdir={dstdir}  userdir={userdir}')
        if not os.path.exists(dstdir):
            os.makedirs(dstdir)
        return dstdir,fnkw_ts,userdir

    def set_files_source(self,reset=True,f_name='',fnkw_ts='',dstdir=''):
        if reset: self.stop()
        # self.srcdir = os.path.dirname(f_name)
        print('f_name: ', f_name)
        fnstr = f_name.split("/")[-2:] if len(f_name.split("/"))>1 else f_name.split("\\")[-2:]
        self.input = '_'.join(fnstr)
        if self.srcdir and f_name.endswith('sx'):
            drv = FD.Driver(f_name)
            pkg_handler = PackageHandler(self)
            self.data_retriever = PRO.Protocol(drv,'sxFile')
            self.data_retriever.set_sys_info_handler(pkg_handler)
            self.data_retriever.set_mic_data_handler(pkg_handler)
            self.data_retriever.set_imu_data_handler(pkg_handler)
            self.data_retriever.set_ecg_data_handler(pkg_handler)
            self.data_retriever.set_endingTX_callback(self.endingTX_callback)
        go = self.setRec(dstdir,fnkw_ts)
        if go:
            print('going to start Engine again for recording!')
            self.start()

    def setRec(self,dstdir='',fnkw_ts=''):
        if not self.thd_rec_flag.is_set():
            dstfn_prefix = f'{dstdir}/{fnkw_ts}'
            if os.path.exists(os.path.dirname(dstdir)):
                existfns = [fn for fn in os.listdir(os.path.dirname(dstdir)) if fnkw_ts in fn]
            else:
                existfns = ''
                os.makedirs(os.path.dirname(dstdir))
            if len(existfns):
                print(f'{dstfn_prefix} has existed!')
                if self.config['overwrite']:
                    print('going to overwrite it!')
                else:
                    print('going to skip it!')
                    self.stop()
                    return False
            self.recThd_audio = RecThread(self.datainfo['mic']['sr'],
                                        1, 0.04, dstfn_prefix, 'mic',
                                        self.datainfo['mic']['fullscale'],
                                        self.flag_dualmic.is_set())
            self.recThd_audio.start()
            self.recThd_acc = RecThread(int(self.datainfo['acc']['sr']),
                                        4, 0.04, dstfn_prefix,'acc',
                                        self.datainfo['acc']['fullscale'],
                                        self.flag_dualmic.is_set())
            self.recThd_acc.start()
            # self.recThd_ecg = RecThread(self.datainfo['ecg']['sr'],
            #                             2, 0.01, dstfn_prefix, 'ecg',
            #                             self.datainfo['ecg']['fullscale'])
            # self.recThd_ecg.start()
            self.recThd_gyro = RecThread(int(self.datainfo['gyro']['sr']),
                                        4, 0.04, dstfn_prefix, 'gyro',
                                        self.datainfo['gyro']['fullscale'],
                                        self.flag_dualmic.is_set())
            self.recThd_gyro.start()
            self.recThd_mag = RecThread(int(self.datainfo['mag']['sr']),
                                        4, 0.04, dstfn_prefix, 'mag',
                                        self.datainfo['mag']['fullscale'],
                                        self.flag_dualmic.is_set())
            self.recThd_mag.start()
            self.recThd_quaternion = RecThread(int(self.datainfo['quaternion']['sr']),
                                            5, 0.04, dstfn_prefix, 'quaternion',
                                            self.datainfo['quaternion']['fullscale'],
                                        self.flag_dualmic.is_set())
            self.recThd_quaternion.start()
            self.recThd_sysinfo = RecThread(1,
                                            3, 0.09, dstfn_prefix, 'sysinfo',
                                            1)
            self.recThd_sysinfo.start()
            self.thd_rec_flag.set()
            return True
        else:
            self.thd_rec_flag.clear()
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

def updateConfig(engine=None):
    with open(f"{os.path.join(os.path.dirname(__file__),'config.json')}", 'r', encoding='utf-8-sig') as reader:
        config = json.loads(reader.read())
    if engine is not None:
        engine.updateConfig(config)
    print('update config')
    return config

def findFileset(config, kw='audio-main',srcdir='', loadall=True):
    root = tk.Tk()
    root.withdraw()

    srcdir = config['dirToloadFile'] if not srcdir else srcdir
    tfn = filedialog.askopenfilename(initialdir=sdir,filetypes=[("SX File",(f"*{kw}*.sx",f"*{kw}*.zip"))])
    if not tfn:
        return ''
    srcdir = os.path.dirname(tfn)
    if loadall:
        fns = [f'{srcdir}\\{fn}' for fn in os.listdir(srcdir)
                if fn.endswith('.sx') or fn.endswith('.zip')]
        for fn in fns:
            if fn.endswith('zip'):
                with ZipFile(fn) as myzip:
                    for zipfn in myzip.namelist():
                        if zipfn.endswith('sx') and not os.path.exists(f'{srcdir}\{zipfn.replace("zip","sx")}'):
                            print('going to upzip',zipfn)
                            myzip.extract(zipfn,path=srcdir)
        fns = [f'{srcdir}\\{fn}' for fn in os.listdir(srcdir)
                if fn.endswith('.sx')]
    else:
        if tfn.endswith('zip'):
            with ZipFile(tfn) as myzip:
                for zipfn in myzip.namelist():
                    if zipfn.endswith('sx') and not os.path.exists(f'{srcdir}\{zipfn.replace("zip","sx")}'):
                        print('going to upzip',zipfn)
                        myzip.extract(zipfn,path=srcdir)
        fns = [tfn.replace("zip","sx")]
    fns.sort()
    print()
    for fn in fns:
        ts = float(os.path.basename(fn)[:-3])/1000
        print(f'{os.path.basename(fn)}  recording time:{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))}')
    print()
    return fns

def unzipS3(srcList,dst,tsRange,overwrite,onlyChkTS):
    ti = time.mktime(time.strptime(f'{tsRange[0]}', "%Y%m%d"))*1000
    try:
        tf = time.mktime(time.strptime(f'{tsRange[1]+1}', "%Y%m%d"))*1000
    except ValueError:
        tf = (tsRange[1]+1-tsRange[0])*60*60*24*1000+ti
    sx_list = []
    sx_list_short = []
    fn_log = 'downloadS3log.json'
    if os.path.exists(fn_log):
        with open(fn_log, 'r', newline='') as jf:
            sx_dict = json.loads(jf.read())
    else:
        sx_dict = {'filename':[]}
    for srcdir in srcList:
        print('check',srcdir)
        fns = [f'{srcdir}\\{fn}' for fn in os.listdir(srcdir)
                if fn.endswith('.zip')
                    and ti <= float(fn[:-3]) <= tf]
        for fn in fns:
            with ZipFile(fn) as myzip:
                for zipfn in myzip.namelist():
                    if not zipfn.endswith('sx'):
                        continue
                    ts = float(zipfn[:-3])/1000
                    recTime = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))
                    filesize = myzip.getinfo(zipfn).file_size
                    msg = (f'{zipfn}>> recording time:{recTime} size:{filesize>>10}KB')
                    if myzip.getinfo(zipfn).file_size>>10 < 200:
                        print(f'{msg}: filesize is too small!')
                        continue
                    if zipfn in sx_dict['filename']:
                        msg +=  ' has been in unzipped list!'
                        if not overwrite:
                            print(f'{msg} ==> skip')
                            continue
                    else:
                        sx_list_short.append(zipfn)
                        print(msg)
                    if not onlyChkTS:
                        if zipfn.endswith('sx') and (not os.path.exists(f'{dst}\\{zipfn}') or overwrite):
                            print(f'\tgoing to upzip to {dst} ')
                            # myzip.extract(zipfn,path=dst)
                            myzip.extractall(path=dst)
                            sx_list.append(f'{dst}\\{zipfn}')
                        else:
                            print(zipfn,'exists?',os.path.exists(f'{dst}\\{zipfn}'),'recording time:',recTime)
                            sx_list.append(f'{dst}\\{zipfn}')
    sx_dict['filename'].extend(sx_list_short)
    with open(fn_log, 'w') as jout:
        json.dump(sx_dict, jout, indent=4, ensure_ascii=False)
    return sx_list


if __name__ == "__main__":
    print('version: 20210628a')
    config = updateConfig()
    datainfo = {'mic':{'fullscale':32768.0, 'sr':4000},
                'ecg':{'fullscale':2000.0, 'sr':512},
                'acc':{'fullscale':4.0, 'sr':112.5/2},
                'gyro':{'fullscale':4.0, 'sr':112.5/2},
                'mag':{'fullscale':4900.0, 'sr':112.5/2},
                'quaternion':{'fullscale':1.0, 'sr':112.5/2}}
    kw = ''
    if config["dirList_load_S3zip"]:
        fns = unzipS3(config["dirList_load_S3zip"],config["dir_upzipS3"],config['ts_loadS3'],
                        config['overwrite'],config['onlyChkTS'])
    else:
        sdir = config['dirToloadFile']
        fns = findFileset(config,kw=kw,srcdir=sdir,loadall=config['load_all_sx'])
    if not config['onlyChkTS']:
        stop_flag = threading.Event()
        engine = Engine(datainfo, config,stopped_flag=stop_flag,filecnt=len(fns))
        t0 = time.time()
        for i,fn in enumerate(fns):
            stop_flag.clear()
            bleaddr,dstdir,userdir = engine.chk_files_format(f_name=fn,cnt=i+1)
            while not stop_flag.wait(2.5):
                print(f'is writing! elapsed time: {time.time()-t0:.1f}sec')
            if config['delSX']:
                os.remove(fn)
            elif (config['moveSX'] or config['dirList_load_S3zip']) and bleaddr:
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
        time.sleep(3)

    print('threading.active=',threading.active_count(),threading.enumerate())