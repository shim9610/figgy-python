"""Surface submission rate, separate from completed RGBA/readback benchmarks."""
import argparse,json,platform,time
from pathlib import Path
import numpy as np
import figgy
from figgy.desktop import poll_events

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--points',type=int,default=100_000);parser.add_argument('--frames',type=int,default=120);parser.add_argument('--output',type=Path,default=Path('benchmarks/results/ui-surface.json'));args=parser.parse_args()
    with figgy.Figure(backend='native') as figure:
        x=np.linspace(0,20,args.points,dtype=np.float64);figure.axes[0].plot(x,np.sin(x));window=figure.show(block=False)
        def draw():
            previous=(json.loads(window.info_json()) or {}).get('surface_frames',0)
            window.refresh();deadline=time.monotonic()+10
            while (json.loads(window.info_json()) or {}).get('surface_frames',0)<=previous:
                poll_events()
                if time.monotonic()>deadline:raise RuntimeError('surface redraw timed out')
        for _ in range(5):draw()
        start=time.perf_counter()
        for _ in range(args.frames):draw()
        elapsed=time.perf_counter()-start
        result={'metric':'surface frame submission rate; not monitor FPS or GPU completion/readback', 'os':platform.platform(),'version':figgy.__version__,'points':args.points,'measured_frames':args.frames,'elapsed_seconds':elapsed,'submitted_frames_per_second':args.frames/elapsed,'host':json.loads(window.info_json()),'renderer':figure.info}
        assert result['host']['rgba_readbacks']==0 and result['host']['png_encodes']==0
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2));window.close();poll_events()
if __name__=='__main__':main()
