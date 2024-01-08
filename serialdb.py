import sqlite3
import sys
import os
import time

class SerialDB:
    def __init__(self,db_path):
        is_existed=os.path.exists(db_path)
        print(f'is {db_path} exists? {is_existed}')
        # path_dir = os.path.dirname(db_path)
        # if not os.path.exists(path_dir):
        #     os.makedirs(path_dir)
        if is_existed:
            self.con = sqlite3.connect(db_path)

        # if(is_existed==False):
        #     cur = self.con.cursor()

        #     #init table
        #     #會避開重複mac address
        #     cur.execute('''CREATE TABLE patch
        #                 (serial INTEGER,ts_sec INTEGER,mac TEXT, key TEXT,hw_ver INTEGER)''')

        #     #原始的處理順序，可能包含重複的序號與mac address
        #     cur.execute('''CREATE TABLE patch_raw
        #                 (serial INTEGER,ts_sec INTEGER,mac TEXT, key TEXT,hw_ver INTEGER)''')

        #     # Save (commit) the changes
        #     self.con.commit()
    
    def get_mfcts(self,sn='',ble='',isSta=False):
        cur = self.con.cursor()
        res = None
        table = 'station' if isSta else 'patch'
        print(f'get_munufacture_time: {table}  sn={sn}    ble={ble}')
        if sn:
            sql = "SELECT ts_sec FROM %s WHERE serial='%s'"%(table,sn)
            # print(f"\tsql={sql}")
            cur.execute(sql)
            res = cur.fetchone()
            
        elif ble:
            tmp = ble.split(':')
            addr = ''
            for i in range(-1,-6,-1):
                addr += tmp[i].lower()
            cur.execute("SELECT ts_sec FROM %s WHERE mac GLOB '%s*' ORDER BY ts_sec DESC LIMIT 1"%(table,addr))
            res = cur.fetchone()
        # print('look up result:',res)
        if res:
            return res
            # if not isSta:
            #     udid = res[2]
            #     key = res[3][:16]
            #     iv = res[3][16:32]
            #     return f"{udid},{key},{iv}"
            # else:
            #     return f"{res[3][:16]},{res[3][16:]}"
        else:
            # sql = "SELECT * FROM patch"
            # cur.execute(sql)
            # res = cur.fetchone()
            # print(res)
            return ""


    def get_key_qrcode(self,sn='',ble='',isSta=False):
        cur = self.con.cursor()
        res = None
        table = 'station' if isSta else 'patch'
        print(f'get_key_qrcode: {table}  sn={sn}    ble={ble}')
        if sn:
            sql = "SELECT * FROM %s WHERE serial='%s'"%(table,sn)
            # print(f"\tsql={sql}")
            cur.execute(sql)
            res = cur.fetchone()
            
        elif ble:
            tmp = ble.split(':')
            addr = ''
            if len(tmp) > 1:
                for i in range(-1,-6,-1):
                    addr += tmp[i].lower()
            else:
                for i in range(-1,-6,-1):
                    addr += (ble[i*2:(i+1)*2 if i<-1 else 12]).lower()
            cur.execute("SELECT * FROM %s WHERE mac GLOB '%s*' ORDER BY ts_sec DESC LIMIT 1"%(table,addr))
            res = cur.fetchone()
        # print('look up result:',res)
        if res:
            if not isSta:
                udid = res[2]
                key = res[3][:16]
                iv = res[3][16:32]
                return f"{udid},{key},{iv}"
            else:
                return f"{res[3][:16]},{res[3][16:]}"
        else:
            # sql = "SELECT * FROM patch"
            # cur.execute(sql)
            # res = cur.fetchone()
            # print(res)
            return ""

    def get_next_serial(self):
        cur = self.con.cursor()

        cur.execute("SELECT serial FROM patch ORDER BY serial DESC LIMIT 1")
        res = cur.fetchone()
        print('get_next_serial: last serial=',res)

        if(res is None):
            return 1
        else:
            return res[0]+1 # res = (int,)
                
    def add_serial_pair(self,serial,mac,key_info,hw_ver):
        cur = self.con.cursor()

        ts_sec=int(time.time())
        cur.execute("INSERT INTO patch_raw VALUES ('%s',%d,'%s','%s',%d)"%(serial,ts_sec,mac,key_info,hw_ver))

        cur.execute("SELECT serial FROM patch WHERE serial='%s' AND mac='%s'"%(serial,mac))
        res=cur.fetchone()
        print('serialdb add_serial_pair: last serial=',res)

        '''
        cur.execute("SELECT EXISTS(SELECT 1 FROM patch WHERE mac='%s')"%(mac))
        res=cur.fetchone()
        '''

        has_duplicate_item=False

        if(res is not None):
            print('serialdb: already exists item with the same mac: "%s" with serial: "%s"'%(mac,res[0]))
            has_duplicate_item=True
        
        if(has_duplicate_item):
            serial=res[0]
            cur.execute("UPDATE patch SET ts_sec=%d,key='%s',hw_ver=%d WHERE serial='%s'"%(ts_sec,key_info,hw_ver,serial))
        else:
            cur.execute("INSERT INTO patch VALUES ('%s',%d,'%s','%s',%d)"%(serial,ts_sec,mac,key_info,hw_ver))

        self.con.commit()

        # sql = (f"SELECT * FROM patch ORDER by ts_sec DESC")
        # cur.execute(sql)
        # res = cur.fetchall()
        # for row in res:
        #     print('serialDB:',row)

        return serial

    def del_serial_pair_by_mac(self,mac):
        cur = self.con.cursor()

        # Insert a row of data
        cur.execute("DELETE FROM patch WHERE mac='%s'"%(mac))

        # Save (commit) the changes
        self.con.commit()
        return True

    def print_items(self):
        cur = self.con.cursor()
        for row in cur.execute('SELECT * FROM patch ORDER BY ts_sec'):
            print(row)

    def get_serial_pair_by_mac(self,mac):
        cur = self.con.cursor()

        # Insert a row of data
        res=cur.execute("SELECT *  FROM patch WHERE mac='%s'"%(mac))
        info=res.fetchone()
        print(info)

        return info
        
    def depose(self):
        self.con.close()

    def get_keyQRCODE_with_blemac(self,blemac):
        ''' station's blemac'''
        tmp = blemac.replace(':',"").lower()
        mac = tmp[:-2] + f'{int(f"0x{tmp[-2:]}",16)-2:02x}'
        cur = self.con.cursor()
        res = None
        sql = "SELECT * FROM station WHERE mac='%s'"%(mac)
        cur.execute(sql)
        res = cur.fetchone()
        if res:
            keyqrcode = f"{res[3][:16]},{res[3][16:]}"
            print(f'get_keyQRCODE={f"{res[3][:16]},{res[3][16:]}"} from blemac={blemac} wifimac={mac}')
            return keyqrcode
        else:
            print(f"get no mac")
            return None

if __name__ == '__main__':
    db=SerialDB()

    serial=db.get_next_serial()
    #db.add_serial_pair(serial,'aa%08d'%(serial),'abc')
    db.add_serial_pair(serial,'aa%08d'%(serial),'abcdefghi')
    db.print_items()

    db.depose()