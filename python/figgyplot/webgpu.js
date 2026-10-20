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
  root.innerHTML=`<div class="figgy-toolbar"><strong>Figgy</strong>${icon('fit','Fit view')}${icon('select','Select')}${icon('layout','Move or resize plot area')}<button data-draw aria-pressed="false">Draw</button><input data-area type="checkbox" hidden><button data-visibility>Show / hide</button><button data-style>Style</button>${icon('copy','Copy Python')}${icon('save','Save PNG')}${icon('properties','Properties')}${icon('fullscreen','Full screen')}<button data-display-scale title="Use the available width instead of the requested Figure size">Fit width</button><span data-status>Preparing…</span></div><div class="figgy-drawing" hidden><div role="toolbar" aria-label="Annotation drawing tools"><button data-tool="select">Select</button><button data-tool="text">Text</button><button data-tool="arrow">Arrow</button><button data-tool="hline">Horizontal line</button><button data-tool="vline">Vertical line</button><button data-tool="hspan">Horizontal band</button><button data-tool="vspan">Vertical band</button><label><input data-anchor-data type="checkbox">Follow data</label></div><p data-drawing-help></p></div><div class="figgy-body"><div class="figgy-stage"><canvas tabindex="0" aria-label="Editable chart"></canvas><svg class="figgy-drawing-preview" aria-hidden="true"></svg></div><div class="figgy-properties" hidden><header><strong>Properties</strong><button data-close-properties>Close</button></header><section class="figgy-navigator"><div class="figgy-navigator-heading">Objects</div><label class="figgy-search"><input type="search" data-object-search placeholder="Find a panel, axis or series…" aria-label="Find chart objects"></label><div data-object-tree role="tree" aria-label="Chart objects"></div></section><div class="figgy-inspector-scroll"><div data-context class="figgy-context"></div><div data-fields></div><details data-advanced><summary>Advanced settings</summary><textarea data-settings></textarea><button data-apply>Apply settings</button></details><details data-code-panel><summary>Python code</summary><textarea data-code readonly></textarea></details></div></div></div><div data-hint>Click an element to edit · Drag to move · Wheel to zoom · Esc: clear · Arrows: move selection</div><div class="figgy-error" role="alert"></div>`;
  el.append(root);
  const canvas=root.querySelector('canvas'), fields=root.querySelector('[data-fields]');
  let inspectedTarget=null,outlineNodes=clone(model.get('state').outline??[]),boundedView=clone(model.get('state').bounded_view??null);
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
  let drawingTool='select',drawingGesture=null;
  const drawingPalette=root.querySelector('.figgy-drawing'),preview=root.querySelector('.figgy-drawing-preview');
  function drawingSupport(){
    const owner=kind||['Base','Annotations'].includes(local.config.active_layer??'Base');
    const rectangular=kind==='boxplot'||kind==='categorical',horizontal=rectangular&&local[kind].direction==='Horizontal';
    return {owner,axes:kind?(rectangular?[horizontal,!horizontal]:[false,false]):[!local.config.polar,!local.config.polar],data:kind?rectangular:!local.config.polar};
  }
  function drawingUI(){
    const {owner,axes,data}=drawingSupport();
    const axis=drawingTool.startsWith('h')?1:drawingTool.startsWith('v')?0:null;
    if(!owner||(axis!==null&&!axes[axis])){drawingTool='select';drawingGesture=null;preview.replaceChildren();}
    for(const button of root.querySelectorAll('[data-tool]')){
      const name=button.dataset.tool,axis=name.startsWith('h')?1:name.startsWith('v')?0:null;
      button.disabled=name!=='select'&&(!owner||(axis!==null&&!axes[axis]));
      button.title=!owner?'Annotations belong to the root panel; select that panel first.':axis!==null&&!axes[axis]?'This chart has no numeric value axis in this direction.':'';
      button.setAttribute('aria-pressed',String(name===drawingTool));
    }
    const anchor=root.querySelector('[data-anchor-data]');anchor.disabled=!owner||!data;if(anchor.disabled)anchor.checked=false;
    root.querySelector('[data-drawing-help]').textContent=!owner?'Select the root panel to draw annotations.':drawingTool==='select'?'Choose a tool. Select an annotation in the chart or object tree to edit.':drawingTool==='text'?'Click to place text, then edit it in Properties. Esc: cancel.':'Drag to draw. Release to create and edit. Esc: cancel. Follow data: move with axis ranges.';
    canvas.style.cursor=drawingTool==='select'?'':'crosshair';
    root.querySelector('[data-select]').setAttribute('aria-pressed',String(drawingTool==='select'&&!root.querySelector('[data-area]').checked));
    root.querySelector('[data-layout]').setAttribute('aria-pressed',String(drawingTool==='select'&&root.querySelector('[data-area]').checked));
  }
  function cancelDrawing(){drawingGesture=null;drawingTool='select';preview.replaceChildren();drawingUI();}
  function previewDrawing(){
    preview.setAttribute('viewBox',`0 0 ${canvas.width} ${canvas.height}`);preview.replaceChildren();
    const g=drawingGesture;if(!g)return;const [x,y]=g.start,[u,v]=g.end,[ax,ay,w,h]=g.area;
    const node=(name,attrs)=>{const n=document.createElementNS('http://www.w3.org/2000/svg',name);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,String(v));preview.append(n);return n;};
    if(g.tool==='text'){node('text',{x:u,y:v,'font-size':16}).textContent='Text';}
    else if(g.tool==='hspan'||g.tool==='vspan')node('rect',g.tool==='hspan'?{x:ax,y:Math.min(y,v),width:w,height:Math.abs(v-y),fill:'#2663ad33'}:{x:Math.min(x,u),y:ay,width:Math.abs(u-x),height:h,fill:'#2663ad33'});
    else {const a=g.tool==='hline'?[ax,v,ax+w,v]:g.tool==='vline'?[u,ay,u,ay+h]:[x,y,u,v];node('line',{x1:a[0],y1:a[1],x2:a[2],y2:a[3],stroke:'#2663ad','stroke-width':1.5});if(g.tool==='arrow'){const t=Math.atan2(v-y,u-x);node('polyline',{points:`${u-10*Math.cos(t-.45)},${v-10*Math.sin(t-.45)} ${u},${v} ${u-10*Math.cos(t+.45)},${v-10*Math.sin(t+.45)}`,stroke:'#2663ad',fill:'none'});}}
  }
  function drawingArea(){return kind?JSON.parse(chart.decorations()).find(d=>d.id==='data_area')?.rect:bounds();}
  function finishDrawing(g){
    if(g.cancelled||g!==drawingGesture)return;
    if(/^[hv]/.test(g.tool)){const [x,y,w,h]=g.area;g.end=[Math.max(x,Math.min(x+w,g.end[0])),Math.max(y,Math.min(y+h,g.end[1]))];}const [x,y]=g.start,[u,v]=g.end;if(['arrow','hspan','vspan'].includes(g.tool)&&Math.hypot(u-x,v-y)<3){cancelDrawing();return;}
    const anchor=p=>JSON.parse(chart.pointer_to_anchor(...p,g.data?'Data':'Ratio'));
    const start=anchor(g.start),end=anchor(g.end);if(!start||!end)throw Error('This chart does not support these annotation coordinates.');
    const line={color:{r:.235,g:.235,b:.235,a:1},width:1.5,style:'Solid'},rich={segments:segments('Text'),color:{r:.137,g:.176,b:.235,a:1},font_size:16,font:''};let geometry;
    if(g.tool==='text')geometry={Text:{anchor:end,text:rich,box_style:null}};
    else if(g.tool==='arrow')geometry={Arrow:{from:start,to:end,style:{line,head_length:10,head_width:8},text:null}};
    else {const axis=g.tool.startsWith('h')?'Y':'X',key=axis==='X'?'x':'y',a=JSON.parse(chart.pointer_to_anchor(x,y,'Data'))?.Data?.[key],b=JSON.parse(chart.pointer_to_anchor(u,v,'Data'))?.Data?.[key];if(!Number.isFinite(a)||!Number.isFinite(b))throw Error('This direction has no value axis.');
      if(g.tool.endsWith('line'))geometry={ReferenceLine:{axis,value:b,style:line,label:null}};else{if(a===b){cancelDrawing();return;}geometry={Span:{axis,from:Math.min(a,b),to:Math.max(a,b),fill:{r:.149,g:.388,b:.678,a:.176}}};}}
    const item={id:`annotation_${crypto.randomUUID()}`,kind:geometry};
    chart.add_annotation(JSON.stringify(item));chart.set_annotations_visible(true);chart.set_active_layer(JSON.stringify('Annotations'));
    const state=snapshot(),index=(kind?state[kind]:state.config).annotations.items.length-1;chart.select_annotation(index);
    selected=kind?`annotation_${index}`:`annotation:${item.id}`;inspectorTarget=null;inspectorLayer=null;
    cancelDrawing();showProperties();dirty=true;commit();
    if(g.tool==='text')requestAnimationFrame(()=>{const input=root.querySelector('[data-property=text]');input?.focus();input?.select();});
  }
  root.querySelector('[data-draw]').addEventListener('click',e=>{drawingPalette.hidden=!drawingPalette.hidden;e.currentTarget.setAttribute('aria-pressed',String(!drawingPalette.hidden));cancelDrawing();});
  for(const button of root.querySelectorAll('[data-tool]'))button.addEventListener('click',()=>{cancelDrawing();drawingTool=button.dataset.tool;layoutMode(false);drawingUI();canvas.focus();});
  root.addEventListener('keydown',e=>{if(e.key==='Escape'&&drawingTool!=='select'){e.preventDefault();e.stopPropagation();cancelDrawing();}},true);
  canvas.addEventListener('lostpointercapture',()=>{if(drawingGesture&&!drawingGesture.released)cancelDrawing();});
  function rendererTarget(target){if(kind||!target?.startsWith('annotation:'))return target;const index=local.config.annotations?.items?.findIndex(v=>'annotation:'+v.id===target);return index>=0?`annotation_${index}`:target;}
  function hostTarget(target){if(kind)return target;const index=/^annotation_(\d+)$/.exec(target??'')?.[1],item=index===undefined?null:local.config.annotations?.items?.[Number(index)];return item?'annotation:'+item.id:target;}

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
  const tree=root.querySelector('[data-object-tree]'),search=root.querySelector('[data-object-search]');
  const expanded=new Map();let treeSelection=null,lastTreeSignature='';
  const layerOf=state=>(kind?state[kind]:state.config).active_layer??'Base';
  const sameLayer=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  function allNodes(nodes=outlineNodes,path=[]){return nodes.flatMap(node=>[{node,path:[...path,node]},...allNodes(node.children,[...path,node])]);}
  function navigateTree(reveal=false){
    const layer=inspectorLayer??layerOf(local),target=inspectorTarget??selected??(layer==='Annotations'?null:elementName('chart_title'));
    let entry=allNodes().find(v=>v.node.target===target&&sameLayer(v.node.layer,layer));
    const signature=JSON.stringify([layer,target]);
    if(signature!==lastTreeSignature){
      if(entry){for(const ancestor of entry.path)expanded.set(ancestor.key,true);if(!inspectorTarget)search.value='';}
      lastTreeSignature=signature;reveal=true;
    }
    treeSelection=entry?.node.key??null;
    const query=search.value.trim().toLowerCase(),focusKey=tree.contains(document.activeElement)?document.activeElement.closest('[data-node]')?.dataset.node:null;
    const scroll=tree.scrollTop;tree.replaceChildren();
    const matches=node=>!query||`${node.label} ${node.kind} ${node.key.split('/').at(-1)}`.toLowerCase().includes(query)||node.children.some(matches);
    const visit=(nodes,depth)=>{for(const node of nodes){
      if(!matches(node))continue;
      const open=Boolean(query)||(expanded.get(node.key)??!node.collapsed);
      const row=document.createElement('div');row.className='figgy-tree-row';row.dataset.node=node.key;row.setAttribute('role','treeitem');row.setAttribute('aria-level',depth+1);row.setAttribute('aria-selected',String(node.key===treeSelection));row.tabIndex=-1;row.title=`${node.kind} · ${node.key}`;
      row.style.setProperty('--depth',depth);if(!node.visible)row.classList.add('figgy-object-hidden');
      if(node.target!==null)row.dataset.object=node.target;
      row.dataset.layer=JSON.stringify(node.layer);
      const toggle=document.createElement('button');toggle.className='figgy-tree-toggle';toggle.tabIndex=-1;toggle.textContent=node.children.length?(open?'▾':'▸'):'';toggle.disabled=!node.children.length;
      if(node.children.length){row.setAttribute('aria-expanded',String(Boolean(open)));toggle.setAttribute('aria-label',`${open?'Collapse':'Expand'} ${node.label}`);}
      toggle.addEventListener('click',e=>{e.stopPropagation();expanded.set(node.key,!open);navigateTree();});
      const label=document.createElement('span');label.className='figgy-tree-label';label.textContent=node.label;
      const type=document.createElement('span');type.className='figgy-tree-kind';type.textContent=['group','element','figure'].includes(node.kind)?'':node.kind;
      row.append(toggle,label,type);row.addEventListener('click',()=>{row.focus({preventScroll:true});if(node.target!==null||node.kind==='layer')chooseObject(node);else{expanded.set(node.key,!open);navigateTree();}});
      row.addEventListener('keydown',event=>{
        const rows=[...tree.querySelectorAll('[role=treeitem]')],index=rows.indexOf(row);
        if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();const next=rows[Math.max(0,Math.min(rows.length-1,index+(event.key==='ArrowDown'?1:-1)))];next.focus();return;}
        if(event.key==='ArrowRight'||event.key==='ArrowLeft'){event.preventDefault();expanded.set(node.key,event.key==='ArrowRight');navigateTree();return;}
        if(event.key==='Enter'||event.key===' '){event.preventDefault();if(node.target!==null||node.kind==='layer')chooseObject(node);else{expanded.set(node.key,!open);navigateTree();}}
        if(event.key==='Escape'){event.preventDefault();canvas.focus();}
      });
      tree.append(row);if(open)visit(node.children,depth+1);
    }};
    visit(outlineNodes,0);
    if(!tree.children.length){const empty=document.createElement('p');empty.className='figgy-empty';empty.textContent='No matching objects';tree.append(empty);}
    const rows=[...tree.querySelectorAll('[role=treeitem]')],active=rows.find(r=>r.dataset.node===treeSelection);
    (active??rows[0])?.setAttribute('tabindex','0');tree.scrollTop=scroll;
    if(focusKey)rows.find(r=>r.dataset.node===focusKey)?.focus({preventScroll:true});
    if(reveal&&active)active.scrollIntoView({block:'nearest',inline:'nearest'});
    const context=root.querySelector('[data-context]');context.textContent=entry?entry.path.slice(1).map(n=>n.label).join(' / '):'Click an object in the chart or tree';context.dataset.target=target??'';
  }
  search.addEventListener('input',()=>navigateTree());
  search.addEventListener('keydown',e=>{if(e.key==='ArrowDown'){e.preventDefault();const q=search.value.toLowerCase(),entry=allNodes().find(({node:n})=>n.target!==null&&`${n.label} ${n.kind} ${n.key.split('/').at(-1)}`.toLowerCase().includes(q));(entry?[...tree.querySelectorAll('[role=treeitem]')].find(r=>r.dataset.node===entry.node.key):tree.querySelector('[role=treeitem]'))?.focus();}if(e.key==='Escape'){search.value='';navigateTree();canvas.focus();}});
  function chooseObject(node){
    const target=node.target,generation=++inspectorGeneration;
    if(node.kind==='panel')expanded.set(node.key,true);
    inspectorTarget=target;inspectorLayer=node.layer;showProperties();properties(false);
    enqueue(()=>{
      if(!sameLayer(layerOf(snapshot()),node.layer)){
        const state=snapshot();(kind?state[kind]:state.config).active_layer=clone(node.layer);if(!kind)state.config.picked_data=null;install(state);wheelArea=null;
      }
      selected=target;
      if(kind){const dataTarget=/^slice_/.test(target??'')||local[kind].series?.some(v=>v.id===target);if(dataTarget){chart.clear_selection();}else if(target)chart.select_decoration(target);else chart.clear_selection();}
      else if(target?.startsWith('annotation:')){chart.select_annotation(local.config.annotations.items.findIndex(v=>'annotation:'+v.id===target));}
      else if(!local.series.some(s=>s.series_id===target)){const bound=target?JSON.parse(chart.decoration_bounds(rendererTarget(target))):null;if(bound){chart.on_press(bound.rect[0]+bound.rect[2]/2,bound.rect[1]+bound.rect[3]/2);chart.on_release();}}
      if(generation===inspectorGeneration){inspectorTarget=null;inspectorLayer=null;}
      dirty=true;commit();
    });
  }
  let decorationIds=[],inspectorTarget=null,inspectorLayer=null,inspectorGeneration=0;
  function properties(refresh=true){
    if(!chart)return;
    if(refresh){local=snapshot();if(kind)decorationIds=JSON.parse(chart.decorations()).map(d=>d.id).filter(id=>id!=='chart_title');}
    drawingUI();navigateTree();selectionProperties();
    inspectedTarget=inspectorTarget??selected??elementName('chart_title');fields.replaceChildren();
    if(layerOf(local)==='Annotations'&&selected===null&&inspectorTarget===null){const hint=document.createElement('p');hint.textContent='Choose an annotation in the tree or click it in the chart.';fields.append(hint);return;}
    if(inspectorLayer&&!sameLayer(inspectorLayer,layerOf(local))){const pending=document.createElement('p');pending.textContent='Selecting object…';fields.append(pending);return;}
    const target=/^(subplot_|overlay_)/.test(inspectedTarget)?inspectedTarget.split(':').pop():inspectedTarget,cfg=configOf(local);
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
    const annotationIndex=kind?Number(/^annotation_(\d+)$/.exec(target)?.[1]??NaN):local.config.annotations?.items?.findIndex(v=>'annotation:'+v.id===target);
    if(Number.isInteger(annotationIndex)&&annotationIndex>=0){
      const owner=s=>kind?s[kind]:s.config,find=s=>owner(s).annotations.items[annotationIndex],item=find(local),name=Object.keys(item.kind)[0],geometry=item.kind[name],shape=s=>find(s).kind[name];
      toggle('visible',item.visible!==false,(s,v)=>find(s).visible=v);
      for(const key of (name==='ReferenceLine'?['value']:name==='Span'?['from','to']:[]))field(key,geometry[key],'number',(s,v)=>shape(s)[key]=v);
      for(const key of ['anchor','from','to'])if(geometry[key]&&typeof geometry[key]==='object'){
        const unit=Object.keys(geometry[key])[0];if(!geometry[key][unit]||typeof geometry[key][unit]!=='object')continue;
        const note=document.createElement('p');note.textContent=`${caption(key)} · ${unit.toLowerCase()} coordinates`;fields.append(note);
        for(const dimension of ['x','y'])field(`${key}_${dimension}`,geometry[key][unit][dimension],'number',(s,v)=>shape(s)[key][unit][dimension]=v);
      }
      const textKey=name==='ReferenceLine'?'label':'text';
      if(name==='Arrow'||name==='ReferenceLine')toggle('show_label',!!geometry[textKey],(s,v)=>shape(s)[textKey]=v?{segments:segments('Label'),color:{r:.15,g:.18,b:.23,a:1},font_size:16,font:''}:null);
      if(geometry[textKey]){const findText=s=>shape(s)[textKey];const input=field('text',text(geometry[textKey]),'text',(s,v)=>findText(s).segments=preserve(findText(s).segments,segments(v)));richControls(findText,inspectedTarget,input);
      field('font_size',geometry[textKey].font_size,'number',(s,v)=>shape(s)[textKey].font_size=v);color('text_color',geometry[textKey].color,s=>shape(s)[textKey].color);}
      if(geometry.fill){color('fill',geometry.fill,s=>shape(s).fill);field('opacity',geometry.fill.a,'number',(s,v)=>shape(s).fill.a=v);}
      const style=name==='Arrow'?geometry.style?.line:geometry.style,styleOf=s=>name==='Arrow'?shape(s).style.line:shape(s).style;
      if(style){color('color',style.color,s=>styleOf(s).color);field('line_width',style.width,'number',(s,v)=>styleOf(s).width=v);}
      if(name==='Arrow')for(const key of ['head_length','head_width'])field(key,geometry.style[key],'number',(s,v)=>shape(s).style[key]=v);
      if(style)choice('line_style',style.style,['Solid','Dash','Dot','DashDot','DashDotDot','ShortDash','ShortDot','ShortDashDot','LongDash','LongDashDot','LongDashDotDot'],(s,v)=>styleOf(s).style=v);
      if(name==='Text'){toggle('text_box',!!geometry.box_style,(s,v)=>shape(s).box_style=v?{fill:{r:1,g:1,b:1,a:.9},border_color:{r:.23,g:.23,b:.23,a:1},border_width:1,padding:4}:null);if(geometry.box_style){color('box_fill',geometry.box_style.fill,s=>shape(s).box_style.fill);color('border_color',geometry.box_style.border_color,s=>shape(s).box_style.border_color);for(const key of ['border_width','padding'])field(key,geometry.box_style[key],'number',(s,v)=>shape(s).box_style[key]=v);}}
      const remove=document.createElement('button');remove.textContent='Delete annotation';remove.dataset.deleteAnnotation='';remove.addEventListener('click',()=>enqueue(()=>{const state=snapshot();owner(state).annotations.items.splice(annotationIndex,1);if(kind)state[kind].decorations.selected=null;selected=null;inspectorTarget=null;install(state);commit();}));fields.prepend(remove);
      root.querySelector('[data-settings]').value=JSON.stringify(local,null,2);return;
    }
    if(kind){
      const c=local[kind];
      if(boundedView){
        const range=c.value_range??boundedView.range;
        const heading=document.createElement('strong');heading.textContent=boundedView.axis==='radius'?'Radial range':'Value axis range';fields.append(heading);
        toggle('auto_range',c.value_range==null,(s,v)=>s[kind].value_range=v?null:clone(range));
        for(const [i,name] of ['range_min','range_max'].entries())field(name,range[i],'number',(s,v)=>{s[kind].value_range=clone(s[kind].value_range??range);s[kind].value_range[i]=v;});
        const hint=document.createElement('p');hint.textContent='Wheel over plot: zoom values · Fit: automatic range';fields.append(hint);
      }
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
      richControls(find,inspectedTarget,textInput);
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
  function onState(){enqueue(()=>{const state=model.get('state');outlineNodes=clone(state.outline??outlineNodes);boundedView=clone(state.bounded_view??boundedView);exportedCode=state.code ?? exportedCode;if(state.revision>revision && !inflight){
    revision=state.revision;pending=null;
    if(!chart){local=clone(state.settings);return;}
    try {install(state.settings);properties();}
    catch(e){fail(e);model.send({action:'rejected',revision,settings:snapshot(),error:String(e)});}
  }});}
  function onMessage(message){
    if(message.client && message.client!==client)return;
    if(message.action==='ack')enqueue(()=>{
      if(message.sequence!==inflight?.sequence)return;
      outlineNodes=clone(message.state.outline??outlineNodes);boundedView=clone(message.state.bounded_view??boundedView);const latest=pending;inflight=null;revision=message.state.revision;exportedCode=message.state.code ?? exportedCode;
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
  root.querySelector('[data-select]').addEventListener('click',()=>{cancelDrawing();layoutMode(false);});
  root.querySelector('[data-layout]').addEventListener('click',()=>{cancelDrawing();layoutMode(true);});
  root.querySelector('[data-display-scale]').addEventListener('click',event=>{const fit=root.dataset.displayScale!=='fit';root.dataset.displayScale=fit?'fit':'actual';event.currentTarget.textContent=fit?'Actual size':'Fit width';resize();});
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
      if(kind){if(kind!=='radial')for(const key of ['legend','grid'])toggle(key,[kind,key]);else{showProperties();selected='chart_title';properties();menu.hidden=true;}return;}
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
  canvas.addEventListener('pointerdown',e=>{if(!chart||e.button!==0)return;e.preventDefault();canvas.focus({preventScroll:true});canvas.setPointerCapture(e.pointerId);const point=localPoint(e);
    if(drawingTool!=='select'){
      const g={tool:drawingTool,start:point,end:point,data:root.querySelector('[data-anchor-data]').checked,area:[0,0,canvas.width,canvas.height]};drawingGesture=g;
      enqueue(()=>{if(g!==drawingGesture)return;g.area=drawingArea()??g.area;const [x,y,w,h]=g.area;if(/^[hv]/.test(g.tool)&&(g.start[0]<x||g.start[0]>x+w||g.start[1]<y||g.start[1]>y+h)){cancelDrawing();return;}previewDrawing();});return;
    }
    pointer={point,origin:point,moved:false,pan:false,target:null,handle:null};const gesture=pointer;inputAt=performance.now();enqueue(async()=>{
    const [x,y]=point;
    if(!kind&&local.config.subplots?.length){
      const width=Math.max(local.config.chart_area.x+local.config.chart_area.width,...local.config.subplots.map(p=>p.config.chart_area.x+p.config.chart_area.width)),scale=canvas.width/width;
      const contains=r=>x>=r.x*scale&&y>=r.y*scale&&x<(r.x+r.width)*scale&&y<(r.y+r.height)*scale;
      const index=local.config.subplots.findIndex(p=>contains(p.config.chart_area)),current=local.config.active_layer?.Subplot??local.config.active_layer?.SubplotOverlay?.[0]??-1;
      if(index!==current&&(index>=0||contains(local.config.chart_area))){const state=snapshot();state.config.active_layer=index<0?'Base':{Subplot:index};state.config.picked_data=null;install(state);wheelArea=null;}
    }
    if(kind){
      gesture.handle=selected?chart.resize_handle(selected,x,y):null;
      gesture.target=gesture.handle?selected:chart.hit_decoration(x,y,root.querySelector('[data-area]').checked);
      selected=gesture.target;
      if(selected)chart.select_decoration(selected);else{const hit=JSON.parse(chart.pick(x,y,true));selected=hit?(kind==='radial'?`slice_${hit.group}_${hit.index}`:hit.series_id):null;}
    }else{
      const hit=chart.hit_test(x,y);selected=hostTarget(hit);stats.last_pointer_hit=hit;
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
  canvas.addEventListener('pointermove',e=>{if(!chart)return;const next=localPoint(e);hoverPoint=next;if(drawingGesture){drawingGesture.end=next;previewDrawing();return;}if(!pointer)return;const gesture=pointer;inputAt=performance.now();enqueue(()=>{
    const distance=Math.hypot(next[0]-gesture.origin[0],next[1]-gesture.origin[1]);if(distance>=3)gesture.moved=true;
    const old=gesture.point;if(gesture.moved||(!kind&&!gesture.pan))gesture.point=next;
    if(kind){if(gesture.target&&gesture.moved&&(next[0]!==old[0]||next[1]!==old[1]))chart.drag(gesture.target,next[0]-old[0],next[1]-old[1],gesture.handle??undefined);}
    else if(gesture.pan){if(gesture.moved){stats.pan_updates=(stats.pan_updates??0)+1;const s=snapshot(),r=bounds();delete s.config.picked_data;selected=null;for(const k of ['bottom_x','top_x'])navigate(configOf(s)[k],1,.5,-(next[0]-old[0])/r[2]);for(const k of ['left_y','right_y'])navigate(configOf(s)[k],1,.5,(next[1]-old[1])/r[3]);install(s);}}
    else chart.on_move(next[0]-old[0],next[1]-old[1]);dirty=true;
  });});
  function release(e){if(drawingGesture){const g=drawingGesture;if(e.type==='pointercancel'){cancelDrawing();return;}g.end=localPoint(e);g.released=true;enqueue(()=>finishDrawing(g));return;}if(!pointer)return;const gesture=pointer;pointer=null;enqueue(()=>{if(!kind)chart.on_release();if(selected&&!gesture.moved)showProperties();commit();});}
  canvas.addEventListener('pointerup',release);canvas.addEventListener('pointercancel',release);canvas.addEventListener('pointerleave',()=>{hoverPoint=null;});
  canvas.addEventListener('wheel',e=>{
    if(chart&&kind&&boundedView){
      const horizontal=boundedView.axis==='x';if(horizontal?e.shiftKey&&!e.ctrlKey:e.ctrlKey&&!e.shiftKey)return;
      e.preventDefault();const point=localPoint(e),delta=e.deltaY||e.deltaX;
      enqueue(()=>{
        const area=JSON.parse(chart.decorations()).find(d=>d.id==='data_area')?.rect;if(!area)return;
        const [x,y,w,h]=area;if(point[0]<x||point[0]>x+w||point[1]<y||point[1]>y+h)return;
        const state=snapshot(),range=state[kind].value_range??boundedView.range;
        const anchor=boundedView.axis==='radius'?0:horizontal?(point[0]-x)/w:1-(point[1]-y)/h,pivot=range[0]+(range[1]-range[0])*anchor;
        const factor=Math.exp(Math.max(-12,Math.min(12,delta/(e.deltaMode===1?1:40)))*.1);
        state[kind].value_range=range.map(v=>pivot+(v-pivot)*factor);install(state);commit();
      });return;
    }
    if(!chart||kind||!wheelArea)return;const point=position(e),a=wheelArea;if(point[0]<a[0]||point[0]>=a[0]+a[2]||point[1]<a[1]||point[1]>=a[1]+a[3])return;e.preventDefault();inputAt=performance.now();const ctrl=e.ctrlKey,shift=e.shiftKey,delta=e.deltaY||e.deltaX;enqueue(()=>{
    const s=snapshot(),r=bounds(),factor=Math.exp(Math.max(-12,Math.min(12,delta/(e.deltaMode===1?1:40)))*.1),x=Math.max(0,Math.min(1,(point[0]-r[0])/r[2])),y=1-Math.max(0,Math.min(1,(point[1]-r[1])/r[3]));
    if(!shift||ctrl)for(const key of ['bottom_x','top_x'])navigate(s.config[key],factor,x);
    if(!ctrl||shift)for(const key of ['left_y','right_y'])navigate(s.config[key],factor,y);
    install(s);commit();
  });},{passive:false});
  canvas.addEventListener('keydown',e=>{if(!chart)return;if(e.key==='F11'){e.preventDefault();fullscreen().catch(fail);return;}if(drawingTool!=='select')return;if((e.key==='Delete'||e.key==='Backspace')&&selected&&(selected.startsWith('annotation:')||/^annotation_\d+$/.test(selected))){e.preventDefault();enqueue(()=>{const s=snapshot(),owner=kind?s[kind]:s.config,index=kind?Number(selected.slice(11)):owner.annotations.items.findIndex(v=>'annotation:'+v.id===selected);if(index>=0)owner.annotations.items.splice(index,1);if(kind)owner.decorations.selected=null;selected=null;install(s);commit();});return;}if(e.key!=='Escape'&&!e.key.startsWith('Arrow'))return;e.preventDefault();const step=e.shiftKey?10:1;enqueue(()=>{
    if(e.key==='Escape'){selected=null;if(kind)chart.clear_selection();else{chart.set_picked_data('null');chart.on_press(-100,-100);chart.on_release();}}
    else{const dx=e.key==='ArrowLeft'?-step:e.key==='ArrowRight'?step:0,dy=e.key==='ArrowUp'?-step:e.key==='ArrowDown'?step:0;
      if(kind){if(selected&&!selected.startsWith('slice_')&&!local[kind].series?.some(s=>s.id===selected))chart.drag(selected,dx,dy,undefined);else if(dx!==0)chart.step_selection(dx<0);}
      else{const cfg=JSON.parse(chart.get_config());if(cfg.picked_data)chart.step_selection(cfg.picked_data.refs[0]?.kind==='matrix_cell'&&cfg.bottom_x.inverted?-dx:dx,cfg.picked_data.refs[0]?.kind==='matrix_cell'&&cfg.left_y.inverted?dy:-dy);else if(selected?.startsWith('annotation:')){const index=local.config.annotations.items.findIndex(v=>'annotation:'+v.id===selected);if(index>=0)chart.drag_annotation(index,dx,dy,undefined);}else if(selected){const b=JSON.parse(chart.decoration_bounds(rendererTarget(selected)));if(b){chart.on_press(b.rect[0]+b.rect[2]/2,b.rect[1]+b.rect[3]/2);chart.on_move(dx,dy);chart.on_release();}}}
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
    const rectangles=[local.config.chart_area,...(local.config.subplots??[]).map(p=>p.config.chart_area)];
    const documentWidth=Math.max(...rectangles.map(r=>r.x+r.width)),documentHeight=Math.max(...rectangles.map(r=>r.y+r.height));
    root.style.setProperty('--figgy-document-width',`${documentWidth}px`);
    canvas.width=documentWidth;canvas.height=documentHeight;
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
    controls.forEach(control=>control.disabled=false);drawingUI();
    root.figgy={stats,diagnostics,annotations:()=>enqueue(()=>JSON.parse(chart.annotations()),true),snapshot:()=>clone(local),flush:async()=>{await queue;await flush();},resize,pick:(x,y,distance)=>enqueue(()=>kind?chart.pick(x,y,false):chart.pick_data(x,y,distance),true),decorations:()=>enqueue(()=>kind?JSON.parse(chart.decorations()):Object.fromEntries(ids.map(id=>[id,JSON.parse(chart.decoration_bounds(id))])),true)};
    model.send({action:'ready',client,info:stats});initializedResolve();raf=requestAnimationFrame(frame);
    },true);
  }catch(e){initializedReject(e);if(!disposed){fail(e);status.textContent='WebGPU failed';model.send({action:'failed',error:String(e)});}}})();
  return ()=>{disposed=true;startInit();initializedReject(Error('Widget disposed'));cancelAnimationFrame(raf);observer.disconnect();model.off('change:state',onState);model.off('msg:custom',onMessage);queue.finally(async()=>{try{await pendingFrame;}catch{}chart?.free();chart=null;}).catch(()=>{});model.send({action:'unmounted',client});root.remove();};
}
export default {render};
