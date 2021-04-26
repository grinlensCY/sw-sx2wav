import threading
import datetime
import soundfile as sf
import time
import os
import queue
import numpy as np

class RecThread(threading.Thread):    
    def __init__(self, sampleRate, channels, waitTime, fn_prefix, job, fullscale, isdualmic):
        #QtCore.QThread.__init__(self)
        super(RecThread, self).__init__()
        self.sampleRate = sampleRate
        self.channels = channels
        self.waitTime = waitTime
        self.q = queue.Queue()
        self.qMulti = [queue.Queue() for i in range(3)]
        self._stop_event = threading.Event()
        # self.filename_prefix = f'{os.path.dirname(__file__)}/record/{fn_prefix}'
        self.filename_prefix = fn_prefix
        self.filename_new = []
        self.daemon = True
        self.job = job
        self.subtype_audio = 'PCM_16'
        self.subtype_NonAudio = 'float'
        self.fullscale = fullscale
        self.isdualmic = isdualmic
        self.name = f'{job}_rec'
        if job == 'mic':
            self.filename_new.append(f'{self.filename_prefix}-audio-main01.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-env01.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-main02.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-main03.wav')
            self.filename_new.append(f'{self.filename_prefix}-audio-ts.wav')
        elif job != 'ecg':
            for i in range(1):
                self.filename_new.append(f'{self.filename_prefix}-{job}-{i+1:02d}.wav')
        elif job == 'ecg':
            self.filename_new.append(f'{self.filename_prefix}-{job}.wav')
        print(self.filename_new)
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
                                subtype=self.subtype_NonAudio) as file4:
                
                fileList = [file0, file1, file2, file3, file4]
                t0 = None
                seglen = 64 if self.sampleRate==4000 else 32
                data_dim = 2 if self.isdualmic else 4
                seg_cnt = 20
                buffer_mic = np.zeros((data_dim,seglen*seg_cnt),dtype=np.float64)
                buffer_ts = np.zeros(seg_cnt,dtype=np.float64)
                cnt = 0
                while not self._stop_event.is_set():
                    if not self.q.empty():
                        tmp = self.q.get_nowait()
                        micdata = np.array(tmp[1:])/self.fullscale
                        # print('record ',micdata.shape)
                        buffer_mic[:,cnt*seglen:(cnt+1)*seglen] = micdata
                        if t0 is None:
                            t0 = tmp[0]
                        buffer_ts[cnt] = (tmp[0]-t0) * 4e-6
                        cnt += 1
                        if cnt == seg_cnt:
                            for i,q in enumerate(buffer_mic):
                                fileList[i].write(q)
                            fileList[-1].write(buffer_ts)
                            cnt = 0
                        # if t0 is None:
                        #     t0 = tmp[0]
                        # ts = (tmp[0]-t0) * 4e-6
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
            if self.isdualmic:
                print(f'recording> remove({self.filename_new[2]})')
                os.remove(self.filename_new[2])
                print(f'recording> remove({self.filename_new[3]})')
                os.remove(self.filename_new[3])
        elif self.job != 'ecg':
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
                data = [[]]   #[[],[],[]]
                t0 = [None, None, None]
                while not self._stop_event.is_set():
                    hasData = False
                    for i in range(1):
                        # if not self.qMulti[i].empty():
                        #     data[i].append(self.qMulti[i].get_nowait())
                        # else:
                        #     time.sleep(self.waitTime)
                        try:
                            data[i].append(self.qMulti[i].get(timeout=0.02))
                            hasData |= True
                        except:
                            # print(f'{self.job}: timeout while getting data of ch{i}')
                            pass
                    if not hasData: emptyCnt += 1
                    if emptyCnt > 200:
                        print(f'end {self.job} recording due to emptyCnt=',emptyCnt)
                        self.stop()
                    for i in range(1):
                        if len(data[i])==2:
                            # print(f'ch{i} ts={data[i][0][0]},{data[i][1][0]} len={len(data[i][0][1])},{len(data[i][1][1])}')
                            if t0[i] is None:
                                t0[i] = data[i][0][0]
                            ts = np.linspace(data[i][0][0]-t0[i], data[i][1][0]-t0[i],
                                             len(data[i][0][1]), endpoint=False) * 4e-6
                            # print(f'{self.job}rec  {np.block([[ts], [np.array(list(data[i][0][1])).T]]).T.shape}')
                            fileList[i].write(
                                np.block([[ts],
                                          [np.array(list(data[i][0][1])).T
                                            /self.fullscale]])
                                .T)
                            del data[i][0]
                            # print(f'ch{i}  ts={ts[0]:.6f}~{ts[-1]:.6f}sec  t0={t0[i]}')
        elif self.job == 'ecg':
            with sf.SoundFile(self.filename_new[0], mode='x',
                                samplerate=self.sampleRate, channels=self.channels,
                                subtype=self.subtype_NonAudio) as file0:
                fileList = [file0]
                data = [[]]
                t0 = [None]
                while not self._stop_event.is_set():
                    for i in range(1):
                        if not self.qMulti[i].empty():
                            data[i].append(self.qMulti[i].get_nowait())
                            emptyCnt = 0
                        else:
                            emptyCnt += 1
                            if emptyCnt > 200:
                                print(f'end {self.job} recording due to emptyCnt=',emptyCnt)
                                self.stop()
                            time.sleep(self.waitTime)
                    for i in range(1):
                        if len(data[i])==2:
                            # print(f'ch{i} ts={data[i][0][0]},{data[i][1][0]} len={len(data[i][0][1])},{len(data[i][1][1])}')
                            if t0[i] is None:
                                t0[i] = data[i][0][0]
                            ts = np.linspace(data[i][0][0]-t0[i], data[i][1][0]-t0[i],
                                             len(data[i][0][1]), endpoint=False) * 4e-6
                            fileList[i].write(
                                np.block([[ts],
                                          [np.array(list(data[i][0][1])).T
                                            /self.fullscale]])
                                .T)
                            del data[i][0]
        print(f'Stop recording {self.job}')
        # for i,f in enumerate(fileList):
        #     print(f'is {self.job} file{i} closed? {f.closed}')
        # time.sleep(self.waitTime)