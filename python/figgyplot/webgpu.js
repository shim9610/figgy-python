// Local packaged WASM/WebGPU host. No image decoding in the redraw path.
let kernelModule;
async function loadKernel(model) {
  if (!kernelModule) kernelModule = (async () => {
    const url = URL.createObjectURL(new Blob([model.get('wasm_js')], {type:'text/javascript'}));
    try {
      const module = await import(url);
      await module.default({module_or_path: bytes(model.get('wasm'))});
      return module;
    } finally { URL.revokeObjectURL(url); }
  })().catch(e => {kernelModule = null; throw e;});
  return kernelModule;
}
function bytes(v) {return v instanceof DataView ? new Uint8Array(v.buffer,v.byteOffset,v.byteLength) : new Uint8Array(v.buffer ?? v,v.byteOffset ?? 0,v.byteLength ?? v.length);}
const clone = value => JSON.parse(JSON.stringify(value));
const rendererVersion = '0.18.0';
const supportedSettings = settings => [1,2].includes(settings.schema_version) && ['0.17.0',rendererVersion].includes(settings.renderer_version);
const text = rich => rich?.segments?.map(s=>s.text).join('') ?? '';
function segments(value) {return Array.from(value,c=>({text:c,superscript:false,subscript:false,italic:false,bold:false,underline:false,greek:false}));}
const side = {bottom:'bottom_x',top:'top_x',left:'left_y',right:'right_y'};
// Properties controls edit both sides of an implicitly shared axis. Raw SSOT
// installation deliberately bypasses this helper, preserving independent axes.
function reconcilePairedAxisEdit(before,state,target){
  const match=/^(?:axis|tick_labels)_(bottom|top|left|right)$/.exec(target);
  if(!match)return;
  const key=side[match[1]],other={bottom_x:'top_x',top_x:'bottom_x',left_y:'right_y',right_y:'left_y'}[key];
  const previous=before.config?.[key],peerBefore=before.config?.[other],axis=state.config?.[key],peer=state.config?.[other];
  if(!previous||!peerBefore||!axis||!peer)return;
  if(!['min','max','scale','inverted'].every(name=>previous[name]===peerBefore[name]))return;
  const changed=(old,value)=>JSON.stringify(old)!==JSON.stringify(value);
  for(const name of ['min','max','scale','inverted','major_spacing','minor_count','tick','major_tick_length','minor_tick_length','line_color','line_width','line_style']){
    if(changed(previous[name],axis[name]))peer[name]=clone(axis[name]);
  }
  for(const [name,value] of Object.entries(axis.label_style??{})){
    if(!['label_offset_x','label_offset_y'].includes(name)&&changed(previous.label_style?.[name],value))peer.label_style[name]=clone(value);
  }
}
const ids = ['chart_title','legend','data_area','colorbar','colorbar_axis','colorbar_tick_labels','colorbar_title',...Object.keys(side).flatMap(s=>[`axis_title_${s}`,`axis_${s}`,`tick_labels_${s}`])];
const labels={chart_title:'Chart title',data_area:'Plot area',legend:'Legend',colorbar:'Color scale',colorbar_axis:'Color scale axis',colorbar_tick_labels:'Color scale labels',colorbar_title:'Color scale title',axis_scale:'Scale',color_scale:'Scale',axis_bottom:'X axis',axis_left:'Y axis',axis_top:'Top axis',axis_right:'Right axis',axis_title_bottom:'X axis title',axis_title_left:'Y axis title',axis_title_top:'Top axis title',axis_title_right:'Right axis title',tick_labels_bottom:'X tick labels',tick_labels_left:'Y tick labels',tick_labels_top:'Top tick labels',tick_labels_right:'Right tick labels',ticks_visible:'Tick marks',tick_labels_visible:'Tick labels',tick_direction:'Tick direction',label_format:'Number format',significant_digits:'Significant digits',font_size:'Font size',font:'Font family',line_width:'Line width'};
const caption=key=>labels[key]??key.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
export function render({model,el}) {
  const root=document.createElement('div');root.className='figgy-editor figgy-webgpu';
  const paths={fit:'M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5M4 4l5 5m11-5-5 5m5 11-5-5M4 20l5-5',select:'M6 3v17l5-5 4 7 3-2-4-6h7Z',layout:'M12 2v20M2 12h20M8 6l4-4 4 4M8 18l4 4 4-4M6 8l-4 4 4 4M18 8l4 4-4 4',copy:'M8 3h9l4 4v14H8ZM8 7H3v14h2M13 11l-2 3 2 3m3-6 2 3-2 3',save:'M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4',properties:'M3 5h18M3 12h18M3 19h18M8 2v6M16 9v6M10 16v6',fullscreen:'M3 9V3h6M15 3h6v6M21 15v6h-6M9 21H3v-6'};
  const icon=(name,label)=>`<button data-${name} title="${label}" aria-label="${label}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]}"/></svg></button>`;
  root.innerHTML=`<div class="figgy-toolbar"><strong>Figgy</strong>${icon('fit','Fit view')}${icon('select','Select')}${icon('layout','Move or resize plot area')}<input data-area type="checkbox" hidden><button data-visibility>Show / hide</button><button data-style>Style</button>${icon('copy','Copy Python')}${icon('save','Save PNG')}${icon('properties','Properties')}${icon('fullscreen','Full screen')}<span data-status>Preparing…</span></div><div class="figgy-body"><div class="figgy-stage"><canvas tabindex="0" aria-label="Editable chart"></canvas></div><div class="figgy-properties" hidden><header><strong>Properties</strong><button data-close-properties>Close</button></header><label>Object <select data-target></select></label><div data-fields></div><details data-advanced><summary>Advanced settings</summary><textarea data-settings></textarea><button data-apply>Apply settings</button></details><details data-code-panel><summary>Python code</summary><textarea data-code readonly></textarea></details></div></div><div data-hint>Click an element to edit · Drag to move · Wheel to zoom · Esc: clear · Arrows: move selection</div><div class="figgy-error" role="alert"></div>`;
  el.append(root);
  const canvas=root.querySelector('canvas'), select=root.querySelector('[data-target]'), fields=root.querySelector('[data-fields]');
  const error=root.querySelector('.figgy-error'), status=root.querySelector('[data-status]');
  const controls=[...root.querySelectorAll('button,input,select,textarea')];
  controls.forEach(control=>control.disabled=true);
  const client=crypto.randomUUID();
  let chart,disposed=false,dirty=true,raf=0,selected=null,pointer=null,queue=Promise.resolve();
  let revision=model.get('state').revision,sequence=0,inflight=null,pending=null,barriers=[],local=clone(model.get('state').settings);
  let background=clone(local.background ?? null);
  const stats={backend:'browser-webgpu',binary_upload_bytes:0,column_uploads:0,surface_frames:0,png_exports:0,kernel_edit_messages:0,last_input_to_submit_ms:0};
  const kind=['radial','categorical','boxplot','radar'].find(k=>local[k]);
  let hoverPoint=null,lastFrame=0,wheelArea=null;
  const textRanges=new Map();
  function showProperties(open=true){root.querySelector('.figgy-properties').hidden=!open;}
  function layoutMode(enabled){if(!enabled&&kind&&chart&&selected==='data_area')enqueue(()=>{chart.clear_selection();selected=null;dirty=true;commit();});root.querySelector('[data-area]').checked=enabled;root.querySelector('[data-layout]').setAttribute('aria-pressed',String(enabled));root.querySelector('[data-select]').setAttribute('aria-pressed',String(!enabled));}
  let inputAt=null,busy=0,startInit,pendingFrame=null,frameError=null;
  let queuedOperations=0,operationSequence=0;
  // Optional CI diagnostics. Never read the WASM chart or wait on GPU work.
  function diagnostics(){return {kind:kind??'cartesian',busy,queued:queuedOperations,
    dirty,frame_pending:!!pendingFrame,frame_error:frameError?String(frameError):null,
    edit_inflight:inflight?.sequence??null,edit_pending:!!pending,
    canvas:[canvas.width,canvas.height],disposed};}
  function trace(stage,details={}){try{globalThis.__figgyTrace?.(stage,{client,...diagnostics(),...details});}catch{}}
  const requested=new Promise(resolve=>{startInit=resolve;});
  let initializedResolve,initializedReject;
  const initialized=new Promise((resolve,reject)=>{initializedResolve=resolve;initializedReject=reject;});
  initialized.catch(()=>{});
  const fail=e=>{error.textContent=String(e?.message ?? e);stats.last_error=error.textContent;};
  const enqueue=(fn,propagate=false)=>{
    const operationId=++operationSequence;queuedOperations++;trace('queue.enqueued',{operationId});
    const operation=queue.then(async()=>{queuedOperations--;if(disposed)throw Error('Widget disposed');busy++;trace('queue.started',{operationId});try{return await fn();}finally{busy--;trace('queue.finished',{operationId});}});
    queue=operation.catch(fail);return propagate?operation:queue;
  };
  function snapshot(){if(kind)return {...clone(local),renderer_version:rendererVersion,[kind]:JSON.parse(chart.get_document())};return {...clone(local),schema_version:local.schema_version,renderer_version:rendererVersion,config:JSON.parse(chart.get_config()),series:JSON.parse(chart.get_series()),...(background ? {background:clone(background)} : {})};}
  function clearColor(color){const c=color ?? {r:1,g:1,b:1,a:1};chart.set_clear_color(c.r,c.g,c.b,c.a);background=clone(color ?? null);}
  function checkNumbers(value,path='settings'){
    if(typeof value==='number' && !Number.isFinite(value))throw Error(`${path} must be finite`);
    if(value && typeof value==='object')for(const [key,item] of Object.entries(value)){
      const next=`${path}.${key}`;
      if(key==='font_size' && typeof item==='number' && !(item>0))throw Error(`${next} must be greater than 0 pixels`);
      if(['line_width','point_size','major_x_width','major_y_width','minor_x_width','minor_y_width'].includes(key) && typeof item==='number' && !(item>=0))throw Error(`${next} must be nonnegative`);
      checkNumbers(item,next);
    }
  }
  function checkNumericConversion(requested,accepted,path='settings'){
    if(typeof requested==='number' && typeof accepted!=='number')throw Error(`${path} exceeds the renderer floating-point range`);
    if(requested && typeof requested==='object')for(const [key,item] of Object.entries(requested)){
      if(!accepted || !(key in accepted)){
        const omittedDefault=(key==='align'&&item==='Left')||(key==='draw_style'&&item?.mode==='precise'&&Object.keys(item).length===1)||(key==='picked_data'&&item===null);
        if(omittedDefault)continue;
        throw Error(`Unknown settings field: ${path}.${key}`);
      }
      checkNumericConversion(item,accepted[key],`${path}.${key}`);
    }
  }
  function install(settings){
    if(kind){
      if(!supportedSettings(settings)||!settings[kind]||settings.series.length)throw Error('Unsupported chart settings');
      checkNumbers(settings);
      const old=snapshot();
      try{chart.set_document(JSON.stringify(settings[kind]),settings.config.chart_area.width,settings.config.chart_area.height);checkNumericConversion(settings[kind],JSON.parse(chart.get_document()));}
      catch(e){chart.set_document(JSON.stringify(old[kind]),old.config.chart_area.width,old.config.chart_area.height);throw e;}
      local=clone(settings);dirty=true;error.textContent='';return;
    }
    // Roll back both trees if either renderer validation rejects a local edit.
    const old=snapshot();
    try {
      if(!supportedSettings(settings))throw Error('Unsupported settings/renderer version');
      checkNumbers(settings);
      const children=settings.config.subplots??[],assigned=new Set(children.flatMap(p=>p.series??[]));
      for(const [config,series] of [[settings.config,settings.series.filter(s=>!assigned.has(s.series_id))],...children.map(p=>[p.config,settings.series.filter(s=>(p.series??[]).includes(s.series_id))])]){
        const mode=config.draw_style?.mode;
        if(mode==='sketch' && series.some(s=>s.render_type.Histogram||s.render_type.Heatmap||s.render_type.Contour||s.render_type.HeatmapContour||s.render_type.Vector))throw Error('Sketch draws line, scatter and errorbar series; bars, fields and vectors are not supported');
        if(mode==='milkyway' && series.some(s=>!s.render_type.Line))throw Error('Milkyway supports line-only series; scatter and marker lines are disabled');
        if(mode==='constellation' && series.some(s=>!s.render_type.ScatterLine))throw Error('Constellation requires line series with markers');
        if(config.chart_title?.top_margin < 0)throw Error('config.chart_title.top_margin must be nonnegative; use offset_y to move the title');
        for(const axis of [config.top_x,config.bottom_x,config.left_y,config.right_y,config.colorbar?.axis,...(config.overlays??[]).map(o=>o.y_axis)].filter(Boolean)){
          const min=axis.scale==='Logarithmic'?Math.log10(axis.min):axis.min, max=axis.scale==='Logarithmic'?Math.log10(axis.max):axis.max;
          if(![min,max,max-min].every(v=>typeof v==='number' && Number.isFinite(Math.fround(v))))throw Error('Axis bounds/span exceed the f32 hi/lo representation range');
        }
      }
      if(JSON.stringify(settings.series)===JSON.stringify(old.series)){chart.set_config(JSON.stringify(settings.config));}
      else{chart.set_picked_data('null');chart.set_series('[]');const staging=clone(settings.config);delete staging.picked_data;delete staging.picked_points;chart.set_config(JSON.stringify(staging));chart.set_series(JSON.stringify(settings.series));chart.set_config(JSON.stringify(settings.config));}clearColor(settings.background);checkNumericConversion(settings,{...clone(settings),config:JSON.parse(chart.get_config()),series:JSON.parse(chart.get_series())});
    }
    catch(e){chart.set_series('[]');chart.set_config(JSON.stringify(old.config));chart.set_series(JSON.stringify(old.series));chart.set_config(JSON.stringify(old.config));clearColor(old.background);local=old;throw e;}
    local={...clone(settings),config:JSON.parse(chart.get_config()),series:JSON.parse(chart.get_series())};dirty=true;error.textContent='';
  }
  function post(){if(inflight || !pending)return;inflight={sequence:++sequence,settings:pending};pending=null;stats.kernel_edit_messages++;model.send({action:'edit',client,sequence,revision,settings:inflight.settings});}
  function commit(){local=snapshot();pending=clone(local);post();properties();}
  function idle(){if(!inflight && !pending){for(const resolve of barriers.splice(0))resolve();}}
  function flush(){post();return !inflight&&!pending ? Promise.resolve() : new Promise(resolve=>barriers.push(resolve));}
  let exportedCode=model.get('state').code ?? '';
  function code(){return exportedCode;}
  const selectedData=document.createElement('section');selectedData.dataset.selectedData='';selectedData.hidden=true;
  root.querySelector('[data-advanced]').before(selectedData);
  let selectedDataKey=null;
  function selectionProperties(){
    if(kind)return;
    const reference=local.config.picked_data?.refs?.[0]??null,key=JSON.stringify(reference);
    if(key===selectedDataKey)return;
    selectedDataKey=key;selectedData.replaceChildren();selectedData.hidden=!reference;
    if(!reference)return;
    const heading=document.createElement('strong');heading.textContent='SELECTED DATA';selectedData.append(heading);
    enqueue(async()=>{
      if(key!==selectedDataKey)return;
      const value=JSON.parse(await chart.selection_details());
      if(key!==selectedDataKey)return;
      if(!value){selectedData.hidden=true;return;}
      for(const name of ['index','x_index','y_index','color_value','size_value','u','v','bin_start','bin_end','x','y','value','orientation']){
        if(value[name]===undefined)continue;
        const row=document.createElement('div');row.dataset.selectedValue=name;row.textContent=`${caption(name)}: ${value[name]}`;selectedData.append(row);
      }
      const hint=document.createElement('small');hint.textContent='Arrows: move selection · Esc: clear';selectedData.append(hint);
    });
  }
  function activePanel(state){
    const layer=state.config.active_layer;
    const index=layer?.Subplot??layer?.SubplotOverlay?.[0];
    return index===undefined?state.config:state.config.subplots[index].config;
  }
  function configOf(state){
    const cfg=activePanel(state),layer=state.config.active_layer;
    const overlay=layer?.Overlay??layer?.SubplotOverlay?.[1];
    if(overlay===undefined)return cfg;
    const view=Object.create(cfg),node=cfg.overlays[overlay];
    Object.defineProperty(view,'right_y',{get:()=>node.y_axis,set:value=>node.y_axis=value});
    return view;
  }
  function seriesInActiveLayer(id){
    const cfg=local.config,layer=cfg.active_layer??'Base';
    const index=cfg.subplots?.findIndex(p=>p.series?.includes(id))??-1;
    const panel=index<0?cfg:cfg.subplots[index].config;
    const overlay=panel.overlays?.findIndex(o=>o.series?.includes(id))??-1;
    const owner=index<0?(overlay<0?'Base':{Overlay:overlay}):(overlay<0?{Subplot:index}:{SubplotOverlay:[index,overlay]});
    return JSON.stringify(owner)===JSON.stringify(layer);
  }
  function elementName(name,state=local){
    const layer=state.config.active_layer,index=layer?.Subplot??layer?.SubplotOverlay?.[0];
    const overlay=layer?.Overlay??layer?.SubplotOverlay?.[1];
    let prefix=index===undefined?'':`subplot_${index}:`;
    if(overlay!==undefined&&['axis_right','tick_labels_right','axis_title_right'].includes(name))prefix+=`overlay_${overlay}:`;
    return prefix+name;
  }
  const layerChoice=document.createElement('select');layerChoice.dataset.layer='';layerChoice.setAttribute('aria-label','Panel and layer');
  root.querySelector('[data-status]').before(layerChoice);
  function layers(){
    if(kind){
      layerChoice.replaceChildren();
      for(const value of ['Base','Annotations']){const option=document.createElement('option');option.value=JSON.stringify(value);option.textContent=value;layerChoice.append(option);}
      layerChoice.value=JSON.stringify(local[kind].active_layer??'Base');layerChoice.hidden=!local[kind].annotations?.items?.length;return;
    }
    const previous=JSON.stringify(local.config.active_layer??'Base');layerChoice.replaceChildren();
    const panels=local.identity?.panels??[{id:'main',overlays:[]}];
    panels.forEach((panel,index)=>{
      const append=(label,value)=>{const option=document.createElement('option');option.textContent=label;option.value=JSON.stringify(value);layerChoice.append(option);};
      append(panel.id,index?{Subplot:index-1}:'Base');
      panel.overlays.forEach((id,o)=>append(id,index?{SubplotOverlay:[index-1,o]}:{Overlay:o}));
    });
    if(local.config.annotations?.items?.length){const option=document.createElement('option');option.textContent='Annotations';option.value=JSON.stringify('Annotations');layerChoice.append(option);}
    layerChoice.value=previous;layerChoice.hidden=layerChoice.options.length<2;
  }
  layerChoice.addEventListener('change',()=>enqueue(()=>{
    const state=snapshot();(kind?state[kind]:state.config).active_layer=JSON.parse(layerChoice.value);selected=null;install(state);wheelArea=null;commit();
  }));
  let decorationIds=[],inspectorTarget=null,inspectorGeneration=0;
  function properties(refresh=true){
    if(!chart)return;
    if(refresh){local=snapshot();if(kind)decorationIds=JSON.parse(chart.decorations()).map(d=>d.id).filter(id=>id!=='chart_title');}
    layers();selectionProperties();
    const previous=inspectorTarget??selected;select.replaceChildren();
    for(const id of (kind?['chart_title',...decorationIds,...(kind==='radial'?local.radial.slices.map((_,i)=>`slice_0_${i}`):local[kind].series.map(s=>s.id))]:[...ids.map(id=>elementName(id)),...local.series.filter(s=>seriesInActiveLayer(s.series_id)).map(s=>s.series_id)])){const option=document.createElement('option');option.value=id;option.textContent=labels[id.split(':').pop()]??(text(local.series.find(s=>s.series_id===id)?.label)||caption(id));select.append(option);}
    select.value=previous ?? elementName('chart_title');fields.replaceChildren();
    const target=/^(subplot_|overlay_)/.test(select.value)?select.value.split(':').pop():select.value,cfg=configOf(local);
    const series=local.series.find(s=>s.series_id===target);
    function applyProperty(apply,value){
      const before=snapshot(),state=clone(before);
      apply(state,value);
      if(!kind)reconcilePairedAxisEdit({config:configOf(before)},{config:configOf(state)},target);
      install(state);commit();
    }
    function field(label,value,type,apply){
      const row=document.createElement('label');row.append(document.createTextNode(label==='visible'&&target.startsWith('axis_')&&!target.startsWith('axis_title_')?'Axis line':caption(label)));const input=document.createElement('input');input.type=type;input.value=value;input.dataset.property=label;
      input.addEventListener('change',()=>enqueue(()=>{applyProperty(apply,type==='number'?Number(input.value):input.value);}));row.append(input);fields.append(row);return input;
    }
    function color(label,value,find){
      const hex='#'+['r','g','b'].map(k=>Math.round(value[k]*255).toString(16).padStart(2,'0')).join('');
      field(label,hex,'color',(s,v)=>{const c=find(s);['r','g','b'].forEach((k,i)=>c[k]=parseInt(v.slice(i*2+1,i*2+3),16)/255);});
    }
    function choice(label,value,values,apply){
      const row=document.createElement('label');row.append(document.createTextNode(label==='visible'&&target.startsWith('axis_')&&!target.startsWith('axis_title_')?'Axis line':caption(label)));const input=document.createElement('select');input.dataset.property=label;
      for(const v of values){const opt=document.createElement('option');opt.value=v;opt.textContent=label==='label_format'?({Decimal:'Decimal (123.45)',Scientific:'Scientific (1.23e2)',Power:'Power (1.23 × 10²)',Timestamp:'Timestamp (configured)'}[v]):label==='tick_direction'?(v==='None'?'Hidden':v==='Both'?'Both sides':v):v==='Logarithmic'?'Logarithmic (base 10)':v;input.append(opt);}input.value=value;
      input.addEventListener('change',()=>enqueue(()=>{try{applyProperty(apply,input.value);}catch(e){input.value=value;throw e;}}));row.append(input);fields.append(row);
    }
    function scaleControl(label,axis,find,dimension){
      choice(label,axis.scale,['Linear','Logarithmic'],(s,v)=>{
        const a=find(s);
        if(v==='Logarithmic'&&a.min<=0){const r=model.get('state').log_bounds[dimension];[a.min,a.max]=r;}
        a.scale=v;a.major_spacing=v==='Logarithmic'?1:(a.max-a.min)/5;
      });
      const note=document.createElement('p');note.textContent='Log view omits zero and negative values; source data is preserved.';fields.append(note);
    }
    function colorScale(){
      if(!cfg.colorbar)return;
      scaleControl('color_scale',cfg.colorbar.axis,s=>configOf(s).colorbar.axis,'z');
      choice('colormap',cfg.colorbar.colormap,['Viridis','Magma','Turbo','GrayScale','RdBu'],(s,v)=>configOf(s).colorbar.colormap=v);
      field('vmin',cfg.colorbar.axis.min,'number',(s,v)=>configOf(s).colorbar.axis.min=v);
      field('vmax',cfg.colorbar.axis.max,'number',(s,v)=>configOf(s).colorbar.axis.max=v);
      numberFormat(cfg.colorbar.axis.label_style,s=>configOf(s).colorbar.axis.label_style);
    }
    function numberFormat(style,find){
      const current=typeof style.format==='string'?style.format:'Timestamp';
      choice('label_format',current,current==='Timestamp'?['Timestamp','Decimal','Scientific','Power']:['Decimal','Scientific','Power'],(s,v)=>{if(v!=='Timestamp')find(s).format=v;});
      if(current==='Timestamp')return;
      const digits=field('significant_digits',style.significant_digits,'number',(s,v)=>{
        if(!Number.isInteger(v)||v<1||v>15)throw Error('Significant digits must be an integer from 1 to 15');
        find(s).significant_digits=v;
      });digits.min='1';digits.max='15';digits.step='1';
    }
    function toggle(label,value,apply){const row=document.createElement('label');row.append(document.createTextNode(label==='visible'&&target.startsWith('axis_')&&!target.startsWith('axis_title_')?'Axis line':caption(label)));const input=document.createElement('input');input.type='checkbox';input.checked=value;input.dataset.property=label;input.addEventListener('change',()=>enqueue(()=>{applyProperty(apply,input.checked);}));row.append(input);fields.append(row);}
    function syncLegend(state){chart.set_series(JSON.stringify(state.series));chart.reset_legend_from_series_labels();configOf(state).legend.content=JSON.parse(chart.get_config()).legend.content;}
    function richControls(find,key,input){
      function remember(){textRanges.set(key,[Array.from(input.value.slice(0,input.selectionStart)).length,Array.from(input.value.slice(0,input.selectionEnd)).length]);}
      input.addEventListener('select',remember);input.addEventListener('keyup',remember);input.addEventListener('mouseup',remember);
      const bar=document.createElement('div');bar.className='figgy-text-format';
      for(const [flag,label] of [['bold','B'],['italic','I'],['underline','U'],['superscript','x²'],['subscript','x₂'],['greek','αβ']]){
        const button=document.createElement('button');button.textContent=label;button.title=flag;button.dataset.format=flag;button.dataset.textTarget=key;
        const value=find(local).segments,r=textRanges.get(key),range=r&&r[0]!==r[1]?r:[0,value.length];
        button.setAttribute('aria-pressed',String(value.slice(...range).length>0&&value.slice(...range).every(s=>s[flag])));
        button.addEventListener('pointerdown',e=>e.preventDefault());
        button.addEventListener('click',()=>enqueue(()=>{const state=snapshot(),chars=find(state).segments,r=textRanges.get(key),range=r&&r[0]!==r[1]?r:[0,chars.length],part=chars.slice(...range),active=part.length>0&&part.every(s=>s[flag]);for(const char of part){char[flag]=!active;if(!active&&flag==='superscript')char.subscript=false;if(!active&&flag==='subscript')char.superscript=false;}if(key.startsWith('legend_label_'))syncLegend(state);install(state);commit();}));bar.append(button);
      }
      input.parentElement.after(bar);
    }
    function preserve(old,next){let start=0,end=0;while(start<Math.min(old.length,next.length)&&old[start].text===next[start].text){next[start]=clone(old[start]);start++;}while(end<Math.min(old.length,next.length)-start&&old.at(-1-end).text===next.at(-1-end).text){next[next.length-1-end]=clone(old.at(-1-end));end++;}return next;}
    if(kind){
      const c=local[kind];
      field('title',c.title,'text',(s,v)=>{s[kind].title=v;if(s[kind].chart_title)s[kind].chart_title.text.segments=segments(v);});
      field('font_size',c.font_size,'number',(s,v)=>s[kind].font_size=v);
      field('font',c.font_family,'text',(s,v)=>s[kind].font_family=v);
      if(kind==='radial'){
        choice('material',c.style.material,['Flat','Matte','Ceramic','BrushedMetal','Paper','Wood','SatinMetal','Toon','Enamel','Hatch','Pearl'],(s,v)=>s.radial.style.material=v);
        for(const name of ['tilt_degrees','depth','texture_strength','texture_scale','roughness','gloss','gap_degrees','inner_corner','outer_corner'])field(name,c.style[name],'number',(s,v)=>s.radial.style[name]=v);
        toggle('shadow',c.style.shadow,(s,v)=>s.radial.style.shadow=v);
        choice('labels',c.labels,['None','Inside','Outside'],(s,v)=>s.radial.labels=v);
        if(c.kind?.Donut)field('inner_radius',c.kind.Donut.inner_radius,'number',(s,v)=>s.radial.kind.Donut.inner_radius=v);
        const selectedSlice=/^slice_(\d+)_(\d+)$/.exec(target);
        const t=selectedSlice?{group:Number(selectedSlice[1]),index:Number(selectedSlice[2])}:c.interaction.selected;
        if(t){const find=s=>t.group?s.radial.split.children[t.index]:s.radial.slices[t.index];const item=find(local);
          field('label',item.label,'text',(s,v)=>find(s).label=v);field('value',item.value,'number',(s,v)=>find(s).value=v);field('explode',item.explode,'number',(s,v)=>find(s).explode=v);color('color',item.color,s=>find(s).color);
        }
      }else{
        for(const name of (kind==='radar'?[]:['category_title','value_title']))field(name,c[name],'text',(s,v)=>s[kind][name]=v);
        for(const name of ['grid','legend'])toggle(name,c[name],(s,v)=>s[kind][name]=v);
        const item=c.series.find(s=>s.id===target)||c.series.find(s=>s.id===c.selected?.series_id);
        if(item){const find=s=>s[kind].series.find(v=>v.id===item.id);field('label',item.label,'text',(s,v)=>find(s).label=v);color('color',item.color,s=>find(s).color);
          if(c.selected && kind==='categorical'){const i=c.categories.findIndex(v=>v.id===c.selected.category_id);field('value',item.values[i],'number',(s,v)=>find(s).values[i]=v);}
        }
      }
      root.querySelector('[data-settings]').value=JSON.stringify(local,null,2);root.querySelector('[data-code]').value=code();return;
    }
    const visibility=target==='chart_title'?['chart_title','visible']:target==='legend'?['legend','visible']:target==='colorbar'?['colorbar','visible']:target.startsWith('axis_title_')?[side[target.slice(11)],'title_option','visible']:target.startsWith('tick_labels_')?[side[target.slice(12)],'label_style','visible']:target.startsWith('axis_')?[side[target.slice(5)],'line_visible']:null;
    if(visibility){const read=s=>visibility.slice(0,-1).reduce((n,k)=>n?.[k],configOf(s)),isTitle=target==='chart_title'||target.startsWith('axis_title_');if(read(local))toggle('visible',read(local)[visibility.at(-1)]&&(!isTitle||Boolean(text(read(local).text).trim())),(s,v)=>{if(isTitle)titleVisibility(s,target,v);else read(s)[visibility.at(-1)]=v;});}
    let path;
    if(target==='chart_title')path=['chart_title','text'];
    else if(target.startsWith('axis_title_'))path=[side[target.slice(11)],'title_option','text'];
    else if(target==='legend')path=['legend','content'];
    if(path){const find=s=>path.reduce((n,k)=>n[k],configOf(s)),rich=find(local);
      // Show the kernel's text for this node while the browser still holds
      // the kernel's segments (it keeps "10⁻³" as typed).
      const kernel=model.get('state'),same=JSON.stringify(path.reduce((n,k)=>n?.[k],kernel.settings?.config)?.segments)===JSON.stringify(rich.segments);
      const shown=same?(kernel.texts?.[target] ?? text(rich)):text(rich);
      // Titles go through the renderer's title helpers: its super/subscript
      // mapping, and set_title's title-band fit.
      const helper={chart_title:'set_title',axis_title_bottom:'set_x_title',axis_title_left:'set_y_title'}[target];
      if(target==='legend')for(const item of local.series.filter(s=>s.label)){
        const findLabel=s=>s.series.find(v=>v.series_id===item.series_id).label,key=`legend_label_${item.series_id}`;
        const input=field(key,text(item.label),'text',(s,v)=>{findLabel(s).segments=preserve(findLabel(s).segments,segments(v));syncLegend(s);});richControls(findLabel,key,input);
      }
      const textInput=field('text',shown,'text',(s,v)=>{
        if(!helper||local.config.subplots?.length||local.config.overlays?.length){find(s).segments=preserve(find(s).segments,segments(v));return;}
        const old=clone(find(s).segments);chart[helper](v);const live=JSON.parse(chart.get_config());
        if(target==='chart_title')configOf(s).chart_title=live.chart_title;else find(s).segments=path.reduce((n,k)=>n[k],live).segments;find(s).segments=preserve(old,find(s).segments);
      });
      richControls(find,target,textInput);
      field('font_size',rich.font_size,'number',(s,v)=>find(s).font_size=v);color('color',rich.color,s=>find(s).color);
      field('font',rich.font,'text',(s,v)=>find(s).font=v);choice('align',rich.align??'Left',['Left','Center','Right'],(s,v)=>find(s).align=v);
    }else if(series){const kind=Object.keys(series.render_type)[0],style=series.render_type[kind];const find=s=>s.series.find(v=>v.series_id===target).render_type[kind];
      if(style.line){color('color',style.line.line_color,s=>find(s).line.line_color);field('line_width',style.line.line_width,'number',(s,v)=>find(s).line.line_width=v);}
      if(style.scatter){color('color',style.scatter.point_color,s=>find(s).scatter.point_color);field('point_size',style.scatter.point_size,'number',(s,v)=>find(s).scatter.point_size=v);}
      if(style.bar){color('color',style.bar.fill_color,s=>find(s).bar.fill_color);field('border_width',style.bar.border_width,'number',(s,v)=>find(s).bar.border_width=v);}
      if(style.err_style){color('error_color',style.err_style.error_bar_color,s=>find(s).err_style.error_bar_color);field('error_width',style.err_style.error_bar_width,'number',(s,v)=>find(s).err_style.error_bar_width=v);}
      if(style.matrix)colorScale();
    }else if(target==='colorbar'||target.startsWith('colorbar_')){colorScale();
    }else if(target.startsWith('axis_')){const key=side[target.slice(5)];
      scaleControl('axis_scale',cfg[key],s=>configOf(s)[key],key.endsWith('_x')?'x':'y');
      toggle('tick_labels_visible',cfg[key].label_style.visible,(s,v)=>configOf(s)[key].label_style.visible=v);
      toggle('ticks_visible',cfg[key].tick!=='None',(s,v)=>configOf(s)[key].tick=v?'Outside':'None');
      choice('tick_direction',cfg[key].tick,['None','Outside','Inside','Both'],(s,v)=>configOf(s)[key].tick=v);
      numberFormat(cfg[key].label_style,s=>configOf(s)[key].label_style);
      for(const name of ['min','max','major_spacing','line_width'])field(name,cfg[key][name],'number',(s,v)=>{configOf(s)[key][name]=v;});color('color',cfg[key].line_color,s=>configOf(s)[key].line_color);
    }else if(target.startsWith('tick_labels_')){const key=side[target.slice(12)];numberFormat(cfg[key].label_style,s=>configOf(s)[key].label_style);field('font_size',cfg[key].label_style.font_size,'number',(s,v)=>configOf(s)[key].label_style.font_size=v);color('color',cfg[key].label_style.color,s=>configOf(s)[key].label_style.color);field('label_font',cfg[key].label_style.label_font,'text',(s,v)=>configOf(s)[key].label_style.label_font=v);}
    root.querySelector('[data-settings]').value=JSON.stringify(local,null,2);root.querySelector('[data-code]').value=code();
  }
  function displaySize(){const rect=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;return [Math.max(1,Math.round(rect.width*dpr)),Math.max(1,Math.round(rect.height*dpr))];}
  function resizeSurface(){const [width,height]=displaySize();if(canvas.width===width&&canvas.height===height)return false;const previous=[canvas.width,canvas.height];canvas.width=width;canvas.height=height;wheelArea=null;chart.resize(width,height);dirty=true;trace('surface.resized',{previous});return true;}
  function resize(){if(!chart || disposed)return;const [width,height]=displaySize();if(canvas.width!==width||canvas.height!==height)enqueue(resizeSurface);}
  function recordFrame(){if(kind)local=snapshot();else{const r=bounds();/* Selection rectangles include the model's 2px handle padding. */wheelArea=[r[0]+2,r[1]+2,r[2]-4,r[3]-4];}dirty=false;stats.surface_frames++;}
  async function readyDisplayedFrame(){
    if(disposed)throw Error('Widget disposed');
    resizeSurface();
    do{trace('ready_frame.started');await chart.first_frame_ready();trace('ready_frame.completed');if(disposed)throw Error('Widget disposed');recordFrame();}while(resizeSurface());
  }
  const observer=new ResizeObserver(resize);
  const position=e=>{const r=canvas.getBoundingClientRect();return [(e.clientX-r.left)*canvas.width/r.width,(e.clientY-r.top)*canvas.height/r.height];};
  async function waitForFrame(){
    trace('display_wait.started');
    if(frameError)throw frameError;
    await pendingFrame;
    if(disposed)throw Error('Widget disposed');
    if(frameError)throw frameError;
    trace('display_wait.completed');
  }
  function frame(now=0){if(disposed)return;
    if(kind&&chart&&!busy&&!pendingFrame&&!frameError){const decoration=hoverPoint?chart.hit_decoration(...hoverPoint,root.querySelector('[data-area]').checked):null;const p=decoration||pointer?null:hoverPoint;if(chart.hover(p?.[0],p?.[1],Math.min((now-lastFrame)/1000,0.1)))dirty=true;lastFrame=now;}
    if(chart&&dirty&&!busy&&!pendingFrame&&!frameError)enqueue(()=>{
      if(!dirty||pendingFrame||frameError)return;
      try{
        chart.frame();
        trace('display.submitted');
        if(inputAt!==null){stats.last_input_to_submit_ms=performance.now()-inputAt;inputAt=null;}
        recordFrame();
        // GPU completion owns no chart borrow and must not hold the edit/ack
        // queue. Only further display submissions wait for this fence.
        const completion=Promise.resolve(chart.gpu_ready()).catch(e=>{
          frameError=e;trace('display.failed',{error:String(e)});if(!disposed)fail(e);throw e;
        }).finally(()=>{if(pendingFrame===completion)pendingFrame=null;trace('display.settled');});
        pendingFrame=completion;
        completion.catch(()=>{}); // Export/prepare also observe the rejection.
      }catch(e){frameError=e;throw e;}
      // Later edits may set dirty while the GPU runs. Completion never clears it.
    });
    raf=requestAnimationFrame(frame);
  }
  async function exporting(scale=1){trace('export.flush_started',{scale});await flush();trace('export.flush_completed');return enqueue(async()=>{await waitForFrame();stats.png_exports++;trace('export.render_started',{scale});const data=bytes(await chart.export_png(scale));trace('export.render_completed',{bytes:data.byteLength});return data;},true);}
  const download=data=>{const url=URL.createObjectURL(new Blob([data],{type:'image/png'})),a=document.createElement('a');a.href=url;a.download='figure.png';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  function onState(){enqueue(()=>{const state=model.get('state');exportedCode=state.code ?? exportedCode;if(state.revision>revision && !inflight){
    revision=state.revision;pending=null;
    if(!chart){local=clone(state.settings);return;}
    try {install(state.settings);properties();}
    catch(e){fail(e);model.send({action:'rejected',revision,settings:snapshot(),error:String(e)});}
  }});}
  function onMessage(message){
    if(message.client && message.client!==client)return;
    if(message.action==='ack')enqueue(()=>{
      if(message.sequence!==inflight?.sequence)return;
      const latest=pending;inflight=null;revision=message.state.revision;exportedCode=message.state.code ?? exportedCode;
      if(message.error){pending=null;install(message.state.settings);fail(message.error);}
      else if(latest){pending=latest;install(latest);post();}else{install(message.state.settings);}
      properties();idle();
    });
    else if(message.action==='barrier' || message.action==='export' || message.action==='prepare'){
      const request={requestId:message.id,action:message.action};trace('request.received',request);
      // Do not block the serialized queue while waiting for an ack processed by it.
      (async()=>{const requestedAt=performance.now();try{if(message.action==='prepare')startInit();await initialized;trace('request.initialized',request);await queue;trace('request.queue_drained',request);await flush();trace('request.edits_acknowledged',request);let result=null;
        if(message.action==='prepare')result=await enqueue(async()=>{
          const start=performance.now(),stages=[];status.textContent='Preparing…';trace('prepare.started',request);
          try{await waitForFrame();if(kind){await readyDisplayedFrame();stages.push({scope:kind,stage:"first-frame",phase:"Ready"});}else{await chart.prewarm_all_with_progress(event=>{stages.push(event);trace('prepare.prewarm',{...request,event});status.textContent="Preparing…";});await readyDisplayedFrame();}status.textContent='Ready';trace('prepare.completed',request);
            return {backend:'webgpu',ready:true,elapsed_ms:performance.now()-requestedAt,prewarm_ms:performance.now()-start,stages,persistent_cache_supported:false};
          }catch(e){status.textContent='WebGPU failed';throw e;}
        },true);
        const data=message.action==='export'?await exporting(message.scale):null;trace('response.send_started',request);model.send({action:'stats',info:stats});model.send({action:'result',id:message.id,result},{},data?[data]:[]);trace('response.sent',{...request,elapsed_ms:performance.now()-requestedAt});}catch(e){trace('request.failed',{...request,error:String(e)});model.send({action:'result',id:message.id,error:String(e)});}})();
    }
  }
  model.on('change:state',onState);model.on('msg:custom',onMessage);
  // Present the chosen inspector immediately without borrowing the renderer.
  // Apply interaction selection in event order so older keys/picks keep their
  // original target and cannot overwrite a newer pending inspector choice.
  select.addEventListener('change',()=>{
    const target=select.value,generation=++inspectorGeneration;
    inspectorTarget=target;properties(false);
    enqueue(()=>{selected=target;if(generation===inspectorGeneration)inspectorTarget=null;properties();});
  });
  root.querySelector('[data-copy]').addEventListener('click',async()=>{try{await queue;await flush();await enqueue(async()=>{const value=code();root.querySelector('[data-code]').value=value;root.querySelector('[data-code-panel]').open=true;try{await navigator.clipboard.writeText(value);}catch{root.querySelector('[data-code]').select();}},true);}catch(e){fail(e);}});
  root.querySelector('[data-save]').addEventListener('click',()=>{exporting().then(download).catch(fail);});
  root.querySelector('[data-fit]').addEventListener('click',async()=>{
    if(!kind&&(local.config.subplots?.length||local.config.overlays?.length||local.series.some(s=>Object.values(s.render_type)[0].line?.fill))){
      try{await queue;await flush();model.send({action:'fit',revision});}catch(e){fail(e);}return;
    }
    enqueue(async()=>{if(kind){const s=snapshot();s[kind].decorations.data_area=null;if(kind==='boxplot'||kind==='radar')s[kind].value_range=null;install(s);}else await chart.auto_fit_all(local.series.length&&local.series.every(s=>s.render_type.Heatmap||s.render_type.Contour||s.render_type.HeatmapContour)?0:0.05);
      dirty=true;commit();});
  });
  root.querySelector('[data-apply]').addEventListener('click',()=>enqueue(()=>{install(JSON.parse(root.querySelector('[data-settings]').value));commit();}));
  root.querySelector('[data-properties]').addEventListener('click',()=>showProperties(root.querySelector('.figgy-properties').hidden));
  root.querySelector('[data-close-properties]').addEventListener('click',()=>showProperties(false));
  root.querySelector('[data-select]').addEventListener('click',()=>layoutMode(false));
  root.querySelector('[data-layout]').addEventListener('click',()=>layoutMode(true));
  const fullscreen=()=>{if(document.fullscreenElement===root)return document.exitFullscreen();return root.requestFullscreen();};
  root.querySelector('[data-fullscreen]').addEventListener('click',()=>fullscreen().catch(fail));
  const menu=document.createElement('div');menu.className='figgy-menu';menu.hidden=true;root.querySelector('.figgy-toolbar').append(menu);
  let menuKind=null;
  function titleVisibility(state,target,visible){
    const node=target==='chart_title'?state.config.chart_title:state.config[side[target.slice(11)]].title_option;
    node.visible=visible;
    if(!visible)return;
    if(!text(node.text).trim())node.text.segments=segments(labels[target]);
    if(target==='chart_title'){
      // Use the renderer's title-band helper, but preserve all existing rich segments.
      const previous=chart.get_config();
      try{chart.set_config(JSON.stringify(state.config));chart.set_title(text(node.text));node.top_margin=Math.max(node.top_margin,JSON.parse(chart.get_config()).chart_title.top_margin);}
      finally{chart.set_config(previous);}
    }else{
      const axis=state.config[side[target.slice(11)]];
      axis.out_margin=Math.max(axis.out_margin,node.text.font_size*2);
    }
  }
  function openMenu(name){
    if(menuKind===name&&!menu.hidden){menu.hidden=true;return;}
    menuKind=name;menu.replaceChildren();menu.hidden=false;local=snapshot();
    function toggle(label,path,target=null){const row=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.dataset.visibility=label;const node=s=>path.slice(0,-1).reduce((n,k)=>n[k],s);input.checked=node(local)[path.at(-1)]&&(!target||Boolean(text(node(local).text).trim()));input.addEventListener('change',()=>enqueue(()=>{const state=snapshot();if(target)titleVisibility(state,target,input.checked);else node(state)[path.at(-1)]=input.checked;install(state);if(target&&input.checked){selected=target;showProperties();}commit();}));row.append(input,document.createTextNode(label));menu.append(row);}
    if(name==='visibility'){
      if(kind){if(kind!=='radial')for(const key of ['legend','grid'])toggle(key,[kind,key]);else{showProperties();select.value='chart_title';properties();menu.hidden=true;}return;}
      for(const [label,path,target] of [['Chart title',['chart_title','visible'],'chart_title'],['Legend',['legend','visible'],null],...Object.entries(side).map(([k,v])=>[labels[`axis_title_${k}`],[v,'title_option','visible'],`axis_title_${k}`])])toggle(label,['config',...path],target);
    }else if(kind){showProperties();menu.hidden=true;}
    else{
      const specs=model.get('draw_styles'),mode=local.config.draw_style?.mode??'precise';
      for(const name of ['precise','sketch','milkyway','constellation']){const b=document.createElement('button');b.textContent=name;b.dataset.styleMode=name;b.setAttribute('aria-pressed',String(mode===name));
        const types=local.series.map(s=>Object.keys(s.render_type)[0]);b.disabled=name==='sketch'?types.some(t=>['Histogram','Heatmap','Contour','HeatmapContour'].includes(t)):name==='milkyway'?types.some(t=>t!=='Line'):name==='constellation'?types.some(t=>t!=='ScatterLine'):false;
        b.addEventListener('click',()=>enqueue(()=>{const state=snapshot();state.config.draw_style={mode:name,...Object.fromEntries(specs[name].map(p=>[p.key,p.default]))};install(state);commit();menu.hidden=true;openMenu('style');}));menu.append(b);}
      for(const spec of specs[mode]){const row=document.createElement('label'),input=document.createElement('input');input.type='number';input.min=spec.min;input.max=spec.max;input.step=spec.integer?1:.05;input.value=local.config.draw_style[spec.key];input.dataset.styleParameter=spec.key;row.append(document.createTextNode(spec.key.replaceAll('_',' ')),input);input.addEventListener('change',()=>enqueue(()=>{const value=Number(input.value);if(!Number.isFinite(value)||value<spec.min||value>spec.max||(spec.integer&&!Number.isInteger(value)))throw Error(`${spec.key} must be in ${spec.min}..${spec.max}`);const state=snapshot();state.config.draw_style[spec.key]=value;install(state);commit();}));menu.append(row);}
    }
  }
  root.querySelector('[data-style]').addEventListener('click',()=>enqueue(()=>openMenu('style')));
  root.querySelector('[data-visibility]').addEventListener('click',()=>enqueue(()=>openMenu('visibility')));
  root.addEventListener('pointerdown',e=>{if(!menu.contains(e.target)&&!e.target.closest('[data-style],[data-visibility]'))menu.hidden=true;});
  const localPoint=e=>{const [x,y]=position(e);return kind?[x*local.config.chart_area.width/canvas.width,y*local.config.chart_area.height/canvas.height]:[x,y];};
  function bounds(){const value=JSON.parse(chart.decoration_bounds(elementName('data_area')));return value?.rect??[0,0,canvas.width,canvas.height];}
  function navigate(a,factor,anchor,shift=0){
    const log=a.scale==='Logarithmic';let lo=log?Math.log10(a.min):a.min,hi=log?Math.log10(a.max):a.max;
    const span=hi-lo;if(a.inverted){anchor=1-anchor;shift=-shift;}const pivot=lo+span*anchor;
    const low=pivot+(lo-pivot)*factor+shift*span,high=pivot+(hi-pivot)*factor+shift*span;
    a.min=log?10**low:low;a.max=log?10**high:high;
  }
  canvas.addEventListener('pointerdown',e=>{if(!chart||e.button!==0)return;e.preventDefault();canvas.focus({preventScroll:true});canvas.setPointerCapture(e.pointerId);const point=localPoint(e);pointer={point,origin:point,moved:false,pan:false,target:null,handle:null};const gesture=pointer;inputAt=performance.now();enqueue(async()=>{
    const [x,y]=point;
    if(kind){
      gesture.handle=selected?chart.resize_handle(selected,x,y):null;
      gesture.target=gesture.handle?selected:chart.hit_decoration(x,y,root.querySelector('[data-area]').checked);
      selected=gesture.target;
      if(selected)chart.select_decoration(selected);else{const hit=JSON.parse(chart.pick(x,y,true));selected=hit?(kind==='radial'?`slice_${hit.group}_${hit.index}`:hit.series_id):null;}
    }else{
      const hit=chart.hit_test(x,y);selected=hit;stats.last_pointer_hit=hit;
      const area=bounds(),inside=x>=area[0]&&x<=area[0]+area[2]&&y>=area[1]&&y<=area[1]+area[3];
      gesture.pan=(hit===elementName('data_area')||(hit===null&&inside))&&!root.querySelector('[data-area]').checked;
      stats.last_pointer_pan=gesture.pan;
      if((hit===null||gesture.pan)){chart.on_press(-100,-100);chart.on_release();const picked=await chart.pick_data(x,y,6);const identity=picked?JSON.parse(picked):null;const ref=identity?Object.fromEntries(Object.entries(identity).filter(([k])=>k!=='distance_px')):null;
        const old=JSON.parse(chart.get_config()).picked_data?.refs?.[0];const same=ref&&JSON.stringify(ref)===JSON.stringify(old);
        selected=same?null:identity?.series_id??null;chart.set_picked_data(JSON.stringify(!same&&ref?{refs:[ref]}:null));
      }else{chart.set_picked_data('null');chart.on_press(x,y);}
    }
    dirty=true;properties();
  });});
  canvas.addEventListener('pointermove',e=>{if(!chart)return;const next=localPoint(e);hoverPoint=next;if(!pointer)return;const gesture=pointer;inputAt=performance.now();enqueue(()=>{
    const distance=Math.hypot(next[0]-gesture.origin[0],next[1]-gesture.origin[1]);if(distance>=3)gesture.moved=true;
    const old=gesture.point;if(gesture.moved||(!kind&&!gesture.pan))gesture.point=next;
    if(kind){if(gesture.target&&gesture.moved&&(next[0]!==old[0]||next[1]!==old[1]))chart.drag(gesture.target,next[0]-old[0],next[1]-old[1],gesture.handle??undefined);}
    else if(gesture.pan){if(gesture.moved){stats.pan_updates=(stats.pan_updates??0)+1;const s=snapshot(),r=bounds();delete s.config.picked_data;selected=null;for(const k of ['bottom_x','top_x'])navigate(configOf(s)[k],1,.5,-(next[0]-old[0])/r[2]);for(const k of ['left_y','right_y'])navigate(configOf(s)[k],1,.5,(next[1]-old[1])/r[3]);install(s);}}
    else chart.on_move(next[0]-old[0],next[1]-old[1]);dirty=true;
  });});
  function release(){if(!pointer)return;const gesture=pointer;pointer=null;enqueue(()=>{if(!kind)chart.on_release();if(selected&&!gesture.moved)showProperties();commit();});}
  canvas.addEventListener('pointerup',release);canvas.addEventListener('pointercancel',release);canvas.addEventListener('pointerleave',()=>{hoverPoint=null;});
  canvas.addEventListener('wheel',e=>{if(!chart||kind||!wheelArea)return;const point=position(e),a=wheelArea;if(point[0]<a[0]||point[0]>=a[0]+a[2]||point[1]<a[1]||point[1]>=a[1]+a[3])return;e.preventDefault();inputAt=performance.now();const ctrl=e.ctrlKey,shift=e.shiftKey,delta=e.deltaY||e.deltaX;enqueue(()=>{
    const s=snapshot(),r=bounds(),factor=Math.exp(Math.max(-12,Math.min(12,delta/(e.deltaMode===1?1:40)))*.1),x=Math.max(0,Math.min(1,(point[0]-r[0])/r[2])),y=1-Math.max(0,Math.min(1,(point[1]-r[1])/r[3]));
    if(!shift||ctrl)for(const key of ['bottom_x','top_x'])navigate(s.config[key],factor,x);
    if(!ctrl||shift)for(const key of ['left_y','right_y'])navigate(s.config[key],factor,y);
    install(s);commit();
  });},{passive:false});
  canvas.addEventListener('keydown',e=>{if(!chart)return;if(e.key==='F11'){e.preventDefault();fullscreen().catch(fail);return;}if(e.key!=='Escape'&&!e.key.startsWith('Arrow'))return;e.preventDefault();const step=e.shiftKey?10:1;enqueue(()=>{
    if(e.key==='Escape'){selected=null;if(kind)chart.clear_selection();else{chart.set_picked_data('null');chart.on_press(-100,-100);chart.on_release();}}
    else{const dx=e.key==='ArrowLeft'?-step:e.key==='ArrowRight'?step:0,dy=e.key==='ArrowUp'?-step:e.key==='ArrowDown'?step:0;
      if(kind){if(selected&&!selected.startsWith('slice_')&&!local[kind].series?.some(s=>s.id===selected))chart.drag(selected,dx,dy,undefined);else if(dx!==0)chart.step_selection(dx<0);}
      else{const cfg=JSON.parse(chart.get_config());if(cfg.picked_data)chart.step_selection(cfg.picked_data.refs[0]?.kind==='matrix_cell'&&cfg.bottom_x.inverted?-dx:dx,cfg.picked_data.refs[0]?.kind==='matrix_cell'&&cfg.left_y.inverted?dy:-dy);else if(selected){const b=JSON.parse(chart.decoration_bounds(selected));if(b){chart.on_press(b.rect[0]+b.rect[2]/2,b.rect[1]+b.rect[3]/2);chart.on_move(dx,dy);chart.on_release();}}}
    }dirty=true;commit();
  });});
  layoutMode(false);
  model.send({action:'mounted',client});
  (async()=>{try{
    if(!model.get('auto_prepare')){status.textContent='Not prepared';await requested;}
    if(disposed)return;
    await enqueue(async()=>{
    if(!navigator.gpu)throw Error('WebGPU is unavailable. Use a supported browser/secure origin; kernel PNG fallback requires an explicit native Figure.widget(backend="png").');
    if(!kernelModule && !model.get('wasm').byteLength)throw Error('Transfer snapshots were released. Recreate the Figure, or use retain_notebook_data=True before display.');
    const module=await loadKernel(model);if(disposed)return;
    canvas.width=local.config.chart_area.width;canvas.height=local.config.chart_area.height;
    canvas.style.aspectRatio=`${canvas.width}/${canvas.height}`;
    chart=kind?await module.FiggyBoundedChart.create(canvas,kind,JSON.stringify(local[kind]),local.config.chart_area.width,local.config.chart_area.height):await module.FiggyChart.create(canvas);if(!kind)chart.set_pool_auto_growth(true);
    if(!kind){
      const getConfig=chart.get_config.bind(chart),setConfig=chart.set_config.bind(chart);
      let projectedColorbar=false;
      chart.set_config=json=>{
        const config=JSON.parse(json);let projected=false;
        if(!config.colorbar){const bar=config.subplots?.find(p=>p.config.colorbar)?.config.colorbar;if(bar){config.colorbar={...clone(bar),visible:false};projected=true;}}
        setConfig(JSON.stringify(config));projectedColorbar=projected;
      };
      chart.get_config=()=>{const config=JSON.parse(getConfig());if(projectedColorbar)delete config.colorbar;return JSON.stringify(config);};
    }

    if(disposed)return;
    const manifest=model.get('manifest'),buffers=model.get('columns');
    if(manifest.length!==buffers.length)throw Error('Transfer snapshots were released. Recreate the Figure, or use retain_notebook_data=True before display.');
    for(let i=0;i<manifest.length;i++){
      const spec=manifest[i],data=bytes(buffers[i]);
      // wasm-bindgen copies this input into WASM memory; upload creates GPU storage.
      const aligned=data.byteOffset%8===0?data:data.slice();
      if(spec.dtype==='float32')chart.register_column_f32(spec.id,new Float32Array(aligned.buffer,aligned.byteOffset,aligned.byteLength/4));
      else if(spec.dtype==='float64')chart.register_column_f64(spec.id,new Float64Array(aligned.buffer,aligned.byteOffset,aligned.byteLength/8));
      else throw Error(`Unsupported binary dtype: ${spec.dtype}`);
      stats.column_uploads++;stats.binary_upload_bytes+=data.byteLength;
    }
    if(!kind){chart.set_config(JSON.stringify(local.config));chart.set_series(JSON.stringify(local.series));chart.set_config(JSON.stringify(local.config));
    clearColor(local.background);}
    properties();
    // Ready covers the displayed surface, including a resize during compilation.
    // Do not immediately submit a second, unawaited frame at another resolution.
    await readyDisplayedFrame();
    observer.observe(canvas);status.textContent='Ready';
    if(disposed)return;
    controls.forEach(control=>control.disabled=false);
    root.figgy={stats,diagnostics,annotations:()=>enqueue(()=>JSON.parse(chart.annotations()),true),snapshot:()=>clone(local),flush:async()=>{await queue;await flush();},resize,pick:(x,y,distance)=>enqueue(()=>kind?chart.pick(x,y,false):chart.pick_data(x,y,distance),true),decorations:()=>enqueue(()=>kind?JSON.parse(chart.decorations()):Object.fromEntries(ids.map(id=>[id,JSON.parse(chart.decoration_bounds(id))])),true)};
    model.send({action:'ready',client,info:stats});initializedResolve();raf=requestAnimationFrame(frame);
    },true);
  }catch(e){initializedReject(e);if(!disposed){fail(e);status.textContent='WebGPU failed';model.send({action:'failed',error:String(e)});}}})();
  return ()=>{disposed=true;startInit();initializedReject(Error('Widget disposed'));cancelAnimationFrame(raf);observer.disconnect();model.off('change:state',onState);model.off('msg:custom',onMessage);queue.finally(async()=>{try{await pendingFrame;}catch{}chart?.free();chart=null;}).catch(()=>{});model.send({action:'unmounted',client});root.remove();};
}
export default {render};
