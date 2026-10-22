"""Send complete X11 clicks before waiting for a rendered frame."""


def click(emit, *, double=False):
    # Pumping between press and release can exceed egui's 0.8s click duration
    # on a slow software GPU. The host must receive a short click, not a hold.
    if double:
        emit('click','--repeat',2,'--delay',70,1)
    else:
        emit('click',1)
