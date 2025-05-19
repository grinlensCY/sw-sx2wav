import threading
import queue
import time
import os

class Driver:
    def __init__(self,file_path,job=''):
        self.file_path=file_path

        self.thd=None
        self.thd_run_flag=None

        self.rx_queue=queue.Queue()

        self.isSXR = True if file_path.endswith('sxr') else False
        print('sx file drv: isSXR?',self.isSXR)
        self.job = job

    def write(self,ba):
        pass

    def read(self):
        if(self.rx_queue.empty()):
            # print('file drv: rx_queue.empty')
            return None
        
        return self.rx_queue.get_nowait()

    def __io_thd_fun__(self,flag,file_path,rxq):
        #ser=None
        fp=None

        try:
            fp=open(file_path,'rb')
            file_size = os.path.getsize(file_path)
            print(f'\ndrv:{self.job} file opened at {fp.tell()}  {file_size=}\n')
            
        except:
            time.sleep(0.5)
            return

        #empty_cnt = 0
        read_cnt = 0
        while(flag.is_set()):
            try:
                #in_len=8000
                dat=fp.read(8000)
                #empty_cnt = 0
            except:
                time.sleep(0.5)
                #empty_cnt += 1
                print(f'drv:{self.job} read empty')
                break

            in_len=len(dat)
            if(in_len>0):
                read_cnt += 1
                rxq.put_nowait(dat)
            else:
                print(f"\ndrv:{self.job} in_len(dat) == 0  {read_cnt=}  pos={fp.tell()}  {file_size=}  {fp.tell()==file_size=}\n")
                if fp.tell()==file_size:
                    break
            # print('in_len=',in_len)
            # time.sleep(0.018)
        self.stop('__io_thd_fun__')

    def start(self):
        self.stop('drv_start')

        self.thd_run_flag=threading.Event()
        self.thd_run_flag.set()


        while not self.rx_queue.empty():
            self.rx_queue.get_nowait()

        self.thd=threading.Thread(target = self.__io_thd_fun__, args =(self.thd_run_flag,self.file_path,self.rx_queue,))
        self.thd.start()
        print(f'drv:{self.job}start {self.thd_run_flag.is_set()}')

    def stop(self,typ=''):
        print(f'\ndrv:{self.job} stop by {typ}  {self.rx_queue.empty()=}  {self.rx_queue.qsize()=}\n')
        if(self.thd_run_flag is not None):
            self.thd_run_flag.clear()
            
            if(self.thd is not None):
                try:
                    self.thd.join(2.0)
                except:
                    pass

        self.thd_run_flag=None
        self.thd=None


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