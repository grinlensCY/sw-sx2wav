import serial
import threading
import queue
import time
import struct

import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
# pip install cryptography

try:
    import file_driver as FD
except:
    from . import file_driver as FD

class SimpleSysInfoHandler:
    def handle_sys_info_pkg(self,dat):
        #print('get sys info')
        pass

class SimpleMicDataHandler:
    def handle_mic_pkg(self,dat):
        #print('get mic')
        pass
    def handle_dual_mic_pkg(self,dat):
        #print('get dual mic')
        pass

class SimpleEcgDataHandler:
    def handle_ecg_raw_pkg(self,dat):
        #print('get ecg raw')
        pass

    def handle_ecg_heart_rate_pkg(self,dat):
        #print('get ecg heart rate')
        pass

    def handle_ecg_signal_quality_pkg(self,dat):
        #print('get ecg signal quality')
        pass

class SimpleImuDataHandler:
    def handle_imu_acc_pkg(self,dat):
        #print('get imu acc')
        pass

    def handle_imu_gyro_pkg(self,dat):
        #print('get imu gyro')
        pass

    def handle_imu_mag_pkg(self,dat):
        #print('get imu mag')
        pass

    def handle_imu_quaternion_pkg(self,dat):
        #print('get imu quaternion')
        pass

class Protocol:
    PKG_EXCAPE_BYTE                 =0x87
    PKG_FRAME_START_BYTE            =0xa0
    PKG_FRAME_FINISH_BYTE           =0xf0

    MSG_TYPE_DUAL_MIC               =0xD0
    MSG_TYPE_MIC                    =0xDA
    MSG_TYPE_QUAT                   =0xDB
    MSG_TYPE_ACC                    =0xDC
    MSG_TYPE_GYRO                   =0xDD
    MSG_TYPE_MAG                    =0xDE
    MSG_TYPE_ECG_HEART_RATE         =0xE1
    MSG_TYPE_ECG_SINGAL_QUARITY     =0xE2
    MSG_TYPE_ECG_RAW_DATA           =0xE3

    MSG_TYPE_SYS_INFO               =0xF0

    CMD_TYPE_CHANGE_PW              =0xC0
    CMD_TYPE_CHANGE_GAIN            =0xC1
    CMD_TYPE_SENSOR_CONTROL         =0xC2

    CMD_TYPE_TX_POWER                =0xCE
    CMD_TYPE_ECHO                    =0xCF

    def __init__(self,drv,name):
        self.driver=drv

        if(type(drv) is FD.Driver):
            self.read_file_mode=True
        else:
            self.read_file_mode=False

        self.thd=None
        self.thd_run_flag=None

        self.tx_queue=None
        self.rx_queue=None
        self.cmd_resp_queue=queue.Queue()

        self.prase_state=0
        self.tmp_ba=None
        self.tmp_ba_get_header=False

        self.enable_auto_prase_pkg()
        self.auto_prase_thd=None

        self.set_sys_info_handler(SimpleSysInfoHandler())
        self.set_mic_data_handler(SimpleMicDataHandler())
        self.set_ecg_data_handler(SimpleEcgDataHandler())
        self.set_imu_data_handler(SimpleImuDataHandler())

        self.pre_statistic_ts=0
        self.data_spd=0
        self.interval_data_amount=0

        '''
        static uint8_t protocol_iv_key[16] = {'S', 'i', 'r', 'i', 'u', 'X', 'e', 'n', 
                                            's', 'e', '2', '1', '0', '0', 'F', 'w'};
        '''
        self.key='SiriuXense2100Fw'.encode('ASCII')
        self.iv= 'akWLytV$N-_X:2zK'.encode('ASCII')
        self.cipher = Cipher(algorithms.AES(self.key), modes.CBC(self.iv),backend=default_backend())

        self.q_mic=queue.Queue()
        self.mic_package_queue=queue.Queue()
        self.name = name

    def __encrypt_content(self,pkg):
        encryptor  = self.cipher.encryptor()
        res=encryptor.update(pkg) + encryptor .finalize()
        return res

    def __decrypt_content(self,pkg):
        decryptor = self.cipher.decryptor()
        res=decryptor.update(pkg) + decryptor.finalize()
        return res

    def __estimate_io_spd(self,bc):
        self.interval_data_amount+=bc

        if(self.pre_statistic_ts==0):
            self.pre_statistic_ts=time.time()
            return

        curr_ts=time.time()
        diff_ts=curr_ts-self.pre_statistic_ts
        if(diff_ts>3):
            self.data_spd=self.interval_data_amount/diff_ts
            print("{:.3f} kBps".format(self.data_spd/1000))
            self.interval_data_amount=0
            self.pre_statistic_ts=curr_ts

    def set_sys_info_handler(self,h):
        self.sys_info_handler=h

    def set_mic_data_handler(self,h):
        self.mic_data_handler=h

    def set_ecg_data_handler(self,h):
        self.ecg_data_handler=h

    def set_imu_data_handler(self,h):
        self.imu_data_handler=h

    def wait_cmd_resp(self,cmd_type,timeout):
        bg_ts=time.time()

        while(True):
            if(time.time()-bg_ts>3):
                return None

            if(self.cmd_resp_queue.empty()):
                time.sleep(0.01)
                continue
            
            pkg=self.cmd_resp_queue.get_nowait()
            if(pkg[0] == cmd_type):
                return pkg
            else:
                #print(pkg)
                continue

    def set_new_password(self,iv,key):
        if(len(iv) != 16 or len(key) !=16):
            return False

        ba=bytearray()
        ba.append(self.CMD_TYPE_CHANGE_PW)
        ba.extend(iv)
        ba.extend(key)

        self.write(ba)

        bg_ts=time.time()
        while(True):
            
            curr_ts=time.time()
            if(curr_ts-bg_ts>3.0):
                return False

            pkg=self.wait_cmd_resp(self.CMD_TYPE_CHANGE_PW,3)
            if(pkg is not None):
                #print(pkg)
                if(len(pkg[2])!=1):
                    continue

                if(pkg[2][0]==0):#success,change pw
                    print('swap pw')
                    self.key=key
                    self.iv= iv
                    self.cipher = Cipher(algorithms.AES(self.key), modes.CBC(self.iv),backend=default_backend())
                    return True

    def set_mic_gain(self,ch1,ch2,ch3,ch4):
        ba=bytearray()
        ba.append(self.CMD_TYPE_CHANGE_GAIN)
        ba.append(ch1)
        ba.append(ch2)
        ba.append(ch3)
        ba.append(ch4)

        self.write(ba)

        pkg=self.wait_cmd_resp(self.CMD_TYPE_CHANGE_GAIN,3)
        if(pkg is not None):
            print(pkg)

    def set_sensor_output(self,en_mic,en_acc,en_gyro,en_mag,en_quat,ecg_en):
        ba=bytearray()
        ba.append(self.CMD_TYPE_SENSOR_CONTROL)

        if(en_mic):
            ba.append(0xff)
        else:
            ba.append(0x00)

        if(en_acc):
            ba.append(0xff)
        else:
            ba.append(0x00)

        if(en_gyro):
            ba.append(0xff)
        else:
            ba.append(0x00)

        if(en_mag):
            ba.append(0xff)
        else:
            ba.append(0x00)

        if(en_quat):
            ba.append(0xff)
        else:
            ba.append(0x00)

        if(ecg_en):
            ba.append(0xff)
        else:
            ba.append(0x00)

            

        self.write(ba)

        pkg=self.wait_cmd_resp(self.CMD_TYPE_SENSOR_CONTROL,3)
        if(pkg is not None):
            print(pkg)
            
    def test_echo(self):
        ba=bytearray()
        ba.append(self.CMD_TYPE_ECHO)
        ba.extend('ECHO'.encode('ASCII'))
        self.write(ba)
        pkg=self.wait_cmd_resp(self.CMD_TYPE_ECHO,3)
        if(pkg is not None):
            print(pkg)

    def set_tx_power(self,pwr):
        ba=bytearray()
        ba.append(self.CMD_TYPE_TX_POWER)
        ba.extend(bytes([pwr & 0x00ff]))
        self.write(ba)
        pkg=self.wait_cmd_resp(self.CMD_TYPE_TX_POWER,3)
        if(pkg is not None):
            print(pkg)

    def get_available_tx_power(self):
        return [-40,-20,-16,-12,-8,-4,0,3,4]

    def write(self,ba):
        en_pkg=self.encry_and_build_bytes_from_pkg(bytes(ba))

        encoded_pkg=bytearray()

        encoded_pkg.append(self.PKG_FRAME_START_BYTE)#usb cdc lost first 0xA0
        #https://devzone.nordicsemi.com/f/nordic-q-a/40431/52840-usb-cdc-missed-first-byte-in-rx-event

        encoded_pkg.append(self.PKG_FRAME_START_BYTE)
        self.__encode_bytes(en_pkg,encoded_pkg)
        encoded_pkg.append(self.PKG_FRAME_FINISH_BYTE)
        print(list(encoded_pkg))
        self.tx_queue.put_nowait(encoded_pkg)

    def read(self):
        if(self.rx_queue.empty()):
            return None
        return self.rx_queue.get_nowait()

    def enable_auto_prase_pkg(self):
        self.is_req_auto_prase_pkg=True

    def disable_auto_prase_pkg(self):
        self.is_req_auto_prase_pkg=False

    def encry_and_build_bytes_from_pkg(self,pkg_ba):#without header and footer
        out_ba=bytearray()
        out_ba.extend(struct.pack('<H',len(pkg_ba)))

        padder = padding.PKCS7(128).padder()
        pkg_ba=padder.update(pkg_ba)+padder.finalize()

        en_pkg_ba=self.__encrypt_content(pkg_ba)
        out_ba.extend(en_pkg_ba)

        checksum=sum(en_pkg_ba)
        checksum=(checksum & 0x00ff)

        out_ba.append(checksum)
        return out_ba

    def decry_and_prase_to_pkg(self,ba):#without header and footer
        pkg_len=len(ba)
        cxt_len=struct.unpack('<H',ba[0:2])[0]

        enc_content=ba[2:-1]
        checksum=sum(enc_content)
        checksum=(checksum & 0x00ff)
        ref_checksum=ba[pkg_len-1]

        if(self.read_file_mode):
            dec_ba=enc_content
        else:
            dec_ba=self.__decrypt_content(enc_content)
        
        if(len(dec_ba) < cxt_len):
            print('pkg len err! %x,%d,%d,%d'%(dec_ba[0],cxt_len,len(dec_ba),pkg_len))
            #print(ba.hex())
            return None

        dec_ba=dec_ba[:cxt_len]

        msg_type=dec_ba[0]
        ts_in_4us=struct.unpack('<I',dec_ba[1:5])[0]
        data=dec_ba[5:]

        
        if(msg_type==self.CMD_TYPE_ECHO):
            ts_in_4us+=1


        return (msg_type,ts_in_4us,data,ref_checksum,ref_checksum==checksum)


    def prase_to_pkg(self,ba):
        pkg_len=len(ba)
        cxt_len=struct.unpack('<H',ba[0:2])[0]

        if(pkg_len-3 != cxt_len):#2byte len,1byte checksum
            return None

        msg_type=ba[2]
        ts_in_4us=struct.unpack('<I',ba[3:7])[0]
        data=ba[7:(7+cxt_len-5)]
        checksum=sum(ba[2:-1])
        checksum=(checksum & 0x00ff)
        ref_checksum=ba[pkg_len-1]

        return (msg_type,ts_in_4us,data,ref_checksum,ref_checksum==checksum)

    def __encode_bytes(self,in_ba,out_ba):
        for b in in_ba:
            if(b==self.PKG_EXCAPE_BYTE):
                out_ba.append(0x87)
                out_ba.append(0x00)
            elif(b==self.PKG_FRAME_START_BYTE):
                out_ba.append(0x87)
                out_ba.append(0x01)
            elif(b==self.PKG_FRAME_FINISH_BYTE):
                out_ba.append(0x87)
                out_ba.append(0x02)
            else:
                out_ba.append(b)

    def __decode_bytes(self,get_esp,ba,rxq):
        for b in ba:
            if(get_esp):
                get_esp=False

                if(b==0x00):
                    self.tmp_ba.append(self.PKG_EXCAPE_BYTE)
                elif(b==0x01):
                    self.tmp_ba.append(self.PKG_FRAME_START_BYTE)
                elif(b==0x02):
                    self.tmp_ba.append(self.PKG_FRAME_FINISH_BYTE)
                else:#error
                    self.tmp_ba.clear()
                    self.tmp_ba_get_header=False
                    print('get err byte')
            else:
                if(self.tmp_ba_get_header==False):
                    if(b==self.PKG_FRAME_START_BYTE):
                        self.tmp_ba.clear()
                        self.tmp_ba_get_header=True
                        get_esp=False
                else:
                    if(b==self.PKG_EXCAPE_BYTE):
                        get_esp=True
                    elif(b==self.PKG_FRAME_START_BYTE):
                        self.tmp_ba.clear()
                        self.tmp_ba_get_header=True
                        print('get multi-header!')
                    elif(b==self.PKG_FRAME_FINISH_BYTE):
                        rxq.put_nowait(self.tmp_ba)
                        self.tmp_ba=bytearray()
                        self.tmp_ba_get_header=False
                    else:
                        self.tmp_ba.append(b)

        return get_esp

    def __decode_thd_fun(self,flag,drv,txq,rxq):
        emptyCnt = 0
        while(flag.is_set()):
            print('protocol: t0   emptyCnt=', emptyCnt)
            get_esp=False
            drv.start()

            while(flag.is_set()):
                is_busy=False

                msg=drv.read()
                if(msg is not None):
                    is_busy=True
                    emptyCnt = 0
                    self.__estimate_io_spd(len(msg))
                    get_esp=self.__decode_bytes(get_esp,msg,rxq)
                    
                if(not txq.empty()):
                    emptyCnt = 0
                    is_busy=True
                    msg=txq.get_nowait()
                    drv.write(msg)

                if(not is_busy):
                    # print('protocol not is_busy, emptyCnt=',emptyCnt)
                    emptyCnt += 1
                    if emptyCnt > 50:
                        print('protocol empty cnt=',emptyCnt)
                        self.endingTX_callback()
                    time.sleep(0.02)

            drv.stop()            

    def __prase_sys_info_pkg(self,pkg):
        ba=pkg[2]
        data_len=len(ba)
        if(data_len != 14 and data_len!=13 and data_len!=18):
            return None

        ts=pkg[1]
        fw_ver=ba[1]<<8 | ba[0]
        hw_ver=ba[3]<<8 | ba[2]
        battery_level=ba[4]
        temperature=ba[6]<<8 | ba[5]
        temperature=temperature/4

        ble_addr=ba[7:13]

        has_ext_pwr=None
        imu_tmp=None
        bat_vol=None

        if(data_len==14):
            has_ext_pwr=ba[13]>0
        elif(data_len==18):
            has_ext_pwr=ba[13]>0
            bat_vol=ba[15]<<8 | ba[14]
            imu_tmp=ba[17]<<8 | ba[16]

            bat_vol=bat_vol/1000.0
            imu_tmp=imu_tmp/100.0

        return (ts,fw_ver,hw_ver,battery_level,temperature,ble_addr,has_ext_pwr,bat_vol,imu_tmp)

    def __prase_dual_mic_pkg(self,pkg):
        ba=pkg[2]
        len_ba=len(ba)
        batch_cnt=int(len_ba/4)

        mic0=[]
        mic1=[]

        offset=0
        for _ in range(batch_cnt):
            val=struct.unpack('<hh',ba[offset:(offset+4)])
            offset+=4

            mic0.append(val[0])
            mic1.append(val[1])

        ts=pkg[1]

        return (ts,mic0,mic1)

    def __prase_mic_pkg(self,pkg):
        ba=pkg[2]
        len_ba=len(ba)
        batch_cnt=int(len_ba/8)

        mic0=[]
        mic1=[]
        mic2=[]
        mic3=[]

        offset=0
        for _ in range(batch_cnt):
            val=struct.unpack('<hhhh',ba[offset:(offset+8)])
            offset+=8

            mic0.append(val[0])
            mic1.append(val[1])
            mic2.append(val[2])
            mic3.append(val[3])

        ts=pkg[1]
        return (ts,mic0,mic1,mic2,mic3)

    def __prase_ecg_hr_pkg(self,pkg):
        ba=pkg[2]
        if(len(ba) != 1):
            return None

        ts=pkg[1]
        hr=ba[0]
        return (ts,hr)

    def __prase_ecg_sq_pkg(self,pkg):
        ba=pkg[2]
        if(len(ba) != 1):
            return None

        ts=pkg[1]
        hr=ba[0]
        return (ts,hr)

    def __prase_ecg_raw_pkg(self, pkg):
        ba=pkg[2]
        len_ba=len(ba)
        batch_cnt=int(len_ba/2)

        ts=pkg[1]
        val_list=[]

        offset=0
        for _ in range(batch_cnt):
            val=struct.unpack('<h',ba[offset:(offset+2)])
            offset+=2
            val_list.append(val[0])

        return (ts,val_list)

    def __prase_imu_3float_pkg(self, pkg):
        ba=pkg[2]
        len_ba=len(ba)
        batch_cnt=int(len_ba/12)

        ts=pkg[1]
        ch=ba[0]
        val_list=[]

        offset=1
        for _ in range(batch_cnt):
            val=struct.unpack('<fff',ba[offset:(offset+12)])
            offset+=12
            val_list.append(val)

        return (ts,ch,val_list)

    def __prase_imu_4float_pkg(self, pkg):
        ba=pkg[2]
        len_ba=len(ba)
        batch_cnt=int((len_ba-1)/16)

        ts=pkg[1]
        ch=ba[0]
        val_list=[]

        offset=1
        for _ in range(batch_cnt):
            val=struct.unpack('<ffff',ba[offset:(offset+16)])
            offset+=16
            val_list.append(val)

        return (ts,ch,val_list)

    def __auto_prase_thd_fun(self,flag,rxq,crq):
        while(flag.is_set()):
            if(self.is_req_auto_prase_pkg==False):
                time.sleep(0.5)
                continue

            if(rxq.empty()):
                time.sleep(0.01)
                continue

            msg=rxq.get_nowait()
            try:
                pkg=self.decry_and_prase_to_pkg(msg)
            except:
                continue
            
            if(pkg is None):
                continue

            if(pkg[4]==False):
                print('check sum fail!')
                continue
            
            pkg_type=pkg[0]

            if(pkg_type==self.MSG_TYPE_SYS_INFO and self.sys_info_handler is not None):
                pkg=self.__prase_sys_info_pkg(pkg)
                if(pkg is not None):
                    self.sys_info_handler.handle_sys_info_pkg(pkg)
            
            elif(pkg_type==self.MSG_TYPE_DUAL_MIC and self.mic_data_handler is not None):
                pkg=self.__prase_dual_mic_pkg(pkg)
                if(pkg is not None):
                    self.mic_data_handler.handle_dual_mic_pkg(pkg)

            elif(pkg_type==self.MSG_TYPE_MIC and self.mic_data_handler is not None):
                pkg=self.__prase_mic_pkg(pkg)
                if(pkg is not None):
                    self.mic_data_handler.handle_mic_pkg(pkg)

            elif(pkg_type==self.MSG_TYPE_QUAT and self.imu_data_handler is not None):
                pkg=self.__prase_imu_4float_pkg(pkg)
                if(pkg is not None):
                    self.imu_data_handler.handle_imu_quaternion_pkg(pkg)
            elif(pkg_type==self.MSG_TYPE_ACC and self.imu_data_handler is not None):
                pkg=self.__prase_imu_3float_pkg(pkg)
                if(pkg is not None):
                    self.imu_data_handler.handle_imu_acc_pkg(pkg)
            elif(pkg_type==self.MSG_TYPE_GYRO and self.imu_data_handler is not None):
                pkg=self.__prase_imu_3float_pkg(pkg)
                if(pkg is not None):
                    self.imu_data_handler.handle_imu_gyro_pkg(pkg)
            elif(pkg_type==self.MSG_TYPE_MAG and self.imu_data_handler is not None):
                pkg=self.__prase_imu_3float_pkg(pkg)
                if(pkg is not None):
                    self.imu_data_handler.handle_imu_mag_pkg(pkg)

            elif(pkg_type==self.MSG_TYPE_ECG_HEART_RATE and self.ecg_data_handler is not None):
                pkg=self.__prase_ecg_hr_pkg(pkg)
                if(pkg is not None):
                    self.ecg_data_handler.handle_ecg_heart_rate_pkg(pkg)
            elif(pkg_type==self.MSG_TYPE_ECG_SINGAL_QUARITY and self.ecg_data_handler is not None):
                pkg=self.__prase_ecg_sq_pkg(pkg)
                if(pkg is not None):
                    self.ecg_data_handler.handle_ecg_signal_quality_pkg(pkg)
            elif(pkg_type==self.MSG_TYPE_ECG_RAW_DATA and self.ecg_data_handler is not None):
                pkg=self.__prase_ecg_raw_pkg(pkg)
                if(pkg is not None):
                    self.ecg_data_handler.handle_ecg_raw_pkg(pkg)
            else:
                if(crq.qsize()<100):
                    crq.put_nowait(pkg)
                print(pkg)

    def get_mic_data_q(self):
        return self.q_mic

    def start(self):
        self.stop()

        self.thd_run_flag=threading.Event()
        self.thd_run_flag.set()

        self.tmp_ba=bytearray()
        
        self.tx_queue=queue.Queue()
        self.rx_queue=queue.Queue()
        self.cmd_resp_queue=queue.Queue()

        self.thd=threading.Thread(target=self.__decode_thd_fun,
                                    args =(self.thd_run_flag,self.driver,self.tx_queue,self.rx_queue,),
                                    name='protocol_decode_thd_fun')
        # self.thd.setDaemon(True)
        self.thd.start()

        self.auto_prase_thd=threading.Thread(target=self.__auto_prase_thd_fun,
                                                args=(self.thd_run_flag,self.rx_queue,self.cmd_resp_queue,),
                                                name='protocol_auto_prase_thd')
        # self.auto_prase_thd.setDaemon(True)
        self.auto_prase_thd.start()

    def stop(self):
        if(self.thd_run_flag is not None):
            self.thd_run_flag.clear()
            
            if(self.thd is not None):
                try:
                    self.thd.join(2.0)
                except:
                    pass

            if(self.auto_prase_thd is not None):
                try:
                    self.auto_prase_thd.join(2.0)
                except:
                    pass

        self.thd_run_flag=None
        self.thd=None
        self.auto_prase_thd=None

    def set_endingTX_callback(self, cb):
        self.endingTX_callback = cb

if __name__ == "__main__":
    #drv = SD.Driver('COM4')
    #drv = FD.Driver('./android_test_file/D2_6A_EF_C4_5E_0D/1614135882794.sx')
    #drv=BD.Driver("E6:78:A3:D6:30:D6")
    #drv = BD.Driver("fc:59:4c:e6:a8:b6")
    drv = BD.Driver("D2:FB:A3:78:07:70")
    

    protocal=Protocol(drv)
    protocal.start()
    protocal.set_mic_gain(0,0,0,0)

    atp=protocal.get_available_tx_power()
    tp_idx=0

    bg_ts=time.time()
    while(True):
        curr_ts=time.time()
        if(curr_ts-bg_ts>100):
            break
        time.sleep(1)
        #protocal.set_mic_gain(0,0,0,0)
        protocal.set_tx_power(atp[tp_idx])
        tp_idx+=1
        if(tp_idx>=len(atp)):
            tp_idx=0

        '''
        msg=protocal.read()
        if(msg is not None):
            pkg=protocal.prase_to_pkg(msg)
            print(pkg)
        '''
    protocal.stop()