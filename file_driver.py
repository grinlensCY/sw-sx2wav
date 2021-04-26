import serial
import threading
import queue
import time

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
            # print('file drv: rx_queue.empty')
            return None
        
        return self.rx_queue.get_nowait()

    def __io_thd_fun__(self,flag,file_path,rxq):
        ser=None
        fp=None

        try:
            fp=open(file_path,'rb')
            print('drv: file opened')
        except:
            time.sleep(0.5)
            return

        while(flag.is_set()):
            try:
                in_len=400
                dat=fp.read(in_len)
            except:
                time.sleep(0.5)
                break

            in_len=len(dat)
            if(in_len>0):
                rxq.put_nowait(dat)
            # print('in_len=',in_len)
            # time.sleep(0.018)

    def start(self):
        self.stop()

        self.thd_run_flag=threading.Event()
        self.thd_run_flag.set()


        while not self.rx_queue.empty():
            self.rx_queue.get_nowait()

        self.thd=threading.Thread(target = self.__io_thd_fun__, args =(self.thd_run_flag,self.file_path,self.rx_queue,))
        self.thd.start()
        print('drv: start self.thd_run_flag:',self.thd_run_flag.is_set())

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

        print('drv: stop')

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