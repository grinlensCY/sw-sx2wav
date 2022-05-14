# 20220421

1. 移除"沒有log file時，就存檔"(因為可以藉由檔名與檔案大小推算出起訖時間
2. 修正 檔案排除名單 的功能
3. 修正 log_x_* 檔案的處理
4. 移除沒有資料的檔案
5. 支援 "FILEXXXX"的檔案(filecheck所救回的檔案，但需要先把附檔名轉成)
6. 依據ts_log.txt，把不同天的檔案分配到dayX的資料夾(包含因斷電而未記錄到的最後一個檔案)
7. 新增 "onlyChkpkgloss" 只進行mic的轉檔

# 20220330

1. config['default']: 用於比對目前的config，並提醒不同於default的
2. config['dirToloadFile']: 保留最近3筆，可以選擇
3. 其他修正

# 20220311

1. 可以轉 station所記錄在SD或透過uart傳給PC的sx檔
2. 訊息加上 已轉的檔案時間、速度
3. 在手動模式下，config['ts_loadS3']用來指定日期範圍，[20220310,20220401], 若為[]，則無限制
4. config['ts_range_sx'] 則是以ts(ms)的格式來限制
5. config['maxMergeInterval_ms'] 小於這時間間隔，就合併

# 20220310

1. '在家受測者' 的資料夾內可以指定ts range

# 20220216 spot data only

1. 給專門輸出 提高sr與fullscale的acc/gyro資料

# 20220204

1. 因應新FW的新資訊格式，避免在console上顯示太多次資料而拖慢速度
2. 避免因掉太多封包造成推算出錯誤的sr
3. 若記錄時當掉了，log沒有記錄到停止時間，則由檔案長度推算停止記錄時間
4. config['ts_range_sx']  指定要處理的ts範圍，[]則表示無限制
5. 修正只有zip的情況

# 20220116

1. 藉由acc sr來偵測fw ts(old:250000  new:32768)
2. skipPkgCnt(忽略前幾筆封包，避免剛好在fw ts被reset階段，mic/imu/sysinfo的t0相差太大)
3. 儲存第一筆fw ts
4. 將合併的sx移到暫存目錄merged，避免干擾原始檔

# 20211205

1. 延長flag_checked_fileformat的waiting times，確保可以解出
2. 修正ts was reset的條件
3. 修正pkgloss的條件
4. pkgloss時，能把資料數補0(audio) 或 最新封包的第一筆數值(not audio)
5. 可以讀sxr(剛從drv.read()讀進來的資料)
6. 保留並改名原來的sx,log
7. 跳過少於20秒的
8. 手動模式下，不移除sx, log

# 20211101

1. 以資料的package size與fw給的time stamp來更新imu sr(拿acc的結果來當作其他的)
2. 自動模式下，以NAS上的資料夾名稱當作目標資料夾
3. sysinfo的存檔為完整的sysinfo
4. 可以合併相連(間隔相差<=5秒)的sx
5. 針對FJ的收音，給予另外的存檔路徑，config['dir_Export_fj']
6. 針對FJ帳號的收音，可以在config['fj_dir_kw']設定 NAS上的資料夾名稱
7. 修正manual mode的錯誤
![image](https://user-images.githubusercontent.com/75962075/130272726-2878e34c-4956-44e6-b1ab-ca647bdfa1a5.png)


# sw-sx2wav Config說明:

## "dirToloadFile": 手動模式下，選擇檔案的起始目錄(會有另外的選擇檔案對話框出現)

## "dirList_load_S3zip": 自動模式下，搜尋檔案的目錄
切換手動/自動模式: "dirList_load_S3zip"設定為""，則為手動模式

自動模式，須將 "dirList_load_S3zip" 設定為 資料夾的**list**

## "dir_upzipS3": 自動模式下，解壓縮zip的目的資料夾，也是載入sx的位置

## "ts_loadS3" 自動模式下，選擇檔案的日期區間
"ts_loadS3": [20210718,20210730],

## "mergeNearby": 10,  是否merge 時間相鄰(<=5sec)的sx

## "dir_Export" 轉檔之後的輸出預設目錄
## "dir_savSX" 如果dir_Export == dir_savSX，則會去找是否有對應的使用者資料夾，否則就存檔在sx的資料夾/ble_addr/date
"dir_Export": "G:\\My Drive\\Experiment\\compilation\\在家受測者",

"dir_Export": "./"

## "fj_dir_kw" 指定NAS上哪些資料夾是屬於FJ帳號
"fj_dir_kw" : ["AOIS3T~5","AO7G2X~7","A80PBY~0"],

## 'dir_Export_fj' 針對S3上FJ帳號的收音，給予另外的存檔路徑
'dir_Export_fj': "//192.168.50.250/SiriuXense數據庫/寶寶音資料庫/7M_baby_patch_DVT",

## "load_all_sx" 手動模式下，是否自動載入所有sx(包含解zip)  0:False
## "onlySelectedBle"  只進行這個ble address的轉檔
"FB:7B:9D:40:33:B4"  或  ""
## "onlyChkTS" (bool) 是否只輸出記錄時間
## "onlyChkFormat" 是否只輸出內容格式，(音檔sr, ble address)
## "onlyMovelog" 是否只將app log改檔名並輸出到目標資料夾，不轉其他檔案
## "onlylog" 是否只轉出sysinfo的檔案(csv)
## "overwrite" 是否覆蓋已存在的檔案
## "delSX" 轉檔之後，是否將sx移除
## "moveSX" 轉檔之後，若不刪除sx，是否將sx移到目標資料夾
