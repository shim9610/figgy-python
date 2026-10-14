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
const text = rich => rich?.segments?.map(s=>s.text).join('') ?? '';
function segments(value) {return Array.from(value,c=>({text:c,superscript:false,subscript:false,italic:false,bold:false,underline:false,greek:false}));}
const side = {bottom:'bottom_x',top:'top_x',left:'left_y',right:'right_y'};
const ids = ['chart_title','axis_title_bottom','axis_title_left','legend','axis_bottom','axis_left','tick_labels_bottom','tick_labels_left','data_area','colorbar'];
export function render({model,el}) {
  const root=document.createElement('div');root.className='figgy-editor';
  root.innerHTML=`<div class="figgy-toolbar"><strong>Browser WebGPU</strong><button data-fit>Fit</button><label><input type="checkbox" data-area> Edit plot area</label><button data-copy>Copy Python</button><button data-save>Save PNG</button><span data-status>Initializing WebGPU…</span></div><div class="figgy-body"><div class="figgy-stage"><canvas></canvas></div><div class="figgy-properties"><label>Object <select data-target></select></label><div data-fields></div><details><summary>SSOT settings</summary><textarea data-settings></textarea><button data-apply>Apply settings</button></details><details data-code-panel><summary>Python code</summary><textarea data-code readonly></textarea></details></div></div><div class="figgy-error" role="alert"></div>`;
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
  let inputAt=null,busy=0,startInit;
  const requested=new Promise(resolve=>{startInit=resolve;});
  let initializedResolve,initializedReject;
  const initialized=new Promise((resolve,reject)=>{initializedResolve=resolve;initializedReject=reject;});
  initialized.catch(()=>{});
  const fail=e=>{error.textContent=String(e?.message ?? e);};
  const enqueue=(fn,propagate=false)=>{
    const operation=queue.then(async()=>{if(disposed)throw Error('Widget disposed');busy++;try{return await fn();}finally{busy--;}});
    queue=operation.catch(fail);return propagate?operation:queue;
  };
  function snapshot(){return {schema_version:1,renderer_version:'0.16.1',config:JSON.parse(chart.get_config()),series:JSON.parse(chart.get_series()),...(background ? {background:clone(background)} : {})};}
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
      if(!accepted || !(key in accepted))throw Error(`Unknown settings field: ${path}.${key}`);
      checkNumericConversion(item,accepted[key],`${path}.${key}`);
    }
  }
  function install(settings){
    // Roll back both trees if either renderer validation rejects a local edit.
    const old=snapshot();
    try {
      if(settings.schema_version!==1 || settings.renderer_version!=='0.16.1')throw Error('Unsupported settings/renderer version');
      checkNumbers(settings);
      const mode=settings.config?.draw_style?.mode;
      if(mode==='milkyway' && settings.series.some(s=>!s.render_type.Line))throw Error('Milkyway supports line-only series; scatter and marker lines are disabled');
      if(mode==='constellation' && settings.series.some(s=>!s.render_type.ScatterLine))throw Error('Constellation requires line series with markers');
      if(settings.config?.chart_title?.top_margin < 0)throw Error('config.chart_title.top_margin must be nonnegative; use offset_y to move the title');
      for(const axis of [settings.config?.top_x,settings.config?.bottom_x,settings.config?.left_y,settings.config?.right_y,settings.config?.colorbar?.axis].filter(Boolean)){
        const min=axis.scale==='Logarithmic'?Math.log10(axis.min):axis.min, max=axis.scale==='Logarithmic'?Math.log10(axis.max):axis.max;
        if(![min,max,max-min].every(v=>typeof v==='number' && Number.isFinite(Math.fround(v))))throw Error('Axis bounds/span exceed the f32 hi/lo representation range');
      }
      chart.set_config(JSON.stringify(settings.config));chart.set_series(JSON.stringify(settings.series));chart.set_config(JSON.stringify(settings.config));clearColor(settings.background);checkNumericConversion(settings,snapshot());
    }
    catch(e){chart.set_config(JSON.stringify(old.config));chart.set_series(JSON.stringify(old.series));chart.set_config(JSON.stringify(old.config));clearColor(old.background);throw e;}
    local=snapshot();dirty=true;error.textContent='';
  }
  function post(){if(inflight || !pending)return;inflight={sequence:++sequence,settings:pending};pending=null;stats.kernel_edit_messages++;model.send({action:'edit',client,sequence,revision,settings:inflight.settings});}
  function commit(){local=snapshot();pending=clone(local);post();properties();}
  function idle(){if(!inflight && !pending){for(const resolve of barriers.splice(0))resolve();}}
  function flush(){post();return !inflight&&!pending ? Promise.resolve() : new Promise(resolve=>barriers.push(resolve));}
  let exportedCode=model.get('state').code ?? '';
  function code(){return exportedCode;}
  function properties(){
    if(!chart)return;
    local=snapshot();
    const previous=selected;select.replaceChildren();
    for(const id of [...ids,...local.series.map(s=>s.series_id)]){const option=document.createElement('option');option.value=id;option.textContent=id;select.append(option);}
    select.value=previous ?? 'chart_title';fields.replaceChildren();
    const target=select.value,cfg=local.config;
    const series=local.series.find(s=>s.series_id===target);
    function field(label,value,type,apply){
      const row=document.createElement('label');row.append(document.createTextNode(label));const input=document.createElement('input');input.type=type;input.value=value;input.dataset.property=label;
      input.addEventListener('change',()=>enqueue(()=>{const state=clone(snapshot());apply(state,type==='number'?Number(input.value):input.value);install(state);commit();}));row.append(input);fields.append(row);
    }
    function color(label,value,find){
      const hex='#'+['r','g','b'].map(k=>Math.round(value[k]*255).toString(16).padStart(2,'0')).join('');
      field(label,hex,'color',(s,v)=>{const c=find(s);['r','g','b'].forEach((k,i)=>c[k]=parseInt(v.slice(i*2+1,i*2+3),16)/255);});
    }
    let path;
    if(target==='chart_title')path=['chart_title','text'];
    else if(target.startsWith('axis_title_'))path=[side[target.slice(11)],'title_option','text'];
    else if(target==='legend')path=['legend','content'];
    if(path){const find=s=>path.reduce((n,k)=>n[k],s.config),rich=find(local);
      field('text',text(rich),'text',(s,v)=>find(s).segments=segments(v));
      field('font_size',rich.font_size,'number',(s,v)=>find(s).font_size=v);color('color',rich.color,s=>find(s).color);
      field('font',rich.font,'text',(s,v)=>find(s).font=v);
    }else if(series){const kind=Object.keys(series.render_type)[0],style=series.render_type[kind];const find=s=>s.series.find(v=>v.series_id===target).render_type[kind];
      if(style.line){color('color',style.line.line_color,s=>find(s).line.line_color);field('line_width',style.line.line_width,'number',(s,v)=>find(s).line.line_width=v);}
      if(style.scatter){color('color',style.scatter.point_color,s=>find(s).scatter.point_color);field('point_size',style.scatter.point_size,'number',(s,v)=>find(s).scatter.point_size=v);}
      if(style.matrix){field('vmin',cfg.colorbar.axis.min,'number',(s,v)=>s.config.colorbar.axis.min=v);field('vmax',cfg.colorbar.axis.max,'number',(s,v)=>s.config.colorbar.axis.max=v);}
    }else if(target.startsWith('axis_')){const key=side[target.slice(5)];for(const name of ['min','max','major_spacing','line_width'])field(name,cfg[key][name],'number',(s,v)=>s.config[key][name]=v);color('color',cfg[key].line_color,s=>s.config[key].line_color);
    }else if(target.startsWith('tick_labels_')){const key=side[target.slice(12)];field('font_size',cfg[key].label_style.font_size,'number',(s,v)=>s.config[key].label_style.font_size=v);color('color',cfg[key].label_style.color,s=>s.config[key].label_style.color);field('label_font',cfg[key].label_style.label_font,'text',(s,v)=>s.config[key].label_style.label_font=v);}
    root.querySelector('[data-settings]').value=JSON.stringify(local,null,2);root.querySelector('[data-code]').value=code();
  }
  function resize(){if(!chart || disposed)return;const rect=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;const width=Math.max(1,Math.round(rect.width*dpr)),height=Math.max(1,Math.round(rect.height*dpr));if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;enqueue(()=>{chart.resize(width,height);dirty=true;});}}
  const observer=new ResizeObserver(resize);
  const position=e=>{const r=canvas.getBoundingClientRect();return [(e.clientX-r.left)*canvas.width/r.width,(e.clientY-r.top)*canvas.height/r.height];};
  function frame(){if(disposed)return;if(chart && dirty && !busy){try{chart.frame();dirty=false;stats.surface_frames++;if(inputAt!==null){stats.last_input_to_submit_ms=performance.now()-inputAt;inputAt=null;}}catch(e){fail(e);}}raf=requestAnimationFrame(frame);}
  async function exporting(scale=1){await flush();return enqueue(async()=>{stats.png_exports++;return bytes(await chart.export_png(scale));},true);}
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
      // Do not block the serialized queue while waiting for an ack processed by it.
      (async()=>{const requestedAt=performance.now();try{if(message.action==='prepare')startInit();await initialized;await queue;await flush();let result=null;
        if(message.action==='prepare')result=await enqueue(async()=>{
          const start=performance.now(),stages=[];status.textContent='Preparing GPU shaders…';
          try{await chart.prewarm_all_with_progress(event=>{stages.push(event);status.textContent=`Preparing GPU: ${event.stage}`;});await chart.first_frame_ready();dirty=true;
            return {backend:'webgpu',ready:true,elapsed_ms:performance.now()-requestedAt,prewarm_ms:performance.now()-start,stages,persistent_cache_supported:false};
          }finally{status.textContent='Browser GPU · resident data';}
        },true);
        const data=message.action==='export'?await exporting(message.scale):null;model.send({action:'stats',info:stats});model.send({action:'result',id:message.id,result},{},data?[data]:[]);}catch(e){model.send({action:'result',id:message.id,error:String(e)});}})();
    }
  }
  model.on('change:state',onState);model.on('msg:custom',onMessage);
  select.addEventListener('change',()=>enqueue(()=>{selected=select.value;properties();}));
  root.querySelector('[data-copy]').addEventListener('click',async()=>{try{await queue;await flush();await enqueue(async()=>{const value=code();root.querySelector('[data-code]').value=value;root.querySelector('[data-code-panel]').open=true;try{await navigator.clipboard.writeText(value);}catch{root.querySelector('[data-code]').select();}},true);}catch(e){fail(e);}});
  root.querySelector('[data-save]').addEventListener('click',()=>{exporting().then(download).catch(fail);});
  root.querySelector('[data-fit]').addEventListener('click',()=>enqueue(async()=>{await chart.auto_fit_all(0.05);dirty=true;commit();}));
  root.querySelector('[data-apply]').addEventListener('click',()=>enqueue(()=>{install(JSON.parse(root.querySelector('[data-settings]').value));commit();}));
  canvas.addEventListener('pointerdown',e=>{if(!chart)return;e.preventDefault();canvas.setPointerCapture(e.pointerId);const [x,y]=position(e);pointer=[x,y];inputAt=performance.now();enqueue(async()=>{
    const hit=chart.hit_test(x,y);selected=hit;
    if((hit===null || hit==='data_area')&&!root.querySelector('[data-area]').checked){chart.on_press(-100,-100);chart.on_release();const picked=await chart.pick_data(x,y,6);const identity=picked?JSON.parse(picked):null;selected=identity?.series_id??null;chart.set_picked_data(JSON.stringify(identity?{refs:[Object.fromEntries(Object.entries(identity).filter(([k])=>k!=='distance_px'))]}:null));}
    else {chart.set_picked_data('null');chart.on_press(x,y);}
    dirty=true;properties();
  });});
  canvas.addEventListener('pointermove',e=>{if(!pointer || !chart)return;const next=position(e),old=pointer;pointer=next;inputAt=performance.now();enqueue(()=>{chart.on_move(next[0]-old[0],next[1]-old[1]);dirty=true;});});
  function release(){if(!pointer)return;pointer=null;enqueue(()=>{chart.on_release();commit();});}
  canvas.addEventListener('pointerup',release);canvas.addEventListener('pointercancel',release);
  canvas.addEventListener('wheel',e=>{e.preventDefault();if(!chart)return;inputAt=performance.now();enqueue(()=>{
    const s=snapshot(),factor=Math.exp(e.deltaY*0.001);for(const key of Object.values(side)){const a=s.config[key];if(a.scale==='Linear'){const mid=(a.min+a.max)/2,half=(a.max-a.min)*factor/2;a.min=mid-half;a.max=mid+half;}}
    install(s);commit();
  });},{passive:false});
  model.send({action:'mounted',client});
  (async()=>{try{
    if(!model.get('auto_prepare')){status.textContent='GPU not prepared · run await fig.prepare_async()';await requested;}
    if(disposed)return;
    await enqueue(async()=>{
    if(!navigator.gpu)throw Error('WebGPU is unavailable. Use a supported browser/secure origin; kernel PNG fallback requires an explicit native Figure.widget(backend="png").');
    if(!kernelModule && !model.get('wasm').byteLength)throw Error('Transfer snapshots were released. Recreate the Figure, or use retain_notebook_data=True before display.');
    const module=await loadKernel(model);if(disposed)return;
    canvas.width=local.config.chart_area.width;canvas.height=local.config.chart_area.height;
    canvas.style.aspectRatio=`${canvas.width}/${canvas.height}`;
    chart=await module.FiggyChart.create(canvas);chart.set_pool_auto_growth(true);
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
    chart.set_config(JSON.stringify(local.config));chart.set_series(JSON.stringify(local.series));chart.set_config(JSON.stringify(local.config));
    clearColor(local.background);
    await chart.first_frame_ready();properties();observer.observe(canvas);resize();status.textContent='Browser GPU · resident data';
    if(disposed)return;
    controls.forEach(control=>control.disabled=false);
    root.figgy={stats,snapshot:()=>clone(local),flush,resize,pick:(x,y,distance)=>enqueue(()=>chart.pick_data(x,y,distance),true)};
    model.send({action:'ready',client,info:stats});initializedResolve();raf=requestAnimationFrame(frame);
    },true);
  }catch(e){initializedReject(e);if(!disposed){fail(e);status.textContent='WebGPU failed';model.send({action:'failed',error:String(e)});}}})();
  return ()=>{disposed=true;startInit();initializedReject(Error('Widget disposed'));cancelAnimationFrame(raf);observer.disconnect();model.off('change:state',onState);model.off('msg:custom',onMessage);queue.finally(()=>{chart?.free();chart=null;}).catch(()=>{});model.send({action:'unmounted',client});root.remove();};
}
export default {render};
