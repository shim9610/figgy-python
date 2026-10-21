"""Native review controller; an external agent polls the printed cache path."""
import argparse
from pathlib import Path

import numpy as np
from figgyplot.review import Session


def build(session):
    x=np.linspace(0,10,101)
    density=session.figure(id='density')
    density.axes[0].plot(x,np.exp(-x/3),id='density-values',linewidth=2.5)
    density.axes[0].set_title('Density profile')
    field=session.figure(id='field-plot')
    field.axes[0].imshow(np.sin(x[:20,None])*np.cos(x[None,:20]),id='field-values')
    field.axes[0].set_title('Spatial distribution')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',help='Resume an existing session cache')
    args=parser.parse_args()
    session=Session.open(args.cache) if args.cache else Session(source={'entrypoint':str(Path(__file__).resolve())})
    with session:
        if not args.cache:build(session)
        print('Review cache:',session.cache_dir,flush=True)
        print('Agent command: python -m figgyplot.review events '+str(session.cache_dir),flush=True)
        session.present();session.run_events(on_status=lambda status:print(status,flush=True))


if __name__=='__main__':main()
