import threading
import queue
import time
import os

class Driver:
    def __init__(self,file_path,job='',skip_bytes=0):
        print(f"FD driver of {__file__}")
        print(f"FD driver: {file_path=}")
        self.file_path=file_path

        self.thd=None
        self.thd_run_flag=None
        self.skip_bytes=skip_bytes

        self.rx_queue=queue.Queue()

        self.isSXR = True if file_path.endswith('sxr') else False
        print('sx file drv: isSXR?',self.isSXR)
        self.job = job
        self.flag_finishstop = threading.Event()
        self.read_cnt = 0

    def write(self,ba):
        pass

    def read(self):
        if(self.rx_queue.empty()):
            # print('file drv: rx_queue.empty')
            return None
        
        return self.rx_queue.get_nowait()

    def is_encrypted(self):
        if(self.file_path.endswith('sxr')):
            return True
        return False

    def __io_thd_fun__(self,flag,file_path,rxq,tEnd=0):
        #ser=None
        fp=None

        try:
            fp=open(file_path,'rb')
            flen = os.path.getsize(file_path)
            readEnd = tEnd * 20 *1024 if tEnd else flen
            print(f'\ndrv:{self.job} file opened at {fp.tell()}  {flen=}  {tEnd=}  {readEnd=}\n')
            
        except:
            time.sleep(0.5)
            return

        self.read_cnt = 0
        rxIdx=self.skip_bytes
        fp.seek(self.skip_bytes)
        while(flag.is_set()):
            try:
                #in_len=8000
                dat=fp.read(8000)

            except:
                print(f'drv:{self.job} read empty')
                time.sleep(0.5)
                break

            in_len=len(dat)
            rxIdx+=in_len
            #print(in_len)

            if(in_len>0):
                self.read_cnt += 1
                rxq.put_nowait(dat)
                if rxIdx >= readEnd:
                    break

            if(rxIdx>=flen):
                break
            
            if(in_len==0):
                time.sleep(0.1)

        flag.clear()
        print(f"file_driver: __io_thd_fun__ finished at {rxIdx=}.  {flen=}  {rxIdx>=flen=}  {rxIdx >= readEnd =}  {self.read_cnt=}")
        if self.job != 'chk_files_format' and rxIdx < min(flen,readEnd):
            raise RuntimeError('rxIdx < min(flen,readEnd)')

    def start(self,job='',tEnd=0):
        print(f"start FD by {job}  {tEnd=}")
        self.stop('drv_start')

        while not self.flag_finishstop.is_set():
            time.sleep(0.01)
        self.flag_finishstop.clear()

        while not self.rx_queue.empty():
            self.rx_queue.get_nowait()
        
        self.thd_run_flag=threading.Event() # flag of is reading 
        self.thd_run_flag.set()

        self.thd=threading.Thread(target = self.__io_thd_fun__, name="FD:__io_thd_fun__", args =(self.thd_run_flag,self.file_path,self.rx_queue,tEnd,))
        self.thd.start()
        print(f'drv:{self.job} start {self.thd_run_flag.is_set()=}')

    def is_finished(self):
        if(self.thd_run_flag is None):
            return True
        return self.thd_run_flag.is_set()==False

    def stop(self,typ=''):
        print(f'\ndrv:{self.job} stop by {typ}  {self.rx_queue.empty()=}  {self.rx_queue.qsize()=}  '
              f'{self.thd.is_alive() if self.thd else self.thd =}\n')
        if(self.thd_run_flag is not None):
            self.thd_run_flag.clear()

            if(self.thd is not None):
                try:
                    self.thd.join(2.0)
                except:
                    pass

        self.thd_run_flag=None
        self.thd=None
        self.flag_finishstop.set()
        print(f'FD stopped by {typ}',threading.enumerate())


if __name__ == "__main__":
    drv = Driver('./android_test_file/D2_6A_EF_C4_5E_0D/1614135882794.sx')
    drv.start()

    bg_ts=time.time()
    while(True):
        curr_ts=time.time()
        if(curr_ts-bg_ts>10):
            break

        msg=drv.read()
        if(msg is not None):
            print(msg)

    drv.stop()