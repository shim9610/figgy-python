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
const labels={chart_title:'Chart title',data_area:'Plot area',legend:'Legend',colorbar:'Color scale',colorbar_axis:'Color scale axis',colorbar_tick_labels:'Color scale labels',colorbar_title:'Color scale title',axis_scale:'Scale',color_scale:'Scale',axis_bottom:'X axis',axis_left:'Y axis',axis_top:'Top axis',axis_right:'Right axis',axis_title_bottom:'X axis title',axis_title_left:'Y axis title',axis_title_top:'Top axis title',axis_title_right:'Right axis title',tick_labels_bottom:'X tick labels',tick_labels_left:'Y tick labels',tick_labels_top:'Top tick labels',tick_labels_right:'Right tick labels',ticks_visible:'Tick marks',tick_labels_visible:'Tick labels',tick_direction:'Tick direction',label_format:'Number format',significant_digits:'Significant digits',auto_ticks:'Automatic tick spacing',font_size:'Font size',font:'Font family',line_width:'Line width'};
const caption=key=>labels[key]??key.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
export function render({model,el}) {
  const root=document.createElement('div');root.className='figgy-editor figgy-webgpu';
  const paths={fit:'M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5M4 4l5 5m11-5-5 5m5 11-5-5M4 20l5-5',select:'M6 3v17l5-5 4 7 3-2-4-6h7Z',layout:'M12 2v20M2 12h20M8 6l4-4 4 4M8 18l4 4 4-4M6 8l-4 4 4 4M18 8l4 4-4 4',copy:'M8 3h9l4 4v14H8ZM8 7H3v14h2M13 11l-2 3 2 3m3-6 2 3-2 3',save:'M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4',properties:'M3 5h18M3 12h18M3 19h18M8 2v6M16 9v6M10 16v6',fullscreen:'M3 9V3h6M15 3h6v6M21 15v6h-6M9 21H3v-6'};
  const icon=(name,label)=>`<button data-${name} title="${label}" aria-label="${label}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]}"/></svg></button>`;
  root.innerHTML=`<div class="figgy-toolbar"><strong>Figgy</strong><button data-undo title="Undo chart edit (Ctrl/Cmd+Z)">Undo</button><button data-redo title="Redo chart edit (Ctrl/Cmd+Shift+Z)">Redo</button>${icon('fit','Fit view')}${icon('select','Select')}${icon('layout','Move or resize plot area')}<button data-draw aria-pressed="false">Draw</button><input data-area type="checkbox" hidden><button data-visibility>Show / hide</button><button data-style>Style</button>${icon('copy','Copy Python')}${icon('save','Save PNG')}${icon('properties','Properties')}${icon('fullscreen','Full screen')}<button data-display-scale title="Use the available width instead of the requested Figure size">Fit width</button><span data-status>Preparing…</span></div><div class="figgy-drawing" hidden><div role="toolbar" aria-label="Annotation drawing tools"><button data-tool="select">Select</button><button data-tool="text">Text</button><button data-tool="arrow">Arrow</button><button data-tool="hline">Horizontal line</button><button data-tool="vline">Vertical line</button><button data-tool="hspan">Horizontal band</button><button data-tool="vspan">Vertical band</button><label><input data-anchor-data type="checkbox">Follow data</label></div><p data-drawing-help></p></div><div class="figgy-body"><div class="figgy-stage"><canvas tabindex="0" aria-label="Editable chart"></canvas><svg class="figgy-panel-focus" aria-hidden="true"></svg><svg class="figgy-drawing-preview" aria-hidden="true"></svg></div><div class="figgy-properties" hidden><header><strong>Properties</strong><button data-close-properties>Close</button></header><section class="figgy-navigator"><div class="figgy-navigator-heading">Objects</div><label class="figgy-search"><input type="search" data-object-search placeholder="Find a panel, axis or series…" aria-label="Find chart objects"></label><div data-object-tree role="tree" aria-label="Chart objects"></div></section><div class="figgy-inspector-scroll"><div data-context class="figgy-context"></div><div data-fields></div><details data-advanced><summary>Advanced settings</summary><textarea data-settings></textarea><button data-apply>Apply settings</button></details><details data-code-panel><summary>Python code</summary><textarea data-code readonly></textarea></details></div></div></div><div data-hint>Click an element to edit · Drag to move · Wheel to zoom · Esc: clear · Arrows: move selection</div><div class="figgy-error" role="alert"></div>`;
  el.append(root);
  const canvas=root.querySelector('canvas'), fields=root.querySelector('[data-fields]');
  let inspectorOwner=null,inspectedTarget=null,outlineNodes=clone(model.get('state').outline??[]),boundedView=clone(model.get('state').bounded_view??null);
  const error=root.querySelector('.figgy-error'), status=root.querySelector('[data-status]');
  const controls=[...root.querySelectorAll('button,input,select,textarea')];
  controls.forEach(control=>control.disabled=true);
  const client=crypto.randomUUID();
  let chart,disposed=false,dirty=true,raf=0,selected=null,pointer=null,queue=Promise.resolve();
  let revision=model.get('state').revision,sequence=0,inflight=null,pending=null,barriers=[],local=clone(model.get('state').settings);
  let editHistory=model.get('state').edit_history??{},historyBusy=false;
  let propertyCatalog=clone(model.get('state').property_catalog??[]),controlQueue=Promise.resolve(),controlFinish=null;
  function historyControls(){for(const action of ['undo','redo']){const button=root.querySelector(`[data-${action}]`);button.disabled=historyBusy||!!inflight||!!pending||!editHistory[`can_${action}`];}}
  function replayEdit(action,args={}){
    const operation=controlQueue.then(async()=>{
      await queue;await flush();if(disposed)throw Error('Widget disposed');
      if(action==='property'){
        const field=propertyCatalog.find(v=>v.id===args.object_id)?.fields.find(v=>v.id===args.property_id);
        if(!field||JSON.stringify(field.value)!==JSON.stringify(args.base_value))throw Error('stale edit: the property changed; refresh and retry');
      }
      historyBusy=true;historyControls();
      await new Promise(resolve=>{controlFinish=resolve;model.send({action,client,revision,...args});});
    });
    controlQueue=operation.catch(e=>{historyBusy=false;historyControls();fail(e);});return controlQueue;
  }
  for(const action of ['undo','redo'])root.querySelector(`[data-${action}]`).addEventListener('click',()=>replayEdit(action));
  root.addEventListener('keydown',e=>{
    if(!(e.ctrlKey||e.metaKey)||e.altKey||e.target.matches('input,textarea,[contenteditable=true]'))return;
    const action=e.key.toLowerCase()==='y'||(e.key.toLowerCase()==='z'&&e.shiftKey)?'redo':e.key.toLowerCase()==='z'?'undo':null;
    if(action){e.preventDefault();if(editHistory[`can_${action}`])replayEdit(action);}
  });
  let background=clone(local.background ?? null);
  const stats={backend:'browser-webgpu',binary_upload_bytes:0,column_uploads:0,surface_frames:0,png_exports:0,kernel_edit_messages:0,last_input_to_submit_ms:0};
  const kind=['radial','categorical','boxplot','radar'].find(k=>local[k]);
  let hoverPoint=null,lastFrame=0,wheelArea=null;
  let focusedPanel=null,observedLayer=null,chooser=null,previewOriginal=null;
  const stage=root.querySelector('.figgy-stage');
  const choiceBox=document.createElement('div');choiceBox.className='figgy-target-chooser';choiceBox.hidden=true;choiceBox.setAttribute('role','dialog');choiceBox.setAttribute('aria-label','Choose what to edit');stage.append(choiceBox);
  const choicePreview=document.createElementNS('http://www.w3.org/2000/svg','svg');choicePreview.classList.add('figgy-choice-preview');choicePreview.setAttribute('aria-hidden','true');stage.append(choicePreview);
  const switchChart=document.createElement('button');switchChart.className='figgy-switch-chart';switchChart.hidden=true;stage.append(switchChart);
  const focusOverlay=root.querySelector('.figgy-panel-focus');
  const panelIndex=layer=>(layer?.Subplot??layer?.SubplotOverlay?.[0]??-1)+1;
  const panelConfig=(index,state=local)=>index===0?state.config:state.config.subplots[index-1].config;
  const panelId=index=>local.identity?.panels?.[index]?.id??`panel_${index}`;
  const baseLayer=index=>index===0?'Base':{Subplot:index-1};
  const hasPanels=()=>!kind&&Boolean(local.config.subplots?.length);
  const focusIndex=()=>focusedPanel===null?null:Array.from({length:(local.config.subplots?.length??0)+1},(_,i)=>i).find(i=>panelId(i)===focusedPanel)??null;
  const inRect=([x,y],[rx,ry,w,h])=>x>=rx&&y>=ry&&x<rx+w&&y<ry+h;
  function panelRect(index){
    const rectangles=[local.config.chart_area,...(local.config.subplots??[]).map(p=>p.config.chart_area)];
    const width=Math.max(...rectangles.map(r=>r.x+r.width)),height=Math.max(...rectangles.map(r=>r.y+r.height));
    const scale=Math.min(canvas.width/width,canvas.height/height),ox=Math.floor((canvas.width-Math.round(width*scale))/2),oy=Math.floor((canvas.height-Math.round(height*scale))/2),r=panelConfig(index).chart_area;
    return [ox+r.x*scale,oy+r.y*scale,r.width*scale,r.height*scale];
  }
  function panelsAt(point){return Array.from({length:(local.config.subplots?.length??0)+1},(_,i)=>i).reverse().filter(i=>inRect(point,panelRect(i)));}
  function panelAt(point){const hits=panelsAt(point),focused=focusIndex();return hits.includes(focused)?focused:hits[0]??null;}
  function overlappingPanels(index){const [x,y,w,h]=panelRect(index);return Array.from({length:(local.config.subplots?.length??0)+1},(_,i)=>i).reverse().filter(i=>{const [a,b,c,d]=panelRect(i);return x<a+c&&a<x+w&&y<b+d&&b<y+h;});}
  function syncPanelFocus(explicit=false){
    if(!hasPanels())focusedPanel=null;
    else if(explicit||(observedLayer!==null&&!sameLayer(observedLayer,local.config.active_layer??'Base')))focusedPanel=panelId(panelIndex(local.config.active_layer));
    else if(focusIndex()===null)focusedPanel=null;
    observedLayer=clone(local.config.active_layer??'Base');
    root.dataset.panelMode=hasPanels()?'grid':'single';
    focusOverlay.replaceChildren();focusOverlay.setAttribute('viewBox',`0 0 ${canvas.width} ${canvas.height}`);
    const index=focusIndex();
    if(hasPanels()&&index!==null){
      const [x,y,w,h]=panelRect(index),rect=document.createElementNS('http://www.w3.org/2000/svg','rect');
      for(const [name,value]of Object.entries({x:x+2,y:y+2,width:Math.max(0,w-4),height:Math.max(0,h-4),rx:3,fill:'none',stroke:'#2663ad','stroke-width':1.5,'vector-effect':'non-scaling-stroke'}))rect.setAttribute(name,value);
      focusOverlay.append(rect);
    }
    focusOverlay.dataset.panel=focusedPanel??'';stats.focused_panel=focusedPanel;
    const overlaps=index===null?[]:overlappingPanels(index);switchChart.hidden=overlaps.length<2;
    if(!switchChart.hidden){const [x,y,w]=panelRect(index);switchChart.textContent=`Switch chart (${overlaps.length})`;switchChart.style.left=`${(x+w)/canvas.width*100}%`;switchChart.style.top=`${y/canvas.height*100}%`;switchChart.onclick=()=>enqueue(()=>openChooser(overlaps.map(panelChoice),[x+w,y+30]));}
    const name=index===null?'':text(panelConfig(index).chart_title?.text)||panelId(index);
    root.querySelector('[data-hint]').textContent=hasPanels()?(index===null?'Click a chart to select it, then click or drag inside to edit':`${name} selected · Click an axis or data to edit · Click another chart to switch · Esc: leave chart`):'Click an element to edit · Drag to move · Wheel to zoom · Esc: clear · Arrows: move selection';
  }
  function layersInPanel(index){const cfg=panelConfig(index);return [baseLayer(index),...(cfg.overlays??[]).map((_,i)=>index===0?{Overlay:i}:{SubplotOverlay:[index-1,i]})];}
  function setPointerLayer(layer){chart.set_active_layer(JSON.stringify(layer));local.config.active_layer=clone(layer);}
  function decorationsAt(point,index){
    const original=JSON.parse(chart.active_layer()),hits=[];
    try{for(const layer of layersInPanel(index).reverse()){
      chart.set_active_layer(JSON.stringify(layer));const target=chart.hit_test(...point);if(target===null||target===undefined)continue;
      if(!hits.some(h=>h.target===target))hits.push({layer:target.includes('overlay_')?layer:baseLayer(index),target});
    }return hits.some(h=>!h.target.endsWith('data_area'))?hits.filter(h=>!h.target.endsWith('data_area')):hits;}finally{chart.set_active_layer(JSON.stringify(original));}
  }
  async function pickPanelCandidates(point,index){
    const config=JSON.parse(chart.get_config()),series=JSON.parse(chart.get_series()),hits=[],excluded=new Set();
    const owner=id=>{for(let i=0;i<=(config.subplots?.length??0);i++){const cfg=i?config.subplots[i-1].config:config;if(i&&!(config.subplots[i-1].series??[]).includes(id))continue;if(!i&&(config.subplots??[]).some(p=>(p.series??[]).includes(id)))continue;const o=(cfg.overlays??[]).findIndex(o=>(o.series??[]).includes(id));return o<0?baseLayer(i):i?{SubplotOverlay:[i-1,o]}:{Overlay:o};}return 'Base';};
    const remaining=()=>series.filter(v=>!excluded.has(v.series_id)).map(v=>{const item=clone(v);for(const style of Object.values(item.render_type))if(style.line)style.line.fill=null;return item;});
    try{
      chart.set_picked_data('null');chart.set_picked_points('null');
      for(const layer of layersInPanel(index).reverse()){
        chart.set_active_layer(JSON.stringify(layer));
        while(series.some(v=>!excluded.has(v.series_id)&&sameLayer(owner(v.series_id),layer))){
          const value=await chart.pick_data(...point,6);if(!value)break;
          const identity=JSON.parse(value),ref=Object.fromEntries(Object.entries(identity).filter(([k])=>k!=='distance_px'));
          if(excluded.has(ref.series_id))throw Error('Picker repeated an excluded series');
          excluded.add(ref.series_id);hits.push({layer,ref,distance:identity.distance_px});
          chart.set_series(JSON.stringify(remaining()));
        }
      }
    }finally{try{chart.set_series(JSON.stringify(series));}finally{chart.set_config(JSON.stringify(config));}}
    hits.sort((a,b)=>a.distance-b.distance);stats.last_pick_candidates=hits.map(h=>({layer:h.layer,series:h.ref.series_id,distance:h.distance}));stats.last_pick_position=point;
    return hits;
  }
  function ownerName(layer){const index=panelIndex(layer),cfg=panelConfig(index),label=text(cfg.chart_title?.text)||panelId(index),o=layer?.Overlay??layer?.SubplotOverlay?.[1];return `${label} · ${o===undefined?'Primary axes':`Right Y · ${local.identity?.panels?.[index]?.overlays?.[o]??o+1}`}`;}
  function panelChoice(index){return {key:`panel/${panelId(index)}`,label:text(panelConfig(index).chart_title?.text)||panelId(index),detail:`Chart · ${panelId(index)}`,layer:baseLayer(index),target:null,color:'#2663ad'};}
  function dataChoice(hit){const id=hit.ref.series_id,series=local.series.find(v=>v.series_id===id),style=Object.values(series?.render_type??{})[0]??{},c=style.line?.line_color??style.scatter?.point_color??style.bar?.fill_color;return {key:`series/${id}`,label:text(series?.label)||id,detail:`${ownerName(hit.layer)} · ${id}`,layer:hit.layer,target:id,ref:hit.ref,color:c?`rgb(${c.r*255} ${c.g*255} ${c.b*255})`:'#556982'};}
  function elementChoice(hit){return {key:`element/${hit.target}`,label:allNodes().find(v=>v.node.target===hostTarget(hit.target)&&sameLayer(v.node.layer,hit.layer))?.node.label??caption(hit.target.split(':').at(-1)),detail:ownerName(hit.layer),layer:hit.layer,target:hostTarget(hit.target),color:'#556982'};}
  function restorePreview(){if(previewOriginal){chart.set_config(JSON.stringify(previewOriginal));previewOriginal=null;}choicePreview.replaceChildren();dirty=true;}
  function cancelChooser(){if(!chooser)return;const restoreFocus=choiceBox.contains(document.activeElement);restorePreview();chooser=null;choiceBox.hidden=true;choiceBox.replaceChildren();stats.choice_candidates=null;stats.choice_preview=null;if(restoreFocus)canvas.focus({preventScroll:true});}
  function previewChoice(index){
    if(!chooser)return;restorePreview();chooser.active=index;const choice=chooser.choices[index];if(!choice)return;
    previewOriginal=JSON.parse(chart.get_config());chart.set_picked_points('null');chart.set_active_layer(JSON.stringify(choice.layer));chart.set_picked_data(JSON.stringify(choice.ref?{refs:[choice.ref]}:null));
    const rect=choice.target?JSON.parse(chart.decoration_bounds(rendererTarget(choice.target)))?.rect:panelRect(panelIndex(choice.layer));
    choicePreview.setAttribute('viewBox',`0 0 ${canvas.width} ${canvas.height}`);
    if(rect){const node=document.createElementNS('http://www.w3.org/2000/svg','rect');for(const [k,v]of Object.entries({x:rect[0],y:rect[1],width:rect[2],height:rect[3],fill:'none',stroke:'#2663ad','stroke-width':2,'stroke-dasharray':'5 3','vector-effect':'non-scaling-stroke'}))node.setAttribute(k,v);choicePreview.append(node);}
    choiceBox.querySelectorAll('[data-choice]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.choice===choice.key)));stats.choice_preview=choice.key;dirty=true;
  }
  function chooseTarget(choice){cancelChooser();chart.set_picked_points('null');setPointerLayer(choice.layer);chart.set_picked_data(JSON.stringify(choice.ref?{refs:[choice.ref]}:null));selected=choice.target;local=snapshot();focusedPanel=panelId(panelIndex(choice.layer));observedLayer=clone(local.config.active_layer??'Base');if(selected)showProperties();dirty=true;commit();canvas.focus({preventScroll:true});}
  function renderChooser(){
    if(!chooser)return;const query=chooser.filter.toLowerCase(),visible=chooser.choices.map((c,i)=>({c,i})).filter(({c})=>`${c.label} ${c.detail}`.toLowerCase().includes(query));chooser.visible=visible.map(v=>v.i);
    const rows=choiceBox.querySelector('[data-choices]');rows.replaceChildren();
    for(const {c,i}of visible){const button=document.createElement('button');button.dataset.choice=c.key;button.setAttribute('role','option');button.setAttribute('aria-selected',String(i===chooser.active));const swatch=document.createElement('span');swatch.className='figgy-choice-swatch';swatch.style.background=c.color;const name=document.createElement('span');name.textContent=c.label;const detail=document.createElement('small');detail.textContent=c.detail;name.append(detail);button.append(swatch,name);button.addEventListener('pointerenter',()=>enqueue(()=>previewChoice(i)));button.addEventListener('click',()=>enqueue(()=>chooseTarget(c)));rows.append(button);}
    if(!visible.length)rows.textContent='No matching targets';
    if(!chooser.visible.includes(chooser.active))previewChoice(chooser.visible[0]??-1);
  }
  function openChooser(choices,point){
    cancelChooser();chooser={choices,active:0,filter:'',visible:choices.map((_,i)=>i)};stats.choice_candidates=choices.map(({key,label,detail})=>({key,label,detail}));
    choiceBox.innerHTML='<header><strong></strong><button data-cancel-choice aria-label="Cancel selection">×</button></header><p>Point to preview · Click to select</p><div data-choices role="listbox" aria-label="Targets at this position"></div><footer>↑↓: preview · Enter: select · Esc: cancel</footer>';
    choiceBox.querySelector('strong').textContent=`Choose what to edit (${choices.length})`;choiceBox.querySelector('[data-cancel-choice]').onclick=()=>enqueue(cancelChooser);
    if(choices.length>8){const input=document.createElement('input');input.type='search';input.placeholder='Find a target…';input.setAttribute('aria-label','Find a target');input.oninput=()=>{if(chooser){chooser.filter=input.value;enqueue(renderChooser);}};choiceBox.insertBefore(input,choiceBox.querySelector('[data-choices]'));}
    choiceBox.hidden=false;renderChooser();
    const scaleX=canvas.clientWidth/canvas.width,scaleY=canvas.clientHeight/canvas.height;
    choiceBox.style.left=`${Math.max(0,Math.min(point[0]*scaleX+12,stage.clientWidth-choiceBox.offsetWidth))}px`;
    choiceBox.style.top=`${Math.max(0,Math.min(point[1]*scaleY+12,stage.clientHeight-choiceBox.offsetHeight))}px`;
    previewChoice(0);
  }
  root.addEventListener('pointerdown',e=>{if(!chooser||choiceBox.contains(e.target)||e.target===switchChart)return;const consume=e.target===canvas;enqueue(cancelChooser);if(consume){e.preventDefault();e.stopImmediatePropagation();}},true);
  root.addEventListener('keydown',e=>{if(!chooser||!['Escape','ArrowDown','ArrowUp','Enter'].includes(e.key))return;e.preventDefault();e.stopImmediatePropagation();enqueue(()=>{if(!chooser)return;if(e.key==='Escape'){cancelChooser();return;}if(e.key==='Enter'){const choice=chooser.choices[chooser.active];if(choice)chooseTarget(choice);return;}const list=chooser.visible,at=list.indexOf(chooser.active),next=(at+(e.key==='ArrowDown'?1:-1)+list.length)%list.length;if(list.length){previewChoice(list[next]);choiceBox.querySelector(`[data-choice][aria-selected="true"]`)?.scrollIntoView({block:'nearest'});}});},true);
  function selectedHandleAt(point){
    if(!selected)return false;
    const value=JSON.parse(chart.decoration_bounds(rendererTarget(selected)));
    return value?.handles?.some(rect=>inRect(point,rect))??false;
  }
  const textRanges=new Map();
  let drawingTool='select',drawingGesture=null;
  const drawingPalette=root.querySelector('.figgy-drawing'),preview=root.querySelector('.figgy-drawing-preview');
  function drawingSupport(){
    const owner=kind||(panelIndex(local.config.active_layer)===0&&(!hasPanels()||focusIndex()===0));
    const rectangular=kind==='boxplot'||kind==='categorical',horizontal=rectangular&&local[kind].direction==='Horizontal';
    return {owner,axes:kind?(rectangular?[horizontal,!horizontal]:[false,false]):[!local.config.polar,!local.config.polar],data:kind?rectangular:!local.config.polar};
  }
  function annotationUnavailable(){return `Annotations are available on “${text(local.config.chart_title?.text)||panelId(0)}”. Select that chart to draw.`;}
  function drawingUI(){
    const {owner,axes,data}=drawingSupport();
    const axis=drawingTool.startsWith('h')?1:drawingTool.startsWith('v')?0:null;
    if(!owner||(axis!==null&&!axes[axis])){drawingTool='select';drawingGesture=null;preview.replaceChildren();}
    for(const button of root.querySelectorAll('[data-tool]')){
      const name=button.dataset.tool,axis=name.startsWith('h')?1:name.startsWith('v')?0:null;
      button.disabled=name!=='select'&&(!owner||(axis!==null&&!axes[axis]));
      button.title=!owner?annotationUnavailable():axis!==null&&!axes[axis]?'This chart has no numeric value axis in this direction.':'';
      button.setAttribute('aria-pressed',String(name===drawingTool));
    }
    const anchor=root.querySelector('[data-anchor-data]');anchor.disabled=!owner||!data;if(anchor.disabled)anchor.checked=false;
    root.querySelector('[data-drawing-help]').textContent=!owner?annotationUnavailable():drawingTool==='select'?'Double-click text to edit it. Drag annotations to move them.':drawingTool==='text'?'Click and type. Enter: apply. Esc: cancel.':'Drag to draw. Release to create and edit. Esc: cancel. Follow data: move with axis ranges.';
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
  let inlineText=null;
  const inlineBox=document.createElement('div');inlineBox.className='figgy-inline-text';inlineBox.hidden=true;
  const inlineInput=document.createElement('textarea');inlineInput.rows=1;inlineInput.dataset.inlineText='';inlineInput.setAttribute('aria-label','Annotation text');inlineInput.placeholder='Type text';
  const inlineHint=document.createElement('small');inlineHint.textContent='Enter: apply · Shift+Enter: new line · Esc: cancel';inlineHint.title=inlineHint.textContent;
  inlineBox.append(inlineInput,inlineHint);root.querySelector('.figgy-stage').append(inlineBox);
  function selectedAnnotation(){const state=snapshot(),items=(kind?state[kind]:state.config).annotations?.items??[];return kind?items[Number(/^annotation_(\d+)$/.exec(selected??'')?.[1])]:items.find(v=>'annotation:'+v.id===selected);}
  function positionInline(){
    if(!inlineText)return;
    const r=canvas.getBoundingClientRect(),g=inlineText;
    // Document pixels and CSS pixels share one scale. The backing surface can
    // still have the preceding size while its resize waits in the host queue.
    const width=local.config.chart_area.width;
    inlineInput.style.fontSize=`${Math.max(10,Math.min(72,g.item.kind.Text.text.font_size*r.width/width))}px`;
    inlineBox.style.maxWidth='calc(100% - 8px)';
    // Percent bounds update with CSS layout even before ResizeObserver runs.
    inlineBox.style.left=`clamp(0px, calc(${g.point[0]/g.size[0]*100}% - 5px), max(0px, calc(100% - min(300px, 100% - 8px))))`;
    inlineHint.hidden=r.height<48;
    inlineInput.style.height='auto';
    const chrome=inlineBox.getBoundingClientRect().height-inlineInput.getBoundingClientRect().height;
    const available=Math.max(0,r.height-chrome);
    inlineInput.style.minHeight=`${Math.min(28,available)}px`;
    inlineInput.style.height=`${Math.min(Math.max(28,inlineInput.scrollHeight),available)}px`;
    // Constrain the complete box after text sizing, including its hint and border.
    inlineBox.style.setProperty('--figgy-inline-height',`${inlineBox.getBoundingClientRect().height}px`);
    inlineBox.style.top=`clamp(0px, calc(${g.point[1]/g.size[1]*100}% - 4px), max(0px, calc(100% - var(--figgy-inline-height))))`;
  }
  function beginInline(item,point,existing=false){
    if(!item?.kind.Text)return;
    inlineText={item:clone(item),original:existing?clone(item):null,point,size:kind?[local.config.chart_area.width,local.config.chart_area.height]:[canvas.width,canvas.height]};
    inlineInput.value=existing?text(item.kind.Text.text):'';inlineBox.hidden=false;positionInline();
    inlineInput.focus({preventScroll:true});inlineInput.select();
    const draft=inlineText;requestAnimationFrame(()=>{if(inlineText===draft)positionInline();});
  }
  function finishInline(apply){
    const draft=inlineText;if(!draft)return;inlineText=null;inlineBox.hidden=true;
    const value=inlineInput.value;
    if(apply&&value.trim())enqueue(()=>{
      const state=snapshot(),owner=kind?state[kind]:state.config;owner.annotations??={visible:true,items:[]};const items=owner.annotations.items;
      const index=items.findIndex(v=>v.id===draft.item.id);
      if(draft.original&&(index<0||JSON.stringify(items[index])!==JSON.stringify(draft.original)))throw Error('Text changed elsewhere. Reopen it to edit the current version.');
      if(draft.original&&value===text(draft.original.kind.Text.text))return;
      const rich=draft.item.kind.Text.text,old=rich.segments,next=segments(value);let prefix=0,suffix=0;
      while(prefix<Math.min(old.length,next.length)&&old[prefix].text===next[prefix].text){next[prefix]=clone(old[prefix]);prefix++;}
      while(suffix<Math.min(old.length,next.length)-prefix&&old.at(-1-suffix).text===next.at(-1-suffix).text){next[next.length-1-suffix]=clone(old.at(-1-suffix));suffix++;}rich.segments=next;
      if(draft.original&&JSON.stringify(draft.item)===JSON.stringify(draft.original))return;
      const at=draft.original?index:items.length;if(draft.original)items[at]=draft.item;else items.push(draft.item);
      owner.annotations.visible=true;owner.active_layer='Annotations';
      if(kind)owner.decorations.selected={Annotation:at};else{owner.picked_data=null;delete owner.picked_points;}
      install(state);selected=kind?`annotation_${at}`:`annotation:${draft.item.id}`;chart.select_annotation(at);commit();
    });
  }
  inlineInput.addEventListener('input',positionInline);
  inlineInput.addEventListener('keydown',e=>{
    e.stopPropagation();if(e.isComposing||e.keyCode===229)return;
    if(e.key==='Escape'||e.key==='Enter'&&!e.shiftKey){e.preventDefault();finishInline(e.key==='Enter');canvas.focus({preventScroll:true});}
  });
  inlineInput.addEventListener('blur',()=>finishInline(true));
  async function annotationGeometry(){
    // Bounded charts prepare their logical annotation map synchronously when
    // adopting a document. Editing it does not depend on a material GPU fence.
    if(kind)return JSON.parse(chart.annotations());
    await waitForFrame();
    if(dirty){await readyDisplayedFrame();dirty=false;}
    return JSON.parse(chart.annotations());
  }
  async function textAnnotationAt(point){
    const owner=kind?snapshot()[kind]:snapshot().config;if(owner.annotations?.visible===false||!owner.annotations?.items?.some(v=>v.kind.Text&&v.visible!==false))return null;
    const entries=await annotationGeometry(),index=chart.hit_annotation(...point);if(index===undefined||!owner.annotations?.items[index]?.kind.Text)return null;
    const entry=entries.find(v=>v.index===index);
    return entry?{item:owner.annotations.items[index],entry}:null;
  }
  canvas.addEventListener('dblclick',e=>{
    if(!chart||drawingTool!=='select')return;e.preventDefault();const point=localPoint(e);
    enqueue(async()=>{const hit=await textAnnotationAt(point);if(hit)beginInline(hit.item,[hit.entry.rect[0],hit.entry.rect[1]],true);});
  });
  function finishDrawing(g){
    if(g.cancelled||g!==drawingGesture)return;
    {const [x,y,w,h]=/^[hv]/.test(g.tool)?g.area:g.panel;g.end=[Math.max(x,Math.min(x+w,g.end[0])),Math.max(y,Math.min(y+h,g.end[1]))];}const [x,y]=g.start,[u,v]=g.end;if(['arrow','hspan','vspan'].includes(g.tool)&&Math.hypot(u-x,v-y)<3){cancelDrawing();return;}
    const anchor=p=>JSON.parse(chart.pointer_to_anchor(...p,g.data?'Data':'Ratio'));
    const start=anchor(g.start),end=anchor(g.end);if(!start||!end)throw Error('This chart does not support these annotation coordinates.');
    const line={color:{r:.235,g:.235,b:.235,a:1},width:1.5,style:'Solid'},rich={segments:segments('Text'),color:{r:.137,g:.176,b:.235,a:1},font_size:16,font:''};let geometry;
    if(g.tool==='text')geometry={Text:{anchor:end,text:rich,box_style:null}};
    else if(g.tool==='arrow')geometry={Arrow:{from:start,to:end,style:{line,head_length:10,head_width:8},text:null}};
    else {const axis=g.tool.startsWith('h')?'Y':'X',key=axis==='X'?'x':'y',a=JSON.parse(chart.pointer_to_anchor(x,y,'Data'))?.Data?.[key],b=JSON.parse(chart.pointer_to_anchor(u,v,'Data'))?.Data?.[key];if(!Number.isFinite(a)||!Number.isFinite(b))throw Error('This direction has no value axis.');
      if(g.tool.endsWith('line'))geometry={ReferenceLine:{axis,value:b,style:line,label:null}};else{if(a===b){cancelDrawing();return;}geometry={Span:{axis,from:Math.min(a,b),to:Math.max(a,b),fill:{r:.149,g:.388,b:.678,a:.176}}};}}
    const item={id:`annotation_${crypto.randomUUID()}`,kind:geometry};
    if(g.tool==='text'){cancelDrawing();beginInline(item,g.end);return;}
    chart.add_annotation(JSON.stringify(item));chart.set_annotations_visible(true);chart.set_active_layer(JSON.stringify('Annotations'));
    const state=snapshot(),index=(kind?state[kind]:state.config).annotations.items.length-1;chart.select_annotation(index);
    selected=kind?`annotation_${index}`:`annotation:${item.id}`;inspectorTarget=null;inspectorLayer=null;
    cancelDrawing();showProperties();dirty=true;commit();
  }
  root.querySelector('[data-draw]').addEventListener('click',e=>{drawingPalette.hidden=!drawingPalette.hidden;e.currentTarget.setAttribute('aria-pressed',String(!drawingPalette.hidden));cancelDrawing();});
  for(const button of root.querySelectorAll('[data-tool]'))button.addEventListener('click',()=>{cancelDrawing();drawingTool=button.dataset.tool;layoutMode(false);drawingUI();canvas.focus();});
  root.addEventListener('keydown',e=>{if(e.key==='Escape'&&drawingTool!=='select'){e.preventDefault();e.stopPropagation();cancelDrawing();}},true);
  canvas.addEventListener('lostpointercapture',()=>{if(drawingGesture&&!drawingGesture.released)cancelDrawing();});
  const blurDrawing=()=>{if(chooser)enqueue(cancelChooser);if(drawingGesture&&!drawingGesture.released)cancelDrawing();};
  window.addEventListener('blur',blurDrawing);
  function rendererTarget(target){if(kind||!target?.startsWith('annotation:'))return target;const index=local.config.annotations?.items?.findIndex(v=>'annotation:'+v.id===target);return index>=0?`annotation_${index}`:target;}
  function hostTarget(target){if(kind)return target;const index=/^annotation_(\d+)$/.exec(target??'')?.[1],item=index===undefined?null:local.config.annotations?.items?.[Number(index)];return item?'annotation:'+item.id:target;}

  function showProperties(open=true){root.querySelector('.figgy-properties').hidden=!open;if(open)navigateTree(true);}
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
  function snapshot(){if(kind)return {...clone(local),renderer_version:rendererVersion,[kind]:JSON.parse(chart.get_document())};return {...clone(local),schema_version:local.schema_version,renderer_version:rendererVersion,config:clone(previewOriginal??JSON.parse(chart.get_config())),series:JSON.parse(chart.get_series()),...(background ? {background:clone(background)} : {})};}
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
        const omittedDefault=(key==='active_layer'&&item==='Base')||(key==='align'&&item==='Left')||(key==='draw_style'&&item?.mode==='precise'&&Object.keys(item).length===1)||(key==='picked_data'&&item===null);
        if(omittedDefault)continue;
        throw Error(`Unknown settings field: ${path}.${key}`);
      }
      checkNumericConversion(item,accepted[key],`${path}.${key}`);
    }
  }
  function install(settings){
    cancelChooser();
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
  function post(){if(inflight || !pending)return;inflight={sequence:++sequence,settings:pending};pending=null;historyControls();stats.kernel_edit_messages++;model.send({action:'edit',client,sequence,revision,settings:inflight.settings});}
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
    if(node.legend)Object.defineProperty(view,'legend',{get:()=>node.legend,set:value=>node.legend=value});
    return view;
  }
  function navigateDocumentAxis(state,dimension,factor,anchor,shift=0){
    const cfg=activePanel(state),layer=state.config.active_layer,overlay=layer?.Overlay??layer?.SubplotOverlay?.[1];
    if(dimension==='y'&&overlay!==undefined){navigate(cfg.overlays[overlay].y_axis,factor,anchor,shift);if(factor!==1&&tickAutomatic(state,'right_y'))retick(cfg.overlays[overlay].y_axis);}
    else for(const key of dimension==='x'?['bottom_x','top_x']:['left_y','right_y']){navigate(cfg[key],factor,anchor,shift);if(factor!==1&&tickAutomatic(state,key))retick(cfg[key]);}
  }
  function tickAddress(state,key){
    const layer=state.config.active_layer,index=(layer?.Subplot??layer?.SubplotOverlay?.[0]??-1)+1,panel=state.identity?.panels?.[index];
    const overlay=layer?.Overlay??layer?.SubplotOverlay?.[1];
    return key==='right_y'&&overlay!==undefined?[panel?.overlays?.[overlay],'y_axis']:[panel?.id,key];
  }
  function tickOwners(state,owner,key){
    const owners=new Set([owner]),dimension={bottom_x:'x',left_y:'y'}[key];
    if(dimension)for(let old=-1;old!==owners.size;){old=owners.size;for(const group of Object.values(state.identity.groups))if(group.axis===dimension&&group.members.some(id=>owners.has(id)))for(const id of group.members)owners.add(id);}
    return owners;
  }
  function tickAutomatic(state,key){const [owner,side]=tickAddress(state,key);return [...tickOwners(state,owner,side)].every(id=>state.identity?.tick_modes?.[id]?.[side]!=='Fixed');}
  function tickMode(state,key,automatic){const [owner,side]=tickAddress(state,key);if(owner===undefined)return;state.identity.tick_modes??={};
    const peer={bottom_x:'top_x',top_x:'bottom_x',left_y:'right_y',right_y:'left_y'}[side],cfg=activePanel(state),keys=[side];
    if(peer&&['min','max','scale','inverted'].every(k=>cfg[key][k]===cfg[peer][k]))keys.push(peer);
    for(const key of keys)for(const id of tickOwners(state,owner,key)){state.identity.tick_modes[id]??={};state.identity.tick_modes[id][key]=automatic?'Auto':'Fixed';}
  }
  function syncTickSpacing(state,key){
    const [owner,side]=tickAddress(state,key);if(!['bottom_x','left_y'].includes(side))return;
    const spacing=activePanel(state)[key].major_spacing;
    for(const id of tickOwners(state,owner,side)){const index=state.identity.panels.findIndex(p=>p.id===id);panelConfig(index,state)[key].major_spacing=spacing;}
  }
  function retick(axis){
    if(axis.scale==='Logarithmic'){const decades=Math.max(1,Math.ceil(Math.log10(axis.max))-Math.floor(Math.log10(axis.min)));axis.major_spacing=decades<=6?1:decades<=12?2:Math.ceil(decades/6);return;}
    const span=axis.max-axis.min;if(!(span>0&&Number.isFinite(span)))return;
    const base=10**Math.floor(Math.log10(span)),fraction=span/base;
    axis.major_spacing=base>0&&Number.isFinite(base)?(fraction>=5?base:fraction>=2?base*.5:base*.2):span;
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
    if(sidebarPointer){formRefreshPending=true;return;}
    const layer=inspectorLayer??layerOf(local),target=inspectorTarget??selected??(hasPanels()||layer==='Annotations'?null:elementName('chart_title'));
    let entry=allNodes().find(v=>v.node.key===inspectorOwner&&v.node.target===target&&sameLayer(v.node.layer,layer))??allNodes().find(v=>v.node.target===target&&sameLayer(v.node.layer,layer));
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
  search.addEventListener('input',()=>navigateTree(!search.value));
  search.addEventListener('keydown',e=>{if(e.key==='ArrowDown'){e.preventDefault();const q=search.value.toLowerCase(),entry=allNodes().find(({node:n})=>n.target!==null&&`${n.label} ${n.kind} ${n.key.split('/').at(-1)}`.toLowerCase().includes(q));(entry?[...tree.querySelectorAll('[role=treeitem]')].find(r=>r.dataset.node===entry.node.key):tree.querySelector('[role=treeitem]'))?.focus();}if(e.key==='Escape'){search.value='';navigateTree();canvas.focus();}});
  function chooseObject(node){
    const target=node.target,generation=++inspectorGeneration;inspectorOwner=node.key;
    if(node.kind==='panel')expanded.set(node.key,true);
    inspectorTarget=target;inspectorLayer=node.layer;showProperties();properties(false);
    enqueue(()=>{
      if(!sameLayer(layerOf(snapshot()),node.layer)){
        const state=snapshot();(kind?state[kind]:state.config).active_layer=clone(node.layer);if(!kind)state.config.picked_data=null;install(state);wheelArea=null;
      }
      selected=target;
      if(!kind){local=snapshot();syncPanelFocus(true);}
      if(kind){const dataTarget=/^slice_/.test(target??'')||local[kind].series?.some(v=>v.id===target);if(dataTarget){chart.clear_selection();}else if(target&&target!=='figure')chart.select_decoration(target);else chart.clear_selection();}
      else if(target?.startsWith('annotation:')){chart.select_annotation(local.config.annotations.items.findIndex(v=>'annotation:'+v.id===target));}
      else if(target!=='figure'&&!local.series.some(s=>s.series_id===target)){const bound=target?JSON.parse(chart.decoration_bounds(rendererTarget(target))):null;if(bound){chart.on_press(bound.rect[0]+bound.rect[2]/2,bound.rect[1]+bound.rect[3]/2);chart.on_release();}}
      if(generation===inspectorGeneration){inspectorTarget=null;inspectorLayer=null;}
      dirty=true;commit();
    });
  }
  let decorationIds=[],inspectorTarget=null,inspectorLayer=null,inspectorGeneration=0,formContext='',sidebarPointer=false,formRefreshPending=false;
  root.querySelector('.figgy-properties').addEventListener('pointerdown',()=>{sidebarPointer=true;},true);
  root.querySelector('.figgy-properties').addEventListener('click',()=>{sidebarPointer=false;},true);
  const releaseSidebar=()=>setTimeout(()=>{sidebarPointer=false;if(formRefreshPending&&!disposed){formRefreshPending=false;enqueue(()=>properties());}},0);
  window.addEventListener('pointerup',releaseSidebar,true);window.addEventListener('pointercancel',releaseSidebar,true);
  fields.addEventListener('focusout',()=>setTimeout(()=>{if(formRefreshPending&&!sidebarPointer&&!disposed){formRefreshPending=false;enqueue(()=>properties());}},0));
  function properties(refresh=true){
    if(!chart)return;
    try{
    if(refresh){local=snapshot();if(kind)decorationIds=JSON.parse(chart.decorations()).map(d=>d.id).filter(id=>id!=='chart_title');}
    if(sidebarPointer){formRefreshPending=true;return;}
    syncPanelFocus();drawingUI();navigateTree();selectionProperties();
    const nextTarget=inspectorTarget??selected??elementName('chart_title'),nextContext=JSON.stringify([layerOf(local),nextTarget]);
    if(nextContext===formContext&&fields.contains(document.activeElement)&&document.activeElement.matches('input,textarea')){formRefreshPending=true;return;}
    if(nextContext!==formContext)root.querySelector('.figgy-inspector-scroll').scrollTop=0;
    formContext=nextContext;inspectedTarget=nextTarget;fields.replaceChildren();
    if(hasPanels()&&selected===null&&inspectorTarget===null){const hint=document.createElement('p');hint.textContent=focusIndex()===null?'Select a chart on the canvas.':'Click a title, axis, legend or data series in the selected chart.';fields.append(hint);return;}
    if(layerOf(local)==='Annotations'&&selected===null&&inspectorTarget===null){const hint=document.createElement('p');hint.textContent='Choose an annotation in the tree or click it in the chart.';fields.append(hint);return;}
    if(inspectorLayer&&!sameLayer(inspectorLayer,layerOf(local))){const pending=document.createElement('p');pending.textContent='Selecting object…';fields.append(pending);return;}
    const target=/^(subplot_|overlay_)/.test(inspectedTarget)?inspectedTarget.split(':').pop():inspectedTarget,cfg=configOf(local);
    const series=local.series.find(s=>s.series_id===target);
    function applyProperty(apply,value){
      const before=snapshot(),state=clone(before);
      apply(state,value);
      const secondary=before.config.active_layer?.Overlay??before.config.active_layer?.SubplotOverlay?.[1];
      if(!kind&&!(secondary!==undefined&&/^(axis|tick_labels)_right$/.test(target)))reconcilePairedAxisEdit({config:configOf(before)},{config:configOf(state)},target);
      if(/^axis_(bottom|top|left|right)$/.test(target))for(const key of ['bottom_x','left_y'])syncTickSpacing(state,key);
      install(state);commit();
    }
    function field(label,value,type,apply){
      const row=document.createElement('label');row.append(document.createTextNode(label==='visible'&&target.startsWith('axis_')&&!target.startsWith('axis_title_')?'Axis line':caption(label)));const input=document.createElement('input');input.type=type;input.value=value;input.dataset.property=label;
      input.addEventListener('change',()=>{const value=type==='number'?Number(input.value):input.value;enqueue(()=>{applyProperty(apply,value);});});row.append(input);fields.append(row);return input;
    }
    function color(label,value,find){
      const hex='#'+['r','g','b'].map(k=>Math.round(value[k]*255).toString(16).padStart(2,'0')).join('');
      field(label,hex,'color',(s,v)=>{const c=find(s);['r','g','b'].forEach((k,i)=>c[k]=parseInt(v.slice(i*2+1,i*2+3),16)/255);});
    }
    function choice(label,value,values,apply){
      const row=document.createElement('label');row.append(document.createTextNode(label==='visible'&&target.startsWith('axis_')&&!target.startsWith('axis_title_')?'Axis line':caption(label)));const input=document.createElement('select');input.dataset.property=label;
      for(const v of values){const opt=document.createElement('option');opt.value=v;opt.textContent=label==='label_format'?({Decimal:'Decimal (123.45)',Scientific:'Scientific (1.23e2)',Power:'Power (1.23 × 10²)',Timestamp:'Timestamp (configured)'}[v]):label==='tick_direction'?(v==='None'?'Hidden':v==='Both'?'Both sides':v):v==='Logarithmic'?'Logarithmic (base 10)':v;input.append(opt);}input.value=value;
      input.addEventListener('change',()=>{const next=input.value;enqueue(()=>{try{applyProperty(apply,next);}catch(e){input.value=value;throw e;}});});row.append(input);fields.append(row);
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
    function legendSeries(state){
      const cfg=activePanel(state),layer=state.config.active_layer,overlay=layer?.Overlay??layer?.SubplotOverlay?.[1];
      const index=layer?.Subplot??layer?.SubplotOverlay?.[0],children=state.config.subplots??[];
      const assigned=new Set(children.flatMap(p=>p.series??[]));
      const owned=new Set(overlay!==undefined&&cfg.overlays[overlay].legend?cfg.overlays[overlay].series:index===undefined?state.series.filter(s=>!assigned.has(s.series_id)).map(s=>s.series_id):children[index].series);
      return state.series.filter(s=>s.label&&owned.has(s.series_id));
    }
    function syncLegend(state){
      const labels=legendSeries(state),chars=configOf(state).legend.content.segments,anchors=[];
      // Read the renderer's explicit symbol fields and tabs. Text may contain
      // newlines; splitting rows on every newline would corrupt multiline labels.
      for(let i=0;i<chars.length;){
        if(chars[i].field_em==null){i++;continue;}
        const start=i;while(i<chars.length&&chars[i].field_em!=null)i++;
        while(i<chars.length&&chars[i].text===' ')i++;
        if(chars[i]?.text==='\t'){anchors.push({start,text:i+1});i++;}
      }
      if(anchors.length!==labels.length)throw Error('This custom legend layout cannot be matched to its labelled series');
      for(let i=anchors.length-1;i>=0;i--){let end=anchors[i+1]?.start??chars.length;if(i+1<anchors.length&&chars[end-1]?.text==='\n')end--;chars.splice(anchors[i].text,end-anchors[i].text,...clone(labels[i].label.segments));}
    }
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
      if(geometry[textKey]){const findText=s=>shape(s)[textKey];
      field('font',geometry[textKey].font,'text',(s,v)=>findText(s).font=v);
      field('font_size',geometry[textKey].font_size,'number',(s,v)=>findText(s).font_size=v);color('text_color',geometry[textKey].color,s=>findText(s).color);
      const input=field('text',text(geometry[textKey]),'text',(s,v)=>findText(s).segments=preserve(findText(s).segments,segments(v)));richControls(findText,inspectedTarget,input);}
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
      field('font',c.font_family,'text',(s,v)=>s[kind].font_family=v);
      field('font_size',c.font_size,'number',(s,v)=>s[kind].font_size=v);
      field('title',c.title,'text',(s,v)=>{s[kind].title=v;if(s[kind].chart_title)s[kind].chart_title.text.segments=segments(v);});
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
    if(target.startsWith('colorbar'))return;
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
      if(target==='legend'){const heading=document.createElement('strong');heading.textContent='All legend entries';fields.append(heading);}
      field('font',rich.font,'text',(s,v)=>find(s).font=v);
      field('font_size',rich.font_size,'number',(s,v)=>find(s).font_size=v);color('color',rich.color,s=>find(s).color);
      if(target==='legend'){const heading=document.createElement('p');heading.textContent='Legend entries · select characters to format them';fields.append(heading);}
      if(target==='legend')for(const [index,item] of legendSeries(local).entries()){
        const findLabel=s=>s.series.find(v=>v.series_id===item.series_id).label,key=`legend_label_${item.series_id}`;
        const input=field(key,text(item.label),'text',(s,v)=>{findLabel(s).segments=preserve(findLabel(s).segments,segments(v));syncLegend(s);});input.parentElement.firstChild.textContent=`Entry ${index+1}`;richControls(findLabel,key,input);
      }
      if(target!=='legend'){const textInput=field('text',shown,'text',(s,v)=>{
        if(!helper||local.config.subplots?.length||local.config.overlays?.length){find(s).segments=preserve(find(s).segments,segments(v));return;}
        const old=clone(find(s).segments);chart[helper](v);const live=JSON.parse(chart.get_config());
        if(target==='chart_title')configOf(s).chart_title=live.chart_title;else find(s).segments=path.reduce((n,k)=>n[k],live).segments;find(s).segments=preserve(old,find(s).segments);
      });
      richControls(find,inspectedTarget,textInput);}
      choice('align',rich.align??'Left',['Left','Center','Right'],(s,v)=>find(s).align=v);
    }else if(series){
    }else if(target==='colorbar'||target.startsWith('colorbar_')){colorScale();
    }else if(target.startsWith('axis_')){const key=side[target.slice(5)];
      toggle('auto_ticks',tickAutomatic(local,key),(s,v)=>{tickMode(s,key,v);if(v)retick(configOf(s)[key]);});
      scaleControl('axis_scale',cfg[key],s=>configOf(s)[key],key.endsWith('_x')?'x':'y');
      toggle('tick_labels_visible',cfg[key].label_style.visible,(s,v)=>configOf(s)[key].label_style.visible=v);
      toggle('ticks_visible',cfg[key].tick!=='None',(s,v)=>configOf(s)[key].tick=v?'Outside':'None');
      choice('tick_direction',cfg[key].tick,['None','Outside','Inside','Both'],(s,v)=>configOf(s)[key].tick=v);
      numberFormat(cfg[key].label_style,s=>configOf(s)[key].label_style);
      for(const name of ['min','max','major_spacing','line_width'])field(name,cfg[key][name],'number',(s,v)=>{configOf(s)[key][name]=v;if(name==='major_spacing')tickMode(s,key,false);else if(['min','max'].includes(name)&&tickAutomatic(s,key))retick(configOf(s)[key]);});color('color',cfg[key].line_color,s=>configOf(s)[key].line_color);
    }else if(target.startsWith('tick_labels_')){const key=side[target.slice(12)];field('label_font',cfg[key].label_style.label_font,'text',(s,v)=>configOf(s)[key].label_style.label_font=v);field('font_size',cfg[key].label_style.font_size,'number',(s,v)=>configOf(s)[key].label_style.font_size=v);color('color',cfg[key].label_style.color,s=>configOf(s)[key].label_style.color);numberFormat(cfg[key].label_style,s=>configOf(s)[key].label_style);}
    root.querySelector('[data-settings]').value=JSON.stringify(local,null,2);root.querySelector('[data-code]').value=code();
    }finally{catalogProperties();}
  }
  function catalogProperties(){
    if(sidebarPointer||fields.contains(document.activeElement)||fields.querySelector('[data-catalog]'))return;
    const target=inspectorTarget??selected??elementName('chart_title');
    if(target?.includes('annotation')||(hasPanels()&&focusIndex()===null&&target!=='figure'))return;
    const matches=v=>v.target===target&&(target==='figure'||sameLayer(v.layer,layerOf(local)));
    const object=propertyCatalog.find(v=>v.id===inspectorOwner&&matches(v))??propertyCatalog.find(matches);
    if(!object)return;
    const primary=local.series.some(v=>v.series_id===target)||target.split(':').at(-1).startsWith('colorbar'),covered=new Set([...fields.querySelectorAll('[data-property]')].map(v=>v.dataset.property));
    const container=document.createElement('div');container.dataset.catalog='';
    const groups=new Map();
    for(const field of object.fields){
      const key=field.path.split('/').at(-1);
      if(!primary&&(covered.has(key)||(key==='scale'&&covered.has('axis_scale'))||(key==='tick'&&covered.has('tick_direction'))))continue;
      if(!groups.has(field.group))groups.set(field.group,[]);groups.get(field.group).push(field);
    }
    let groupIndex=0;
    for(const [group,entries]of groups){
      const section=document.createElement('details');section.dataset.propertySection=group;section.open=primary&&groupIndex++<2;
      const heading=document.createElement('summary');heading.textContent=group;section.append(heading);
      for(const field of entries){
        const row=document.createElement('label');row.append(document.createTextNode(field.label));
        const input=document.createElement(field.kind==='choice'?'select':'input');
        input.dataset.catalogField=field.id;
        const key=field.path.split('/').at(-1);
        input.dataset.property=({'Color scale/axis/scale':'color_scale','Color scale/axis/min':'vmin','Color scale/axis/max':'vmax'})[field.id]??(primary&&['line_color','point_color'].includes(key)&&!container.querySelector('[data-property=color]')?'color':key);
        let base=clone(field.value);
        input.addEventListener('focus',()=>{base=clone(propertyCatalog.find(v=>v.id===object.id)?.fields.find(v=>v.id===field.id)?.value??field.value);});
        if(field.kind==='choice')for(const value of field.choices){const option=document.createElement('option');option.value=value;option.textContent=caption(value);input.append(option);}
        if(field.kind==='boolean'){input.type='checkbox';input.checked=field.value;}
        else if(field.kind==='color'){input.type='color';input.value='#'+['r','g','b'].map(k=>Math.round(field.value[k]*255).toString(16).padStart(2,'0')).join('');}
        else{if(input.tagName==='INPUT')input.type=field.kind==='number'?'number':'text';input.value=field.kind==='numbers'?field.value.join(', '):field.value;if(field.kind==='number')input.step=field.integer?'1':'any';}
        function submit(){try{
          let value=field.kind==='boolean'?input.checked:field.kind==='number'?Number(input.value):field.kind==='numbers'?input.value.split(/[,;\s]+/).filter(Boolean).map(Number):input.value;
          if(field.kind==='color')value={...base,...Object.fromEntries(['r','g','b'].map((k,i)=>[k,parseInt(input.value.slice(1+i*2,3+i*2),16)/255]))};
          if((typeof value==='number'&&!Number.isFinite(value))||(Array.isArray(value)&&value.some(v=>!Number.isFinite(v))))throw Error('Enter finite numbers');
          replayEdit('property',{object_id:object.id,property_id:field.id,value,base_value:base});
        }catch(e){fail(e);}}
        input.addEventListener('change',submit);row.append(input);section.append(row);
        if(field.kind==='color'){
          const opacityRow=document.createElement('label');opacityRow.textContent=field.label+' opacity';const alpha=document.createElement('input');alpha.type='number';alpha.min=0;alpha.max=1;alpha.step=.05;alpha.value=field.value.a;alpha.dataset.catalogAlpha=field.id;
          alpha.addEventListener('change',()=>replayEdit('property',{object_id:object.id,property_id:field.id,value:{...field.value,a:Number(alpha.value)},base_value:field.value}));opacityRow.append(alpha);section.append(opacityRow);
        }
      }
      container.append(section);
    }
    for(const text of object.notices){const note=document.createElement('p');note.className='figgy-property-note';note.textContent=text;container.append(note);}
    fields.append(container);
  }
  function displaySize(){const rect=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;return [Math.max(1,Math.round(rect.width*dpr)),Math.max(1,Math.round(rect.height*dpr))];}
  function resizeSurface(){const [width,height]=displaySize();if(canvas.width===width&&canvas.height===height)return false;const previous=[canvas.width,canvas.height];canvas.width=width;canvas.height=height;wheelArea=null;chart.resize(width,height);positionInline();dirty=true;trace('surface.resized',{previous});return true;}
  let resizeQueued=false;
  function resize(){if(!chart || disposed)return;const [width,height]=displaySize();if(!resizeQueued&&(canvas.width!==width||canvas.height!==height)){resizeQueued=true;enqueue(()=>{try{return resizeSurface();}finally{resizeQueued=false;}});}}
  function recordFrame(){syncPanelFocus();if(kind)local=snapshot();else{const r=bounds();/* Selection rectangles include the model's 2px handle padding. */wheelArea=[r[0]+2,r[1]+2,r[2]-4,r[3]-4];}dirty=false;stats.surface_frames++;}
  async function readyDisplayedFrame(){
    if(disposed)throw Error('Widget disposed');
    resizeSurface();
    do{trace('ready_frame.started');await chart.first_frame_ready();trace('ready_frame.completed');if(disposed)throw Error('Widget disposed');recordFrame();}while(resizeSurface());
  }
  const observer=new ResizeObserver(()=>{resize();positionInline();});
  let pixelRatio=devicePixelRatio||1;
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
    // DPR can change without a CSS resize or a media-query change event. Read
    // only the scalar each frame; measure layout through the common resize path
    // only when the scale changes.
    const nextPixelRatio=devicePixelRatio||1;
    if(nextPixelRatio!==pixelRatio){pixelRatio=nextPixelRatio;resize();positionInline();}
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
  async function exporting(scale=1){trace('export.flush_started',{scale});await controlQueue;await flush();trace('export.flush_completed');return enqueue(async()=>{cancelChooser();await waitForFrame();stats.png_exports++;trace('export.render_started',{scale});const data=bytes(await chart.export_png(scale));trace('export.render_completed',{bytes:data.byteLength});return data;},true);}
  const download=data=>{const url=URL.createObjectURL(new Blob([data],{type:'image/png'})),a=document.createElement('a');a.href=url;a.download='figure.png';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  function onState(){enqueue(()=>{const state=model.get('state');propertyCatalog=clone(state.property_catalog??propertyCatalog);editHistory=state.edit_history??{};historyControls();outlineNodes=clone(state.outline??outlineNodes);boundedView=clone(state.bounded_view??boundedView);exportedCode=state.code ?? exportedCode;if(state.revision>revision && !inflight){
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
      propertyCatalog=clone(message.state.property_catalog??propertyCatalog);editHistory=message.state.edit_history??{};historyControls();properties();idle();
    });
    else if(message.action==='history_result')enqueue(()=>{
      historyBusy=false;editHistory=message.state.edit_history??{};revision=message.state.revision;
      if(message.operation!=='property'){selected=null;inspectorTarget=null;}
      propertyCatalog=clone(message.state.property_catalog??propertyCatalog);outlineNodes=clone(message.state.outline??outlineNodes);boundedView=clone(message.state.bounded_view??boundedView);
      exportedCode=message.state.code??exportedCode;install(message.state.settings);historyControls();properties();
      if(message.error)fail(message.error);
      const finish=controlFinish;controlFinish=null;finish?.();
    });
    else if(message.action==='barrier' || message.action==='export' || message.action==='prepare'){
      const request={requestId:message.id,action:message.action};trace('request.received',request);
      // Do not block the serialized queue while waiting for an ack processed by it.
      (async()=>{const requestedAt=performance.now();try{if(message.action==='prepare')startInit();await initialized;trace('request.initialized',request);await controlQueue;await queue;trace('request.queue_drained',request);await flush();trace('request.edits_acknowledged',request);let result=null;
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
  function selectPanelAt(point){
    const panels=panelsAt(point);if(focusIndex()===null&&panels.length>1){openChooser(panels.map(panelChoice),point);return;}
    const at=panelAt(point);selected=null;chart.on_press(-100,-100);chart.on_release();chart.set_picked_data('null');
    if(at!==null)setPointerLayer(baseLayer(at));
    local=snapshot();focusedPanel=at===null?null:panelId(at);observedLayer=clone(local.config.active_layer??'Base');wheelArea=null;dirty=true;commit();
  }
  canvas.addEventListener('pointerdown',e=>{if(!chart||e.button!==0)return;inspectorOwner=null;if(inlineText){finishInline(true);canvas.focus({preventScroll:true});return;}e.preventDefault();canvas.focus({preventScroll:true});canvas.setPointerCapture(e.pointerId);const point=localPoint(e),pointSize=[canvas.width,canvas.height];
    if(drawingTool!=='select'){
      if(hasPanels()&&(focusIndex()===null||panelAt(point)!==focusIndex())){enqueue(()=>{cancelDrawing();selectPanelAt(point);});return;}
      const g={tool:drawingTool,start:point,end:point,data:root.querySelector('[data-anchor-data]').checked,area:[0,0,canvas.width,canvas.height]};drawingGesture=g;
      enqueue(()=>{if(g!==drawingGesture)return;g.panel=kind?[0,0,local.config.chart_area.width,local.config.chart_area.height]:panelRect(0);if(!inRect(g.start,g.panel)){cancelDrawing();return;}g.area=drawingArea()??g.area;const [x,y,w,h]=g.area;if(/^[hv]/.test(g.tool)&&(g.start[0]<x||g.start[0]>x+w||g.start[1]<y||g.start[1]>y+h)){cancelDrawing();return;}previewDrawing();});return;
    }
    pointer={point,origin:point,moved:false,pan:false,target:null,handle:null};const gesture=pointer;inputAt=performance.now();enqueue(async()=>{
    if(!kind){point[0]*=canvas.width/pointSize[0];point[1]*=canvas.height/pointSize[1];gesture.size=[canvas.width,canvas.height];}
    const [x,y]=point;
    if(hasPanels()&&(panelAt(point)!==focusIndex()||focusIndex()===null)){
      gesture.focusOnly=true;selectPanelAt(point);return;
    }
    if(kind){
      if(await textAnnotationAt(point))chart.set_active_layer(JSON.stringify('Annotations'));
      gesture.handle=selected?chart.resize_handle(selected,x,y):null;
      gesture.target=gesture.handle?selected:chart.hit_decoration(x,y,root.querySelector('[data-area]').checked);
      selected=gesture.target;
      if(selected)chart.select_decoration(selected);else{const hit=JSON.parse(chart.pick(x,y,true));selected=hit?(kind==='radial'?`slice_${hit.group}_${hit.index}`:hit.series_id):null;}
    }else{
      // Keep existing resize handles before probing other axis owners.
      if(selectedHandleAt(point)){chart.on_press(x,y);dirty=true;return;}
      const index=panelIndex(local.config.active_layer);
      const annotations=local.config.annotations;
      let annotation=null;
      if(index===0&&annotations?.visible!==false&&annotations?.items?.length){await annotationGeometry();const at=chart.hit_annotation(x,y);if(at!==undefined&&at!==null)annotation=at;}
      const hits=annotation===null?decorationsAt(point,index):[{layer:'Annotations',target:`annotation_${annotation}`}];
      const probeState=snapshot();probeState.config.active_layer=baseLayer(index);
      const original=JSON.parse(chart.active_layer());chart.set_active_layer(JSON.stringify(baseLayer(index)));
      const area=JSON.parse(chart.decoration_bounds(elementName('data_area',probeState)))?.rect??panelRect(index);chart.set_active_layer(JSON.stringify(original));
      const inside=inRect(point,area);
      gesture.pan=annotation===null&&hits.every(h=>h.target.endsWith('data_area'))&&inside&&!root.querySelector('[data-area]').checked;
      stats.last_pointer_hit=hits[0]?.target??null;stats.last_pointer_pan=gesture.pan;
      if(gesture.pan){
        chart.on_press(-100,-100);chart.on_release();const picks=await pickPanelCandidates(point,index);
        if(picks.length>1){gesture.choices=picks.map(dataChoice);return;}
        const picked=picks[0],old=JSON.parse(chart.get_config()).picked_data?.refs?.[0],same=picked&&JSON.stringify(picked.ref)===JSON.stringify(old);
        if(picked)setPointerLayer(picked.layer);
        selected=same?null:picked?.ref.series_id??null;
        chart.set_picked_data(JSON.stringify(!same&&picked?{refs:[picked.ref]}:null));
      }else if(hits.length>1){gesture.choices=hits.map(elementChoice);return;}
      else{
        const hit=hits[0];chart.set_picked_data('null');if(hit)setPointerLayer(hit.layer);
        selected=hostTarget(hit?.target??null);chart.on_press(x,y);
      }
    }
    dirty=true;properties();
  });});
  canvas.addEventListener('pointermove',e=>{if(!chart)return;const next=localPoint(e);hoverPoint=next;if(drawingGesture){const g=drawingGesture,r=/^[hv]/.test(g.tool)?g.area:g.panel;g.end=r?[Math.max(r[0],Math.min(r[0]+r[2],next[0])),Math.max(r[1],Math.min(r[1]+r[3],next[1]))]:next;previewDrawing();return;}if(!pointer)return;const gesture=pointer,nextSize=[canvas.width,canvas.height];inputAt=performance.now();enqueue(()=>{
    if(gesture.focusOnly)return;
    if(!kind){next[0]*=canvas.width/nextSize[0];next[1]*=canvas.height/nextSize[1];const oldSize=gesture.size??nextSize;gesture.point=gesture.point.map((v,i)=>v*(i?canvas.height:canvas.width)/oldSize[i]);gesture.origin=gesture.origin.map((v,i)=>v*(i?canvas.height:canvas.width)/oldSize[i]);gesture.size=[canvas.width,canvas.height];}
    const distance=Math.hypot(next[0]-gesture.origin[0],next[1]-gesture.origin[1]);if(distance>=3)gesture.moved=true;
    const old=gesture.point;if(gesture.moved||(!kind&&!gesture.pan))gesture.point=next;
    if(kind){if(gesture.target&&gesture.moved&&(next[0]!==old[0]||next[1]!==old[1]))chart.drag(gesture.target,next[0]-old[0],next[1]-old[1],gesture.handle??undefined);}
    else if(gesture.pan){if(gesture.moved){stats.pan_updates=(stats.pan_updates??0)+1;const s=snapshot(),r=bounds();delete s.config.picked_data;selected=null;navigateDocumentAxis(s,'x',1,.5,-(next[0]-old[0])/r[2]);navigateDocumentAxis(s,'y',1,.5,(next[1]-old[1])/r[3]);install(s);}}
    else if(!gesture.choices)chart.on_move(next[0]-old[0],next[1]-old[1]);dirty=true;
  });});
  function release(e){if(drawingGesture){const g=drawingGesture;if(e.type==='pointercancel'){cancelDrawing();return;}g.end=localPoint(e);g.released=true;enqueue(()=>finishDrawing(g));return;}if(!pointer)return;const gesture=pointer;pointer=null;enqueue(()=>{if(gesture.focusOnly)return;if(!kind)chart.on_release();if(gesture.choices&&!gesture.moved&&e.type!=='pointercancel'){openChooser(gesture.choices,gesture.origin);return;}if(selected&&!gesture.moved&&!selectedAnnotation()?.kind.Text)showProperties();commit();});}
  root.querySelector('.figgy-stage').addEventListener('pointerdown',e=>{if(e.target===e.currentTarget&&hasPanels())enqueue(()=>selectPanelAt([-100,-100]));});
  canvas.addEventListener('pointerup',release);canvas.addEventListener('pointercancel',release);canvas.addEventListener('pointerleave',()=>{hoverPoint=null;});
  canvas.addEventListener('wheel',e=>{
    if(chooser){e.preventDefault();return;}
    if(inlineText){e.preventDefault();return;}
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
    if(!chart||kind||!wheelArea||(hasPanels()&&focusIndex()===null))return;const point=position(e),a=wheelArea;if(point[0]<a[0]||point[0]>=a[0]+a[2]||point[1]<a[1]||point[1]>=a[1]+a[3])return;e.preventDefault();inputAt=performance.now();const ctrl=e.ctrlKey,shift=e.shiftKey,delta=e.deltaY||e.deltaX,pointSize=[canvas.width,canvas.height];enqueue(()=>{
    point[0]*=canvas.width/pointSize[0];point[1]*=canvas.height/pointSize[1];
    const s=snapshot(),r=bounds(),factor=Math.exp(Math.max(-12,Math.min(12,delta/(e.deltaMode===1?1:40)))*.1),x=Math.max(0,Math.min(1,(point[0]-r[0])/r[2])),y=1-Math.max(0,Math.min(1,(point[1]-r[1])/r[3]));
    if(!shift||ctrl)navigateDocumentAxis(s,'x',factor,x);
    if(!ctrl||shift)navigateDocumentAxis(s,'y',factor,y);
    install(s);commit();
  });},{passive:false});
  canvas.addEventListener('keydown',e=>{if(!chart)return;if(e.key==='F11'){e.preventDefault();fullscreen().catch(fail);return;}if(drawingTool!=='select')return;if((e.key==='Delete'||e.key==='Backspace')&&selected&&(selected.startsWith('annotation:')||/^annotation_\d+$/.test(selected))){e.preventDefault();enqueue(()=>{const s=snapshot(),owner=kind?s[kind]:s.config,index=kind?Number(selected.slice(11)):owner.annotations.items.findIndex(v=>'annotation:'+v.id===selected);if(index>=0)owner.annotations.items.splice(index,1);if(kind)owner.decorations.selected=null;selected=null;install(s);commit();});return;}if(e.key!=='Escape'&&!e.key.startsWith('Arrow'))return;e.preventDefault();const step=e.shiftKey?10:1;enqueue(()=>{
    if(e.key==='Escape'){selected=null;focusedPanel=null;observedLayer=clone(local.config.active_layer??'Base');wheelArea=null;if(kind)chart.clear_selection();else{chart.set_picked_data('null');chart.on_press(-100,-100);chart.on_release();}}
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
    controls.forEach(control=>control.disabled=false);historyControls();drawingUI();
    root.figgy={stats,diagnostics,annotations:()=>enqueue(annotationGeometry,true),snapshot:()=>clone(local),flush:async()=>{await controlQueue;await queue;await flush();},resize,pick:(x,y,distance)=>enqueue(()=>kind?chart.pick(x,y,false):chart.pick_data(x,y,distance),true),decorations:()=>enqueue(async()=>{if(kind)return JSON.parse(chart.decorations());await waitForFrame();resizeSurface();if(dirty)await readyDisplayedFrame();return Object.fromEntries(ids.map(name=>{const id=elementName(name);return [id,JSON.parse(chart.decoration_bounds(id))];}));},true)};
    model.send({action:'ready',client,info:stats});initializedResolve();raf=requestAnimationFrame(frame);
    },true);
  }catch(e){initializedReject(e);if(!disposed){fail(e);status.textContent='WebGPU failed';model.send({action:'failed',error:String(e)});}}})();
  return ()=>{window.removeEventListener('pointerup',releaseSidebar,true);window.removeEventListener('pointercancel',releaseSidebar,true);window.removeEventListener('blur',blurDrawing);disposed=true;controlFinish?.();controlFinish=null;startInit();initializedReject(Error('Widget disposed'));cancelAnimationFrame(raf);observer.disconnect();model.off('change:state',onState);model.off('msg:custom',onMessage);queue.finally(async()=>{try{await pendingFrame;}catch{}chart?.free();chart=null;}).catch(()=>{});model.send({action:'unmounted',client});root.remove();};
}
export default {render};
