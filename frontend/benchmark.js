const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty = (value) => String(value || '').replaceAll('_',' ');
const pct = (value) => `${Math.round((value || 0) * 100)}%`;
const money = (value) => `$${Number(value || 0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
const state = { summaries:[], answer:null, trace:[], tab:'overview' };

async function get(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}
function renderList() {
  const filter = $('filter').value.trim().toLowerCase();
  const rows = state.summaries.filter((item) => `${item.case_id} ${item.pattern} ${item.verdict}`.toLowerCase().includes(filter));
  $('case-count').textContent = state.summaries.length;
  $('case-list').innerHTML = rows.map((item) => `<button class="case-item ${item.case_id===state.answer?.case_id?'active':''}" data-case="${esc(item.case_id)}"><div class="case-item-top"><b>${esc(item.case_id)}</b><span class="risk-tag ${item.fraud_probability<.5?'low':''}">${pct(item.fraud_probability)}</span></div><small>${esc(pretty(item.pattern))} · <span class="${item.verdict==='fraud'?'fraud':''}">${esc(item.verdict)}</span></small><small>${esc(pretty(item.final_action))}</small></button>`).join('') || '<p class="muted" style="padding:18px">No cases match.</p>';
}
function actionRows(actions) {
  return actions.map((action) => `<div class="action-row"><b>${esc(pretty(action.action))}</b><span class="route-chip ${esc(action.route)}">${esc(action.route)}</span><p>${esc(action.reason)}</p></div>`).join('');
}
function evidenceRows(items) {
  return items.map((item,index) => `<div class="evidence-item"><strong><span class="evidence-id">E${String(index+1).padStart(3,'0')}</span>${esc(item.claim)}</strong><small><span class="evidence-ref">${esc(item.source.toUpperCase())} · ${esc(item.ref)}</span></small><div class="ids">${item.entity_ids.map((id)=>`<span>${esc(id)}</span>`).join('')}</div></div>`).join('');
}
function render() {
  const answer = state.answer;
  renderList();
  $('empty-state').hidden=!!answer;$('case-view').hidden=!answer;
  if (!answer) return;
  const c=answer.case, actions=answer.next_best_actions;
  $('provenance').textContent=c.written_to_graph?'TIGERGRAPH CASE RECORDED':'OFFLINE ANALYSIS · GRAPH WRITE PENDING';
  $('case-id').textContent=answer.case_id;
  $('case-title').textContent=`${pretty(c.pattern)} investigation`;
  $('case-subtitle').textContent=`${c.verdict.toUpperCase()} verdict · ${c.evidence.length} evidence items · ${answer.tool_calls} retrieval calls`;
  $('case-status').textContent=pretty(c.status).toUpperCase();
  $('metric-risk').textContent=pct(c.fraud_probability);
  const confidence=state.trace.find((step)=>step.tool==='uncertainty_assessment')?.result?.match(/evidence_confidence=([0-9.]+)/)?.[1];
  $('metric-confidence').textContent=confidence?pct(Number(confidence)):'—';
  $('metric-pattern').textContent=pretty(c.pattern);
  $('metric-exposure').textContent=money(c.exposure_usd);
  document.querySelectorAll('.tab').forEach((button)=>button.classList.toggle('active',button.dataset.tab===state.tab));
  renderTab(answer);
  const final=actions.final;
  $('decision-content').innerHTML=`<div class="right-label">FINAL ASSESSMENT</div><div class="risk-row"><span>Fraud probability</span><strong>${pct(c.fraud_probability)}</strong></div><div class="bar"><i style="width:${pct(c.fraud_probability)}"></i></div><div class="right-label">VERDICT</div><span class="verdict-chip ${c.verdict==='fraud'?'fraud':''}">${esc(c.verdict)}</span><div class="right-label">NEXT BEST ACTIONS</div>${actionRows(final)}<div class="right-label">HUMAN APPROVAL</div><div class="approval-note">${final.some((a)=>a.route!=='auto')?'L1/L2 actions are recommendations awaiting human authorization.':'All recommended actions are on the automatic route.'}</div><div class="right-label">CASE MEMORY</div><p>${c.similar_prior_cases.length?esc(c.similar_prior_cases.join(', ')):'No related closed case was used.'}</p><div class="data-note">${c.written_to_graph?'Case was written to TigerGraph.':'These results were computed from the supplied CSV index. TigerGraph writeback is not claimed.'}</div>`;
}
function renderTab(answer) {
  const c=answer.case, target=$('tab-content');
  if (state.tab==='overview') {
    target.innerHTML=`<div class="two-col"><div><section class="card"><span class="eyebrow">INVESTIGATION SUMMARY</span><h3>What the evidence supports</h3><p>${esc(c.summary)}</p>${c.pattern_description?`<p style="margin-top:12px">${esc(c.pattern_description)}</p>`:''}</section><section class="card"><h3>Key evidence</h3><div class="evidence-list">${evidenceRows(c.evidence.slice(0,4))}</div></section></div><div><section class="card"><h3>Case extent</h3><div class="summary-list"><div class="summary-line"><b>Suspected transactions</b><span>${c.affected_txn_ids.length?esc(c.affected_txn_ids.join(', ')):'Unresolved'}</span></div><div class="summary-line"><b>Connected cards</b><span>${c.connected_card_ids.length?esc(c.connected_card_ids.join(', ')):'No verified card link'}</span></div><div class="summary-line"><b>First suspicious transaction</b><span>${esc(c.first_suspicious_txn_id||'Unresolved')}</span></div><div class="summary-line"><b>Similar closed cases</b><span>${c.similar_prior_cases.length?esc(c.similar_prior_cases.join(', ')):'None used'}</span></div></div></section><section class="card"><h3>Stopping decision</h3><p>${esc(answer.stop_reason)}</p></section></div></div>`;
  } else if (state.tab==='evidence') {
    target.innerHTML=`<section class="card"><h3>Attributable evidence <span class="muted">(${c.evidence.length})</span></h3><div class="evidence-list">${evidenceRows(c.evidence)}</div></section>`;
  } else if (state.tab==='map') {
    target.innerHTML='<section class="card"><h3>Evidence citation map</h3><div id="citation-map" class="citation-map"></div><p class="map-help">Lines show which recorded evidence cites each entity ID. This is a citation view; shared profiles and transaction relationships are described in the evidence ledger.</p></section>';
    renderMap(c.evidence);
  } else if (state.tab==='progression') {
    target.innerHTML=`<div class="two-col"><section class="card"><div class="action-stage"><h4>BEFORE ADDITIONAL EVIDENCE</h4>${actionRows(answer.next_best_actions.initial)}</div><div class="action-stage"><h4>AFTER ASSUMED RESPONSE</h4>${actionRows(answer.next_best_actions.final)}</div></section><div><section class="card"><h3>What changed</h3><p>${esc(answer.next_best_actions.what_changed)}</p></section><section class="card"><h3>Evidence requested</h3>${answer.evidence_requests.length?answer.evidence_requests.map((r)=>`<div class="evidence-item"><strong>${esc(pretty(r.type))} · after step ${r.asked_after_step}</strong><p>${esc(r.assumed_response)}</p></div>`).join(''):'<p>No additional evidence was requested.</p>'}</section></div></div>`;
  } else if (state.tab==='report') {
    const s=answer.sar;
    target.innerHTML=`<section class="card"><span class="eyebrow">SUSPICIOUS ACTIVITY REPORT</span><h3>${s.file?'Filing recommended · L2 approval':'No filing recommended'}</h3><p>${esc(s.reason)}</p>${s.file?`<div class="data-note">This is a draft recommendation. Filing requires L2 authorization.</div><p class="sar-narrative">${esc(s.narrative)}</p><div class="ids">${s.subjects.map((subject)=>`<span>${esc(subject)}</span>`).join('')}</div><p style="margin-top:12px">${esc(s.activity_dates.join(' to '))} · ${money(s.total_amount_usd)}</p>`:''}</section>`;
  } else if (state.tab==='trace') {
    target.innerHTML=`<section class="card"><h3>Bounded investigation trace</h3><p>Each step records a retrieval or assessment. The exact tool call count includes the index queries behind these steps.</p><div>${state.trace.map((step)=>`<div class="trace-step"><span class="trace-num">${step.step}</span><div><b>${esc(pretty(step.tool))}</b><p>${esc(step.result)} · seed ${esc(step.seed)}</p></div></div>`).join('')}</div><div class="data-note">Token usage: ${answer.tokens}. Latency: ${answer.latency_s}s. ${c.written_to_graph?'TigerGraph write verified.':'Graph writeback is pending.'}</div></section>`;
  }
}
function renderMap(evidence) {
  const shown=evidence.slice(0,8);
  const entities=[...new Set(shown.flatMap((item)=>item.entity_ids))].slice(0,16);
  const height=Math.max(440,Math.max(shown.length,entities.length)*30+60);
  const ePos=new Map(shown.map((item,i)=>[item,{x:150,y:42+i*(height-80)/Math.max(1,shown.length-1)}]));
  const idPos=new Map(entities.map((id,i)=>[id,{x:610,y:42+i*(height-80)/Math.max(1,entities.length-1)}]));
  const lines=shown.flatMap((item)=>item.entity_ids.filter((id)=>idPos.has(id)).map((id)=>`<line x1="150" y1="${ePos.get(item).y}" x2="610" y2="${idPos.get(id).y}" stroke="#426a73" opacity=".58"/>`)).join('');
  const claims=shown.map((item,i)=>`<g><circle cx="150" cy="${ePos.get(item).y}" r="12" fill="#173c40" stroke="#7ee0cf" stroke-width="2"/><text x="150" y="${ePos.get(item).y+4}" text-anchor="middle" fill="#b8f0e8" font-size="10">${i+1}</text><text x="127" y="${ePos.get(item).y+4}" text-anchor="end" fill="#b7d7d5" font-size="10">${esc(item.ref.slice(0,22))}</text></g>`).join('');
  const nodes=entities.map((id)=>`<g><circle cx="610" cy="${idPos.get(id).y}" r="5" fill="#ffb365"/><text x="624" y="${idPos.get(id).y+4}" fill="#d4e7e9" font-size="10">${esc(id.slice(0,22))}</text></g>`).join('');
  $('citation-map').innerHTML=`<svg viewBox="0 0 780 ${height}" role="img" aria-label="Evidence citations connected to real entity identifiers">${lines}${claims}${nodes}</svg>`;
}
async function selectCase(caseId) {
  [state.answer,state.trace]=await Promise.all([get(`/api/benchmark/${encodeURIComponent(caseId)}`),get(`/api/benchmark/${encodeURIComponent(caseId)}/trace`)]);
  render();
}
document.addEventListener('click',(event)=>{const button=event.target.closest('[data-case]');if(button){selectCase(button.dataset.case).catch(showError);return;}const tab=event.target.closest('[data-tab]');if(tab){state.tab=tab.dataset.tab;render();}});
$('filter').addEventListener('input',renderList);
function showError(error){$('empty-state').hidden=false;$('case-view').hidden=true;$('empty-state').innerHTML=`<h1>Unable to load cases</h1><p>${esc(error.message)}</p>`;}
(async()=>{try{state.summaries=await get('/api/benchmark');if(!state.summaries.length)throw new Error('Run the HHGOA benchmark to create the case files.');await selectCase('HHG-019');}catch(error){showError(error);}})();
