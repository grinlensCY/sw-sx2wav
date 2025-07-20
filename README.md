# sw-sx2wav

This script processes `.sx` and `.sxr` files, which appear to be sensor data files. It can perform various operations on these files, such as converting them to `.wav` format, merging them, and filtering them based on various criteria.

## Configuration

The behavior of the script is controlled by a `config.json` file. The following is a description of the available options:

### General

*   `dirToloadFile`: (string) The starting directory for the file selection dialog in manual mode.
*   `dirList_load_S3zip`: (list of strings) A list of directories to search for `.zip` files from an S3 bucket. If this is an empty string, the script will run in manual mode.
*   `dir_upzipS3`: (string) The destination directory for unzipping `.zip` files in automatic mode.
*   `ts_loadS3`: (list of two integers) A date range `[YYYYMMDD, YYYYMMDD]` for filtering files from the S3 bucket in automatic mode.
*   `ts_range_sx`: (list of two integers) A timestamp range in milliseconds for filtering `.sx` files. Use `-1` for no limit.
*   `mergeNearby`: (integer) The maximum interval in seconds between two `.sx` files to be merged.
*   `maxMergeInterval_ms`: (integer) The maximum interval in milliseconds between two `.sx` files to be merged.
*   `dir_Export`: (string) The default output directory for the converted files.
*   `dir_savSX`: (string) If this is the same as `dir_Export`, the script will look for a user-specific folder. Otherwise, it will save the files in a subdirectory of the `.sx` file's location.
*   `fj_dir_kw`: (list of strings) A list of keywords to identify folders belonging to the "FJ" account on a NAS.
*   `dir_Export_fj`: (string) A separate output directory for recordings from the "FJ" account on an S3 bucket.

### Processing Options

*   `load_all_sx`: (integer) Set to non-zero to automatically load all `.sx` files (including unzipping) in manual mode.
*   `onlySelectedBle`: (string) A BLE address to filter the files. Only files from this address will be processed.
*   `onlyChkTS`: (integer) Set to non-zero to only output the recording time.
*   `onlyChkFormat`: (integer) Set to non-zero to only output the content format (audio sample rate, BLE address).
*   `onlyMovelog`: (integer) Set to non-zero to only rename and move the app log to the destination folder without converting other files.
*   `onlylog`: (integer) Set to non-zero to only convert the `sysinfo` file to CSV.
*   `overwrite`: (integer) Set to non-zero to overwrite existing files.
*   `delSX`: (integer) Set to non-zero to delete the `.sx` files after conversion.
*   `moveSX`: (integer) Set to non-zero to move the `.sx` files to the destination folder after conversion (if `delSX` is zero).
*   `skipPkgCnt`: (integer) The number of initial packages to skip to avoid timestamp inconsistencies.
*   `skipBytes_sec`: (integer) The number of bytes to skip from the beginning of the file, in seconds.
*   `prompt_convert`: (integer) Set to non-zero to prompt the user before converting each file.
*   `6ch`: (integer) Set to non-zero to enable 6-channel audio processing.
*   `debug`: (integer) Set to non-zero to enable debug mode.
*   `autoRun`: (object)
    *   `go`: (integer) Set to non-zero to enable automatic execution.
    *   `forceRunAll`: (integer) Set to non-zero to force the script to run on all files, even if they have been processed before.
