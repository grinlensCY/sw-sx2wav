import os, sys

# dirname = os.path.dirname(PySide2.__file__)
# plugin_path = os.path.join(dirname, 'plugins', 'platforms')
# os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path

import threading
import time,json,csv
import numpy as np
from scipy import signal


import queue
from enum import Enum


class Detector:
    def __init__(self, tsHz, micsr, audioPkglen):
        self.tsHz = tsHz
        self.micsr = micsr
        self.audioPkglen = audioPkglen
        self.flag_runAttached = threading.Event()
        # self.flag_tempAttached = threading.Event()
        # self.flag_wellattached = threading.Event()
        print(f"Detector: tsHz={tsHz}  micsr={micsr}")
        
    
    def set_qMicAttach(self,q):
        self.qMicAttach2 = q

    def set_qAccAttach(self,q):
        self.qAccAttach = q

    def set_qTempAttach(self,q):
        self.qTempAttach = q

    def set_flag_tempAttached(self,f):
        self.flag_tempAttached = f

    def set_flag_wellattached(self,f):
        self.flag_wellattached = f

    def myprint(self,msg):
        print(f'\nDetector:{msg}\n')

    def proc_detect_attachment2(self,thd_calc_flag,flag_tempAttached,keepawake=False,keepimuawake=True,mustisHeld=False):
        '''
        keepawake: keep all senser awake; only for debug
        keepimuawake: keep imu awake; only for debug
        mustisHeld: isHeld is a must for isAttached
        '''
        # while (not self.flag_mic_sr_checked.wait(0.2) or not self.flag_imu_sr_checked.wait(0.2)):
        #     pass
        # if not flag.is_set():
        #     print(f'\nquit proc_detect_attachment because flag_mic_sr_checked?{self.flag_mic_sr_checked.is_set()}  '
        #             f'flag_imu_sr_checked?{self.flag_imu_sr_checked.is_set()}  '
        #             f'and flag?{flag.is_set()}')
        #     return
        # self.flag_micData_got.wait(10)
        # self.flag_imuData_got.wait(10)

        print('\nstart proc_detect_attachment2')
        # self.flag_runAttached.set()
        # ===== for report
        # t0 = time.perf_counter()
        # === define dstfn and check if saved data exists
        # loadcsv = bool(self.config['attach']['loadcsv'])

        if keepawake:
            keepimuawake = True

        # if keepimuawake:
        #     str_condition = f"_keepawake" if keepawake else '_micsleep'
        # else:
        #     str_condition = f"_keepawake" if keepawake else '_sleep'
        # str_condition += f"_mustisHeld" if mustisHeld else '_HeldOrHeating'
        # dstfn = f"{self.prefix_dstdir_time}Attach{str_condition}.csv"
        # dstfnMic = f"{self.prefix_dstdir_time}micAttach{str_condition}.csv"
        # dstfnAcc = f"{self.prefix_dstdir_time}accAttach{str_condition}.csv"
        # dstfnTemp = f"{self.prefix_dstdir_time}tempAttach{str_condition}.csv"
        # dstfnlog = f"{self.prefix_dstdir_time}Attach{str_condition}.log"
        # print('', file=open(dstfnlog,'w',newline=''))
        # print('proc_detect_attachment: dstfn=',dstfn,os.path.basename(dstfnMic),os.path.basename(dstfnAcc),os.path.basename(dstfnTemp))
        # loadcsv &= os.path.exists(dstfn)
        # loadcsv &= os.path.exists(dstfnAcc)
        # loadcsv &= os.path.exists(dstfnTemp)
        # loadcsv &= os.path.exists(dstfnMic)

        # emptyCnt = 0
        # if loadcsv:
        #     emptyCnt = self.proc_waitq_time
        #     tsMx = None
        #     print('\nproc_detect_attachment: load csv data only!')
        
        self.myprint(f'start proc_detect_attachment {time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())}')

        isSleep = True
        isHeld = False
        isAttached = False
        isWellAttached = False
        # isTs0Synced = False

        # === sleep
        sleepCnt = 0
        sleepDuration_sec = 5
        sleepDuration = sleepDuration_sec*self.tsHz
        tsPre_sleep = None
        # # = for report only
        # ts0Sleep = None
        # tsSleep = 0

        # === acc
        accPV_shake_LL = 0.08
        hasShake = False
        hasShakeCnt = 0
        pkglenAcc = 20
        accuNum = 5
        seglenAcc = pkglenAcc*accuNum   # one Acc pkg_duration*accNum = 20/104*5 = 0.95 sec
        hasShake_th = 3     # seglenAcc*hasShake_th = 0.95*3 => similar to holding patch for more than 2.8sec 
        hasShake_UL = 10    # 0.95*10 = 9.5sec (an additional delay to keep isHeld status)
        # = reset
        segdatAcc = np.zeros((3,seglenAcc))
        idxSegAcc = 0
        last2mxAcc = np.ones((3,2))*-4  # calculate pv of 2 seglenAcc --> 1.9sec
        last2miAcc = np.ones((3,2))*4
        idxLast2Acc = 0
        byHolding = False
        # # = for report only
        # headerAcc = ['ts', 'ax0_pv', 'ax1_pv', 'ax2_pv', 'hasShake', 'hasShakeCnt', 'byHolding', 'isHeld']
        # resAcc = np.array([0.0, 0.0, 0.0, 0.0, False, 0, False, False],dtype=object)
        # final_resAcc = []
        ts0Acc = None
        # tsAcc = 0
        # pretsAcc = None
        # intervalAccTs = 20/self.datainfo['acc']['sr']*self.tsHz
        # # stepAccTs_UL = intervalAccTs * 1.5

        # === temperature
        # = calcluate slope every around 5sec
        # = hasHeat lasts for 30sec (one step long(10sec) drop is acceptable  )
        tSlope_LL = np.array([-0.01, 0.01, 0.02, -0.02])/self.tsHz   # [是否為cooling, 是否為heating, 是否為明顯heating, 是否為明顯cooling] #[-0.009, 0.01, 0.015]
        temp_LL = 31
        temp_adap_LL = temp_LL
        hasHeatCnt_UL_sec = 52
        hasHeatCnt_UL = None    # 類似 維持 tempAttached 40sec (52是因為還要考慮 hasHeatCnt_th_sec), 如果溫度數據間隔約5.5sec，這數值 = 10
        hasHeatCnt_th_sec = 12
        hasHeatCnt_th = -1     # 類似 累績10sec的概念, 如果溫度數據間隔約5.5sec，這數值 = 2
        stepTemp = None     # 接近5sec的概念, 如果溫度數據間隔5.5sec，這數值 = 1
        # = reset
        # intervalTempTs = None
        pretsTemp = None
        tsPre_temp = None
        tempPre = None
        hasHeatCnt = 0
        tempAttached = False
        tStep_temp_th = 5*self.tsHz
        cntTemp = 0
        byHeating = False
        byHeatingCnt = 0
        risingTemp_score = 0
        risingTemp_t0 = 0
        risingTemp_MxWaitingTicks = 250*self.tsHz
        temp_adap_LL_tmp = 0
        # # = for report only
        # headerTemp = ['ts', 'imuT(degC)','sysT(degC)','slope','hasHeat','hasheatCnt','charging','tempAttached',
        #                 'byHeating','isAttached','isSleep','byHeatingCnt']
        ts0Temp = None
        # tsTemp = 0
        # final_resTemp = []

        # === mic
        p_25_LL = 4e-2      # power threshold of 25Hz low-pass signal
        micsr = self.micsr
        zi_25lp = None
        zi_40_60_bp = None
        prolen = int(micsr*3)
        _,b_25lp,a_25lp,_ = self.bwfilter(sr=micsr,
                                            f_cut=[25],filtype='lowpass',job='micAttach')
        _,b_40_60_bp,a_40_60_bp,_ = self.bwfilter(sr=micsr,
                                                    f_cut=[40,60],filtype='bandpass',job='micAttach')
        # = reset
        p_25 = 0
        p_40_60 = 0
        idxMic = 0
        has_snd_cnt = 0
        micAttached = False
        # # = for report only
        # headerMic = ['tNow','p_25','p_40_60','p25>th','p25>p40_60','has_snd_cnt','micAttached','isWellAttached']
        ts0Mic = None
        # tsMic = 0
        # final_resMic = []

        # === attach
        # # = for report only
        # header = ['tsSleep', 'isSleep', 'tsAcc', 'isHeld', 'tsTemp', 'isAttached', 'tsMic', 'isWellAttached']
        # final_res = []

        # === for debug
        toffset = 0
        toffset_temp = 0
        # tsList = []
        emptyCnt = 0

        while thd_calc_flag.is_set(): #and emptyCnt < self.proc_waitq_time:
            if self.qMicAttach2.empty() and self.qAccAttach.empty() and self.qTempAttach.empty():
                emptyCnt += 1
                if emptyCnt > 10:
                    print(f'\ndetect_attach empty > 200 => break\n')
                    break
                else:
                    # print('proc_detect_attachment: waiting for qXXXAttach for',emptyCnt,time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime()))
                    time.sleep(0.5)
                    continue
            emptyCnt = 0
            # updatedAcc = False
            # updatedTemp = False
            # updatedMic = False
            # hasAwoken = False
            gotTempDat = False
            heatmsg = ""
            movemsg = ""

            if not self.qAccAttach.empty():
                tsO,tmp = self.qAccAttach.get_nowait()  # 20(pkg len) x 3, ts is only for debug
                # tsList.append(tsO)
                if ts0Acc is None:
                    print('just get ts0Acc')
                    ts0Acc = tsO
                    # ts0Sleep = tsO
                    pretsAcc = 0
                ts = tsO + toffset - ts0Acc
                # if tsO < ts0Acc or ts < pretsAcc or ts < 0:   # ts was reset
                #     msg =  f'acc ts was reset, tsO < ts0Acc?{tsO < ts0Acc} ts < pretsAcc?{ts < pretsAcc} ts < 0?{ts < 0} tsO={tsO} ts={ts:.0f}={ts/self.tsHz} pretsAcc={pretsAcc:.0f} toffset={toffset:.0f} ts0Acc={ts0Acc}\n'
                #     ts0Acc = tsO
                #     ts0Sleep = tsO
                #     ts0Mic = tsO
                #     toffset = pretsAcc + intervalAccTs
                #     ts = tsO + toffset - ts0Acc
                #     msg += f'       updating   tsO={tsO} ts={ts:.0f}={ts/self.tsHz} toffset={toffset:.0f} ts0Acc={ts0Acc} {time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())}'
                #     print(msg, file=open(dstfnlog,'a',newline=''))
                # if not keepawake and not keepimuawake and isSleep:     # check if time to wake up(mcu應該是在外圈來執行?)
                #     if tsPre_sleep is None:
                #         tsPre_sleep = ts
                #     else:
                #         isSleep = ts - tsPre_sleep < sleepDuration
                #         hasAwoken |= not isSleep
                # pretsAcc = ts
                if keepawake or keepimuawake or not isSleep:
                    dat = np.array(tmp)
                    for ax in range(3):
                        segdatAcc[ax][idxSegAcc*pkglenAcc:(idxSegAcc+1)*pkglenAcc] = dat[:,ax]
                    idxSegAcc += 1
                    if idxSegAcc >= accuNum:
                        idxSegAcc = 0
                        hasShake = False
                        for ax in range(3):
                            last2mxAcc[ax][idxLast2Acc] = np.max(segdatAcc[ax])
                            last2miAcc[ax][idxLast2Acc] = np.min(segdatAcc[ax])
                            pv = np.max(last2mxAcc[ax]) - np.min(last2miAcc[ax])    # calculate PV of overlapped zones
                            hasShake = hasShake or pv > accPV_shake_LL
                            # resAcc[ax+1] = pv
                        idxLast2Acc = 1 if not idxLast2Acc else 0                   
                        if hasShake and hasShakeCnt < hasShake_UL:
                            hasShakeCnt += 1
                        elif not hasShake and hasShakeCnt > 0:
                            hasShakeCnt -= 1
                        isHeld = hasShakeCnt >= hasShake_th
                        byHolding |= isHeld     #  有透過拿取動作啟動過了，然後觀察是否有接著tempAttached狀態 ，而不一定需要與溫度貼附狀態有重疊
                        isSleep = not byHolding and not byHeating and not tempAttached
                        # if isSleep:
                        #     # tsPre_sleep = ts  # update tsPre_sleep after tempAttached
                        #     # for report only
                        #     tsSleep = (ts - ts0Sleep)/self.tsHz
                        
                        # # = for report only
                        # tsSleep = tsAcc = ts/self.tsHz
                        # resAcc[0] = tsAcc
                        # resAcc[4] = hasShake
                        # resAcc[5] = hasShakeCnt
                        # resAcc[6] = byHolding
                        # resAcc[7] = isHeld
                        # final_resAcc = np.vstack((final_resAcc,resAcc)) if len(final_resAcc) else resAcc.copy()
                        # updatedAcc = True
                    movemsg += f"hasShake={hasShake}  hasShakeCnt={hasShakeCnt}(hasShake_UL={hasShake_UL})  isHeld={isHeld}\n"
                else:   # in sleep --> reset ACC
                    # self.qAccAttach.queue.clear()
                    segdatAcc = np.zeros((3,seglenAcc))
                    idxSegAcc = 0
                    last2mxAcc = np.ones((3,2))*-4
                    last2miAcc = np.ones((3,2))*4
                    idxLast2Acc = 0
                    hasShake = False
                    isHeld = False
                    hasShakeCnt = 0
                    byHolding = False
                    # # for report only
                    # tsSleep = ts/self.tsHz
                
            if not self.qTempAttach.empty():
                gotTempDat = True
                tsO,sysT,temp,charging = self.qTempAttach.get_nowait()
                if ts0Temp is None: # = for report only
                    ts0Temp = tsO
                    # ts0Sleep = tsO
                    pretsTemp = 0
                    pretsTemp2 = 0
                # elif intervalTempTs is None and pretsTemp2 != pretsTemp: # = for report only
                #     intervalTempTs = pretsTemp - pretsTemp2

                ts = tsO + toffset_temp - ts0Temp
                # if tsO < ts0Temp or ts < pretsTemp or ts < 0:   # ts was reset
                #     msg =  f'temp ts was reset, tsO < ts0Temp?{tsO < ts0Temp} ts < pretsTemp?{ts < pretsTemp} ts < 0?{ts < 0}  tsO={tsO} ts={ts:.0f}={ts/self.tsHz} ts0Temp={ts0Temp} pretsTemp={pretsTemp:.0f} toffset_temp={toffset_temp} ts0Temp={ts0Temp}\n'
                #     ts0Sleep = tsO
                #     ts0Mic = tsO
                #     ts0Temp = tsO
                #     toffset_temp = pretsTemp + intervalTempTs if intervalTempTs is not None else pretsTemp
                #     ts = tsO + toffset_temp - ts0Temp
                #     msg += f'       updating    tsO={tsO} ts={ts:.0f}={ts/self.tsHz} toffset_temp={toffset_temp} ts0Temp={ts0Temp} {time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())}'
                #     print(msg, file=open(dstfnlog,'a',newline=''))

                pretsTemp2 = pretsTemp
                pretsTemp = ts 
                if not keepawake and not keepimuawake and isSleep:     # check if time to wake up(mcu應該是在外圈來執行?)
                    if tsPre_sleep is None:
                        tsPre_sleep = ts
                    else:
                        isSleep = ts - tsPre_sleep < sleepDuration
                        # hasAwoken |= not isSleep
                isSleep |= charging

                # == reset temp_adap_LL
                # = temp_adap_LL非預設值 且 (非貼附 or 睡眠中(充電中也算) or (非wellAttached 且 溫度 與 temp_adap_LLt差距小於0.5度))
                if temp_adap_LL != temp_LL and (not isAttached or isSleep or (not isWellAttached and temp - 0.5 < temp_adap_LL)):
                    # 充電中 或 (以每5.5秒得一次資料來說)大約連續10分鐘的可能閒置狀態 ==>，就可以reset temp_adap_LL
                    if not charging and sleepCnt < 110:
                        sleepCnt += 1
                    else:
                        msg = (f"\n\ttemp_{temp:.1f}  temp_adap_LL_{temp_adap_LL:.1f}  ")
                        if charging or temp - 0.5 < temp_adap_LL: # 冷卻很久了(多個保險) 或 充電
                            temp_adap_LL = temp_LL
                            temp_adap_LL_tmp = 0
                            sleepCnt = 0
                            risingTemp_score = 0
                            print(f"{msg} --> reset temp_adap_LL and temp_adap_LL_tmp")
                else:
                    sleepCnt = 0

                if not charging and (keepawake or keepimuawake or not isSleep) and hasHeatCnt_th < 7:
                    if tsPre_temp is None:
                        tsPre_temp = ts
                        tempPre = temp
                    if stepTemp is None:    # to calc stepTemp/hasHeatCnt_th/hasHeatCnt_UL
                        tDiff = ts - tsPre_temp
                        # print(f"before: stepTemp={stepTemp}  {cntTemp=}  tDiff={tDiff/self.tsHz:.2f} tStep_temp_th={tStep_temp_th/self.tsHz:.2f} hasHeatCnt_th={hasHeatCnt_th}  hasHeatCnt_UL={hasHeatCnt_UL}")
                        if cntTemp and tDiff >= tStep_temp_th:    # cntTemp非0(才有意義，也避免hasHeatCnt_th無限大) + tDiff >= 5sec
                            stepTemp = cntTemp
                            tDiff_sec = tDiff/self.tsHz/cntTemp
                            hasHeatCnt_th = np.floor(hasHeatCnt_th_sec/tDiff_sec)
                            hasHeatCnt_UL = round(hasHeatCnt_UL_sec/tDiff_sec)
                            # print(f"update stepTemp={stepTemp}  hasHeatCnt_th={hasHeatCnt_th}  hasHeatCnt_UL={hasHeatCnt_UL}  {hasHeatCnt_th_sec=}  {tDiff_sec=}")
                    elif cntTemp and not cntTemp%stepTemp:
                        temp_diff = temp-tempPre
                        ts_diff = ts-tsPre_temp
                        # print(f"ts_diff={ts}-{tsPre_temp}={ts_diff/self.tsHz:.2f}")
                        slope = temp_diff/ts_diff
                        if temp_adap_LL_tmp:
                            risingTemp_score += temp-tempPre
                            risingTemp_t0 = ts if not risingTemp_t0 else risingTemp_t0
                            print(ts/self.tsHz,'ts_diff=',(ts-risingTemp_t0)/self.tsHz,'risingTemp_score=',risingTemp_score)
                        tsPre_temp = ts
                        tempPre = temp
                        
                        c10 = temp >= temp_adap_LL # high temperature 
                        c11 = slope > tSlope_LL[0] # not in cooling process
                        c2 = slope >= tSlope_LL[1] # heating process
                        if c2: # 加熱中
                            byHeatingCnt += 1
                            # 累積14次加熱之後(約80sec)(可能是25-->28degC)，且持續加熱中，溫度也低於temp_adap_LL
                            # (避免環境偏冷的情況，貼附之後，過了急速升溫期卻還沒到高溫門檻)
                            if (byHeatingCnt == 14 or (slope > tSlope_LL[2] and byHeatingCnt == 10)) and temp < temp_adap_LL:
                                temp_adap_LL = temp     # 設定當下的溫度為 溫度低標
                                temp_adap_LL_tmp = 0
                                print(f"\n\tupdated temp_adap_LL={temp_adap_LL:.3f}\n")
                            # 持續加熱了一小段時間, 溫度也低於temp_LL, 還沒被更新(也許是短暫離開還在有點高溫的情況，所以先設定28.5為門檻)
                            elif temp > 28.5 and byHeatingCnt == 3 and temp < temp_LL and temp_adap_LL == temp_LL and temp_adap_LL_tmp == 0:
                                temp_adap_LL_tmp = temp
                                risingTemp_score = 0
                                print(f"\n\tupdated temp_adap_LL_tmp={temp_adap_LL_tmp:.3f}\n")
                        elif byHeatingCnt > 0:
                            byHeatingCnt -= 1 if c11 or byHeatingCnt == 1 else 2 # 若有明顯的降溫，就試著加速脫離byHeating
                        byHeating = byHeatingCnt > 1 and c11

                        hasHeat = (c10 and c11) or c2
                        heatmsg += f"slope={slope*self.tsHz:.3f}\n"
                        heatmsg += (f"hasheat?{hasHeat}: c10?{c10}  c11?{c11}  c2?{c2}  hasHeatCnt_UL={hasHeatCnt_UL}  hasHeatCnt_th={hasHeatCnt_th}\n")

                        if (byHeating or hasHeat) and hasHeatCnt <= hasHeatCnt_UL:
                            hasHeatCnt += 1
                        elif (not byHeating and not hasHeat) and hasHeatCnt > 0:
                            hasHeatCnt -= 1
                        if not c11 and hasHeatCnt > hasHeatCnt_th: # definitely cooling => speed up "going to not tempAttached"
                            hasHeatCnt -= 1 if slope > tSlope_LL[3] else 2

                        tempAttached = hasHeatCnt > hasHeatCnt_th   # or (isHeld and c2)
                        if byHeating or tempAttached:
                            flag_tempAttached.set()
                        else:
                            flag_tempAttached.clear()
                        # self.update_attached_callback('temp',self.flag_tempAttached.is_set())

                        # if byHeating:
                        #     byHeating = byHeatingCnt > 1 or tempAttached    # reset if not tempAttached and not in heating process
                        if byHolding:
                            byHolding = isHeld or byHeating or tempAttached    # reset if not tempAttached and not in heating process
                        # must be triggered by holding(if mustisHeld) and (heating process or high temp)
                        isAttached = (byHolding and (byHeating or tempAttached)) if mustisHeld else (byHeating or tempAttached)
                        isSleep = not byHolding and not byHeating and not tempAttached  #not isAttached and not isHeld
                        if isSleep:
                            tsPre_sleep = ts
                            # for report only
                            tsSleep = ts/self.tsHz
                        # = set temp_adap_LL = temp_adap_LL_tmp
                        if not isAttached and temp_adap_LL_tmp and temp_adap_LL == temp_LL and risingTemp_score > 1 and 0 < ts-risingTemp_t0 < risingTemp_MxWaitingTicks:
                            temp_adap_LL = temp_adap_LL_tmp
                            risingTemp_score = 0
                            temp_adap_LL_tmp = 0
                            risingTemp_t0 = 0
                            print(f"\n\tupdated temp_adap_LL={temp_adap_LL:.3f} by temp_adap_LL_tmp\n")

                        # = for report only
                        # headerTemp = ['ts', 'imuT(degC)','sysT(degC)','slope',
                        #               'hasHeat','hasheatCnt','charging','tempAttached','byHeating','isAttached','isSleep','byHeatingCnt']
                        # tsTemp = ts/self.tsHz
                        # resTemp = np.array([tsTemp,temp,sysT,slope,hasHeat,hasHeatCnt,
                        #                     charging,tempAttached,byHeating,isAttached,isSleep,byHeatingCnt],dtype=object)
                        # final_resTemp = np.vstack((final_resTemp,resTemp)) if len(final_resTemp) else resTemp.copy()
                        # updatedTemp = True
                    cntTemp += 1
                    # print(f'{cntTemp=}')
                else:   # sleep
                    # self.qTempAttach.queue.clear()    # 因為這裡都得進來讀ts，所以應該是不用這段
                    tsPre_temp = None
                    tempPre = None
                    hasHeatCnt = 0
                    byHeatingCnt = 0
                    tempAttached = False
                    cntTemp = 0
                    isAttached = False
                    byHeating = False
                    byHolding = False
                    if hasHeatCnt_th >= 7:
                        hasHeatCnt_th = -1
                        stepTemp = None
                        print('\n reset hasHeatCnt_th\n')

                    flag_tempAttached.clear()
                    # self.update_attached_callback('temp',self.flag_tempAttached.is_set())
                    # # for report only
                    # tsSleep = ts/self.tsHz

            if not self.qMicAttach2.empty(): # 為了可以進來判斷是否該起床了，否則就不用進來讀取
                tsO,snd = self.qMicAttach2.get_nowait()
                # print(f'got qMicAttach2 max={np.max(snd):.5f}  len={len(snd)}')
                # print('got qMicAttach2')
                # if not keepawake and isSleep:     # check if time to wake up(mcu也許有別的方式，而不用靠這裡的sensor?)
                #     if tsPre_sleep is None:
                #         tsPre_sleep = ts
                #     else:
                #         isSleep = ts - tsPre_sleep < sleepDuration
                #         hasAwoken |= not isSleep
                if ts0Mic is None:
                    ts0Mic = tsO
                    # ts0Sleep = tsO
                ts = tsO + toffset - ts0Mic
                if keepawake or isAttached:
                    # print(f'got qMicAttach2 + isAttached?{isAttached}  max={np.max(snd):.5f}  len={len(snd)}')
                    idxMic += self.audioPkglen
                    tmp,_,_,zi_25lp = self.bwfilter(data_in=snd,b_filt=b_25lp,a_filt=a_25lp,
                                                    zf=zi_25lp)
                    p_25 += np.power(tmp,2).sum()
                    # print("got p_25")
                    tmp,_,_,zi_40_60_bp = self.bwfilter(data_in=snd,b_filt=b_40_60_bp,a_filt=a_40_60_bp,
                                                        zf=zi_40_60_bp)
                    p_40_60 += np.power(tmp,2).sum()
                    # print("got p_40_60")
                    if idxMic >= prolen:
                        c1 = p_25 > p_25_LL
                        c2 = p_25 > p_40_60
                        if c1 and c2 and has_snd_cnt < 3:
                            has_snd_cnt += 1
                        elif (not c1 or not c2) and has_snd_cnt > -3:
                            has_snd_cnt -= 1
                        micAttached = True if has_snd_cnt > 1 else False
                        isWellAttached = isAttached and micAttached

                        if isWellAttached:
                            self.flag_wellattached.set()
                            # self.update_attached_callback('well',True)
                        else:
                            self.flag_wellattached.clear()
                            # self.update_attached_callback('well',False)

                        # if micAttached:
                        #     self.flag_micAttached.set()
                        # else:
                        #     self.flag_micAttached.clear()

                        # self.update_attached_callback('well',self.flag_wellattached.is_set())
                        # self.update_attached_callback('mic',self.flag_micAttached.is_set())

                        # # for debug only
                        # tsMic = ts/self.tsHz
                        # resMic = np.array([tsMic,p_25,p_40_60,c1,c2,has_snd_cnt,micAttached,isWellAttached],dtype=object)
                        # final_resMic = np.vstack((final_resMic,resMic)) if len(final_resMic) else resMic.copy()
                        # updatedMic = True
                        # reset
                        p_25 = 0.0
                        p_40_60 = 0.0
                        idxMic = 0
                        # print('updateMic ',resMic,final_resMic.shape)
                # elif not self.qMicAttach.empty():
                else:
                    # self.qMicAttach.queue.clear()
                    p_25 = 0.0
                    p_40_60 = 0.0
                    idxMic = 0
                    has_snd_cnt = 0
                    micAttached = False
                    isWellAttached = False
                    self.flag_wellattached.clear()
                    # self.flag_micAttached.clear()
                    # self.update_attached_callback('well',self.flag_wellattached.is_set())
            
            if gotTempDat:
                self.myprint(f"{tsO/self.tsHz:.1f}sec:{movemsg}{heatmsg}"
                    f"byHolding/Attached/micAttached/WellAttached={byHolding}/{isAttached}/{micAttached}/{isWellAttached}\n"
                    f"temp/temp_LL/temp_adap_LL/temp_adap_LL_tmp={temp:.3f}/{temp_LL:.1f}/{temp_adap_LL:.3f}/{temp_adap_LL_tmp:.1f}\n"
                    f"byHeatingCnt/hasHeatCnt/risingTemp_score/sleepCnt/has_snd_cnt={byHeatingCnt}/{hasHeatCnt}/{risingTemp_score:.1f}/{sleepCnt}/{has_snd_cnt}\n"
                    f"flag_tempAttached/flag_wellattached={flag_tempAttached.is_set()}/{self.flag_wellattached.is_set()}")
        
        self.myprint(f"end of attachement2: thd_cal_flag?{thd_calc_flag.is_set()}\n")
            
    # def reset(self):
    #     self.input = ''
    #     self.tagfn = None
    #     self.recT0 = None
    #     self.engineT0 = None
    #     # [0]timestamp,               [1]firmware ver,    [2]hardware ver,    [3]battery level(%),
    #     # [4]temperature(degreeC),    [5]ble addr,        [6]charging    ,    [7]Bat vol(mV),
    #     # [8]imu_temperature(degC)
    #     self.sysinfo = ['','','','','','','']
    #     self.strPkgSpd = ''
    #     self.cnt_stable_rr = 0
    #     self.cnt_stable_hr = 0

    #     # for ac in self.anc_ac_list:
    #     #     ac.reset()

    # def depose(self):
    #     self.stop()

        # for ac in self.anc_ac_list:
        #     ac.release()

    # def stop(self):        
    #     self.thd_ch_proc_run_flag.clear()
    #     self.thd_draw_run_flag.clear()
    #     self.thd_audio_run_flag.clear()
    #     # self.thd_calc_stop_flag.set() # 統一在後面的self.switch_thd('calc')處理，不然會被後面的 self.switch_thd('calc') 再次重啟
    #     if self.thd_rec_flag.is_set():
    #         print('\ngoing to stop recording!')
    #         self.setRec()

    #     if self.data_retriever is not None and 'wavfile' in self.data_retriever.name:
    #         print('closing thd_dumpNonSndData')
    #         for thd in self.thd_dumpNonSndData:
    #             if thd.is_alive():
    #                 thd.join(0.5)
    #                 thd = None

    #     print('--stop data_retriever')
    #     if(self.data_retriever is not None):
    #         self.data_retriever.stop()
    #         self.data_retriever=None
    #     self.bledrv = None
        
    #     print('--stop thd_ch_proc')
    #     if(self.thd_ch_proc is not None and self.thd_ch_proc.is_alive()):
    #         self.thd_ch_proc.join(0.5)
    #         self.thd_ch_proc=None
        
    #     print('--stop thd_spec')
    #     if(self.thd_spec is not None and self.thd_spec.is_alive()):
    #         self.thd_spec.join(0.5)
    #         self.thd_spec=None

    #     print('stop thd calc')
    #     self.switch_thd('calc')

    #     # print('--stop thd_hr')
    #     # if(self.thd_hr is not None and self.thd_hr.is_alive()):
    #     #     self.thd_hr.join(0.5)
    #     #     self.thd_hr=None
        
    #     # print('--stop thd_hr_ecg')
    #     # if(self.thd_hr_ecg is not None and self.thd_hr_ecg.is_alive()):
    #     #     self.thd_hr_ecg.join(0.5)
    #     #     self.thd_hr_ecg=None

    #     print('--stop thd_audio')
    #     if(self.thd_audio is not None and self.thd_audio.is_alive()):
    #         self.thd_audio.join(0.5)
    #         self.thd_audio=None
    #     print(f'\tself.thd_audio={self.thd_audio}')
    #     if self.thd_audio is not None:
    #         print(f'\tself.thd_audio.is_alive()?{self.thd_audio.is_alive()}')

    #     print('--stop thd_curv')
    #     if (self.thd_curv is not None and self.thd_curv.is_alive()):
    #         self.thd_curv.join(0.5)
    #         self.thd_curv = None

    #     # print('--stop thd_pose_activity')
    #     # if self.thd_pose_activity is not None and self.thd_pose_activity.is_alive():
    #     #     self.thd_pose_activity.join(0.5)
    #     #     self.thd_pose_activity = None

    #     # print('--stop thd_rr')
    #     # if(self.thd_rr is not None and self.thd_rr.is_alive()):
    #     #     self.thd_rr.join(0.5)
    #     #     self.thd_rr=None

    #     # print('--stop thd_attachedCheck')
    #     # if self.thd_attachedCheck is not None and self.thd_attachedCheck.is_alive():
    #     #     self.thd_attachedCheck.join(0.5)
    #     #     self.thd_attachedCheck = None

    #     print('--stop thd_attachedCheck2')
    #     if self.thd_attachedCheck2 is not None and self.thd_attachedCheck2.is_alive():
    #         self.thd_attachedCheck2.join(0.5)
    #         self.thd_attachedCheck2 = None

    #     print('--stop thd_spl')
    #     if self.thd_spl is not None and self.thd_spl.is_alive():
    #         self.thd_spl.join(0.5)
    #         self.thd_spl = None
        
    #     # print('--stop thd_bsOdd')
    #     # if self.thd_bsOdd is not None and self.thd_bsOdd.is_alive():
    #     #     self.thd_bsOdd.join(0.5)
    #     #     self.thd_bsOdd = None

    #     print('--stop audio player stream')
    #     if self.audio_player is not None and not self.audio_player.event.is_set():
    #         print('\tneed to close audio_player stream')
    #         self.audio_player.closeStream()

    #     for cp in self.ch_proc_list:
    #         cp.stop()

    #     self.reset()

    #     self.curvePainter.reset()
    #     self.trendChart.reset()

    #     print('engine stop')

    def start(self,flag):
        print(f'\nstart Detectors: flag {flag.is_set()}\n')
        # self.thd_ch_proc=threading.Thread(target=self.proc_ch,
        #                                     args=(self.thd_ch_proc_run_flag,dq,),
        #                                     name='thd_ch_proc', daemon=True)
        # self.thd_ch_proc.start()

        self.thd_attachedCheck2 = threading.Thread(target=self.proc_detect_attachment2,
                                                args=(flag,),
                                                name='thd_attachedCheck', daemon=True)
        self.thd_attachedCheck2.start()
        
    # # @QtCore.Slot()
    # def start_remain_thd(self):
    #     print('\nstart_remain_thd')
    #     # === pre-processing(such as ANC) audio data and put into queue
    #     for cp in self.ch_proc_list:
    #         cp.start()

    #     self.thd_ch_proc_run_flag= threading.Event()
    #     self.thd_ch_proc_run_flag.set()
    #     dq=self.data_retriever.get_mic_data_q()
    #     self.thd_ch_proc=threading.Thread(target=self.proc_ch,
    #                                         args=(self.thd_ch_proc_run_flag,dq,),
    #                                         name='thd_ch_proc', daemon=True)
    #     self.thd_ch_proc.start()


    #     print(f"start_remain_thd: switch_thd('calc')")
    #     self.switch_thd('calc')

    #     #check if all channel ready
    #     time.sleep(0.5)

    #     while(True):
    #         is_ready=True
    #         for cp in self.ch_proc_list:
    #             is_ready &= cp.is_ready
                
    #         if(is_ready):
    #             break
    #         else:
    #             time.sleep(0.01)

    #     # self.thd_audio_run_flag = threading.Event()
    #     # print(f"start_remain_thd: switch_thd('playback_on')")
    #     if not self.config['OQC']:
    #         self.switch_thd('playback_on')

    
    # def switch_thd(self,typ):
    #     if typ == 'calc':
    #         if self.thd_calc_stop_flag.is_set():
    #             print(f'engine switch_thd: ')
    #             for cp in self.ch_proc_list:
    #                 cp.queue_anc_res_for_out.queue.clear()
    #                 cp.queue_anc_res_for_out2.queue.clear()
    #             self.thd_calc_stop_flag.clear()


    #             # 混和感測的貼附偵測  已經可以跑
    #             if self.fwVer and not self.flag_getAttachFromFW.is_set():
    #                 self.thd_attachedCheck2 = threading.Thread(target=self.proc_detect_attachment2,
    #                                                         args=(self.thd_ch_proc_run_flag,self.thd_calc_stop_flag,),
    #                                                         name='thd_attachedCheck', daemon=True)
    #                 self.thd_attachedCheck2.start()
    #         else:
    #             print('stop all detectors, calc HR, rr, and fetal movement, pose_activity, attach2')
    #             self.thd_calc_stop_flag.set()
                
    #             if self.thd_attachedCheck2 is not None and self.thd_attachedCheck2.is_alive():
    #                 self.thd_attachedCheck2.join(0.5)
    #                 self.thd_attachedCheck2 = None


    def hhmmss(self, sec, typ=0):
        h, r = divmod(sec, 3600)
        m, s = divmod(r, 60)
        return f'{h:02.0f}:{m:02.0f}:{s:02.0f}'


    def bwfilter(self, data_in=None, sr=None, f_cut=None, N_filt=3, filtype='bandpass',
                    b_filt=None, a_filt=None, isfiltfilt=False, forback=False, iszi=True, zf=None, job=''):
        """apply butterworth filter with zero phase shift"""
        data_filtered = None
        next_zi = None
        if b_filt is None:
            nyq = sr/2
            wn = np.array(f_cut) if isinstance(f_cut,list) or isinstance(f_cut,tuple) else np.array([f_cut])
            if not wn[0] and wn[-1]>=nyq:
                print(f'engine bwfilter_{job}:  wn{wn} is not valid!')
                return data_in,[],[],[]
            if np.max(wn) >= nyq and filtype == 'bandpass':
                # wn[np.argmax(wn)] = nyq*0.99
                wn = wn[0]
                filtype = 'highpass'
            if wn.size == 2 and not wn[0]:
                wn = wn[1]
                filtype = 'lowpass'
            elif wn.size == 2 and wn[-1]>=nyq:
                wn = wn[0]
                filtype = 'highpass'
            elif (filtype != 'bandpass' and filtype != 'bandstop') and wn.size == 2:
                wn = wn[0] if filtype == 'highpass' else wn[1]
            print((f'engine bwfilter_{job}: sr{sr:.2f} wn{wn} type:{filtype} N={N_filt} '
                    f'isfiltfilt:{isfiltfilt} forback:{forback} iszi:{iszi}'))
            b_filt, a_filt = signal.butter(N_filt, wn/nyq, btype=filtype)
        if data_in is not None:
            if isfiltfilt:
                data_filtered = signal.filtfilt(b_filt, a_filt, data_in)
            elif forback:
                zi = signal.lfilter_zi(b_filt, a_filt)
                data_filtered,_ = signal.lfilter(b_filt, a_filt, data_in, zi=zi*data_in[0])
                data_filtered,_ = signal.lfilter(b_filt, a_filt, data_filtered[::-1], zi=zi*data_filtered[-1])
                data_filtered = data_filtered[::-1]
            elif not iszi:
                data_filtered = signal.lfilter(b_filt, a_filt, data_in)
            elif iszi and zf is not None:
                # print('w zf',zf)
                data_filtered,next_zi = signal.lfilter(b_filt, a_filt, data_in, zi=zf)
                # print('out zi',next_zi)
            elif iszi:
                # print('no zf',zf)
                zi = signal.lfilter_zi(b_filt, a_filt)
                data_filtered,next_zi = signal.lfilter(b_filt, a_filt, data_in, zi=zi*data_in[0])
        return data_filtered, b_filt, a_filt, next_zi



if __name__ == "__main__":
    pass