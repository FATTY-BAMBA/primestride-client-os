(() => {
  const lab = document.getElementById('ingestion-lab');
  if (!lab) return;

  const companyId = lab.dataset.companyId;
  const drop = document.getElementById('ingestion-drop');
  const oldInput = document.getElementById('ingestion-file');
  const input = oldInput.cloneNode(true); // remove v0.7 listeners if browser cached old assets
  oldInput.replaceWith(input);
  const results = document.getElementById('inspection-results');
  const errorBox = document.getElementById('ingestion-error');
  const categorySelect = document.getElementById('inspection-category');
  const sourceInput = document.getElementById('inspection-source');
  const oldSave = document.getElementById('inspection-save');
  const saveBtn = oldSave.cloneNode(true);
  oldSave.replaceWith(saveBtn);
  const saveStatus = document.getElementById('inspection-save-status');

  let inspection = null;
  const MAX_FILE_BYTES = 20 * 1024 * 1024;
  const MAX_SCAN_ROWS = 1200;
  const MAX_DATA_ROWS = 500;

  const CANONICAL_RULES = [
    {target:'Customer.code', labels:['客戶編號','客戶代號','customer code','client code','customer id','客編'], tags:['customer_identity','customer_product']},
    {target:'Customer.name', labels:['客戶名稱','客戶','customer name','customer','client name','client','公司名稱'], tags:['customer_identity','customer_product']},
    {target:'Contact.name', labels:['聯絡人','窗口','contact','contact name'], tags:[]},
    {target:'Product.code', labels:['品號','料號','sku','product code','item code','產品編號'], tags:['product_spec','customer_product']},
    {target:'Product.name', labels:['品名','產品名稱','產品','product name','product','item name','item','品名 規格'], tags:['product_spec','customer_product']},
    {target:'Specification.value', labels:['規格','尺寸','spec','specification','size','型號'], tags:['product_spec']},
    {target:'Material.name', labels:['材質','材料','material','paper','紙材','紙張'], tags:['product_spec']},
    {target:'Quote.quote_number', labels:['報價單號','報價編號','quote no','quote number','quotation no','quotation number'], tags:['historical_quotes','quote_history']},
    {target:'Quote.created_at', labels:['報價日期','quote date','quotation date'], tags:['historical_quotes','quote_history','time_fields']},
    {target:'QuoteLine.quantity', labels:['數量','qty','quantity','訂購數量'], tags:['quantity']},
    {target:'QuoteLine.unit_price', labels:['單價','報價單價','unit price','quoted price','price'], tags:['quoted_price','quote_history']},
    {target:'Quote.total', labels:['總價','報價金額','報價總額','total','total price','amount','quotation amount'], tags:['quoted_price','quote_history']},
    {target:'Quote.accepted_price', labels:['成交價','成交金額','accepted price','deal price','成交單價'], tags:['accepted_price']},
    {target:'MaterialCost.unit_cost', labels:['材料成本','材成本','material cost','紙張成本'], tags:['material_cost','cost']},
    {target:'Cost.processing', labels:['加工成本','加工費','processing cost','加工單價'], tags:['processing_cost','cost']},
    {target:'Metric.margin', labels:['毛利','毛利率','margin','gross profit','gross margin'], tags:['margin']},
    {target:'Order.order_number', labels:['訂單編號','訂單號','order no','order number','sales order'], tags:['order_reference','order_history']},
    {target:'WorkOrder.work_order_number', labels:['工單編號','工單號','製令','製令單號','work order','work order no','wo no'], tags:['work_order_id','work_order_history']},
    {target:'WorkOrder.promised_date', labels:['交期','承諾交期','預計交期','due date','promised date','delivery date'], tags:['promised_date','time_fields']},
    {target:'WorkOrder.status', labels:['狀態','工單狀態','目前狀態','status','current status','進度'], tags:['current_status']},
    {target:'Operation.stage', labels:['站別','生產站別','製程','工序','stage','process','operation'], tags:['production_stages','production_events']},
    {target:'Operation.machine', labels:['機台','機器','machine','equipment'], tags:['station_machine','production_events']},
    {target:'Operation.assignee', labels:['負責人','作業員','經手人','operator','assignee','responsible person'], tags:['assignee']},
    {target:'Operation.actual_start', labels:['開始時間','實際開始','start time','actual start','start date'], tags:['actual_timestamps','time_fields','production_events']},
    {target:'Operation.actual_end', labels:['完成時間','實際完成','end time','actual end','completed at','completion date'], tags:['actual_timestamps','time_fields','production_events']},
    {target:'WorkException.reason', labels:['延誤原因','異常原因','重工原因','例外備註','exception','delay reason','rework','異常'], tags:['exceptions','production_events']},
    {target:'Metric.revenue', labels:['營收','銷售額','revenue','sales amount','sales'], tags:['revenue']},
    {target:'Metric.cost', labels:['成本','總成本','cost','total cost'], tags:['cost']},
    {target:'MetricDefinition.name', labels:['kpi','指標','metric','管理指標'], tags:['kpi_definitions']},
    {target:'PricingRule.note', labels:['報價規則','計價規則','pricing rule','pricing logic','加價規則','折扣規則'], tags:['pricing_rules']},
    {target:'Quote.exception_note', labels:['特殊報價','例外報價','備註','remark','note','exception note'], tags:['exception_examples']}
  ];

  const CATEGORY_SIGNALS = {
    quotes: ['quote','quotation','報價','單價','成交價','報價單號','材料成本','加工成本'],
    work_orders: ['work order','工單','製令','站別','製程','交期','機台','開始時間','完成時間'],
    reports: ['revenue','sales','margin','gross profit','營收','毛利','kpi','報表'],
    customers: ['customer','client','客戶','聯絡人','contact'],
    products: ['product','item','sku','品號','品名','規格','材質','material']
  };

  const MODULE_TAGS = {
    4: new Set(['historical_quotes','customer_identity','product_spec','quantity','quoted_price','accepted_price','material_cost','processing_cost','pricing_rules','exception_examples']),
    5: new Set(['work_order_id','order_reference','product_spec','quantity','promised_date','production_stages','station_machine','assignee','current_status','actual_timestamps','exceptions']),
    6: new Set(['quote_history','order_history','work_order_history','revenue','cost','margin','customer_product','time_fields','production_events','kpi_definitions'])
  };

  drop.onclick = e => { if (e.target !== input) input.click(); };
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('dragover'); };
  drop.ondragleave = () => drop.classList.remove('dragover');
  drop.ondrop = e => {
    e.preventDefault(); drop.classList.remove('dragover');
    if (e.dataTransfer.files[0]) analyzeFile(e.dataTransfer.files[0]);
  };
  input.onchange = () => input.files[0] && analyzeFile(input.files[0]);
  saveBtn.onclick = saveInspection;

  function normalize(s) {
    return String(s ?? '').trim().toLowerCase().replace(/[\s_\-\/()（）:：.]+/g, ' ');
  }
  function isBlank(v){ return v === null || v === undefined || String(v).trim() === ''; }
  function compactRow(row){
    const out = Array.isArray(row) ? Array.from(row, v => v ?? '') : [];
    while (out.length && isBlank(out[out.length-1])) out.pop();
    return out;
  }
  function nonEmptyCount(row){ return compactRow(row).filter(v => !isBlank(v)).length; }
  function looksTotalOrNote(row){
    const text = normalize(compactRow(row).filter(v=>!isBlank(v)).join(' '));
    return /^(total|subtotal|grand total|sum|合計|總計|小計|備註|note|notes|說明)/.test(text);
  }

  function scoreLabel(header, label) {
    const h = normalize(header), l = normalize(label);
    if (!h || !l) return 0;
    if (h === l) return 1;
    if (h.includes(l) || l.includes(h)) return 0.84;
    const ht = new Set(h.split(' ')), lt = l.split(' ');
    const overlap = lt.filter(x => ht.has(x)).length;
    return overlap ? 0.58 * (overlap / lt.length) : 0;
  }
  function mapHeader(header) {
    let best = null;
    for (const rule of CANONICAL_RULES) {
      for (const label of rule.labels) {
        const score = scoreLabel(header, label);
        if (!best || score > best.score) best = {...rule, score};
      }
    }
    return (!best || best.score < 0.5) ? {target:null, score:0, tags:[]} : best;
  }
  function headerRowScore(row) {
    const cells = compactRow(row).filter(v=>!isBlank(v));
    if (cells.length < 2) return -10;
    let mapped = 0, textish = 0, shortish = 0;
    for (const v of cells) {
      if (mapHeader(v).target) mapped++;
      if (!/^[-+]?\d+(?:[.,]\d+)?%?$/.test(String(v).trim())) textish++;
      if (String(v).trim().length <= 35) shortish++;
    }
    const unique = new Set(cells.map(normalize)).size;
    return mapped * 5 + Math.min(cells.length,12) + textish * .7 + shortish * .25 + (unique/cells.length) * 2 - (looksTotalOrNote(row) ? 8 : 0);
  }

  function detectRegions(rawRows, sheetName='Sheet') {
    const rows = rawRows.slice(0,MAX_SCAN_ROWS).map(compactRow);
    const candidates = [];
    for (let i=0;i<rows.length;i++) {
      const score = headerRowScore(rows[i]);
      if (score >= 5) candidates.push({rowIndex:i, score});
    }
    candidates.sort((a,b)=>b.score-a.score);
    const regions=[];
    for (const cand of candidates.slice(0,12)) {
      const header = rows[cand.rowIndex];
      const width = Math.max(1, header.length);
      const data=[];
      let blankRun=0;
      for(let r=cand.rowIndex+1;r<rows.length;r++) {
        const row=rows[r];
        if (nonEmptyCount(row)===0) {
          blankRun++;
          if (blankRun>=2 && data.length>=2) break;
          continue;
        }
        blankRun=0;
        if (looksTotalOrNote(row) && data.length>=2) break;
        const anotherHeader = headerRowScore(row) >= cand.score + 2 && data.length>=2;
        if (anotherHeader) break;
        const clipped=Array.from({length:width},(_,i)=>row[i]??'');
        if (nonEmptyCount(clipped)>0) data.push(clipped);
        if (data.length>=MAX_DATA_ROWS) break;
      }
      if (!data.length) continue;
      const mapped=header.filter(v=>!isBlank(v) && mapHeader(v).target).length;
      const density=data.slice(0,50).reduce((n,row)=>n+nonEmptyCount(row),0)/(Math.max(1,Math.min(50,data.length))*Math.max(1,width));
      const regionScore=cand.score + mapped*3 + Math.min(data.length,30)*.3 + density*5;
      regions.push({sheetName, headerRow:cand.rowIndex, headers:header, rows:data, score:regionScore, mapped, density});
    }
    const dedup=[];
    const seen=new Set();
    for(const r of regions.sort((a,b)=>b.score-a.score)) {
      const key=`${sheetName}:${r.headerRow}`;
      if(!seen.has(key)){seen.add(key);dedup.push(r);}
    }
    return dedup.slice(0,5);
  }

  function chooseBestRegion(sheetTables) {
    const all = sheetTables.flatMap(s=>s.regions);
    if (!all.length) throw new Error('No table-like region detected. The workbook may be a form/layout rather than a row-column dataset. You can still register it manually for document review.');
    all.sort((a,b)=>b.score-a.score);
    return {best:all[0], alternatives:all.slice(1,5)};
  }

  function sanitizeTable(region) {
    const rawHeaders=region.headers.map((h,i)=>String(h??'').trim());
    const maxCols=Math.max(rawHeaders.length,...region.rows.map(r=>r.length),0);
    const keep=[];
    for(let i=0;i<maxCols;i++){
      const header=rawHeaders[i]||'';
      const hasData=region.rows.some(r=>!isBlank(r[i]));
      if(!isBlank(header)||hasData) keep.push(i);
    }
    const seen=new Map();
    const headers=keep.map((idx,pos)=>{
      let h=rawHeaders[idx]||`Column ${pos+1}`;
      const key=normalize(h)||`column ${pos+1}`;
      const n=(seen.get(key)||0)+1; seen.set(key,n);
      if(n>1) h=`${h} (${n})`;
      return h;
    });
    const rows=region.rows.map(r=>keep.map(i=>r[i]??''));
    return {headers,rows};
  }

  function inferCategory(headers, filename, sheetName='') {
    const text=normalize(headers.join(' ')+' '+filename+' '+sheetName);
    const scored=Object.entries(CATEGORY_SIGNALS).map(([key,signals])=>[key,signals.reduce((n,s)=>n+(text.includes(normalize(s))?1:0),0)]).sort((a,b)=>b[1]-a[1]);
    return scored[0][1]>0?scored[0][0]:'other';
  }
  function parseNumberish(v){
    const s=String(v??'').trim().replace(/[,$＄NT$元張個pcsPCS]/g,'').replace(/,/g,'');
    if(!s) return null;
    if(/^[-+]?\d+(?:\.\d+)?%$/.test(s)) return Number(s.slice(0,-1))/100;
    return /^[-+]?\d+(?:\.\d+)?$/.test(s)?Number(s):null;
  }
  function looksDate(v){
    const s=String(v??'').trim();
    if(/^\d{4}[\/-]\d{1,2}[\/-]\d{1,2}/.test(s)||/^\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4}/.test(s)) return true;
    const n=Number(s); return Number.isFinite(n)&&n>20000&&n<80000; // Excel serial range
  }
  function inferType(values) {
    const nonempty=values.filter(v=>!isBlank(v)); if(!nonempty.length)return'empty';
    let numbers=0,dates=0,bools=0;
    for(const raw of nonempty.slice(0,100)){
      const v=String(raw).trim(); if(parseNumberish(v)!==null)numbers++; if(looksDate(v))dates++; if(/^(true|false|yes|no|是|否)$/i.test(v))bools++;
    }
    const n=Math.min(nonempty.length,100); if(dates/n>.7)return'date'; if(numbers/n>.75)return'number'; if(bools/n>.8)return'boolean'; return'text';
  }
  function normalizeStatus(v){
    const s=normalize(v);
    if(['completed','complete','done','finished','完成','已完成','完工','已完工'].includes(s))return'completed';
    if(['in progress','進行中','加工中','生產中'].includes(s))return'in_progress';
    if(['pending','待處理','待加工','等待'].includes(s))return'pending';
    if(['delayed','delay','延誤','延期'].includes(s))return'delayed';
    if(['rework','重工','返工'].includes(s))return'rework';
    return s;
  }
  function profile(headers,rows){
    const cols=headers.map((header,i)=>{
      const values=rows.map(r=>r[i]); const nonempty=values.filter(v=>!isBlank(v)); const mapping=mapHeader(header);
      return {header,index:i,type:inferType(values),nonempty:nonempty.length,missingRate:rows.length?(rows.length-nonempty.length)/rows.length:0,unique:new Set(nonempty.map(v=>String(v).trim())).size,mapping,values};
    }).filter(Boolean);
    const fingerprints=rows.map(r=>JSON.stringify(r.map(v=>String(v??'').trim()))); const duplicates=fingerprints.length-new Set(fingerprints).size;
    return {cols,duplicates};
  }
  function qualityFlags(rows,prof,meta){
    const flags=[];
    if(meta.headerRow>0) flags.push({level:'ok',title:`Header detected on row ${meta.headerRow+1}`,detail:`${meta.headerRow} title/metadata row(s) were ignored before the table.`});
    if(meta.alternatives>0) flags.push({level:'warn',title:`${meta.alternatives} additional table-like region(s) found`,detail:'The highest-confidence region is shown. Review alternate regions if this workbook contains multiple tables.'});
    if(meta.sheetCount>1) flags.push({level:'ok',title:`${meta.sheetCount} worksheets scanned`,detail:`Selected ${meta.sheetName} because it had the strongest table signal.`});
    if(prof.duplicates>0)flags.push({level:'warn',title:`${prof.duplicates} duplicate row(s) detected`,detail:'Review duplicates before using counts, calibration, or KPI calculations.'});
    const baseNames=new Map();
    prof.cols.forEach(c=>{
      const base=normalize(c.header.replace(/ \(\d+\)$/,'')); baseNames.set(base,(baseNames.get(base)||0)+1);
      if(c.type==='empty')flags.push({level:'warn',title:`Empty column: ${c.header}`,detail:'No usable values were found in the selected table region.'});
      else if(c.missingRate>=.5)flags.push({level:'warn',title:`High missing rate: ${c.header}`,detail:`${Math.round(c.missingRate*100)}% of inspected rows are blank.`});
      if(c.mapping.target==='WorkOrder.status'){
        const variants=new Set(c.values.filter(v=>!isBlank(v)).map(normalizeStatus));
        const rawVariants=new Set(c.values.filter(v=>!isBlank(v)).map(v=>normalize(v)));
        if(rawVariants.size>variants.size && rawVariants.size>=3) flags.push({level:'warn',title:'Mixed status vocabulary detected',detail:`${rawVariants.size} raw status labels collapse to ${variants.size} normalized status values.`});
      }
    });
    for(const [name,count] of baseNames){if(name&&count>1)flags.push({level:'warn',title:`Duplicate header: ${name}`,detail:`${count} columns use the same/similar header. They were kept separate for review.`});}
    if(!flags.length)flags.push({level:'ok',title:'No obvious structural issues in the selected region',detail:'This is a structural profile, not a full business-validity certification.'});
    return flags;
  }
  function evidenceSuggestions(category,rowCount,cols){
    const detected=new Map();
    for(const c of cols){if(!c||!c.mapping||!c.mapping.target)continue;for(const tag of c.mapping.tags||[]){const cur=detected.get(tag);if(!cur||c.mapping.score>cur.conf)detected.set(tag,{conf:c.mapping.score,header:c.header,target:c.mapping.target});}}
    if(category==='quotes'){detected.set('historical_quotes',{conf:rowCount>=5?.95:.7,header:`${rowCount} row(s)`,target:'Dataset'});detected.set('quote_history',{conf:rowCount>=5?.95:.7,header:`${rowCount} row(s)`,target:'Dataset'});}
    if(category==='work_orders')detected.set('work_order_history',{conf:rowCount>=5?.95:.7,header:`${rowCount} row(s)`,target:'Dataset'});
    const suggestions=[];for(const[moduleNo,allowed]of Object.entries(MODULE_TAGS)){for(const[tag,info]of detected){if(!allowed.has(tag))continue;suggestions.push({moduleNo:Number(moduleNo),criterion:tag,status:info.conf>=.78?'available':'partial',source:info.header,target:info.target});}}
    const key=x=>`${x.moduleNo}:${x.criterion}`;return[...new Map(suggestions.map(s=>[key(s),s])).values()].sort((a,b)=>a.moduleNo-b.moduleNo||a.criterion.localeCompare(b.criterion));
  }

  async function analyzeFile(file){
    clearError();saveStatus.textContent='';results.classList.remove('active');
    try{
      if(file.size>MAX_FILE_BYTES)throw new Error('This preview limits local inspection to 20 MB. Register larger files manually until background ingestion is connected.');
      const ext=file.name.split('.').pop().toLowerCase();let parsed;
      if(['csv','tsv','txt'].includes(ext))parsed=parseDelimited(await file.text(),ext==='tsv'?'\t':null,file.name);
      else if(ext==='json')parsed=parseJson(await file.text(),file.name);
      else if(ext==='xlsx')parsed=await parseXlsx(file);
      else throw new Error('Unsupported file type. Use CSV, TSV, JSON or XLSX for structured inspection. PDFs/documents can still be registered for later document parsing.');

      const choice=chooseBestRegion(parsed.sheetTables);
      const table=sanitizeTable(choice.best);
      if(table.headers.length<2||!table.rows.length)throw new Error('A possible table was found, but it does not contain enough structured rows/columns to map safely.');
      const rows=table.rows.slice(0,MAX_DATA_ROWS);const prof=profile(table.headers,rows);
      const category=inferCategory(table.headers,file.name,choice.best.sheetName);
      const flags=qualityFlags(rows,prof,{headerRow:choice.best.headerRow,alternatives:choice.alternatives.length,sheetCount:parsed.sheetTables.length,sheetName:choice.best.sheetName});
      const evidence=evidenceSuggestions(category,choice.best.rows.length,prof.cols);const hash=await sha256(file);
      inspection={file,headers:table.headers,rows,totalRows:choice.best.rows.length,prof,category,flags,evidence,hash,sheets:parsed.sheetTables.map(s=>s.name),sheetName:choice.best.sheetName,headerRow:choice.best.headerRow,alternatives:choice.alternatives};
      categorySelect.value=category;sourceInput.value='Local browser inspection';renderInspection();
    }catch(err){showError(err?.message||String(err));}
  }

  function parseDelimited(text,forcedDelimiter=null,name='Delimited'){
    const sample=text.slice(0,8000),delimiter=forcedDelimiter||detectDelimiter(sample);const rows=[];let row=[],field='',quoted=false;
    for(let i=0;i<text.length;i++){const ch=text[i];if(quoted){if(ch==='"'&&text[i+1]==='"'){field+='"';i++;}else if(ch==='"')quoted=false;else field+=ch;}else{if(ch==='"')quoted=true;else if(ch===delimiter){row.push(field);field='';}else if(ch==='\n'){row.push(field.replace(/\r$/,''));rows.push(row);row=[];field='';}else field+=ch;}}
    if(field.length||row.length){row.push(field.replace(/\r$/,''));rows.push(row);}const clean=rows.filter(r=>nonEmptyCount(r)>0);if(!clean.length)throw new Error('No rows detected.');
    return{sheetTables:[{name,regions:detectRegions(clean,name)}]};
  }
  function detectDelimiter(sample){const candidates=[',','\t',';','|'];return candidates.map(d=>[d,(sample.match(new RegExp(d==='|'?'\\|':d,'g'))||[]).length]).sort((a,b)=>b[1]-a[1])[0][0];}
  function parseJson(text,name='JSON'){
    const data=JSON.parse(text);let arr;if(Array.isArray(data))arr=data;else if(data&&typeof data==='object')arr=Object.values(data).find(v=>Array.isArray(v))||[data];else throw new Error('JSON must contain an object or array of objects.');
    const objs=arr.filter(x=>x&&typeof x==='object'&&!Array.isArray(x));if(!objs.length)throw new Error('No object records detected in JSON.');
    const headers=[...new Set(objs.flatMap(o=>Object.keys(o)))];const rows=[headers,...objs.map(o=>headers.map(h=>formatJsonValue(o[h])))];return{sheetTables:[{name,regions:detectRegions(rows,name)}]};
  }
  function formatJsonValue(v){return v&&typeof v==='object'?JSON.stringify(v):(v??'');}

  async function parseXlsx(file){
    const bytes=new Uint8Array(await file.arrayBuffer()),entries=await unzipEntries(bytes),decoder=new TextDecoder('utf-8');const xml=name=>entries[name]?decoder.decode(entries[name]):null;
    const workbook=xml('xl/workbook.xml');if(!workbook)throw new Error('XLSX workbook metadata could not be read.');
    const wbDoc=parseXml(workbook),sheetNodes=els(wbDoc,'sheet');if(!sheetNodes.length)throw new Error('No worksheet metadata found in XLSX.');
    const relMap={};const rels=xml('xl/_rels/workbook.xml.rels');if(rels){for(const r of els(parseXml(rels),'Relationship'))relMap[r.getAttribute('Id')]=r.getAttribute('Target');}
    let shared=[];const sharedXml=xml('xl/sharedStrings.xml');if(sharedXml)shared=els(parseXml(sharedXml),'si').map(si=>si.textContent||'');
    const sheets=sheetNodes.map((s,i)=>({name:s.getAttribute('name')||`Sheet ${i+1}`,rid:s.getAttribute('r:id')||s.getAttributeNS('http://schemas.openxmlformats.org/officeDocument/2006/relationships','id')}));
    const sheetTables=[];
    for(let si=0;si<sheets.length;si++){
      const s=sheets[si];let target=relMap[s.rid]||`worksheets/sheet${si+1}.xml`;target=target.replace(/^\//,'');const path=target.startsWith('xl/')?target:'xl/'+target.replace(/^\.\//,'');const sx=xml(path);if(!sx)continue;
      const doc=parseXml(sx),parsedRows=[];
      for(const rowNode of els(doc,'row').slice(0,MAX_SCAN_ROWS)){
        const row=[];for(const c of els(rowNode,'c')){const idx=columnIndex(c.getAttribute('r')||'');const t=c.getAttribute('t');let value='';const v=els(c,'v')[0];if(t==='inlineStr')value=(els(c,'is')[0]?.textContent||'');else if(v){const raw=v.textContent||'';value=t==='s'?(shared[Number(raw)]??raw):raw;}row[idx]=value;}parsedRows.push(compactRow(row));
      }
      const clean=parsedRows.filter(r=>nonEmptyCount(r)>0);sheetTables.push({name:s.name,regions:detectRegions(clean,s.name)});
    }
    if(!sheetTables.length)throw new Error('Workbook opened, but no readable worksheet content was found.');return{sheetTables};
  }
  function parseXml(text){const doc=new DOMParser().parseFromString(text,'application/xml');if(els(doc,'parsererror').length)throw new Error('Malformed workbook XML encountered.');return doc;}
  function els(node,name){const direct=[...node.getElementsByTagName(name)];if(direct.length)return direct;try{return[...node.getElementsByTagNameNS('*',name)];}catch{return[];}}
  function columnIndex(ref){const m=String(ref).match(/^[A-Z]+/i);if(!m)return 0;let n=0;for(const ch of m[0].toUpperCase())n=n*26+(ch.charCodeAt(0)-64);return n-1;}
  async function unzipEntries(bytes){
    const dv=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);let eocd=-1;for(let i=bytes.length-22;i>=Math.max(0,bytes.length-65557);i--){if(dv.getUint32(i,true)===0x06054b50){eocd=i;break;}}if(eocd<0)throw new Error('Invalid XLSX ZIP structure.');
    const count=dv.getUint16(eocd+10,true),cdOffset=dv.getUint32(eocd+16,true);let p=cdOffset;const out={},td=new TextDecoder('utf-8');
    for(let e=0;e<count;e++){if(dv.getUint32(p,true)!==0x02014b50)break;const method=dv.getUint16(p+10,true),compSize=dv.getUint32(p+20,true),nameLen=dv.getUint16(p+28,true),extraLen=dv.getUint16(p+30,true),commentLen=dv.getUint16(p+32,true),localOffset=dv.getUint32(p+42,true);const name=td.decode(bytes.slice(p+46,p+46+nameLen));if(dv.getUint32(localOffset,true)!==0x04034b50)throw new Error('Invalid XLSX local ZIP header.');const lName=dv.getUint16(localOffset+26,true),lExtra=dv.getUint16(localOffset+28,true),dataStart=localOffset+30+lName+lExtra,compressed=bytes.slice(dataStart,dataStart+compSize);if(name.startsWith('xl/')){if(method===0)out[name]=compressed;else if(method===8)out[name]=await inflateRaw(compressed);}p+=46+nameLen+extraLen+commentLen;}return out;
  }
  async function inflateRaw(data){if(!('DecompressionStream'in window))throw new Error('This browser cannot decompress XLSX locally. Export as CSV or use a current Chrome/Edge browser.');const ds=new DecompressionStream('deflate-raw');return new Uint8Array(await new Response(new Blob([data]).stream().pipeThrough(ds)).arrayBuffer());}
  async function sha256(file){const digest=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());return[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('');}

  function renderInspection(){
    results.classList.add('active');const i=inspection;
    setText('stat-rows',i.totalRows);setText('stat-fields',i.headers.length);setText('stat-mapped',i.prof.cols.filter(c=>c?.mapping?.target).length);setText('stat-quality',i.flags.filter(f=>f.level!=='ok').length);setText('stat-hash',i.hash.slice(0,8));setText('stat-filetype',i.file.name.split('.').pop().toUpperCase());categorySelect.value=i.category;
    const note=document.getElementById('xlsx-sheet-note');note.innerHTML=`Selected table: <b>${esc(i.sheetName)}</b> · header row ${i.headerRow+1} · ${i.sheets.length} sheet(s) scanned${i.alternatives.length?` · ${i.alternatives.length} alternate region(s) detected`:''}`;
    document.getElementById('detected-fields-body').innerHTML=i.prof.cols.map(c=>{if(!c)return'';const m=c.mapping||{target:null,score:0};const conf=m.score>=.8?'high':m.score>=.5?'medium':'';return`<tr><td><b>${esc(c.header)}</b><small>${c.type} · ${c.nonempty}/${i.rows.length} non-empty</small></td><td>${m.target?`<span class="mapping-target">${esc(m.target)}</span>`:'<span class="mapping-target none">No confident mapping</span>'}</td><td><span class="confidence ${conf}">${m.target?Math.round(m.score*100)+'%':'—'}</span></td><td>${Math.round(c.missingRate*100)}%</td><td>${c.unique}</td></tr>`;}).join('');
    document.getElementById('quality-list').innerHTML=i.flags.map(f=>`<div class="quality-item ${f.level}"><span>${f.level==='ok'?'✓':f.level==='bad'?'!':'△'}</span><div><b>${esc(f.title)}</b><small>${esc(f.detail)}</small></div></div>`).join('');
    document.getElementById('evidence-suggestions').innerHTML=i.evidence.length?i.evidence.map((e,idx)=>`<label class="evidence-suggestion"><input type="checkbox" data-evidence-index="${idx}" checked><div><b>Module 0${e.moduleNo} · ${esc(e.criterion)}</b><small>${esc(e.source)} → ${esc(e.target)}</small></div><em class="${e.status==='partial'?'partial':''}">${e.status}</em></label>`).join(''):'<div class="inspection-empty">No readiness evidence can be suggested confidently from this region yet.</div>';
    const ph=i.headers.slice(0,14),pr=i.rows.slice(0,8);document.getElementById('preview-table').innerHTML=`<thead><tr>${ph.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${pr.map(r=>`<tr>${ph.map((_,idx)=>`<td>${esc(r[idx]??'')}</td>`).join('')}</tr>`).join('')}</tbody>`;
    setText('inspection-filename',i.file.name);setText('inspection-meta',`${formatBytes(i.file.size)} · SHA-256 ${i.hash.slice(0,16)}… · locally inspected · raw file not persisted`);
  }

  async function saveInspection(){
    if(!inspection)return;saveBtn.disabled=true;saveStatus.className='save-status';saveStatus.textContent='Saving…';
    try{const category=categorySelect.value,mappingSummary=inspection.prof.cols.filter(c=>c?.mapping?.target).slice(0,30).map(c=>`${c.header}→${c.mapping.target}`).join('; ');const notes=`v0.8 messy-data inspection | sheet=${inspection.sheetName} | header_row=${inspection.headerRow+1} | rows=${inspection.totalRows} | fields=${inspection.headers.length} | mapped=${inspection.prof.cols.filter(c=>c?.mapping?.target).length} | quality_flags=${inspection.flags.filter(f=>f.level!=='ok').length} | sha256=${inspection.hash} | mappings=${mappingSummary}`;await postForm(`/companies/${companyId}/data-intake/register`,{filename:inspection.file.name,category,source:sourceInput.value||'Local browser inspection',notes});const selected=[...document.querySelectorAll('[data-evidence-index]:checked')].map(el=>inspection.evidence[Number(el.dataset.evidenceIndex)]).filter(Boolean);for(const e of selected)await postForm(`/companies/${companyId}/readiness-evidence`,{module_no:String(e.moduleNo),criterion_key:e.criterion,status:e.status,source:inspection.file.name,notes:`v0.8 suggestion from selected table region (${inspection.sheetName}, header row ${inspection.headerRow+1}): ${e.source} → ${e.target}. Human-confirmed before save.`});saveStatus.textContent=`Saved metadata + ${selected.length} approved evidence item(s). Reloading…`;setTimeout(()=>location.reload(),650);}catch(err){saveStatus.className='save-status error';saveStatus.textContent=err?.message||String(err);saveBtn.disabled=false;}
  }
  async function postForm(url,obj){const body=new URLSearchParams(obj),res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'},body,redirect:'follow'});if(!res.ok)throw new Error(`Save failed (${res.status})`);}
  function setText(id,v){const el=document.getElementById(id);if(el)el.textContent=v;}
  function formatBytes(n){if(n<1024)return`${n} B`;if(n<1024*1024)return`${(n/1024).toFixed(1)} KB`;return`${(n/1024/1024).toFixed(1)} MB`;}
  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function showError(msg){errorBox.textContent=msg;errorBox.classList.add('active');}
  function clearError(){errorBox.textContent='';errorBox.classList.remove('active');}
})();
