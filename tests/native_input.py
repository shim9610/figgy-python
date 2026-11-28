"""Send complete X11 clicks before waiting for a rendered frame."""
import subprocess


def set_clipboard(text):
    # xclip forks a selection owner that must survive until the next paste.
    # Its stdout/stderr must not retain pytest's CI log pipe after Python exits.
    subprocess.run(['xclip','-selection','clipboard','-t','UTF8_STRING'],
                   input=text,text=True,check=True,timeout=10,
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


def click(emit, *, double=False):
    # Pumping between press and release can exceed egui's 0.8s click duration
    # on a slow software GPU. The host must receive a short click, not a hold.
    if double:
        emit('click','--repeat',2,'--delay',70,1)
    else:
        emit('click',1)
