# 20210821

1. 以資料的package size與fw給的time stamp來更新imu sr(拿acc的結果來當作其他的)
2. 自動模式下，以NAS上的資料夾名稱當作目標資料夾
3. sysinfo的存檔為完整的sysinfo
![image](https://user-images.githubusercontent.com/75962075/130272726-2878e34c-4956-44e6-b1ab-ca647bdfa1a5.png)


# sw-sx2wav Config說明:

## "dirToloadFile": 手動模式下，選擇檔案的起始目錄(會有另外的選擇檔案對話框出現)

## "dirList_load_S3zip": 自動模式下，搜尋檔案的目錄
切換手動/自動模式: "dirList_load_S3zip"設定為""，則為手動模式

自動模式，須將 "dirList_load_S3zip" 設定為 資料夾的**list**

## "dir_upzipS3": 自動模式下，解壓縮zip的目的資料夾，也是載入sx的位置

## "ts_loadS3" 自動模式下，選擇檔案的日期區間
"ts_loadS3": [20210718,20210730], 

## "dir_Export" 轉檔之後的輸出預設目錄
## "dir_savSX" 如果dir_Export == dir_savSX，則會去找是否有對應的使用者資料夾，否則就存檔在sx的資料夾/ble_addr/date
"dir_Export": "G:\\My Drive\\Experiment\\compilation\\在家受測者",

"dir_Export": "./"

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
