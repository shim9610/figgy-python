"""Render task-specific built-in styles, with execution-local inheritance.

Run: python examples/style_gallery.py --output /tmp/figgy-style-gallery
Requires Pillow only to compose the overview; every chart is rendered by Figgy.
"""
from pathlib import Path
import argparse
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import figgyplot as fg
from figgyplot._style_presets import PROFILES


def make(name):
    p=PROFILES[name];printed=p.get('print',False)
    dpi=300 if printed else 100
    # Bounded boxplot text has an upstream 32 logical-pixel ceiling. At 9 pt,
    # 240 DPI fits; 300 DPI is rejected rather than silently shrinking text.
    if name=='print.monochrome':dpi=240
    size=((89/25.4,62/25.4) if name=='publication.nature' else (88.9/25.4,65/25.4)) if printed else ((4.1,5.2) if name=='dashboard.mobile' else (8.2,4.6))
    if name in ('dashboard.operations','dashboard.analysis','dashboard.instrument'):size=(12.2,4.7)
    fig=fg.Figure(figsize=size,dpi=dpi);ax=fig.axes[0]
    x=np.linspace(0,12,121)
    if name=='publication.nature':
        t=np.arange(6);a=.3+.55*(1-np.exp(-t/2));b=.25+.4*(1-np.exp(-t/3))
        ax.errorbar(t,a,yerr=.035,marker='o',label='Control');ax.errorbar(t,b,yerr=.045,marker='s',label='Treatment')
        ax.set_xlabel('Time (h)');ax.set_ylabel('Response (a.u.)');ax.set_xlim(-.2,5.3);ax.set_ylim(.1,1)
    elif name=='publication.ieee-proceedings':
        x=np.geomspace(1,1e4,121)
        for i in range(3):ax.plot(x,-10*np.log10(1+(x/(30*(i+1)))**2),linestyle=['-','--',':'][i],label=f'Filter {i+1}')
        ax.set_xscale('log');ax.set_xlabel('Frequency (Hz)');ax.set_ylabel('Gain (dB)');ax.set_xlim(1,1e4);ax.set_ylim(-55,2)
    elif name=='publication.kfas':
        x=np.arange(6)
        ax.errorbar(x,4+1.4*x,yerr=.6,marker='o',label='Site A');ax.errorbar(x,3+1.1*x,yerr=.8,marker='s',label='Site B')
        ax.set_xlabel('Age (year)');ax.set_ylabel('Length (cm)');ax.set_xlim(-.2,5.3);ax.set_ylim(0,13)
    elif name=='print.monochrome':
        ax.boxplot([[3,4,4.5,5,5.2,6,8],[4,5,5.2,6,7,7.2,9],[2,3,3.5,4,4.2,5,6]],labels=['Control','Batch A','Batch B'])
        ax.set_ylabel('Strength (MPa)')
    elif name in ('dashboard.executive','dashboard.public'):
        ax.barh(['North','South','East','West'],[[72,64,85,59],[68,67,78,63]],label=['Current','Previous'])
        ax.set_title('Regional delivery performance');ax.set_xlabel('Completed orders (thousands)')
    elif name=='dashboard.operations':
        fig.set_layout([['latency','errors','traffic']]);xx=np.arange(30)
        specs=[('latency','Request latency','p95 latency (ms)',110+14*np.sin(xx/3),150),
               ('errors','Error rate','Failed requests (%)',.6+.25*np.sin(xx/4),.9),
               ('traffic','Request volume','Requests / second',320+30*np.sin(xx/5),None)]
        for key,title,unit,y,threshold in specs:
            a=fig.subplots[key].axes;a.plot(xx,y,style_key=key,label='Measured')
            if threshold is not None:a.plot([0,29],[threshold]*2,style_key='warning',label='Supplied limit')
            a.set_title(title);a.set_ylabel(unit);a.set_xlabel('Elapsed time (min)');a.set_xlim(0,29);a.legend()
    elif name=='dashboard.analysis':
        fig.set_layout([['comparison','deviation']]);a=fig.subplots['comparison'].axes
        for i in range(4):a.plot(x,.4*x+np.sin(x+i)*.45+i*.12,style_key='context')
        a.plot(x,.4*x+np.sin(x)*.45+1,style_key='focus',label='Selected cohort')
        a.set_title('Focus in cohort context');a.set_xlabel('Time (h)');a.set_ylabel('Response (a.u.)');a.legend()
        a=fig.subplots['deviation'].axes
        z=np.outer(np.sin(np.linspace(-2,2,16)),np.cos(np.linspace(-2,2,18)))*12
        a.imshow(z,cmap='RdBu',vmin=-12,vmax=12,origin='lower')
        a.set_title('Deviation from supplied reference');a.set_xlabel('Position X (mm)');a.set_ylabel('Position Y (mm)')
    elif name=='dashboard.instrument':
        fig.set_layout([['wave','spectrum']]);a=fig.subplots['wave'].axes
        a.plot(x,np.sin(8*x)*np.exp(-x/7),style_key='sensor',label='Sensor A');a.set_title('Damped oscillation')
        a.set_xlabel('Time (ms)');a.set_ylabel('Voltage (V)');a.set_xlim(0,12);a.set_ylim(-1.1,1.1)
        a=fig.subplots['spectrum'].axes;f=np.geomspace(10,1e4,200)
        a.plot(f,1/np.sqrt(1+(f/250)**4),style_key='sensor');a.set_xscale('log');a.set_yscale('log')
        a.set_title('Frequency response');a.set_xlabel('Frequency (Hz)');a.set_ylabel('Amplitude (V)');a.set_xlim(10,1e4);a.set_ylim(.0001,2)
    elif name=='dashboard.wallboard':
        y=135+10*np.sin(x/2);ax.plot(x,y,style_key='focus',label='Measured')
        ax.plot([0,12],[180,180],style_key='warning',label='Supplied limit')
        ax.set_title('Latency · 132 ms');ax.set_xlabel('Elapsed time (min)');ax.set_ylabel('p95 latency (ms)');ax.set_ylim(0,220);ax.set_xlim(0,12)
    elif name=='dashboard.mobile':
        ax.plot(np.arange(7),[42,48,45,59,65,61,73],marker='o',style_key='focus')
        ax.set_title('Weekly activity');ax.set_xlabel('Day');ax.set_ylabel('Completed tasks');ax.set_xlim(-.3,6.3);ax.set_ylim(0,85)
    elif name=='scientific.precision':
        for i in range(3):ax.plot(x,np.sin(x*(i+1))*.7+i*2,label=f'Channel {i+1}')
        ax.set_title('Three calibrated measurement channels');ax.set_xlabel('Time (s)');ax.set_ylabel('Voltage + offset (V)');ax.set_xlim(0,12);ax.set_ylim(-1,5)
    elif name=='education.explainer':
        y=.5*x+np.sin(x)*.3
        ax.fill_between(x,.5*x-.7,.5*x+.7,alpha=.12,style_key='focus')
        ax.scatter(x[::6],y[::6],style_key='focus',label='Observed');ax.plot(x,.5*x,style_key='reference',label='Model')
        ax.arrow(3,4,2,-1.5);ax.text(1,4.5,'Compare data and model')
        ax.set_title('Trend and uncertainty');ax.set_xlabel('Input');ax.set_ylabel('Response');ax.set_xlim(0,12);ax.set_ylim(-1,7)
    else:
        x=x[::6]
        for i,name_ in enumerate(['Baseline','Candidate A','Candidate B']):
            ax.plot(x,1-np.exp(-x/(2+i)),marker=['o','s','D'][i],label=name_)
        ax.set_title('Response over time');ax.set_xlabel('Time (s)');ax.set_ylabel('Normalized response');ax.set_xlim(0,12);ax.set_ylim(0,1.1)
    if name not in ('print.monochrome','dashboard.executive','dashboard.public','dashboard.operations','dashboard.analysis','dashboard.instrument','dashboard.mobile'):ax.legend()
    return fig


def contrast(c,b):
    def lum(x):
        v=[x[k] for k in ('r','g','b')];return sum(w*(z/12.92 if z<=.04045 else ((z+.055)/1.055)**2.4) for w,z in zip((.2126,.7152,.0722),v))
    a,d=lum(c),lum(b);return (max(a,d)+.05)/(min(a,d)+.05)


def main(output):
    output.mkdir(parents=True,exist_ok=True);manifest={}
    for name in PROFILES:
        with fg.style_context(name):fig=make(name)
        try:
            token=fig.style_defaults;path=output/(name+'.png');fig.savefig(path)
            image=Image.open(path).convert('RGBA');image.save(path,dpi=(fig.dpi,fig.dpi))
            token.save(output/(name+'.style.json'))
            a=token.appearance
            manifest[name]=dict(fg.styles.describe(name),image=path.name,dpi=fig.dpi,
                size_px=image.size,category_contrast=[contrast(c,a['background']) for c in a['palette']],
                semantic_contrast={key:contrast(v['line']['line_color'],a['background']) for key,v in a['roles'].items()},
                inherited_after_scope=True,renderer='Figgy native')
        finally:fig.close()
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
    # Captions and thumbnails are the only composed pixels; standalone exports
    # retain the exact native rendering and include physical DPI metadata.
    for group,names in [('publication',[n for n in PROFILES if n.startswith(('publication.','print.'))]),
                        ('screens',[n for n in PROFILES if not n.startswith(('publication.','print.'))])]:
        tilew,tileh=680,340;sheet=Image.new('RGB',(tilew*2,tileh*((len(names)+1)//2)),'#eff2f6');draw=ImageDraw.Draw(sheet)
        for i,name in enumerate(names):
            x=(i%2)*tilew;y=(i//2)*tileh;draw.text((x+16,y+8),name,fill='#202733',font=font)
            im=Image.open(output/(name+'.png')).convert('RGB');im.thumbnail((tilew-30,tileh-45),Image.Resampling.LANCZOS)
            sheet.paste(im,(x+(tilew-im.width)//2,y+37))
        sheet.save(output/(group+'-overview.png'))
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(output)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('/tmp/figgy-style-gallery'))
    main(parser.parse_args().output)
