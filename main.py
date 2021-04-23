import os,threading,time,json
import file_driver as FD
from package_handler import PackageHandler
from WriteDataToFileThread import RecThread
import protocol as PRO
import tkinter as tk
from tkinter import filedialog

class Engine:
    def __init__(self,datainfo=None, config=None):
        self.datainfo = datainfo

        self.config = config

        self.thd_rec_flag = threading.Event()

        self.reset()

        self.data_retriever = None
        self.recThd_audio = None
        self.recThd_acc = None
        self.recThd_ecg = None
        self.recThd_gyro = None
        self.recThd_mag = None
        self.recThd_quaternion = None
        # self.recT0 = None
        self.input = ''
        self.flag_stop_ChkRecThd = threading.Event()
        self.strPkgSpd = ''

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

        print('--stop data_retriever')
        if(self.data_retriever is not None):
            self.data_retriever.stop()
            self.data_retriever=None
        
        self.reset()

        print('engine stop')
    
    def chkRecThd(self, flag):
        print('start to ChkRecThd')
        while not flag.wait(3):
            print(self.strPkgSpd)
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
            if not isRun: break
        self.stop()

    def updateConfig(self,config):
        self.config = config

    def set_files_source(self,reset=True,f_name='',srcdir='',fnkw=''):
        if reset: self.stop()
        srcdir = os.path.dirname(f_name)
        print('f_name: ', f_name)
        fnstr = f_name.split("/")[-2:] if len(f_name.split("/"))>1 else f_name.split("\\")[-2:]
        self.input = '_'.join(fnstr)
        if srcdir and f_name.endswith('sx'):
            drv = FD.Driver(f_name)
            pkg_handler = PackageHandler(self)
            self.data_retriever = PRO.Protocol(drv,'sxFile')
            self.data_retriever.set_sys_info_handler(pkg_handler)
            self.data_retriever.set_mic_data_handler(pkg_handler)
            self.data_retriever.set_imu_data_handler(pkg_handler)
            self.data_retriever.set_ecg_data_handler(pkg_handler)
            self.data_retriever.set_endingTX_callback(self.endingTX_callback)
        # self.start_remain_thd()
        # self.data_retriever.start()
        self.setRec('test',float(os.path.basename(f_name)[:-3])/1000)
        self.start()        
        return f'File_{fnstr}'

    def setRec(self,dir_RecProj='',ts=0):
        if not self.thd_rec_flag.is_set():
            # self.recT0 = time.localtime()
            fn_ts = (f'{dir_RecProj.replace(" ","")}/'
                        if dir_RecProj.replace(" ","")
                        else '')
            fn_ts += f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(ts))}'
            self.tagfn = f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())}.txt'
            # print(fn_ts)
            self.recThd_audio = RecThread(self.datainfo['mic']['sr'],
                                        1, 0.01, fn_ts, 'mic',
                                        self.datainfo['mic']['fullscale'])
            self.recThd_audio.start()
            self.recThd_acc = RecThread(int(self.datainfo['acc']['sr']),
                                        4, 0.01, fn_ts,'acc',
                                        self.datainfo['acc']['fullscale'])
            self.recThd_acc.start()
            # self.recThd_ecg = RecThread(self.datainfo['ecg']['sr'],
            #                             2, 0.01, fn_ts, 'ecg',
            #                             self.datainfo['ecg']['fullscale'])
            # self.recThd_ecg.start()
            self.recThd_gyro = RecThread(int(self.datainfo['gyro']['sr']),
                                        4, 0.01, fn_ts, 'gyro',
                                        self.datainfo['gyro']['fullscale'])
            self.recThd_gyro.start()
            self.recThd_mag = RecThread(int(self.datainfo['mag']['sr']),
                                        4, 0.01, fn_ts, 'mag',
                                        self.datainfo['mag']['fullscale'])
            self.recThd_mag.start()
            self.recThd_quaternion = RecThread(int(self.datainfo['quaternion']['sr']),
                                            5, 0.01, fn_ts, 'quaternion',
                                            self.datainfo['quaternion']['fullscale'])
            self.recThd_quaternion.start()
            self.thd_rec_flag.set()
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
    tfn = filedialog.askopenfilename(initialdir=srcdir,filetypes=[("SXwav",f"*{kw}*.sx")])
    if not tfn:
        return ''
    srcdir = os.path.dirname(tfn)
    # kw2 = 'audio-main01' if 'ts' in kw else ''
    if loadall:
        fns = [f'{srcdir}\\{fn}' for fn in os.listdir(srcdir)
                if fn.endswith('.sx')]
    else:
        fns = [f'{srcdir}\\{fn}' for fn in os.listdir(srcdir)
                if os.path.basename(tfn)[:19] == fn[:19]]
                    # and (not kw2 or kw2 in fn or kw in fn)]
    fns.sort()
    [print(os.path.basename(fn)) for fn in fns]
    return fns


if __name__ == "__main__":
    config = updateConfig()
    datainfo = {'mic':{'fullscale':32768.0, 'sr':4000, 'disp_time':config['mic_visible_sec']},
                'ecg':{'fullscale':2000.0, 'sr':512, 'disp_time':config['ecg_visible_sec']},
                'acc':{'fullscale':4.0, 'sr':112.5/2, 'disp_time':config['curv_visible_sec']},
                'gyro':{'fullscale':4.0, 'sr':112.5/2, 'disp_time':config['curv_visible_sec']},
                'mag':{'fullscale':4900.0, 'sr':75, 'disp_time':config['curv_visible_sec']},
                'quaternion':{'fullscale':1.0, 'sr':112.5/2, 'disp_time':config['curv_visible_sec']},
                'trend': {'fullscale':[[90,180],[60,150]], 'sr':1/3, 'disp_time':config['trend_chart_min']*60}}
    engine = Engine(datainfo, config)
    kw = ''
    sdir = config['dirToloadFile']
    fns = findFileset(config,kw=kw,srcdir=sdir,loadall=config['load_all_sx'])
    # for fn in fns:
    engine.set_files_source(reset=False,f_name=fns[0])