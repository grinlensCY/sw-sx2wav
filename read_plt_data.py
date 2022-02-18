import librosa
import tkinter as tk
from tkinter import filedialog
import matplotlib.pyplot as plt
import matplotlib.widgets as mwidgets
import matplotlib
chinese_font = matplotlib.font_manager.FontProperties(fname='C:\Windows\Fonts\mingliu.ttc')

srcdir = r'C:\Users\chenyikuo\Downloads\tmp\FCBB5ED99F60\2022-02-17'
fns = ['','']
# fns[0] = f'{srcdir}/2022-02-17-15-28-04-acc-01.wav'
fns[0] = filedialog.askopenfilename(initialdir=srcdir,filetypes=[("SXwav","*acc-01.wav")])
fns[1] = fns[0].replace("acc","gyro")
ti = 0
duration = 300
fig, axs = plt.subplots(2,1,figsize=(18,9))
path_str = srcdir.split('\\')[-4:]
plt.suptitle(f"{path_str}",fontproperties=chinese_font, fontsize=16)
ax_str = ['x','y','z']
typ_str = ['acc','gyro']
fs = [16,2000]  # very IMPORTANT: data of wav-file must be multiplied by fs to restore real value
for typ in range(2):
    y, sr = librosa.load(fns[typ],sr=None,mono=False,offset=ti,duration=duration)
    ts = y[0]
    for ax in range(3):
        axs[typ].plot(ts,y[ax+1]*fs[typ],label=f'{typ_str[typ]}_{ax_str[ax]}')
    axs[typ].legend(prop=chinese_font)
    axs[typ].grid(axis='both')
    axs[typ].set_ylim((-fs[typ],fs[typ]))
multi=mwidgets.MultiCursor(plt.gcf().canvas, axs, color='r', lw=1)
plt.tight_layout()
plt.show()