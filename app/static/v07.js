(() => {
  const lab = document.getElementById('ingestion-lab');
  if (!lab) return;

  const companyId = lab.dataset.companyId;
  const drop = document.getElementById('ingestion-drop');
  const input = document.getElementById('ingestion-file');
  const results = document.getElementById('inspection-results');
  const errorBox = document.getElementById('ingestion-error');
  const categorySelect = document.getElementById('inspection-category');
  const sourceInput = document.getElementById('inspection-source');
  const saveBtn = document.getElementById('inspection-save');
  const saveStatus = document.getElementById('inspection-save-status');

  let inspection = null;

  const CANONICAL_RULES = [
    {target:'Customer.code', labels:['客戶編號','客戶代號','customer code','client code','customer id','客編'], tags:['customer_identity','customer_product']},
    {target:'Customer.name', labels:['客戶名稱','客戶','customer name','customer','client name','client','公司名稱'], tags:['customer_identity','customer_product']},
    {target:'Contact.name', labels:['聯絡人','窗口','contact','contact name'], tags:[]},
    {target:'Product.code', labels:['品號','料號','sku','product code','item code','產品編號'], tags:['product_spec','customer_product']},
    {target:'Product.name', labels:['品名','產品名稱','產品','product name','product','item name','item'], tags:['product_spec','customer_product']},
    {target:'Specification.value', labels:['規格','尺寸','spec','specification','size','型號'], tags:['product_spec']},
    {target:'Material.name', labels:['材質','材料','material','paper','紙材','紙張'], tags:['product_spec']},
    {target:'Quote.quote_number', labels:['報價單號','報價編號','quote no','quote number','quotation no','quotation number'], tags:['historical_quotes','quote_history']},
    {target:'Quote.created_at', labels:['報價日期','quote date','quotation date','date'], tags:['historical_quotes','quote_history','time_fields']},
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
    {target:'WorkOrder.status', labels:['狀態','工單狀態','status','current status','進度'], tags:['current_status']},
    {target:'Operation.stage', labels:['站別','製程','工序','stage','process','operation'], tags:['production_stages','production_events']},
    {target:'Operation.machine', labels:['機台','機器','machine','equipment'], tags:['station_machine','production_events']},
    {target:'Operation.assignee', labels:['負責人','作業員','經手人','operator','assignee','responsible person'], tags:['assignee']},
    {target:'Operation.actual_start', labels:['開始時間','實際開始','start time','actual start','start date'], tags:['actual_timestamps','time_fields','production_events']},
    {target:'Operation.actual_end', labels:['完成時間','實際完成','end time','actual end','completed at','completion date'], tags:['actual_timestamps','time_fields','production_events']},
    {target:'WorkException.reason', labels:['延誤原因','異常原因','重工原因','exception','delay reason','rework','異常'], tags:['exceptions','production_events']},
    {target:'Metric.revenue', labels:['營收','銷售額','revenue','sales amount','sales'], tags:['revenue']},
    {target:'Metric.cost', labels:['成本','總成本','cost','total cost'], tags:['cost']},
    {target:'MetricDefinition.name', labels:['kpi','指標','metric','管理指標'], tags:['kpi_definitions']},
    {target:'PricingRule.note', labels:['報價規則','計價規則','pricing rule','pricing logic','加價規則','折扣規則'], tags:['pricing_rules']},
    {target:'Quote.exception_note', labels:['特殊報價','例外報價','備註','remark','note','exception note'], tags:['exception_examples']}
  ];

  const CATEGORY_SIGNALS = {
    quotes: ['quote','quotation','報價','單價','成交價','報價單號'],
    work_orders: ['work order','工單','製令','站別','製程','交期','機台'],
    reports: ['revenue','sales','margin','gross profit','營收','毛利','kpi','報表'],
    customers: ['customer','client','客戶','聯絡人','contact'],
    products: ['product','item','sku','品號','品名','規格','材質','material']
  };

  const MODULE_TAGS = {
    4: new Set(['historical_quotes','customer_identity','product_spec','quantity','quoted_price','accepted_price','material_cost','processing_cost','pricing_rules','exception_examples']),
    5: new Set(['work_order_id','order_reference','product_spec','quantity','promised_date','production_stages','station_machine','assignee','current_status','actual_timestamps','exceptions']),
    6: new Set(['quote_history','order_history','work_order_history','revenue','cost','margin','customer_product','time_fields','production_events','kpi_definitions'])
  };

  drop.addEventListener('click', () => input.click());
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('dragover'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('dragover'));
  drop.addEventListener('drop', e => {
    e.preventDefault(); drop.classList.remove('dragover');
    if (e.dataTransfer.files[0]) analyzeFile(e.dataTransfer.files[0]);
  });
  input.addEventListener('change', () => input.files[0] && analyzeFile(input.files[0]));
  saveBtn.addEventListener('click', saveInspection);

  function normalize(s) {
    return String(s ?? '').trim().toLowerCase().replace(/[\s_\-\/()（）]+/g, ' ');
  }

  function scoreLabel(header, label) {
    const h = normalize(header), l = normalize(label);
    if (!h || !l) return 0;
    if (h === l) return 1;
    if (h.includes(l) || l.includes(h)) return 0.82;
    const ht = new Set(h.split(' ')), lt = l.split(' ');
    const overlap = lt.filter(x => ht.has(x)).length;
    return overlap ? 0.55 * (overlap / lt.length) : 0;
  }

  function mapHeader(header) {
    let best = null;
    for (const rule of CANONICAL_RULES) {
      for (const label of rule.labels) {
        const score = scoreLabel(header, label);
        if (!best || score > best.score) best = {...rule, score};
      }
    }
    if (!best || best.score < 0.5) return {target:null, score:0, tags:[]};
    return best;
  }

  function inferCategory(headers, filename) {
    const text = normalize(headers.join(' ') + ' ' + filename);
    const scored = Object.entries(CATEGORY_SIGNALS).map(([key, signals]) => [key, signals.reduce((n,s) => n + (text.includes(normalize(s)) ? 1 : 0), 0)]).sort((a,b)=>b[1]-a[1]);
    return scored[0][1] > 0 ? scored[0][0] : 'other';
  }

  function inferType(values) {
    const nonempty = values.filter(v => v !== null && v !== undefined && String(v).trim() !== '');
    if (!nonempty.length) return 'empty';
    let numbers=0, dates=0, bools=0;
    for (const raw of nonempty.slice(0,100)) {
      const v = String(raw).trim();
      if (/^-?[\d,]+(?:\.\d+)?%?$/.test(v)) numbers++;
      if (/^(true|false|yes|no|是|否)$/i.test(v)) bools++;
      if (/^\d{4}[\/-]\d{1,2}[\/-]\d{1,2}/.test(v) || /^\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4}/.test(v)) dates++;
    }
    const n = Math.min(nonempty.length,100);
    if (dates/n > .75) return 'date';
    if (numbers/n > .8) return 'number';
    if (bools/n > .8) return 'boolean';
    return 'text';
  }

  function profile(headers, rows) {
    const cols = headers.map((header, i) => {
      const values = rows.map(r => r[i]);
      const nonempty = values.filter(v => v !== null && v !== undefined && String(v).trim() !== '');
      const unique = new Set(nonempty.map(v => String(v).trim())).size;
      const mapping = mapHeader(header);
      return {
        header, index:i, type:inferType(values), nonempty:nonempty.length,
        missingRate: rows.length ? (rows.length - nonempty.length)/rows.length : 0,
        unique, mapping
      };
    });
    const fingerprints = rows.map(r => JSON.stringify(r));
    const duplicates = fingerprints.length - new Set(fingerprints).size;
    return {cols, duplicates};
  }

  function qualityFlags(headers, rows, profileData) {
    const flags = [];
    if (!rows.length) flags.push({level:'bad', title:'No data rows detected', detail:'The file has headers or structure but no usable records.'});
    if (profileData.duplicates > 0) flags.push({level:'warn', title:`${profileData.duplicates} duplicate row(s) detected`, detail:'Review before using this dataset for counts or model calibration.'});
    profileData.cols.forEach(c => {
      if (c.type === 'empty') flags.push({level:'warn', title:`Empty column: ${c.header}`, detail:'Column contains no values in the inspected rows.'});
      else if (c.missingRate >= .5) flags.push({level:'warn', title:`High missing rate: ${c.header}`, detail:`${Math.round(c.missingRate*100)}% of inspected rows are blank.`});
    });
    if (!flags.length) flags.push({level:'ok', title:'No obvious structural issues in the inspected sample', detail:'This is not a full data-quality certification; deeper checks happen during mapping.'});
    return flags;
  }

  function evidenceSuggestions(category, rowCount, cols) {
    const detectedTags = new Map();
    for (const c of cols) {
      if (!c.mapping.target) continue;
      for (const tag of c.mapping.tags || []) {
        const current = detectedTags.get(tag);
        const conf = c.mapping.score;
        if (!current || conf > current.conf) detectedTags.set(tag, {conf, header:c.header, target:c.mapping.target});
      }
    }
    if (category === 'quotes') {
      detectedTags.set('historical_quotes', {conf: rowCount >= 5 ? .95 : .7, header:`${rowCount} row(s)`, target:'Dataset'});
      detectedTags.set('quote_history', {conf: rowCount >= 5 ? .95 : .7, header:`${rowCount} row(s)`, target:'Dataset'});
    }
    if (category === 'work_orders') detectedTags.set('work_order_history', {conf: rowCount >= 5 ? .95 : .7, header:`${rowCount} row(s)`, target:'Dataset'});

    const suggestions=[];
    for (const [moduleNo, allowed] of Object.entries(MODULE_TAGS)) {
      for (const [tag, info] of detectedTags.entries()) {
        if (!allowed.has(tag)) continue;
        const status = info.conf >= .78 ? 'available' : 'partial';
        suggestions.push({moduleNo:Number(moduleNo), criterion:tag, status, source:info.header, target:info.target});
      }
    }
    const key = x => `${x.moduleNo}:${x.criterion}`;
    return [...new Map(suggestions.map(s => [key(s),s])).values()].sort((a,b)=>a.moduleNo-b.moduleNo || a.criterion.localeCompare(b.criterion));
  }

  async function analyzeFile(file) {
    clearError();
    saveStatus.textContent='';
    try {
      const ext = file.name.split('.').pop().toLowerCase();
      let parsed;
      if (['csv','tsv','txt'].includes(ext)) parsed = parseDelimited(await file.text(), ext === 'tsv' ? '\t' : null);
      else if (ext === 'json') parsed = parseJson(await file.text());
      else if (ext === 'xlsx') parsed = await parseXlsx(file);
      else throw new Error('Unsupported file type in v0.7. Use CSV, TSV, JSON or XLSX. PDFs stay in the file inventory until the document parser is connected.');

      const headers = parsed.headers.map((h,i)=> String(h || `Column ${i+1}`).trim());
      const rows = parsed.rows.slice(0,500);
      const prof = profile(headers, rows);
      const category = inferCategory(headers, file.name);
      const flags = qualityFlags(headers, rows, prof);
      const evidence = evidenceSuggestions(category, parsed.totalRows ?? rows.length, prof.cols);
      const hash = await sha256(file);
      inspection = {file, headers, rows, totalRows:parsed.totalRows ?? rows.length, sheets:parsed.sheets||[], prof, category, flags, evidence, hash};
      categorySelect.value = category;
      sourceInput.value = 'Local browser inspection';
      renderInspection();
    } catch (err) {
      showError(err.message || String(err));
      results.classList.remove('active');
    }
  }

  function parseDelimited(text, forcedDelimiter=null) {
    const sample = text.slice(0,5000);
    const delimiter = forcedDelimiter || detectDelimiter(sample);
    const rows=[]; let row=[], field='', quoted=false;
    for (let i=0;i<text.length;i++) {
      const ch=text[i];
      if (quoted) {
        if (ch==='"' && text[i+1]==='"') { field+='"'; i++; }
        else if (ch==='"') quoted=false;
        else field+=ch;
      } else {
        if (ch==='"') quoted=true;
        else if (ch===delimiter) { row.push(field); field=''; }
        else if (ch==='\n') { row.push(field.replace(/\r$/,'')); rows.push(row); row=[]; field=''; }
        else field+=ch;
      }
    }
    if (field.length || row.length) { row.push(field.replace(/\r$/,'')); rows.push(row); }
    const clean = rows.filter(r => r.some(v => String(v).trim() !== ''));
    if (!clean.length) throw new Error('No rows detected.');
    return {headers:clean[0], rows:clean.slice(1), totalRows:Math.max(0,clean.length-1)};
  }

  function detectDelimiter(sample) {
    const candidates=[',','\t',';','|'];
    return candidates.map(d => [d,(sample.match(new RegExp(d==='|'?'\\|':d,'g'))||[]).length]).sort((a,b)=>b[1]-a[1])[0][0];
  }

  function parseJson(text) {
    const data=JSON.parse(text);
    let arr;
    if (Array.isArray(data)) arr=data;
    else if (data && typeof data==='object') arr=Object.values(data).find(v=>Array.isArray(v)) || [data];
    else throw new Error('JSON must contain an object or array of objects.');
    const objs=arr.filter(x=>x && typeof x==='object' && !Array.isArray(x));
    if (!objs.length) throw new Error('No object records detected in JSON.');
    const headers=[...new Set(objs.flatMap(o=>Object.keys(o)))];
    const rows=objs.map(o=>headers.map(h=>formatJsonValue(o[h])));
    return {headers,rows,totalRows:rows.length};
  }
  function formatJsonValue(v){ return v && typeof v==='object' ? JSON.stringify(v) : (v ?? ''); }

  async function parseXlsx(file) {
    const bytes=new Uint8Array(await file.arrayBuffer());
    const entries=await unzipEntries(bytes);
    const decoder=new TextDecoder('utf-8');
    const xml = name => entries[name] ? decoder.decode(entries[name]) : null;
    const workbook=xml('xl/workbook.xml');
    if (!workbook) throw new Error('XLSX workbook.xml not found.');
    const rels=xml('xl/_rels/workbook.xml.rels');
    const wbDoc=new DOMParser().parseFromString(workbook,'application/xml');
    const sheetNodes=[...wbDoc.getElementsByTagName('sheet')];
    if (!sheetNodes.length) throw new Error('No worksheet found in XLSX.');
    const relMap={};
    if (rels) {
      const relDoc=new DOMParser().parseFromString(rels,'application/xml');
      [...relDoc.getElementsByTagName('Relationship')].forEach(r=>relMap[r.getAttribute('Id')]=r.getAttribute('Target'));
    }
    const sheets=[];
    sheetNodes.forEach((s,i)=>sheets.push({name:s.getAttribute('name')||`Sheet ${i+1}`, rid:s.getAttribute('r:id') || s.getAttributeNS('http://schemas.openxmlformats.org/officeDocument/2006/relationships','id')}));
    const first=sheets[0];
    let target=relMap[first.rid] || 'worksheets/sheet1.xml';
    target=target.replace(/^\//,'');
    const sheetPath=target.startsWith('xl/') ? target : 'xl/' + target.replace(/^\.\//,'');
    const sheetXml=xml(sheetPath);
    if (!sheetXml) throw new Error(`Worksheet ${sheetPath} not found in XLSX.`);
    let shared=[];
    const sharedXml=xml('xl/sharedStrings.xml');
    if (sharedXml) {
      const doc=new DOMParser().parseFromString(sharedXml,'application/xml');
      shared=[...doc.getElementsByTagName('si')].map(si=>si.textContent || '');
    }
    const doc=new DOMParser().parseFromString(sheetXml,'application/xml');
    const parsedRows=[];
    [...doc.getElementsByTagName('row')].slice(0,501).forEach(rowNode=>{
      const row=[];
      [...rowNode.getElementsByTagName('c')].forEach(c=>{
        const ref=c.getAttribute('r')||''; const idx=columnIndex(ref);
        const t=c.getAttribute('t'); let value='';
        const v=c.getElementsByTagName('v')[0];
        if (t==='inlineStr') value=c.getElementsByTagName('is')[0]?.textContent || '';
        else if (v) {
          const raw=v.textContent || '';
          value=t==='s' ? (shared[Number(raw)] ?? raw) : raw;
        }
        row[idx]=value;
      });
      parsedRows.push(row.map(v=>v??''));
    });
    const clean=parsedRows.filter(r=>r.some(v=>String(v).trim()!==''));
    if (!clean.length) throw new Error('No populated rows detected in first worksheet.');
    return {headers:clean[0],rows:clean.slice(1),totalRows:Math.max(0,clean.length-1),sheets:sheets.map(s=>s.name)};
  }

  function columnIndex(ref) {
    const m=String(ref).match(/^[A-Z]+/i); if(!m) return 0;
    let n=0; for(const ch of m[0].toUpperCase()) n=n*26+(ch.charCodeAt(0)-64);
    return n-1;
  }

  async function unzipEntries(bytes) {
    const dv=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
    let eocd=-1;
    for(let i=bytes.length-22;i>=Math.max(0,bytes.length-65557);i--){ if(dv.getUint32(i,true)===0x06054b50){eocd=i;break;} }
    if(eocd<0) throw new Error('Invalid XLSX ZIP structure.');
    const count=dv.getUint16(eocd+10,true), cdOffset=dv.getUint32(eocd+16,true);
    let p=cdOffset; const out={}; const td=new TextDecoder('utf-8');
    for(let e=0;e<count;e++) {
      if(dv.getUint32(p,true)!==0x02014b50) break;
      const method=dv.getUint16(p+10,true), compSize=dv.getUint32(p+20,true), nameLen=dv.getUint16(p+28,true), extraLen=dv.getUint16(p+30,true), commentLen=dv.getUint16(p+32,true), localOffset=dv.getUint32(p+42,true);
      const name=td.decode(bytes.slice(p+46,p+46+nameLen));
      if(dv.getUint32(localOffset,true)!==0x04034b50) throw new Error('Invalid XLSX local ZIP header.');
      const lName=dv.getUint16(localOffset+26,true), lExtra=dv.getUint16(localOffset+28,true), dataStart=localOffset+30+lName+lExtra;
      const compressed=bytes.slice(dataStart,dataStart+compSize);
      if (name.startsWith('xl/')) {
        if(method===0) out[name]=compressed;
        else if(method===8) out[name]=await inflateRaw(compressed);
      }
      p += 46+nameLen+extraLen+commentLen;
    }
    return out;
  }

  async function inflateRaw(data) {
    if (!('DecompressionStream' in window)) throw new Error('This browser cannot decompress XLSX locally. Use a current Chrome/Edge browser or export the sheet as CSV for this preview.');
    const ds=new DecompressionStream('deflate-raw');
    const stream=new Blob([data]).stream().pipeThrough(ds);
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }

  async function sha256(file) {
    const digest=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());
    return [...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('');
  }

  function renderInspection() {
    results.classList.add('active');
    const i=inspection;
    setText('stat-rows',i.totalRows); setText('stat-fields',i.headers.length); setText('stat-mapped',i.prof.cols.filter(c=>c.mapping.target).length); setText('stat-quality',i.flags.filter(f=>f.level!=='ok').length); setText('stat-hash',i.hash.slice(0,8));
    document.getElementById('stat-filetype').textContent=i.file.name.split('.').pop().toUpperCase();
    if(i.sheets.length) document.getElementById('xlsx-sheet-note').textContent=`XLSX preview uses first worksheet: ${i.sheets[0]} · Workbook sheets: ${i.sheets.join(', ')}`;
    else document.getElementById('xlsx-sheet-note').textContent='';
    categorySelect.value=i.category;

    document.getElementById('detected-fields-body').innerHTML=i.prof.cols.map(c=>{
      const conf=c.mapping.score>=.8?'high':c.mapping.score>=.5?'medium':'';
      return `<tr><td><b>${esc(c.header)}</b><small>${c.type} · ${c.nonempty}/${i.rows.length} non-empty</small></td><td>${c.mapping.target?`<span class="mapping-target">${esc(c.mapping.target)}</span>`:'<span class="mapping-target none">No confident mapping</span>'}</td><td><span class="confidence ${conf}">${c.mapping.target?Math.round(c.mapping.score*100)+'%':'—'}</span></td><td>${Math.round(c.missingRate*100)}%</td><td>${c.unique}</td></tr>`;
    }).join('');

    document.getElementById('quality-list').innerHTML=i.flags.map(f=>`<div class="quality-item ${f.level}"><span>${f.level==='ok'?'✓':f.level==='bad'?'!':'△'}</span><div><b>${esc(f.title)}</b><small>${esc(f.detail)}</small></div></div>`).join('');

    document.getElementById('evidence-suggestions').innerHTML=i.evidence.length ? i.evidence.map((e,idx)=>`<label class="evidence-suggestion"><input type="checkbox" data-evidence-index="${idx}" checked><div><b>Module 0${e.moduleNo} · ${esc(e.criterion)}</b><small>${esc(e.source)} → ${esc(e.target)}</small></div><em class="${e.status==='partial'?'partial':''}">${e.status}</em></label>`).join('') : '<div class="inspection-empty">No readiness evidence can be suggested confidently from these headers yet.</div>';

    const previewHeaders=i.headers.slice(0,14);
    const previewRows=i.rows.slice(0,8);
    document.getElementById('preview-table').innerHTML=`<thead><tr>${previewHeaders.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${previewRows.map(r=>`<tr>${previewHeaders.map((_,idx)=>`<td>${esc(r[idx]??'')}</td>`).join('')}</tr>`).join('')}</tbody>`;
    document.getElementById('inspection-filename').textContent=i.file.name;
    document.getElementById('inspection-meta').textContent=`${formatBytes(i.file.size)} · SHA-256 ${i.hash.slice(0,16)}… · inspected locally`;
  }

  async function saveInspection() {
    if(!inspection) return;
    saveBtn.disabled=true; saveStatus.className='save-status'; saveStatus.textContent='Saving…';
    try {
      const category=categorySelect.value;
      const mappingSummary=inspection.prof.cols.filter(c=>c.mapping.target).slice(0,20).map(c=>`${c.header}→${c.mapping.target}`).join('; ');
      const notes=`v0.7 local inspection | rows=${inspection.totalRows} | fields=${inspection.headers.length} | mapped=${inspection.prof.cols.filter(c=>c.mapping.target).length} | quality_flags=${inspection.flags.filter(f=>f.level!=='ok').length} | sha256=${inspection.hash} | mappings=${mappingSummary}`;
      await postForm(`/companies/${companyId}/data-intake/register`,{filename:inspection.file.name,category,source:sourceInput.value||'Local browser inspection',notes});
      const selected=[...document.querySelectorAll('[data-evidence-index]:checked')].map(el=>inspection.evidence[Number(el.dataset.evidenceIndex)]);
      for(const e of selected){
        await postForm(`/companies/${companyId}/readiness-evidence`,{module_no:String(e.moduleNo),criterion_key:e.criterion,status:e.status,source:inspection.file.name,notes:`Suggested from v0.7 local field inspection: ${e.source} → ${e.target}. Human-confirmed before save.`});
      }
      saveStatus.textContent=`Saved file metadata + ${selected.length} evidence item(s). Reloading…`;
      setTimeout(()=>window.location.reload(),700);
    } catch(err) {
      saveStatus.className='save-status error'; saveStatus.textContent=err.message||String(err);
      saveBtn.disabled=false;
    }
  }

  async function postForm(url,obj){
    const body=new URLSearchParams(obj);
    const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'},body,redirect:'follow'});
    if(!res.ok) throw new Error(`Save failed (${res.status})`);
  }

  function setText(id,v){document.getElementById(id).textContent=v;}
  function formatBytes(n){if(n<1024)return `${n} B`;if(n<1024*1024)return `${(n/1024).toFixed(1)} KB`;return `${(n/1024/1024).toFixed(1)} MB`;}
  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function showError(msg){errorBox.textContent=msg;errorBox.classList.add('active');}
  function clearError(){errorBox.textContent='';errorBox.classList.remove('active');}
})();