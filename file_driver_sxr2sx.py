import serial
import threading
import queue
import time
import os

class Driver:
    def __init__(self,file_path):
        self.file_path=file_path

        self.thd=None
        self.thd_run_flag=None

        self.rx_queue=queue.Queue()

    def write(self,ba):
        pass

    def read(self):
        if(self.rx_queue.empty()):
            return None
        
        return self.rx_queue.get_nowait()

    def is_encrypted(self):
        if(self.file_path.endswith('sxr')):
            return True
        return False

    def __io_thd_fun__(self,flag,file_path,rxq):
        ser=None
        fp=None

        try:
            fp=open(file_path,'rb')
        except:
            time.sleep(0.5)
            return

        flen=os.path.getsize(file_path)
        rxIdx=0

        while(flag.is_set()):
            try:
                in_len=400
                dat=fp.read(in_len)
            except:
                print('AAAAAAAAAAAAAAAA')
                time.sleep(0.5)
                break

            in_len=len(dat)
            rxIdx+=in_len
            #print(in_len)

            if(in_len>0):
                rxq.put_nowait(dat)

            if(rxIdx>=flen):
                break
            
            if(in_len==0):
                time.sleep(0.1)

        flag.clear()
        print(rxIdx,flen)

    def start(self):
        self.stop()

        self.thd_run_flag=threading.Event()
        self.thd_run_flag.set()


        while not self.rx_queue.empty():
            self.rx_queue.get_nowait()

        self.thd=threading.Thread(target = self.__io_thd_fun__, args =(self.thd_run_flag,self.file_path,self.rx_queue,))
        self.thd.start()

    def is_finished(self):
        if(self.thd_run_flag is None):
            return True
        return self.thd_run_flag.is_set()==False

    def stop(self):
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