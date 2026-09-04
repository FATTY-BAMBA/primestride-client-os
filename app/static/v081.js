(() => {
  const lab = document.getElementById('ingestion-lab');
  if (!lab) return;

  const companyId = lab.dataset.companyId;
  const drop = document.getElementById('ingestion-drop');
  const input0 = document.getElementById('ingestion-file');
  const input = input0.cloneNode(true); input0.replaceWith(input);
  const results = document.getElementById('inspection-results');
  const errorBox = document.getElementById('ingestion-error');
  const categorySelect = document.getElementById('inspection-category');
  const sourceInput = document.getElementById('inspection-source');
  const save0 = document.getElementById('inspection-save');
  const saveBtn = save0.cloneNode(true); save0.replaceWith(saveBtn);
  const saveStatus = document.getElementById('inspection-save-status');

  const MAX_FILE_BYTES = 20 * 1024 * 1024;
  const MAX_SCAN_ROWS = 1200;
  const MAX_DATA_ROWS = 500;
  let inspection = null;

  const RULES = [
    {target:'Customer.code',labels:['客戶編號','客戶代號','customer code','client code','customer id','客編'],tags:['customer_identity','customer_product']},
    {target:'Customer.name',labels:['客戶名稱','客戶','customer name','customer','client name','client','公司名稱'],tags:['customer_identity','customer_product']},
    {target:'Contact.name',labels:['聯絡人','窗口','contact name','contact'],tags:[]},
    {target:'Product.code',labels:['品號','料號','sku','product code','item code','產品編號'],tags:['product_spec','customer_product']},
    {target:'Product.name',labels:['品名','產品名稱','product name','item name','產品'],tags:['product_spec','customer_product']},
    {target:'Specification.value',labels:['規格','尺寸','specification','spec','size','型號'],tags:['product_spec']},
    {target:'Material.name',labels:['材質','材料','material','paper','紙材','紙張'],tags:['product_spec']},
    {target:'Quote.quote_number',labels:['報價單號','報價編號','quote no','quote number','quotation no','quotation number'],tags:['historical_quotes','quote_history']},
    {target:'Quote.created_at',labels:['報價日期','quote date','quotation date'],tags:['historical_quotes','quote_history','time_fields']},
    {target:'QuoteLine.quantity',labels:['數量','qty','quantity','訂購數量'],tags:['quantity']},
    {target:'QuoteLine.unit_price',labels:['單價','報價單價','unit price','quoted price'],tags:['quoted_price','quote_history']},
    {target:'Quote.total',labels:['總價','報價金額','報價總額','total price','quotation amount','quote amount'],tags:['quoted_price','quote_history']},
    {target:'Quote.accepted_price',labels:['成交價','成交金額','accepted price','deal price','成交單價'],tags:['accepted_price']},
    {target:'Quote.salesperson',labels:['salesperson','sales rep','sales representative','業務','業務員','業務人員'],tags:[]},
    {target:'MaterialCost.unit_cost',labels:['材料成本','材成本','material cost','紙張成本'],tags:['material_cost','cost']},
    {target:'Cost.processing',labels:['加工成本','加工費','processing cost','加工單價'],tags:['processing_cost','cost']},
    {target:'Metric.margin',labels:['毛利','毛利率','margin','gross profit','gross margin'],tags:['margin']},
    {target:'Order.order_number',labels:['訂單編號','訂單號','order no','order number','sales order'],tags:['order_reference','order_history']},
    {target:'WorkOrder.work_order_number',labels:['工單編號','工單號','製令','製令單號','work order no','work order number','wo no'],tags:['work_order_id','work_order_history']},
    {target:'WorkOrder.promised_date',labels:['交期','承諾交期','預計交期','due date','promised date','delivery date'],tags:['promised_date','time_fields']},
    {target:'Operation.stage',labels:['站別','生產站別','製程','工序','stage','process','operation'],tags:['production_stages','production_events']},
    {target:'Operation.machine',labels:['機台','機器','machine','equipment'],tags:['station_machine','production_events']},
    {target:'Operation.assignee',labels:['負責人','作業員','經手人','operator','assignee','responsible person'],tags:['assignee']},
    {target:'Operation.actual_start',labels:['開始時間','實際開始','start time','actual start','start date'],tags:['actual_timestamps','time_fields','production_events']},
    {target:'Operation.actual_end',labels:['完成時間','實際完成','end time','actual end','completed at','completion date'],tags:['actual_timestamps','time_fields','production_events']},
    {target:'WorkException.reason',labels:['延誤原因','異常原因','重工原因','例外備註','delay reason','rework reason','exception reason','異常'],tags:['exceptions','production_events']},
    {target:'Metric.revenue',labels:['營收','銷售額','revenue','sales amount'],tags:['revenue']},
    {target:'Metric.cost',labels:['總成本','total cost'],tags:['cost']},
    {target:'MetricDefinition.name',labels:['kpi','指標','metric','管理指標'],tags:['kpi_definitions']},
    {target:'PricingRule.note',labels:['報價規則','計價規則','pricing rule','pricing logic','加價規則','折扣規則'],tags:['pricing_rules']},
    {target:'Quote.exception_note',labels:['特殊報價','例外報價','備註','remark','notes','note','exception note'],tags:['exception_examples']}
  ];

  const MODULE_TAGS = {
    4:new Set(['historical_quotes','customer_identity','product_spec','quantity','quoted_price','accepted_price','material_cost','processing_cost','pricing_rules','exception_examples']),
    5:new Set(['work_order_id','order_reference','product_spec','quantity','promised_date','production_stages','station_machine','assignee','current_status','actual_timestamps','exceptions']),
    6:new Set(['quote_history','order_history','work_order_history','revenue','cost','margin','customer_product','time_fields','production_events','kpi_definitions'])
  };

  drop.onclick = e => { if (e.target !== input) input.click(); };
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('dragover'); };
  drop.ondragleave = () => drop.classList.remove('dragover');
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove('dragover'); if (e.dataTransfer.files[0]) analyzeFile(e.dataTransfer.files[0]); };
  input.onchange = () => input.files[0] && analyzeFile(input.files[0]);
  saveBtn.onclick = saveInspection;

  function norm(v){ return String(v ?? '').trim().toLowerCase().replace(/[\s_\-\/()（）:：.]+/g,' '); }
  function blank(v){ return v===null || v===undefined || String(v).trim()===''; }
  function rowCopy(r){ const out=Array.isArray(r)?Array.from(r,v=>v??''):[]; while(out.length&&blank(out[out.length-1]))out.pop(); return out; }
  function nonempty(r){ return rowCopy(r).filter(v=>!blank(v)).length; }
  function isAsciiPhrase(s){ return /^[a-z0-9 %]+$/i.test(s); }

  function labelScore(header,label){
    const h=norm(header),l=norm(label); if(!h||!l)return 0; if(h===l)return 1;
    if(isAsciiPhrase(l)){
      const ht=h.split(' '),lt=l.split(' '); const hs=new Set(ht);
      if(lt.every(t=>hs.has(t))) return 0.86;
      return 0;
    }
    if(h.includes(l)||l.includes(h)) return 0.86;
    return 0;
  }
  function baseMap(header){
    let best={target:null,score:0,tags:[]};
    for(const rule of RULES)for(const label of rule.labels){const score=labelScore(header,label);if(score>best.score)best={...rule,score};}
    return best.score>=0.5?best:{target:null,score:0,tags:[]};
  }
  function contextualMap(header,category){
    const h=norm(header);
    if(['status','狀態','目前狀態','current status','進度'].includes(h)){
      if(category==='quotes') return {target:'Quote.status',score:0.78,tags:[]};
      if(category==='work_orders') return {target:'WorkOrder.status',score:0.82,tags:['current_status']};
      return {target:null,score:0,tags:[]};
    }
    if(['date','日期'].includes(h)) return {target:null,score:0,tags:[]};
    return baseMap(header);
  }

  function looksTotalOrNote(r){ const t=norm(rowCopy(r).filter(v=>!blank(v)).join(' ')); return /^(total|subtotal|grand total|sum|合計|總計|小計|備註|note|notes|說明)/.test(t); }
  function activeSegments(rows,rowIndex){
    const header=rowCopy(rows[rowIndex]); const max=Math.max(header.length,...rows.slice(rowIndex+1,rowIndex+11).map(r=>r.length),0); const active=[];
    for(let c=0;c<max;c++){
      const headerHit=!blank(header[c]); let dataHits=0,seen=0;
      for(const r of rows.slice(rowIndex+1,rowIndex+11)){seen++;if(!blank(r[c]))dataHits++;}
      active[c]=headerHit || (seen&&dataHits/seen>=0.25);
    }
    const segs=[];let start=null;
    for(let c=0;c<=active.length;c++){
      if(c<active.length&&active[c]){if(start===null)start=c;}
      else if(start!==null){if(c-start>=2)segs.push([start,c-1]);start=null;}
    }
    return segs.length?segs:[[0,Math.max(1,header.length-1)]];
  }
  function segmentRow(row,a,b){ return Array.from({length:b-a+1},(_,i)=>row[a+i]??''); }
  function headerScore(row){
    const cells=rowCopy(row).filter(v=>!blank(v)); if(cells.length<2)return-10;
    let mapped=0,textish=0; for(const v of cells){if(baseMap(v).target)mapped++;if(!/^[-+]?\d+(?:[.,]\d+)?%?$/.test(String(v).trim()))textish++;}
    return mapped*5 + Math.min(cells.length,12) + textish*0.5 + (looksTotalOrNote(row)?-10:0);
  }
  function detectRegions(rawRows,sheetName='Sheet'){
    const rows=rawRows.slice(0,MAX_SCAN_ROWS).map(rowCopy); const regs=[];
    for(let ri=0;ri<rows.length;ri++){
      for(const [a,b] of activeSegments(rows,ri)){
        const h=segmentRow(rows[ri],a,b),hs=headerScore(h); if(hs<5)continue;
        const data=[];let blankRun=0;
        for(let r=ri+1;r<rows.length;r++){
          const seg=segmentRow(rows[r],a,b);
          if(nonempty(seg)===0){blankRun++;if(blankRun>=2&&data.length>=2)break;continue;}blankRun=0;
          if(looksTotalOrNote(seg)&&data.length>=2)break;
          if(headerScore(seg)>=hs+3&&data.length>=2)break;
          data.push(seg); if(data.length>=MAX_DATA_ROWS)break;
        }
        if(!data.length)continue;
        const mapped=h.filter(v=>!blank(v)&&baseMap(v).target).length;
        const density=data.slice(0,50).reduce((n,r)=>n+nonempty(r),0)/(Math.max(1,Math.min(50,data.length))*Math.max(1,h.length));
        regs.push({sheetName,headerRow:ri,startCol:a,endCol:b,headers:h,rows:data,score:hs+mapped*3+Math.min(data.length,30)*0.3+density*5,mapped,density});
      }
    }
    const seen=new Set(),out=[];
    for(const r of regs.sort((x,y)=>y.score-x.score)){const k=`${sheetName}:${r.headerRow}:${r.startCol}:${r.endCol}`;if(!seen.has(k)){seen.add(k);out.push(r);}}
    return out.slice(0,8);
  }
  function bestRegion(sheetTables){ const all=sheetTables.flatMap(s=>s.regions); if(!all.length)throw new Error('No table-like region detected. This workbook may be a form/layout rather than a row-column dataset.'); all.sort((a,b)=>b.score-a.score); return {best:all[0],alts:all.slice(1,5)}; }
  function sanitize(region){
    const raw=region.headers.map(v=>String(v??'').trim()),max=Math.max(raw.length,...region.rows.map(r=>r.length),0),keep=[];
    for(let i=0;i<max;i++){if(!blank(raw[i])||region.rows.some(r=>!blank(r[i])))keep.push(i);}
    const seen=new Map();const headers=keep.map((idx,pos)=>{let h=raw[idx]||`Column ${pos+1}`;const k=norm(h)||`column ${pos+1}`,n=(seen.get(k)||0)+1;seen.set(k,n);if(n>1)h=`${h} (${n})`;return h;});
    return {headers,rows:region.rows.map(r=>keep.map(i=>r[i]??''))};
  }

  function inferCategory(headers,filename,sheetName=''){
    const text=norm(headers.join(' ')+' '+filename+' '+sheetName); const scores={quotes:0,work_orders:0,reports:0,customers:0,products:0};
    const add=(k,phrases,w)=>{for(const p of phrases)if(text.includes(norm(p)))scores[k]+=w;};
    add('quotes',['quote history','quote no','quote number','quote date','quotation','報價單號','報價日期'],5);
    add('quotes',['unit price','accepted price','quoted price','material cost','processing cost','成交價','材料成本','加工成本'],3);
    add('work_orders',['work order','工單編號','製令單號','work order no'],5);
    add('work_orders',['promised date','delivery date','生產站別','機台','開始時間','完成時間','current status'],3);
    add('reports',['revenue','gross profit','gross margin','kpi','營收','毛利','管理報表'],4);
    add('customers',['customer name','customer code','client name','客戶名稱','客戶編號'],3);
    add('products',['product code','product name','sku','品號','品名'],2);
    add('products',['specification','material','規格','材質'],1);
    const order=['quotes','work_orders','reports','customers','products']; order.sort((a,b)=>scores[b]-scores[a]); return scores[order[0]]>0?order[0]:'other';
  }

  function parseNum(v){const s=String(v??'').trim().replace(/NT\$/gi,'').replace(/[,$＄元張個]/g,'').replace(/,/g,'');if(!s)return null;if(/^[-+]?\d+(?:\.\d+)?%$/.test(s))return Number(s.slice(0,-1))/100;return /^[-+]?\d+(?:\.\d+)?$/.test(s)?Number(s):null;}
  function looksDate(v){const s=String(v??'').trim();if(/^\d{4}[\/-]\d{1,2}[\/-]\d{1,2}/.test(s)||/^\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4}/.test(s))return true;const n=Number(s);return Number.isFinite(n)&&n>20000&&n<80000;}
  function typeOf(values){const vals=values.filter(v=>!blank(v));if(!vals.length)return'empty';let n=0,d=0,b=0;for(const v of vals.slice(0,100)){if(parseNum(v)!==null)n++;if(looksDate(v))d++;if(/^(true|false|yes|no|是|否)$/i.test(String(v).trim()))b++;}const m=Math.min(vals.length,100);if(d/m>.7)return'date';if(n/m>.75)return'number';if(b/m>.8)return'boolean';return'text';}
  function normalizeStatus(v){const s=norm(v);if(['completed','complete','done','finished','完成','已完成','完工','已完工'].includes(s))return'completed';if(['in progress','進行中','加工中','生產中'].includes(s))return'in_progress';if(['pending','待處理','待加工','等待'].includes(s))return'pending';if(['delayed','delay','延誤','延期'].includes(s))return'delayed';if(['rework','重工','返工'].includes(s))return'rework';return s;}
  function profile(headers,rows,category){
    const cols=headers.map((header,i)=>{const values=rows.map(r=>r[i]),vals=values.filter(v=>!blank(v)),mapping=contextualMap(header,category);return{header,index:i,type:typeOf(values),nonempty:vals.length,missingRate:rows.length?(rows.length-vals.length)/rows.length:0,unique:new Set(vals.map(v=>String(v).trim())).size,mapping,values};});
    const fp=rows.map(r=>JSON.stringify(r.map(v=>String(v??'').trim())));return{cols,duplicates:fp.length-new Set(fp).size};
  }
  function quality(rows,prof,meta){
    const flags=[];if(meta.headerRow>0)flags.push({level:'ok',title:`Header detected on row ${meta.headerRow+1}`,detail:`Ignored ${meta.headerRow} title/metadata row(s) before the selected table.`});
    if(meta.startCol>0)flags.push({level:'ok',title:'Horizontal table region isolated',detail:`Selected columns ${meta.startCol+1}–${meta.endCol+1}; side notes/reference blocks were excluded.`});
    if(meta.alts>0)flags.push({level:'warn',title:`${meta.alts} alternate table-like region(s) found`,detail:'The highest-confidence region is shown; other regions were kept separate instead of merged.'});
    if(meta.sheets>1)flags.push({level:'ok',title:`${meta.sheets} worksheets scanned`,detail:`Selected ${meta.sheetName} as the strongest table region.`});
    if(prof.duplicates>0)flags.push({level:'warn',title:`${prof.duplicates} duplicate row(s) detected`,detail:'Review duplicates before using counts, calibration or KPI calculations.'});
    prof.cols.forEach(c=>{if(c.type==='empty')flags.push({level:'warn',title:`Empty column: ${c.header}`,detail:'No usable values in selected region.'});else if(c.missingRate>=.5)flags.push({level:'warn',title:`High missing rate: ${c.header}`,detail:`${Math.round(c.missingRate*100)}% blank.`});if(c.mapping.target==='WorkOrder.status'){const raw=new Set(c.values.filter(v=>!blank(v)).map(norm)),normalized=new Set(c.values.filter(v=>!blank(v)).map(normalizeStatus));if(raw.size>normalized.size&&raw.size>=3)flags.push({level:'warn',title:'Mixed status vocabulary detected',detail:`${raw.size} raw labels normalize to ${normalized.size} status values.`});}});
    if(!flags.length)flags.push({level:'ok',title:'No obvious structural issues in selected region',detail:'Structural profile only; business validity still requires review.'});return flags;
  }
  function evidence(category,rowCount,cols){
    const det=new Map();for(const c of cols){if(!c.mapping?.target)continue;for(const tag of c.mapping.tags||[]){const cur=det.get(tag);if(!cur||c.mapping.score>cur.conf)det.set(tag,{conf:c.mapping.score,header:c.header,target:c.mapping.target});}}
    if(category==='quotes'){det.set('historical_quotes',{conf:rowCount>=5?.95:.7,header:`${rowCount} row(s)`,target:'Dataset'});det.set('quote_history',{conf:rowCount>=5?.95:.7,header:`${rowCount} row(s)`,target:'Dataset'});}if(category==='work_orders')det.set('work_order_history',{conf:rowCount>=5?.95:.7,header:`${rowCount} row(s)`,target:'Dataset'});
    const out=[];for(const[m,allowed]of Object.entries(MODULE_TAGS))for(const[tag,info]of det)if(allowed.has(tag))out.push({moduleNo:Number(m),criterion:tag,status:info.conf>=.78?'available':'partial',source:info.header,target:info.target});const k=x=>`${x.moduleNo}:${x.criterion}`;return[...new Map(out.map(x=>[k(x),x])).values()].sort((a,b)=>a.moduleNo-b.moduleNo||a.criterion.localeCompare(b.criterion));
  }

  async function analyzeFile(file){
    clearError();results.classList.remove('active');saveStatus.textContent='';
    try{
      if(file.size>MAX_FILE_BYTES)throw new Error('Local preview limit is 20 MB. Register larger files manually until background ingestion is connected.');
      const ext=file.name.split('.').pop().toLowerCase();let parsed;
      if(['csv','tsv','txt'].includes(ext))parsed=parseDelimited(await file.text(),ext==='tsv'?'\t':null,file.name);
      else if(ext==='json')parsed=parseJson(await file.text(),file.name);
      else if(ext==='xlsx')parsed=await parseXlsx(file);
      else throw new Error('Unsupported structured file type. Use CSV, TSV, JSON or XLSX.');
      const choice=bestRegion(parsed.sheetTables),table=sanitize(choice.best);if(table.headers.length<2||!table.rows.length)throw new Error('A table candidate was found but is not structured enough to map safely.');
      const category=inferCategory(table.headers,file.name,choice.best.sheetName),rows=table.rows.slice(0,MAX_DATA_ROWS),prof=profile(table.headers,rows,category),flags=quality(rows,prof,{headerRow:choice.best.headerRow,startCol:choice.best.startCol,endCol:choice.best.endCol,alts:choice.alts.length,sheets:parsed.sheetTables.length,sheetName:choice.best.sheetName}),ev=evidence(category,choice.best.rows.length,prof.cols),hash=await sha256(file);
      inspection={file,headers:table.headers,rows,totalRows:choice.best.rows.length,prof,category,flags,evidence:ev,hash,sheets:parsed.sheetTables.map(s=>s.name),sheetName:choice.best.sheetName,headerRow:choice.best.headerRow,startCol:choice.best.startCol,endCol:choice.best.endCol,alternatives:choice.alts};categorySelect.value=category;sourceInput.value='Local browser inspection';render();
    }catch(err){showError(err?.message||String(err));}
  }

  function parseDelimited(text,forced=null,name='Delimited'){const delimiter=forced||detectDelimiter(text.slice(0,8000)),rows=[];let row=[],field='',q=false;for(let i=0;i<text.length;i++){const ch=text[i];if(q){if(ch==='"'&&text[i+1]==='"'){field+='"';i++;}else if(ch==='"')q=false;else field+=ch;}else{if(ch==='"')q=true;else if(ch===delimiter){row.push(field);field='';}else if(ch==='\n'){row.push(field.replace(/\r$/,''));rows.push(row);row=[];field='';}else field+=ch;}}if(field.length||row.length){row.push(field.replace(/\r$/,''));rows.push(row);}const clean=rows.filter(r=>nonempty(r)>0);if(!clean.length)throw new Error('No rows detected.');return{sheetTables:[{name,regions:detectRegions(clean,name)}]};}
  function detectDelimiter(s){const cs=[',','\t',';','|'];return cs.map(d=>[d,(s.match(new RegExp(d==='|'?'\\|':d,'g'))||[]).length]).sort((a,b)=>b[1]-a[1])[0][0];}
  function parseJson(text,name='JSON'){const data=JSON.parse(text),arr=Array.isArray(data)?data:(data&&typeof data==='object'?(Object.values(data).find(v=>Array.isArray(v))||[data]):[]),objs=arr.filter(x=>x&&typeof x==='object'&&!Array.isArray(x));if(!objs.length)throw new Error('No object records found in JSON.');const h=[...new Set(objs.flatMap(o=>Object.keys(o)))],rows=[h,...objs.map(o=>h.map(k=>o[k]&&typeof o[k]==='object'?JSON.stringify(o[k]):(o[k]??'')))];return{sheetTables:[{name,regions:detectRegions(rows,name)}]};}
  async function parseXlsx(file){
    const bytes=new Uint8Array(await file.arrayBuffer()),entries=await unzip(bytes),dec=new TextDecoder('utf-8'),xml=n=>entries[n]?dec.decode(entries[n]):null,workbook=xml('xl/workbook.xml');if(!workbook)throw new Error('XLSX workbook metadata could not be read.');
    const wb=parseXml(workbook),sheetNodes=els(wb,'sheet');if(!sheetNodes.length)throw new Error('No worksheet metadata found.');const relMap={},rels=xml('xl/_rels/workbook.xml.rels');if(rels)for(const r of els(parseXml(rels),'Relationship'))relMap[r.getAttribute('Id')]=r.getAttribute('Target');let shared=[];const sx=xml('xl/sharedStrings.xml');if(sx)shared=els(parseXml(sx),'si').map(si=>si.textContent||'');
    const sheets=sheetNodes.map((s,i)=>({name:s.getAttribute('name')||`Sheet ${i+1}`,rid:s.getAttribute('r:id')||s.getAttributeNS('http://schemas.openxmlformats.org/officeDocument/2006/relationships','id')})),sheetTables=[];
    for(let si=0;si<sheets.length;si++){const s=sheets[si];let target=relMap[s.rid]||`worksheets/sheet${si+1}.xml`;target=target.replace(/^\//,'');const path=target.startsWith('xl/')?target:'xl/'+target.replace(/^\.\//,''),txt=xml(path);if(!txt)continue;const doc=parseXml(txt),rows=[];for(const rn of els(doc,'row').slice(0,MAX_SCAN_ROWS)){const row=[];for(const c of els(rn,'c')){const idx=colIndex(c.getAttribute('r')||''),t=c.getAttribute('t');let val='';const v=els(c,'v')[0];if(t==='inlineStr')val=els(c,'is')[0]?.textContent||'';else if(v){const raw=v.textContent||'';val=t==='s'?(shared[Number(raw)]??raw):raw;}row[idx]=val;}rows.push(rowCopy(row));}const clean=rows.filter(r=>nonempty(r)>0);sheetTables.push({name:s.name,regions:detectRegions(clean,s.name)});}if(!sheetTables.length)throw new Error('Workbook opened but no readable worksheet content found.');return{sheetTables};
  }
  function parseXml(t){const d=new DOMParser().parseFromString(t,'application/xml');if(els(d,'parsererror').length)throw new Error('Malformed workbook XML.');return d;}
  function els(node,name){const d=[...node.getElementsByTagName(name)];if(d.length)return d;try{return[...node.getElementsByTagNameNS('*',name)];}catch{return[];}}
  function colIndex(ref){const m=String(ref).match(/^[A-Z]+/i);if(!m)return 0;let n=0;for(const ch of m[0].toUpperCase())n=n*26+(ch.charCodeAt(0)-64);return n-1;}
  async function unzip(bytes){const dv=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);let e=-1;for(let i=bytes.length-22;i>=Math.max(0,bytes.length-65557);i--){if(dv.getUint32(i,true)===0x06054b50){e=i;break;}}if(e<0)throw new Error('Invalid XLSX ZIP structure.');const count=dv.getUint16(e+10,true),off=dv.getUint32(e+16,true),out={},td=new TextDecoder('utf-8');let p=off;for(let j=0;j<count;j++){if(dv.getUint32(p,true)!==0x02014b50)break;const method=dv.getUint16(p+10,true),size=dv.getUint32(p+20,true),nl=dv.getUint16(p+28,true),el=dv.getUint16(p+30,true),cl=dv.getUint16(p+32,true),lo=dv.getUint32(p+42,true),name=td.decode(bytes.slice(p+46,p+46+nl)),ln=dv.getUint16(lo+26,true),le=dv.getUint16(lo+28,true),start=lo+30+ln+le,data=bytes.slice(start,start+size);if(name.startsWith('xl/')){if(method===0)out[name]=data;else if(method===8)out[name]=await inflate(data);}p+=46+nl+el+cl;}return out;}
  async function inflate(data){if(!('DecompressionStream'in window))throw new Error('Browser cannot decompress XLSX locally. Export as CSV or use current Chrome/Edge.');const ds=new DecompressionStream('deflate-raw');return new Uint8Array(await new Response(new Blob([data]).stream().pipeThrough(ds)).arrayBuffer());}
  async function sha256(file){const d=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());return[...new Uint8Array(d)].map(b=>b.toString(16).padStart(2,'0')).join('');}

  function render(){
    results.classList.add('active');const i=inspection;set('stat-rows',i.totalRows);set('stat-fields',i.headers.length);set('stat-mapped',i.prof.cols.filter(c=>c.mapping?.target).length);set('stat-quality',i.flags.filter(f=>f.level!=='ok').length);set('stat-hash',i.hash.slice(0,8));set('stat-filetype',i.file.name.split('.').pop().toUpperCase());categorySelect.value=i.category;
    const note=document.getElementById('xlsx-sheet-note');note.innerHTML=`Selected table: <b>${esc(i.sheetName)}</b> · header row ${i.headerRow+1} · columns ${i.startCol+1}–${i.endCol+1} · ${i.sheets.length} sheet(s) scanned${i.alternatives.length?` · ${i.alternatives.length} alternate region(s)`:''}`;
    document.getElementById('detected-fields-body').innerHTML=i.prof.cols.map(c=>{const m=c.mapping||{target:null,score:0},conf=m.score>=.8?'high':m.score>=.5?'medium':'';return`<tr><td><b>${esc(c.header)}</b><small>${c.type} · ${c.nonempty}/${i.rows.length} non-empty</small></td><td>${m.target?`<span class="mapping-target">${esc(m.target)}</span>`:'<span class="mapping-target none">No confident mapping</span>'}</td><td><span class="confidence ${conf}">${m.target?Math.round(m.score*100)+'%':'—'}</span></td><td>${Math.round(c.missingRate*100)}%</td><td>${c.unique}</td></tr>`;}).join('');
    document.getElementById('quality-list').innerHTML=i.flags.map(f=>`<div class="quality-item ${f.level}"><span>${f.level==='ok'?'✓':'△'}</span><div><b>${esc(f.title)}</b><small>${esc(f.detail)}</small></div></div>`).join('');
    document.getElementById('evidence-suggestions').innerHTML=i.evidence.length?i.evidence.map((e,idx)=>`<label class="evidence-suggestion"><input type="checkbox" data-evidence-index="${idx}" checked><div><b>Module 0${e.moduleNo} · ${esc(e.criterion)}</b><small>${esc(e.source)} → ${esc(e.target)}</small></div><em class="${e.status==='partial'?'partial':''}">${e.status}</em></label>`).join(''):'<div class="inspection-empty">No readiness evidence can be suggested confidently from this table yet.</div>';
    const h=i.headers.slice(0,14),r=i.rows.slice(0,8);document.getElementById('preview-table').innerHTML=`<thead><tr>${h.map(x=>`<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${r.map(row=>`<tr>${h.map((_,n)=>`<td>${esc(row[n]??'')}</td>`).join('')}</tr>`).join('')}</tbody>`;set('inspection-filename',i.file.name);set('inspection-meta',`${bytes(i.file.size)} · SHA-256 ${i.hash.slice(0,16)}… · locally inspected · raw file not persisted`);
  }
  async function saveInspection(){if(!inspection)return;saveBtn.disabled=true;saveStatus.textContent='Saving…';try{const category=categorySelect.value,map=inspection.prof.cols.filter(c=>c.mapping?.target).slice(0,30).map(c=>`${c.header}→${c.mapping.target}`).join('; '),notes=`v0.8.1 messy-data inspection | sheet=${inspection.sheetName} | header_row=${inspection.headerRow+1} | columns=${inspection.startCol+1}-${inspection.endCol+1} | rows=${inspection.totalRows} | fields=${inspection.headers.length} | mapped=${inspection.prof.cols.filter(c=>c.mapping?.target).length} | quality_flags=${inspection.flags.filter(f=>f.level!=='ok').length} | sha256=${inspection.hash} | mappings=${map}`;await post(`/companies/${companyId}/data-intake/register`,{filename:inspection.file.name,category,source:sourceInput.value||'Local browser inspection',notes});const selected=[...document.querySelectorAll('[data-evidence-index]:checked')].map(el=>inspection.evidence[Number(el.dataset.evidenceIndex)]).filter(Boolean);for(const e of selected)await post(`/companies/${companyId}/readiness-evidence`,{module_no:String(e.moduleNo),criterion_key:e.criterion,status:e.status,source:inspection.file.name,notes:`v0.8.1 suggestion from ${inspection.sheetName}: ${e.source} → ${e.target}. Human-confirmed before save.`});saveStatus.textContent=`Saved metadata + ${selected.length} approved evidence item(s). Reloading…`;setTimeout(()=>location.reload(),650);}catch(err){saveStatus.className='save-status error';saveStatus.textContent=err?.message||String(err);saveBtn.disabled=false;}}
  async function post(url,obj){const body=new URLSearchParams(obj),res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'},body,redirect:'follow'});if(!res.ok)throw new Error(`Save failed (${res.status})`);}
  function set(id,v){const e=document.getElementById(id);if(e)e.textContent=v;}function bytes(n){if(n<1024)return`${n} B`;if(n<1048576)return`${(n/1024).toFixed(1)} KB`;return`${(n/1048576).toFixed(1)} MB`;}function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}function showError(m){errorBox.textContent=m;errorBox.classList.add('active');}function clearError(){errorBox.textContent='';errorBox.classList.remove('active');}
})();
