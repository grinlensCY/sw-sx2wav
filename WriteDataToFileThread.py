import threading
import csv
import soundfile as sf
import time
import os
import queue
import numpy as np
import csv

class RecThread(threading.Thread):    
    def __init__(self, sampleRate, channels, waitTime, fn_prefix, job, fullscale, isdualmic=False, recT0=None, config={}, ts_Hz=32768):
        #QtCore.QThread.__init__(self)
        super(RecThread, self).__init__()
        self.sampleRate = sampleRate
        self.channels = channels
        self.waitTime = waitTime
        self.q = queue.Queue()
        self.qMulti = [queue.Queue() for i in range(3)]
        self._stop_event = threading.Event()
        # self.filename_prefix = f'{os.path.dirname(__file__)}/record/{fn_prefix}'
        self.recT0 = recT0
        self.filename_prefix = fn_prefix
        self.filename_new = []
        self.daemon = True
        self.job = job
        self.subtype_audio = 'PCM_16'
        self.subtype_NonAudio = 'float'
        self.fullscale = fullscale
        self.isdualmic = isdualmic
        self.name = f'{job}_rec'
        self.fn_errlog = f'{self.filename_prefix}-errlog.txt'
        self.fn_ts_t0_mic = f'{self.filename_prefix}-ts_t0_mic.txt'
        self.fn_ts_t0_acc = f'{self.filename_prefix}-ts_t0_acc.txt'
        self.config = config
        self.ts_Hz = ts_Hz
        print(f'start recording at {fn_prefix}', file=open(self.fn_errlog,'a',newline=''))
        if job == 'mic':
            self.filename_new.append(f'{self.filename_prefix}-audio-main01.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-env01.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-main02.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-main03.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-ts.wav')
        elif job == 'sysinfo':
            self.filename_new.append(f'{self.filename_prefix}-{job}.csv')
        elif job != 'ecg':
            for i in range(1):
                self.filename_new.append(f'{self.filename_prefix}-{job}-{i+1:02d}.wav')
        elif job == 'ecg':
            self.filename_new.append(f'{self.filename_prefix}-{job}.wav')
        if not self.config['onlytst0']:
            for fn in self.filename_new:
                print('going to record',fn)
                if os.path.exists(fn):
                    os.remove(fn)
                    print('replace existing',os.path.basename(fn))
        else:
            print('\nonly export fwt0')
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
                        micdata = np.array(tmp[1:])/self.fullscale
                        t0 = tmp[0]
                        pkglen = len(micdata[0])
                        tlast5 = np.array([0],dtype='uint32')
                        msg = f'{self.job},t0_fw={t0},pkglen={micdata[0].size}'
                        print(msg, file=open(self.fn_ts_t0_mic,'w',newline=''))
                        self.stop()
                    else:
                        time.sleep(self.waitTime)
            else:
                sr_PatchTS = int(1/0.016)
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
                                    samplerate=sr_PatchTS, channels=self.channels,
                                    subtype=self.subtype_NonAudio) as file4:
                    fileList = [file0, file1, file2, file3, file4]
                    t0 = None
                    seglen = 64 if self.sampleRate==4000 else 32
                    data_dim = 2 if self.isdualmic else 4
                    seg_cnt = 40
                    buffer_mic = np.zeros((data_dim,seglen*seg_cnt),dtype=np.float64)
                    buffer_ts = np.zeros(seg_cnt,dtype=np.float64)
                    toffset = 0
                    cnt = 0
                    while not self._stop_event.is_set():
                        if not self.q.empty():
                            msg = ''
                            tmp = self.q.get_nowait()
                            micdata = np.array(tmp[1:])/self.fullscale
                            if t0 is None:  # initial
                                t0 = tmp[0]
                                data_dim = len(micdata)
                                pkglen = len(micdata[0])
                                tlast5 = np.array([0],dtype='uint32')
                                msg = f'{self.job},t0_fw={t0},pkglen={micdata[0].size}'
                                print(msg, file=open(self.fn_ts_t0_mic,'w',newline=''))
                            tstmp = tmp[0] + toffset-t0
                            if tmp[0] < t0 or tstmp < tlast5[-1] or tstmp < 0:    # ts was reset
                                msg += (f'\n{self.job} ts was reset because ')
                                msg += (f'\ttmp[0]={tmp[0]} < t0={t0} or tstmp={tstmp} < tpre={tlast5[-1]}  ')
                                msg += f'tlast5[-3:]={tlast5[-3:]}  toffset={toffset}\n'
                                t0 = tmp[0]
                                toffset = tlast5[-1]+np.mean(np.diff(tlast5)) if len(tlast5) > 1 and np.diff(tlast5).any() else tlast5[-1]
                                tstmp = tmp[0] + toffset-t0
                                msg += (f'\tcorrected t0={t0}  toffset={toffset} tstmp={tstmp/self.ts_Hz:.3f} = '
                                        f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(self.recT0+tstmp/self.ts_Hz))}')
                            elif tstmp - tlast5[-1] > max_ts_diff: # pkgloss (ts_now >> ts_pre)
                                ts_diff_target = np.median(np.diff(tlast5)) if len(tlast5)>1 and np.diff(tlast5).any() else ts_diff_target
                                msg += (f'\nmic pkgloss at {tstmp/self.ts_Hz:.3f} {time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(self.recT0+tstmp/self.ts_Hz))}')
                                msg += (f'\t{tstmp}({tstmp/self.ts_Hz:.3f}) - {tlast5[-1]}({tlast5[-1]/self.ts_Hz:.3f})'
                                        f' = {tstmp - tlast5[-1]}={(tstmp - tlast5[-1])/self.ts_Hz:.2f}sec > {max_ts_diff}')
                                add_cnt = 1
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
                            if len(msg):
                                try:
                                    print(msg, file=open(self.fn_errlog,'a',newline=''))
                                except Exception as e:
                                    print(f'{self.job}: {e}')
                                    time.sleep(0.01)
                                    print(msg, file=open(self.fn_errlog,'a',newline=''))
                            tstmp = tmp[0] + toffset-t0
                            tlast5 = np.r_[tlast5, tstmp]
                            if tlast5.size > 5:
                                tlast5 = tlast5[-5:]
                            buffer_ts[cnt] = (tstmp) / self.ts_Hz
                            buffer_mic[:,cnt*seglen:(cnt+1)*seglen] = micdata
                            cnt += 1
                            if cnt == seg_cnt:
                                for i,q in enumerate(buffer_mic):
                                    fileList[i].write(q)
                                fileList[-1].write(buffer_ts)
                                cnt = 0
                            # if t0 is None:
                            #     t0 = tmp[0]
                            # ts = (tmp[0]-t0) / self.ts_Hz
                            # for i,q in enumerate(micdata):
                            #     fileList[i].write(q)  # block=True, timeout=0.05
                            # fileList[-1].write(ts)
                            emptyCnt = 0
                        else:
                            emptyCnt += 1
                            if emptyCnt > 200:
                                print(f'end {self.job} recording due to emptyCnt=',emptyCnt)
                                if cnt and cnt < seg_cnt:
                                    for i,q in enumerate(buffer_mic[:,:cnt*seglen]):
                                        fileList[i].write(q)
                                    fileList[-1].write(buffer_ts[:cnt])
                                self.stop()
                            time.sleep(self.waitTime)
                            # break
        elif self.job == 'sysinfo':
            if self.config['onlytst0']:
                print(f'end {self.job} recording due to onlytst0=',self.config['onlytst0'])
                self.stop()
            else:
                t0 = None
                toffset = 0
                with open(self.filename_new[0], 'a', newline='') as csvfile:
                    writer = csv.writer(csvfile, delimiter='\t')
                    # writer.writerow(['time','bat(%)','temperature(degC)','bat(mV)'])
                    writer.writerow(['time','fwVer','hwVer','bat(%)','temperature(degC)','ble','charging','bat(mV)','imuTemp(degC)'])
                    while not self._stop_event.is_set():
                        msg = ''
                        hasData = False
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
                                        f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(self.recT0+tstmp/self.ts_Hz))}')
                            if len(msg):
                                try:
                                    print(msg, file=open(self.fn_errlog,'a',newline=''))
                                except Exception as e:
                                    print(f'{self.job}: {e}')
                                    time.sleep(0.01)
                                    print(msg, file=open(self.fn_errlog,'a',newline=''))
                            tstmp = tmp[0] + toffset-t0
                            tlast5 = np.r_[tlast5, tstmp]
                            if tlast5.size > 5:
                                tlast5 = tlast5[-5:]
                            tmp[0] = tstmp / self.ts_Hz
                            # print('sysinfo rec',tmp)
                            writer.writerow(tmp)
                            hasData |= True
                        except:
                            # print(f'{self.job}: timeout while getting data')
                            pass
                        if not hasData:
                            emptyCnt += 1
                        else:
                            emptyCnt = 0
                        if emptyCnt > 200:
                            print(f'end {self.job} recording due to emptyCnt=',emptyCnt)
                            self.stop()
        elif self.job != 'ecg':
            if self.config['onlytst0']:
                while not self._stop_event.is_set():
                    if not self.qMulti[0].empty():
                        tmp = self.qMulti[0].get(timeout=0.02)
                        t0 = tmp[0]
                        data_dim = len(tmp[1][0])
                        pkglen = len(tmp[1])
                        tlast5 = np.array([0],dtype='uint32')
                        if self.job == 'acc':
                            msg = f'{self.job},t0_fw={t0},pkglen={len(tmp[1])}'
                            print(msg, file=open(self.fn_ts_t0_acc,'w',newline=''))
                        self.stop()
                    else:
                        emptyCnt += 1
                        if emptyCnt > 100:
                            print(f'end {self.job} recording due to emptyCnt=',emptyCnt)
                            self.stop()
                        time.sleep(self.waitTime)
            else:
                with sf.SoundFile(self.filename_new[0], mode='x',
                                    samplerate=self.sampleRate, channels=self.channels,
                                    subtype=self.subtype_NonAudio) as file0:
                    # sf.SoundFile(self.filename_new[1], mode='x',
                    #                 samplerate=self.sampleRate, channels=self.channels,
                    #                 subtype=self.subtype_NonAudio) as file1,\
                    # sf.SoundFile(self.filename_new[2], mode='x',
                    #                 samplerate=self.sampleRate, channels=self.channels,
                    #                 subtype=self.subtype_NonAudio) as file2:
                    fileList = [file0]#, file1, file2]
                    # data = [[]]   #[[],[],[]]
                    t0 = None # [None]#, None, None]
                    toffset = 0
                    while not self._stop_event.is_set():
                        if not self.qMulti[0].empty():
                            msg = ''
                            emptyCnt = 0
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
                                    msg = f'{self.job},t0_fw={t0},pkglen={len(tmp[1])}'
                                    print(msg, file=open(self.fn_ts_t0_acc,'w',newline=''))
                            tstmp = tmp[0] + toffset-t0
                            if tmp[0] < t0 or tstmp < tlast5[-1] or tstmp < 0: # ts was reset
                                msg += (f'\n{self.job} ts was reset because')
                                msg += (f'\ttmp[0]={tmp[0]} < t0={t0} or tstmp={tstmp} < tpre={tlast5[-1]}  ')
                                msg += f'tlast5={tlast5}  toffset={toffset}\n'
                                t0 = tmp[0]
                                toffset = tlast5[-1]+np.mean(np.diff(tlast5)) if len(tlast5) > 1 and np.diff(tlast5).any() else tlast5[-1]
                                tstmp = tmp[0] + toffset-t0
                                msg += (f'\tcorrected t0={t0}  toffset={toffset} tstmp={tstmp/self.ts_Hz:.3f} = '
                                        f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(self.recT0+tstmp/self.ts_Hz))}')
                            elif tstmp - tlast5[-1] > max_ts_diff: # pkgloss (ts_now >> ts_pre)
                                ts_diff_target = np.median(np.diff(tlast5)) if len(tlast5)>1 and np.diff(tlast5).any() else ts_diff_target
                                msg += (f'\n\t{self.job} pkgloss at {tstmp/self.ts_Hz:.3f} '
                                        f'{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(self.recT0+tstmp/self.ts_Hz))}')
                                msg += (f'\t{tstmp}({tstmp/self.ts_Hz:.3f}) - {tlast5[-1]}({tlast5[-1]/self.ts_Hz:.3f})'
                                        f' = {tstmp - tlast5[-1]}={(tstmp - tlast5[-1])/self.ts_Hz:.2f}sec > {max_ts_diff}')
                                add_cnt = 1
                                while tstmp - tlast5[-1] > max_ts_diff:
                                    tstmp2 = tlast5[-1] + ts_diff_target
                                    tlast5 = np.r_[tlast5, tstmp2]
                                    if tlast5.size > 5:
                                        tlast5 = tlast5[-5:]
                                    ts = np.linspace(tstmp2, tstmp2+ts_diff_target, pkglen, endpoint=False) / self.ts_Hz
                                    fileList[0].write(
                                        np.block([[ts],
                                                [np.array(tmp[1])[0].reshape((3,1))*np.ones((data_dim,pkglen))/self.fullscale]]).T)
                                    add_cnt += 1
                            tstmp = tmp[0] + toffset-t0
                            # if tstmp < 0 or tlast5[-1] < 0:
                            #     msg += (f'{self.job} before tlast5({tlast5[-1]}) < 0 at {tstmp/self.ts_Hz} tstmp={tstmp}  tmp[0]={tmp[0]}  toffset={toffset}  t0={t0}\n')
                            tlast5 = np.r_[tlast5, tstmp]
                            # if tlast5[-1] < 0:
                            #     msg += (f'{self.job} after tlast5({tlast5[-1]}) < 0 at {tstmp/self.ts_Hz} tstmp={tstmp}  tmp[0]={tmp[0]}  toffset={toffset}  t0={t0}\n')
                            #     tlast5[-1] = tstmp
                            if len(msg):
                                try:
                                    print(msg, file=open(self.fn_errlog,'a',newline=''))
                                except Exception as e:
                                    print(f'{self.job}: {e}')
                                    time.sleep(0.01)
                                    print(msg, file=open(self.fn_errlog,'a',newline=''))
                            if tlast5.size > 5:
                                tlast5 = tlast5[-5:]
                            ts = np.linspace(tstmp, tstmp+ts_diff_target, pkglen, endpoint=False) / self.ts_Hz
                            fileList[0].write(
                                        np.block([[ts],
                                                [np.array(list(tmp[1])).T/self.fullscale]]).T)
                        else:
                            emptyCnt += 1
                            if emptyCnt > 200:
                                print(f'end {self.job} recording due to emptyCnt=',emptyCnt)
                                self.stop()
                            time.sleep(self.waitTime)

        # elif self.job == 'ecg':
            # if not self.config['onlytst0']:
            #     with sf.SoundFile(self.filename_new[0], mode='x',
            #                         samplerate=self.sampleRate, channels=self.channels,
            #                         subtype=self.subtype_NonAudio) as file0:
            #         fileList = [file0]
            #         data = [[]]
            #         t0 = [None]
            #         while not self._stop_event.is_set():
            #             for i in range(1):
            #                 if not self.qMulti[i].empty():
            #                     data[i].append(self.qMulti[i].get_nowait())
            #                     emptyCnt = 0
            #                 else:
            #                     emptyCnt += 1
            #                     if emptyCnt > 200:
            #                         print(f'end {self.job} recording due to emptyCnt=',emptyCnt)
            #                         self.stop()
            #                     time.sleep(self.waitTime)
            #             for i in range(1):
            #                 if len(data[i])==2:
            #                     # print(f'ch{i} ts={data[i][0][0]},{data[i][1][0]} len={len(data[i][0][1])},{len(data[i][1][1])}')
            #                     if t0[i] is None:
            #                         t0[i] = data[i][0][0]
            #                     ts = np.linspace(data[i][0][0]-t0[i], data[i][1][0]-t0[i],
            #                                     len(data[i][0][1]), endpoint=False) / self.ts_Hz
            #                     fileList[i].write(
            #                         np.block([[ts],
            #                                 [np.array(list(data[i][0][1])).T
            #                                     /self.fullscale]])
            #                         .T)
            #                     del data[i][0]
        
        print(f'Stop recording {self.job}')
        for fn in self.filename_new:
            print('finish recording',fn)
        # for i,f in enumerate(fileList):
        #     print(f'is {self.job} file{i} closed? {f.closed}')
        # time.sleep(self.waitTime)