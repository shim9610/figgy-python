"""Analytic feature scenes: authored geometry/colors, independent of readback."""
import numpy as np

BLUE = '#2040c0'
ORANGE = '#c04020'
RED = '#c02040'
GREEN = '#208020'
FEATURES = ('mapped_points','vector_points','vector_grid','steps','baseline_fill',
            'series_fill','polar','radar','annotations')


def populate(figure, feature):
    """960x600 document, 400x400 plot at (100,100), ranges [0,4]."""
    ax = figure.axes[0]
    if feature == 'mapped_points':
        ax.scatter([.8,2,3.2],[1,2,3],c=[.1,.5,.9],cmap='gray',vmin=0,vmax=1,
                   s=[0,.5,1],size_domain=(0,1),size_range=(8,24),size_scale='radius',id='points')
    elif feature == 'vector_points':
        ax.quiver([1,3],[1,3],[1,0],[0,-1],units='data',scale=1,color=BLUE,width=3,
                  head_length=12,head_width=10,values=[.25,.75],cmap='gray',vmin=0,vmax=1,id='arrows')
    elif feature == 'vector_grid':
        ax.quiver([1,3],[1,3],[[.8,0],[-.8,0]],[[0,.8],[0,-.8]],units='data',
                  scale=1,color=ORANGE,width=3,head_length=12,head_width=10,
                  values=[[.2,.4],[.6,.8]],cmap='gray',vmin=0,vmax=1,id='arrows')
    elif feature == 'steps':
        ax.step([.5,1.5,2.5,3.5],[1,3,2,1],where='mid',color=BLUE,linewidth=3,id='steps')
    elif feature == 'baseline_fill':
        ax.fill_between([.5,2,3.5],[1,3,1],.5,color=BLUE,alpha=1,id='band')
    elif feature == 'series_fill':
        ax.fill_between([.5,2,3.5],[2,3,2],[1,2,1],color=ORANGE,alpha=1,id='band')
    elif feature == 'polar':
        ax.set_polar(angle_unit='Radians',clockwise=True)
        ax.plot(np.arange(5)*np.pi/2,[1,2,3,1,1],color=BLUE,linewidth=3,id='orbit')
        ax.text(.65,.05,'Polar',coords='ratio',fontsize=10,color=GREEN,id='note')
    elif feature == 'radar':
        # Empty captions remove font-metric dependence; the fixed 400px box,
        # 16px caption reserve and 14px padding give a 170px outer radius.
        ax.radar(['','','',''],[[1,2,3,1],[3,1,2,2]],labels=['First','Second'],colors=[BLUE,RED],value_range=[0,4],font_size=16,
                 grid=False,legend=False,style=dict(line_width_px=4,fill_opacity=0,marker='None'))
        ax.set_title('Independent title',fontsize=18,color='purple')
    elif feature == 'annotations':
        ax.plot([.5,3.5],[.5,.5],color=BLUE,linewidth=2,id='signal')
        ax.axhline(2,color=RED,linewidth=3,id='reference')
        ax.axvspan(1,2,color=BLUE,alpha=.25,id='band')
        ax.text(.65,.25,'TEST',coords='ratio',fontsize=14.4,color=GREEN,id='note')
    else:
        raise AssertionError(feature)
    if feature != 'radar':
        ax.set_xlim(0,4);ax.set_ylim(0,4)
    state = figure.get_settings()
    config = state['config']
    config['chart_title'].update(visible=False,top_margin=0)
    for key, margin in (('top_x',100),('bottom_x',100),('left_y',100),('right_y',460)):
        axis = config[key]
        axis.update(out_margin=margin,line_visible=False,major_tick_length=0,minor_tick_length=0)
        axis['label_style']['visible'] = False
        axis['title_option']['visible'] = False
    for key in ('show_major_x','show_major_y','show_minor_x','show_minor_y'):
        config['grid'][key] = False
    if 'colorbar' in config:
        config['colorbar']['visible'] = False
    if feature == 'radar':
        state['radar']['decorations']['data_area'] = dict(x=100,y=100,width=400,height=400)
    figure.apply_settings(state)
    return ax


def rgb(color):
    return np.array([int(color[i:i+2],16) for i in (1,3,5)])


def assert_color(image, point, color, *, radius=1):
    x,y = point
    patch = image[y-radius:y+radius+1,x-radius:x+radius+1,:3].astype(int)
    expected = rgb(color) if isinstance(color,str) else np.array(color)
    assert np.any(np.max(np.abs(patch-expected),axis=2)<=3), (point,expected.tolist(),patch.tolist())


def assert_white(image, point):
    x,y = point
    assert np.all(image[y-1:y+2,x-1:x+2,:3]>=250), (point,image[y,x].tolist())


def assert_feature_image(image, feature):
    assert image.shape == (600,960,4), image.shape
    if feature == 'mapped_points':
        for x,y,gray,radius in ((180,400,26,8*100/144),(300,300,128,16*100/144),(420,200,230,24*100/144)):
            assert_color(image,(x,y),[gray]*3)
            assert_color(image,(x+int(radius)-2,y),[gray]*3)
            assert_white(image,(x+int(radius)+8,y))
            reach = int(np.ceil(radius+8))
            patch = image[y-reach:y+reach+1,x-reach:x+reach+1,:3].astype(int)
            area = np.count_nonzero(np.max(np.abs(patch-gray),axis=2)<=3)
            assert np.pi*(radius-2)**2<=area<=np.pi*(radius+2)**2,(radius,area)
        assert_white(image,(240,350))
    elif feature in ('vector_points','vector_grid'):
        arrows = [(200,400,300,400),(400,200,400,300)] if feature=='vector_points' else [
            (200,400,280,400),(400,400,400,320),(200,200,120,200),(400,200,400,280)]
        colors = ([64]*3,[191]*3) if feature=='vector_points' else ([51]*3,[102]*3,[153]*3,[204]*3)
        for (x,y,tx,ty),color in zip(arrows,colors):
            dx,dy = np.sign(tx-x),np.sign(ty-y)
            assert_color(image,((x+tx)//2,(y+ty)//2),color)
            # Inside the triangular head, off the shaft; direction matters.
            assert_color(image,(int(tx-12*dx+4*dy),int(ty-12*dy-4*dx)),color)
            assert_white(image,(int(x-12*dx),int(y-12*dy)))
            assert_white(image,(int(tx+10*dx),int(ty+10*dy)))
    elif feature == 'steps':
        for point in ((175,400),(200,300),(250,200),(300,250),(350,300),(400,350),(425,400)):
            assert_color(image,point,BLUE)
        for point in ((175,350),(275,225),(375,350)):
            assert_white(image,point)
    elif feature == 'baseline_fill':
        for point in ((300,350),(300,425),(300,225)):
            assert_color(image,point,BLUE)
        for point in ((300,475),(300,160)):
            assert_white(image,point)
    elif feature == 'series_fill':
        for point in ((300,250),(175,350)):
            assert_color(image,point,ORANGE)
        for point in ((300,350),(300,170),(175,425)):
            assert_white(image,point)
    elif feature == 'polar':
        for point in ((325,350),(225,350),(225,275),(325,275)):
            assert_color(image,point,BLUE)
        for point in ((325,250),(300,300)):
            assert_white(image,point)
    elif feature == 'radar':
        for point in ((343,279),(343,364),(268,332),(279,279)):
            assert_color(image,point,BLUE)
        for point in ((321,236),(321,343),(258,343),(258,236)):
            assert_color(image,point,RED)
        assert_white(image,(300,300))
        assert_white(image,(375,250))
    elif feature == 'annotations':
        assert_color(image,(400,300),RED)
        assert_color(image,(250,150),[199,207,239])
        assert_white(image,(325,150))
        text = image[195:230,355:440,:3].astype(int)
        assert np.count_nonzero(np.max(np.abs(text-rgb(GREEN)),axis=2)<=3)>=20,'missing or misplaced annotation text'
        assert_white(image,(400,400))
    else:
        raise AssertionError(feature)
