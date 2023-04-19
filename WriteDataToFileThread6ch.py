import threading
import csv
import soundfile as sf
import time
import os
import queue
import numpy as np
import csv, json
import matplotlib.pyplot as plt
import matplotlib
chinese_font = matplotlib.font_manager.FontProperties(fname='C:\Windows\Fonts\mingliu.ttc')

class RecThread(threading.Thread):
    def __init__(self, sampleRate, channels, waitTime, fn_prefix, job, fullscale, recT0, config={}, ts_Hz=32768):
        #QtCore.QThread.__init__(self)
        super(RecThread, self).__init__()
        self.sampleRate = sampleRate
        self.channels = channels
        self.waitTime = waitTime
        self.q = queue.Queue()
        self.qMulti = [queue.Queue() for i in range(3)]
        self._stop_event = threading.Event()
        # self.filename_prefix = f'{os.path.dirname(__file__)}/record/{fn_ts}'
        self.filename_prefix = fn_prefix
        if not os.path.exists(os.path.dirname(self.filename_prefix)):
            os.makedirs(os.path.dirname(self.filename_prefix))
        self.recT0 = recT0
        self.filename_new = []
        self.daemon = True
        self.job = job
        self.subtype_audio = 'PCM_16'
        self.subtype_NonAudio = 'float'
        self.fullscale = fullscale
        self.name = f'{job}_rec'
        self.fn_errlog = f'{self.filename_prefix}-errlog_{job}.txt'
        self.fn_ts_t0_mic = f'{self.filename_prefix}-ts_t0_mic.txt'
        self.fn_ts_t0_acc = f'{self.filename_prefix}-ts_t0_acc.txt'
        self.config = config
        self.ts_Hz = ts_Hz
        self.err = {'reset_ts':[], 'pkgloss_ts':[], 'pkgloss_duration':[]}
        self.fn_errJson = f'{self.filename_prefix}-errlog_{job}.json'
        try:
            print(f'start recording at {self.filename_prefix}', file=open(self.fn_errlog,'w',newline='', encoding='utf-8-sig'))
        except Exception as e:
            print(f'{self.job}: {e}')
            time.sleep(0.01)
            print(f'start recording at {self.filename_prefix}', file=open(self.fn_errlog,'w',newline='', encoding='utf-8-sig'))
        if job == 'mic':
            self.filename_new.append(f'{self.filename_prefix}-audio-main01.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-main02.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-main03.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-main04.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-main05.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-main06.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-ts.wav')
        [print(os.path.basename(fn)) for fn in self.filename_new]
        if not os.path.exists(os.path.dirname(self.filename_prefix)):
            os.makedirs(os.path.dirname(self.filename_prefix))

    def __del__(self):
        # self.wait()
        self._stop_event.set()

    def stop(self):        
        self._stop_event.set()
        #print('Stop All Channels recording-stop_event:', self.stopped())

    def stopped(self):
        return self._stop_event.is_set()

    def hhmmss(self, sec):
        h, r = divmod(sec, 3600)
        m, s = divmod(r, 60)
        return f'{h:02.0f}:{m:02.0f}:{s:02.0f}'
    
    def addData(self, data, ch=None):
        if ch is None:
            self.q.put_nowait(data)
        else:
            self.qMulti[ch].put_nowait(data)
            # print(f'qMutil[{ch}] size={self.qMulti[ch].qsize()}')
    
    def plt_pkgloss(self,fn):
        # path = r'P:\Backups\Google - Chenyi Kuo\Google Drive\Experiment\compilation\FJ_baby\12M_baby_patch_DVT\F2_CF_F9_99_7D_F4_內建天線_綁帶加扣具測試_未脫落_2022_03_13_14\F2CFF9997DF4\2022-03-13'
        # fn = [f'{path}\\{fn}' for fn in os.listdir(path) if fn.endswith('json')][0]
        with open(fn, 'r', newline='',encoding='utf-8-sig') as jf:
            log = json.loads(jf.read())
        xtick_step = 60*60
        if log['whole_duration'] < 10*60:
            minor_xtick_step = 10
            xticks = np.arange(0,log['whole_duration']+minor_xtick_step,xtick_step)
            xticks_minor = np.arange(0,log['whole_duration']+minor_xtick_step,minor_xtick_step)
        elif log['whole_duration'] < 30*60:
            minor_xtick_step = 1*60
            xticks = np.arange(0,log['whole_duration']+minor_xtick_step,xtick_step)
            xticks_minor = np.arange(0,log['whole_duration']+minor_xtick_step,minor_xtick_step)
        elif log['whole_duration'] < 60*60:
            minor_xtick_step = 5*60
            xticks = np.arange(0,log['whole_duration']+minor_xtick_step,xtick_step)
            xticks_minor = np.arange(0,log['whole_duration']+minor_xtick_step,minor_xtick_step)
        else:
            minor_xtick_step = 10*60
            xticks = np.arange(0,log['whole_duration']+minor_xtick_step,xtick_step)
            xticks_minor = np.arange(0,log['whole_duration']+minor_xtick_step,minor_xtick_step)
        print(f"whole_duration={log['whole_duration']}  xtick_step={xtick_step}  minor_xtick_step={minor_xtick_step}  xticks={xticks[[0,-1]]}")
        figw = max(min(1*log['whole_duration']/minor_xtick_step+2,72),16)
        print(f'estimated figW={figw:.1f}')
        if 'ts0' in log.keys():
            time_ts = log['ts0']
        else:
            time_ts = time.mktime(time.strptime(os.path.basename(fn)[:19],"%Y-%m-%d-%H-%M-%S"))
        xticklabels = [f'{time.strftime("%b/%d %H:%M:%S",time.localtime(time_ts+sec))}'
                                for sec in xticks]
        xticklabels_minor = [f'{time.strftime("%H:%M:%S",time.localtime(time_ts+sec))}'
                                        for sec in xticks_minor]
        fig, axs = plt.subplots(2,1,figsize=(figw,6))
        print(fn)
        path_str = fn.split('\\')[-6:]
        plt.suptitle(f"trend chart of empty_duration\n{path_str}", fontproperties=chinese_font)
        axs[0].plot(log['pkgloss_ts'],log['pkgloss_duration'],marker='o',ls='',label='pkgloss_duration(sec)')
        if len(log['reset_ts']):
            axs[0].plot(log['reset_ts'],np.ones(len(log['reset_ts'])),marker='o',ls='',label='reset_ts')
        axs[1].plot(log['pkgloss_ts'],log['pkgloss_duration'],marker='o',ls='',label='pkgloss_duration(sec)')
        if len(log['pkgloss_duration']) > 2:
            ul = np.std(log['pkgloss_duration'])*4 + np.mean(log['pkgloss_duration'])
            mask = log['pkgloss_duration'] < ul
            if np.count_nonzero(mask) > 2:
                new_UL = np.std(np.array(log['pkgloss_duration'])[mask])*5 + np.mean(np.array(log['pkgloss_duration'])[mask])
                axs[1].set_ylim((0,new_UL))
        axs[0].set_xticks(xticks)
        axs[0].set_xticklabels(xticklabels)
        axs[0].set_xticks(xticks_minor,minor=True)
        axs[0].set_xticklabels(xticklabels,va='bottom')
        axs[0].set_xticklabels(xticklabels_minor,minor=True)
        axs[0].set_xlim(xticks_minor[[0,-1]])
        axs[1].set_xticks(xticks_minor)
        axs[1].set_xlim(xticks_minor[[0,-1]])
        for ax in axs:
            ax.grid(axis='both',which='both')
            ax.legend(loc='upper left')
        # axs[0].grid(axis='both',which='both')
        # axs[1].grid(axis='both',which='both')
        plt.tight_layout()
        pngfn = fn.replace('json','png')
        plt.savefig(pngfn)
        plt.close()

    def run(self):
        # while True:
        # if not self._stop_event.is_set():
            # time.sleep(0.1)
        print(f'job:{self.job}: Start All Channels recording')
        emptyCnt = 0
        if self.job == 'mic':
            if self.config['onlytst0']:
                while not self._stop_event.is_set():
                    if not self.q.empty():
                        msg = ''
                        tmp = self.q.get_nowait()
                        data = np.array(tmp[1:])/self.fullscale
                        t0 = tmp[0]
                        pkglen = len(data[0])
                        tlast5 = np.array([0],dtype='uint32')
                        msg = f'{self.job},t0_fw={t0},pkglen={data[0].size}'
                        print(msg, file=open(self.fn_ts_t0_mic,'w',newline='', encoding='utf-8-sig'))
                        self.stop()
                    else:
                        time.sleep(self.waitTime)
            else:
                self.processedT = 0
                sr_PatchTS = int(1/0.008)
                ts_diff_target = 0.016 * self.ts_Hz
                max_ts_diff = ts_diff_target*1.4
                with sf.SoundFile(self.filename_new[0], mode='x',
                                    samplerate=self.sampleRate, channels=self.channels,
                                    subtype=self.subtype_audio) as file0,\
                    sf.SoundFile(self.filename_new[1], mode='x',
                                    samplerate=self.sampleRate, channels=self.channels,
                                    subtype=self.subtype_audio) as file1,\
                    sf.SoundFile(self.filename_new[2], mode='x',
                                    samplerate=self.sampleRate, channels=self.channels,
                                    subtype=self.subtype_audio) as file2,\
                    sf.SoundFile(self.filename_new[3], mode='x',
                                    samplerate=self.sampleRate, channels=self.channels,
                                    subtype=self.subtype_audio) as file3,\
                    sf.SoundFile(self.filename_new[4], mode='x',
                                    samplerate=self.sampleRate, channels=self.channels,
                                    subtype=self.subtype_audio) as file4,\
                    sf.SoundFile(self.filename_new[5], mode='x',
                                    samplerate=self.sampleRate, channels=self.channels,
                                    subtype=self.subtype_audio) as file5,\
                    sf.SoundFile(self.filename_new[6], mode='x',
                                    samplerate=sr_PatchTS, channels=self.channels,
                                    subtype=self.subtype_NonAudio) as file6:                
                    fileList = [file0, file1, file2, file3, file4, file5, file6]
                    t0 = None
                    seglen = 16
                    data_dim = 6
                    seg_cnt = 40
                    buffer_mic = np.zeros((data_dim,seglen*seg_cnt),dtype=np.float64)
                    buffer_ts = np.zeros(seg_cnt,dtype=np.float64)
                    toffset = 0
                    cnt = 0
                    while not self._stop_event.is_set():
                        if not self.q.empty():
                            msg = ''
                            tmp = self.q.get_nowait()
                            data = np.array(tmp[1:])/self.fullscale
                            if t0 is None:  # initial
                                t0 = tmp[0]
                                data_dim = len(data)
                                pkglen = len(data[0])
                                tlast5 = np.array([0],dtype='uint32')
                                msg = f'{self.job},t0_fw={t0},pkglen={data[0].size},tsHz={self.ts_Hz}'
                                print(msg, file=open(self.fn_ts_t0_mic,'w',newline='',encoding='utf-8-sig'))
                            tstmp = tmp[0] + toffset-t0
                            if tmp[0] < t0 or tstmp < tlast5[-1] or tstmp < 0:    # ts was reset
                                msg += (f'\n{self.job} ts was reset because ')
                                msg += (f'\ttmp[0]={tmp[0]} < t0={t0} or tstmp={tstmp} < tpre={tlast5[-1]}  ')
                                msg += f'tlast5[-3:]={tlast5[-3:]}  toffset={toffset}\n'
                                t0 = tmp[0]
                                toffset = tlast5[-1]+np.mean(np.diff(tlast5)) if len(tlast5) > 1 and np.diff(tlast5).any() else tlast5[-1]
                                tstmp = tmp[0] + toffset-t0
                                ts_sec = tstmp/self.ts_Hz
                                msg += (f'\tcorrected t0={t0}  toffset={toffset} tstmp={ts_sec:.3f} = '
                                        f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(self.recT0+ts_sec))}')
                                self.err['reset_ts'].append(ts_sec)
                            elif tstmp - tlast5[-1] > max_ts_diff: # pkgloss (ts_now >> ts_pre)
                                ts_sec = tstmp/self.ts_Hz
                                empty_sec = (tstmp - tlast5[-1])/self.ts_Hz
                                ts_diff_target = np.median(np.diff(tlast5)) if len(tlast5)>1 and np.diff(tlast5).any() else ts_diff_target
                                msg += (f'\nmic pkgloss at {ts_sec:.3f} {time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(self.recT0+ts_sec))}')
                                msg += (f'\t{tstmp}({ts_sec:.3f}) - {tlast5[-1]}({tlast5[-1]/self.ts_Hz:.3f})'
                                        f' = {tstmp - tlast5[-1]}={empty_sec:.4f}sec > {max_ts_diff}')
                                add_cnt = 1
                                self.err['pkgloss_ts'].append(ts_sec)
                                self.err['pkgloss_duration'].append(empty_sec)
                                while tstmp - tlast5[-1] > max_ts_diff:
                                    tstmp2 = tlast5[-1] + ts_diff_target
                                    tlast5 = np.r_[tlast5, tstmp2]
                                    if tlast5.size > 5:
                                        tlast5 = tlast5[-5:]
                                    ts = tstmp2 / self.ts_Hz
                                    # msg += (f'\tadd {add_cnt} ts:{tstmp2} {ts:.3f}')
                                    add_cnt += 1
                                    buffer_mic[:,cnt*seglen:(cnt+1)*seglen] = np.zeros((data_dim,seglen))
                                    buffer_ts[cnt] = ts
                                    cnt += 1
                                    if cnt == seg_cnt:
                                        for i,q in enumerate(buffer_mic):
                                            fileList[i].write(q)
                                        fileList[-1].write(buffer_ts)
                                        cnt = 0

                            tstmp = tmp[0] + toffset-t0
                            tlast5 = np.r_[tlast5, tstmp]
                            if tlast5.size > 5:
                                tlast5 = tlast5[-5:]
                            buffer_ts[cnt] = (tstmp) / self.ts_Hz
                            try:
                                buffer_mic[:,cnt*seglen:(cnt+1)*seglen] = data
                            except:
                                lenDiff = seglen - data.shape[1]
                                print(f"array dimension mismatchs! lenDiff={lenDiff}")
                                ts_sec = tstmp/self.ts_Hz
                                msg += (f'\narray dimension mismatchs! lenDiff={lenDiff}  tstmp={ts_sec:.3f} = '
                                        f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(self.recT0+ts_sec))}')
                                if lenDiff < 0:
                                    buffer_mic[:,cnt*seglen:(cnt+1)*seglen] = data[:,:64]
                                elif lenDiff > 0:
                                    buffer_mic[:,cnt*seglen:(cnt+1)*seglen] = np.hstack((data,np.zeros((2,lenDiff))))
                            if len(msg):
                                try:
                                    print(msg, file=open(self.fn_errlog,'a',newline='',encoding='utf-8-sig'))
                                except Exception as e:
                                    print(f'{self.job}: {e}')
                                    time.sleep(0.01)
                                    print(msg, file=open(self.fn_errlog,'a',newline='',encoding='utf-8-sig'))
                            cnt += 1
                            self.processedT += 0.016
                            if cnt == seg_cnt:
                                for i,q in enumerate(buffer_mic):
                                    fileList[i].write(q)
                                fileList[-1].write(buffer_ts)
                                cnt = 0
                            emptyCnt = 0
                        else:
                            emptyCnt += 1
                            if emptyCnt > 200:
                                print(f'end {self.job} recording due to emptyCnt=',emptyCnt)
                                if cnt and cnt < seg_cnt:
                                    for i,q in enumerate(buffer_mic[:,:cnt*seglen]):
                                        fileList[i].write(q)
                                    fileList[-1].write(buffer_ts[:cnt])
                                self.err['whole_duration'] = buffer_ts[-1]
                                self.err['reset_cnt'] = len(self.err['reset_ts'])
                                self.err['pkgloss_cnt'] = len(self.err['pkgloss_ts'])
                                self.err['pkgloss_sec_sum'] = np.sum(self.err['pkgloss_duration'])
                                self.err['pkgloss_avgcnt'] = self.err['pkgloss_cnt']/self.err['whole_duration']
                                self.err['pkgloss_avgsec'] = self.err['pkgloss_sec_sum']/self.err['whole_duration']
                                self.err['ts0'] = self.recT0
                                # print((f"\nerr:  reset_cnt={self.err['reset_cnt']}\n"
                                #         f"err:  pkgloss cnt={self.err['pkgloss_cnt']} duration={self.err['pkgloss_sec_sum']}\n"))
                                with open(self.fn_errJson, 'w', newline='') as jout:
                                    json.dump(self.err, jout, ensure_ascii=False)
                                self.plt_pkgloss(self.fn_errJson)
                                self.stop()
                            time.sleep(self.waitTime)
        elif self.job == 'sysinfo':
            t0 = None
            toffset = 0
            with open(self.filename_new[0], 'a', newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter='\t')
                # writer.writerow(['time','bat(%)','temperature(degC)','bat(mV)'])
                writer.writerow(['time','fwVer','hwVer','bat(%)','temperature(degC)','ble','charging','bat(mV)','imuTemp(degC)'])
                while not self._stop_event.is_set():
                    msg = ''
                    try:
                        tmp = self.q.get(timeout=self.waitTime)
                        if t0 is None:
                            t0 = tmp[0]
                            tlast5 = np.array([0],dtype='uint32')
                        tstmp = tmp[0] + toffset-t0
                        if tmp[0] < t0 or tstmp < tlast5[-1] or tstmp < 0:   # ts was reset
                            msg += (f'\n{self.job} ts was reset because ')
                            msg += (f'\ttmp[0]={tmp[0]} < t0={t0} or tstmp={tstmp} < tpre={tlast5[-1]}  ')
                            msg += f'tlast5[-3:]={tlast5[-3:]}  toffset={toffset}\n'
                            t0 = tmp[0]
                            toffset = tlast5[-1]+np.mean(np.diff(tlast5)) if len(tlast5) > 1 and np.diff(tlast5).any() else tlast5[-1]
                            tstmp = tmp[0] + toffset-t0
                            msg += (f'\tcorrected t0={t0}  toffset={toffset} tstmp={tstmp/self.ts_Hz:.3f} = '
                                    f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(self.recT0+tstmp/self.ts_Hz))}  '
                                    f'at {time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())}')
                        if len(msg):
                            try:
                                print(msg, file=open(self.fn_errlog,'a',newline='',encoding='utf-8-sig'))
                            except Exception as e:
                                print(f'{self.job}: {e}')
                                time.sleep(0.01)
                                print(msg, file=open(self.fn_errlog,'a',newline='',encoding='utf-8-sig'))
                        tstmp = tmp[0] + toffset-t0
                        tlast5 = np.r_[tlast5, tstmp]
                        if tlast5.size > 5:
                            tlast5 = tlast5[-5:]
                        tmp[0] = tstmp/self.ts_Hz
                        # print('sysinfo rec',tmp)
                        tmp[1] = hex(tmp[1])
                        tmp[2] = hex(tmp[2])
                        writer.writerow(tmp)

                    except:
                        # print(f'{self.job}: timeout while getting data')
                        pass
        elif self.job != 'ecg':
            toffset = 0
            pkglen = 20
            ts_interval = pkglen/self.sampleRate
            ts_diff_target = ts_interval*self.ts_Hz
            max_ts_diff = ts_diff_target*1.4
            # ts_sr = int(1/ts_interval)
            iswritten = False
            with sf.SoundFile(self.filename_new[0], mode='x',
                                samplerate=self.sampleRate, channels=self.channels,
                                subtype=self.subtype_NonAudio) as file0:
                # sf.SoundFile(self.filename_new[1], mode='x',
                #                 samplerate=ts_sr, channels=1,
                #                 subtype='FLOAT') as file1:
                # sf.SoundFile(self.filename_new[2], mode='x',
                #                 samplerate=self.sampleRate, channels=self.channels,
                #                 subtype=self.subtype_NonAudio) as file2:
                fileList = [file0] #, file1]#, file2]
                t0 = None # [None]#, None, None]
                while not self._stop_event.is_set():
                    if not self.qMulti[0].empty():
                        iswritten = True
                        msg = ''
                        tmp = self.qMulti[0].get(timeout=0.02)
                        if t0 is None:
                            t0 = tmp[0]
                            data_dim = len(tmp[1][0])
                            pkglen = len(tmp[1])
                            tlast5 = np.array([0],dtype='uint32')
                            ts_interval = pkglen/self.sampleRate
                            ts_diff_target = ts_interval*self.ts_Hz
                            max_ts_diff = ts_diff_target*1.4
                            if self.job == 'acc':
                                msg = f'{self.job},t0_fw={t0},pkglen={len(tmp[1])},tsHz={self.ts_Hz}'
                                print(msg, file=open(self.fn_ts_t0_acc,'w',newline='',encoding='utf-8-sig'))
                        tstmp = tmp[0] + toffset-t0
                        if tmp[0] < t0 or tstmp < tlast5[-1] or tstmp < 0: # ts was reset
                            msg += (f'\n{self.job} ts was reset because')
                            msg += (f'\ttmp[0]={tmp[0]} < t0={t0} or tstmp={tstmp} < tpre={tlast5[-1]}  ')
                            msg += f'tlast5={tlast5}  toffset={toffset}\n'
                            t0 = tmp[0]
                            toffset = tlast5[-1]+np.mean(np.diff(tlast5)) if len(tlast5) > 1 and np.diff(tlast5).any() else tlast5[-1]
                            tstmp = tmp[0] + toffset-t0
                            msg += (f'\tcorrected t0={t0}  toffset={toffset} tstmp={tstmp/self.ts_Hz:.3f} = '
                                    f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(self.recT0+tstmp/self.ts_Hz))}  '
                                    f'at {time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())}')
                        elif tstmp - tlast5[-1] > max_ts_diff: # pkgloss (ts_now >> ts_pre)
                            ts_diff_target = np.median(np.diff(tlast5)) if len(tlast5)>1 and np.diff(tlast5).any() else ts_diff_target
                            msg += (f'\n\t{self.job} pkgloss at {tstmp/self.ts_Hz:.3f} '
                                    f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())}')
                            msg += (f'\t{tstmp}({tstmp/self.ts_Hz:.3f}) - {tlast5[-1]}({tlast5[-1]/self.ts_Hz:.3f})'
                                    f' = {tstmp - tlast5[-1]}={(tstmp - tlast5[-1])/self.ts_Hz:.2f}sec > {max_ts_diff}')
                            add_cnt = 1
                            while tstmp - tlast5[-1] > max_ts_diff:
                                tstmp2 = tlast5[-1] + ts_diff_target
                                tlast5 = np.r_[tlast5, tstmp2]
                                if tlast5.size > 5:
                                    tlast5 = tlast5[-5:]
                                ts = np.linspace(tstmp2, tstmp2+ts_diff_target, pkglen, endpoint=False)/self.ts_Hz
                                # msg += (f'\tadd {add_cnt} ts:{tstmp2} {ts[0]:.3f} {ts[-1]:.3f}')
                                # msg += (f'\t{self.job} mean={np.mean(tmp[1],axis=0).reshape((3,1))}')
                                fileList[0].write(
                                    np.block([[ts],
                                            [np.array(tmp[1])[0].reshape((3,1))*np.ones((data_dim,pkglen))/self.fullscale]]).T)
                                add_cnt += 1
                        tstmp = tmp[0] + toffset-t0
                        tlast5 = np.r_[tlast5, tstmp]
                        if len(msg):
                            try:
                                print(msg, file=open(self.fn_errlog,'a',newline='',encoding='utf-8-sig'))
                            except Exception as e:
                                print(f'{self.job}: {e}')
                                time.sleep(0.01)
                                print(msg, file=open(self.fn_errlog,'a',newline='',encoding='utf-8-sig'))
                        if tlast5.size > 5:
                            tlast5 = tlast5[-5:]
                        ts = np.linspace(tstmp, tstmp+ts_diff_target, pkglen, endpoint=False)/self.ts_Hz
                        fileList[0].write(
                                    np.block([[ts],
                                            [np.array(list(tmp[1])).T/self.fullscale]]).T)
                    else:
                        time.sleep(self.waitTime)
            if not iswritten:
                os.remove(self.filename_new[0])
                os.remove(self.fn_errlog)

        elif self.job == 'ecg':
            iswritten = False
            with sf.SoundFile(self.filename_new[0], mode='x',
                                samplerate=int(self.sampleRate), channels=self.channels,
                                subtype=self.subtype_NonAudio) as file0:
                fileList = [file0]

                t0 = None
                while not self._stop_event.is_set():
                    if not self.qMulti[0].empty():
                        iswritten = True
                        tmp = self.qMulti[0].get(timeout=0.02)
                        if t0 is None:
                            msg = ''
                            t0 = tmp[0]
                            data_dim = len(tmp[1][0])
                            pkglen = len(tmp[1])
                            tlast5 = np.array([0],dtype='uint32')
                            ts_interval = pkglen/self.sampleRate
                            ts_diff_target = ts_interval*self.ts_Hz
                            max_ts_diff = ts_diff_target*1.4
                            toffset = 0
                            if self.job == 'acc':
                                msg = f'{self.job},t0_fw={t0},pkglen={len(tmp[1])},tsHz={self.ts_Hz}'
                                print(msg, file=open(self.fn_ts_t0_acc,'w',newline='',encoding='utf-8-sig'))
                        tstmp = tmp[0] + toffset-t0
                        if tmp[0] < t0 or tstmp < tlast5[-1] or tstmp < 0: # ts was reset
                            msg += (f'\n{self.job} ts was reset because')
                            msg += (f'\ttmp[0]={tmp[0]} < t0={t0} or tstmp={tstmp} < tpre={tlast5[-1]}  ')
                            msg += f'tlast5={tlast5}  toffset={toffset}\n'
                            t0 = tmp[0]
                            toffset = tlast5[-1]+np.mean(np.diff(tlast5)) if len(tlast5) > 1 and np.diff(tlast5).any() else tlast5[-1]
                            tstmp = tmp[0] + toffset-t0
                            msg += (f'\tcorrected t0={t0}  toffset={toffset} tstmp={tstmp/self.ts_Hz:.3f} = '
                                    f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(self.recT0+tstmp/self.ts_Hz))}  '
                                    f'at {time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())}')
                        elif tstmp - tlast5[-1] > max_ts_diff: # pkgloss (ts_now >> ts_pre)
                            ts_diff_target = np.median(np.diff(tlast5)) if len(tlast5)>1 and np.diff(tlast5).any() else ts_diff_target
                            msg += (f'\n\t{self.job} pkgloss at {tstmp/self.ts_Hz:.3f} '
                                    f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())}')
                            msg += (f'\t{tstmp}({tstmp/self.ts_Hz:.3f}) - {tlast5[-1]}({tlast5[-1]/self.ts_Hz:.3f})'
                                    f' = {tstmp - tlast5[-1]}={(tstmp - tlast5[-1])/self.ts_Hz:.2f}sec > {max_ts_diff}')
                            add_cnt = 1
                            while tstmp - tlast5[-1] > max_ts_diff:
                                tstmp2 = tlast5[-1] + ts_diff_target
                                tlast5 = np.r_[tlast5, tstmp2]
                                if tlast5.size > 5:
                                    tlast5 = tlast5[-5:]
                                ts = np.linspace(tstmp2, tstmp2+ts_diff_target, pkglen, endpoint=False)/self.ts_Hz
                                # msg += (f'\tadd {add_cnt} ts:{tstmp2} {ts[0]:.3f} {ts[-1]:.3f}')
                                # msg += (f'\t{self.job} mean={np.mean(tmp[1],axis=0).reshape((3,1))}')
                                fileList[0].write(
                                    np.block([[ts],
                                            [np.array(tmp[1])[0].reshape((3,1))*np.ones((data_dim,pkglen))/self.fullscale]]).T)
                                add_cnt += 1

                        tstmp = tmp[0] + toffset-t0
                        tlast5 = np.r_[tlast5, tstmp]
                        if len(msg):
                            try:
                                print(msg, file=open(self.fn_errlog,'a',newline='',encoding='utf-8-sig'))
                            except Exception as e:
                                print(f'{self.job}: {e}')
                                time.sleep(0.01)
                                print(msg, file=open(self.fn_errlog,'a',newline='',encoding='utf-8-sig'))
                        if tlast5.size > 5:
                            tlast5 = tlast5[-5:]
                        ts = np.linspace(tstmp, tstmp+ts_diff_target, pkglen, endpoint=False)/self.ts_Hz
                        fileList[0].write(
                                    np.block([[ts],
                                            [np.array(list(tmp[1])).T/self.fullscale]]).T)
                    else:
                        time.sleep(self.waitTime)
            if not iswritten:
                os.remove(self.filename_new[0])
                os.remove(self.fn_errlog)

        print(f'Stop recording {self.job}')
        if self.job == 'mic':
            endts = time.time()
            msg = (f'recording ends at {time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(endts))}  '
                    f'duration= {self.hhmmss(endts-self.recT0)}')
            print(msg, file=open(self.fn_errlog,'a',newline=''))
        # for i,f in enumerate(fileList):
        #     print(f'is {self.job} file{i} closed? {f.closed}')
        # time.sleep(self.waitTime)