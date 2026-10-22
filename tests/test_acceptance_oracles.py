"""Deliberately wrong results must fail the actual feature/recovery assertions."""
import numpy as np
import pytest
import figgyplot as fg
from figgyplot.review import Session

from feature_visual_assertions import FEATURES, populate, assert_feature_image
from test_review import test_complete_binary_checkpoint_restores_all_families as check_restore
from recovery_assertions import RecordedUploads, record_uploads, assert_arrays, assert_cached_columns, assert_renderer_columns


@pytest.fixture(scope='module',params=FEATURES)
def reference_image(request):
    feature=request.param
    with fg.Figure(backend='native',figsize=(9.6,6),dpi=100) as figure:
        populate(figure,feature)
        image=figure.render_rgba()
        assert_feature_image(image,feature)
        return feature,image


def semantic_error(figure, feature):
    state=figure.get_settings()
    if feature=='mapped_points':state['config']['colorbar']['colormap']='Viridis'
    elif feature in ('vector_points','vector_grid'):
        components=state['series'][0]['render_type']['Vector']['components']
        fields=components['Points' if feature=='vector_points' else 'Grid']
        fields['u'],fields['v']=fields['v'],fields['u']
    elif feature=='steps':state['series'][0]['render_type']['Line']['line']['interpolation']='Linear'
    elif feature in ('baseline_fill','series_fill'):
        state['series'][-1]['render_type']['Line']['line']['fill']={'ToBaseline':0}
    elif feature=='polar':state['config']['polar']['clockwise']=False
    elif feature=='radar':state['radar']['value_range']=[0,8]
    elif feature=='annotations':state['config']['annotations']['items'].pop()
    figure.apply_settings(state)


@pytest.mark.parametrize('fault',['white','single_pixel','wrong_color','shifted','semantic'])
def test_visual_oracle_rejects_wrong_output(reference_image,fault):
    feature,original=reference_image
    image=original.copy()
    if fault in ('white','single_pixel'):
        image[:]=255
        if fault=='single_pixel':image[0,0,:3]=0
    elif fault=='wrong_color':image[...,:3][np.any(image[...,:3]<250,axis=2)]=[240,220,0]
    elif fault=='shifted':image=np.roll(image,(41,53),axis=(0,1))
    else:
        with fg.Figure(backend='native',figsize=(9.6,6),dpi=100) as figure:
            populate(figure,feature);semantic_error(figure,feature);image=figure.render_rgba()
    with pytest.raises(AssertionError):assert_feature_image(image,feature)


@pytest.mark.parametrize('feature',FEATURES)
def test_roundtrip_check_rejects_the_previously_accepted_single_pixel(monkeypatch,feature):
    from test_renderer_018_features import test_features_round_trip_and_replay_without_reupload as check
    calls=[]
    def substituted(figure,*args,**kwargs):
        image=np.full((600,960,4),255,dtype=np.uint8)
        image[0,0,:3]=0;calls.append(True)
        return image
    monkeypatch.setattr(fg.Figure,'render_rgba',substituted)
    with pytest.raises(AssertionError):check('native',feature)
    assert calls==[True,True,True]  # Replay equality passed; the independent scene rejected it.


@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('family',['line','mapped','matrix','vector','vector_grid','fill_pair','panels'])
@pytest.mark.parametrize('fault',['zero','reversed','dtype'])
def test_restore_oracle_rejects_wrong_payload(tmp_path,monkeypatch,backend,family,fault):
    restore=Session.restore
    def changed(session,*args,**kwargs):
        read=session._store.get
        def wrong(reference):
            array=read(reference)
            if fault=='zero':return np.zeros_like(array)
            if fault=='reversed':return array[::-1].copy()
            return array.astype(np.float32)
        with monkeypatch.context() as patch:
            patch.setattr(session._store,'get',wrong)
            return restore(session,*args,**kwargs)
    monkeypatch.setattr(Session,'restore',changed)
    with pytest.raises(AssertionError,match='restored upload'):
        check_restore(tmp_path,family,backend,monkeypatch)


@pytest.mark.parametrize('backend',['native','webgpu'])
def test_checkpoint_oracle_rejects_writer_mutating_original_input(tmp_path,monkeypatch,backend):
    from figgyplot._review_store import Store
    put=Store.put
    def changed(store,array):
        array[:]=0
        return put(store,array)
    monkeypatch.setattr(Store,'put',changed)
    with pytest.raises(AssertionError,match='columns:'):
        check_restore(tmp_path,'line',backend,monkeypatch)


@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('family',['line','mapped','matrix','vector','vector_grid','fill_pair','panels'])
def test_renderer_oracle_rejects_wrong_resident_values(tmp_path,monkeypatch,backend,family):
    # Keep cache files and the observed upload arguments correct. Corrupt only
    # the final device upload / browser transfer snapshot to exercise the next
    # verification boundary independently of the restored-upload assertion.
    import importlib
    module=importlib.import_module('figgyplot.figure')
    from figgyplot.notebook import NotebookData
    restore=Session.restore
    class WrongDevice:
        def __init__(self,native):self.native=native
        def __getattr__(self,name):return getattr(self.native,name)
        def upload_column(self,name,array):self.native.upload_column(name,np.zeros_like(array))
    def changed(session,*args,**kwargs):
        with monkeypatch.context() as patch:
            if backend=='native':
                constructor=module.NativeFigure
                patch.setattr(module,'NativeFigure',lambda *a,**k:WrongDevice(constructor(*a,**k)))
            else:
                upload=NotebookData.upload_column
                def wrong_transfer(data,name,array):
                    upload(data,name,array)
                    dtype,payload=data.columns[name]
                    data.columns[name]=(dtype,bytes(len(payload)))
                patch.setattr(NotebookData,'upload_column',wrong_transfer)
            return restore(session,*args,**kwargs)
    monkeypatch.setattr(Session,'restore',changed)
    with pytest.raises(AssertionError,match='GPU column|browser transfer'):
        check_restore(tmp_path,family,backend,monkeypatch)


@pytest.mark.parametrize('backend',['native','webgpu'])
@pytest.mark.parametrize('dtype',[np.float32,np.float64])
def test_restore_preserves_float_types_bits_and_gpu_values(tmp_path,monkeypatch,backend,dtype):
    y=np.array([-0.,np.pi,-2.5,2**-30,1e9+.125,-1e-9,np.nan,np.inf,-np.inf],dtype=dtype)
    bits=y.view(np.uint32 if dtype==np.float32 else np.uint64)
    bits[6]=0x7fc00042 if dtype==np.float32 else 0x7ff8000000000042
    x=np.arange(len(y),dtype=dtype)
    original={}
    with Session(tmp_path,backend=backend) as session:
        figure=session.figure(id='precision')
        figure._native=RecordedUploads(figure._native,original)
        figure.axes[0].plot(x,y,id='signal')
        assert original['signal/x'].dtype==x.dtype
        assert original['signal/y'].tobytes()==y.tobytes()
        session.start();session.submit('precision','request_changes')
        checkpoint=session.feedback(session.events()[0]['work_id'])['round']['documents']['precision']
        assert_cached_columns(tmp_path,checkpoint,original)
    with record_uploads(monkeypatch) as uploaded, Session.open(tmp_path) as resumed:
        recovered=resumed.restore('precision',backend=backend)
        assert_arrays(original,uploaded,'restored upload')
        assert_renderer_columns(recovered,original)
