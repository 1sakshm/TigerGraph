const $ = (id) => document.getElementById(id);
const state = { cases: [], selected: null, tab: 'overview', mode: null, highlighted: [] };
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const pct = (value) => `${Math.round((value || 0) * 100)}%`;
const pretty = (value) => String(value || '').replaceAll('_', ' ');

async function request(path, options = {}) {
  const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}
function flash(message, error = false) {
  const toast = $('toast'); toast.textContent = message; toast.className = `toast${error ? ' error' : ''}`; toast.hidden = false;
  clearTimeout(flash.timer); flash.timer = setTimeout(() => toast.hidden = true, 4500);
}
async function refresh(selectId = state.selected?.id) {
  state.cases = await request('/api/cases');
  state.selected = state.cases.find((item) => item.id === selectId) || state.cases[0] || null;
  render();
}
function render() {
  $('case-count').textContent = state.cases.length;
  $('queue-status').textContent = `${state.cases.length} TOTAL`;
  $('case-list').innerHTML = state.cases.length ? state.cases.map((item) => {
    const recommendation = item.recommendations.at(-1);
    return `<button class="case-item ${item.id === state.selected?.id ? 'active' : ''}" data-case="${esc(item.id)}"><div class="case-item-top"><b>${esc(item.id)}</b><span class="risk-tag ${item.risk < .5 ? 'low' : ''}">${item.risk >= .7 ? 'HIGH' : item.risk >= .4 ? 'MEDIUM' : 'LOW'}</span></div><small>${esc(item.transaction_id)} · ${esc(pretty(item.status))}</small><small>${esc(pretty(recommendation?.action || 'Investigating'))}</small></button>`;
  }).join('') : '<div class="card" style="margin:16px">No cases yet. Start with a transaction ID.</div>';
  const selected = state.selected;
  $('empty-state').hidden = Boolean(selected); $('case-view').hidden = !selected;
  if (!selected) { $('decision-content').innerHTML = '<h2>No case selected</h2><p>Investigation findings and next actions will appear here.</p>'; return; }
  $('case-id').textContent = selected.id;
  $('case-title').textContent = `Transaction ${selected.transaction_id}`;
  $('case-subtitle').textContent = `${pretty(selected.trigger)} · ${new Date(selected.created_at).toLocaleString()}`;
  $('case-status').textContent = pretty(selected.status).toUpperCase();
  $('metric-risk').textContent = pct(selected.risk);
  $('metric-confidence').textContent = pct(selected.confidence);
  $('metric-patterns').textContent = selected.patterns.length;
  $('metric-memory').textContent = selected.related_cases.length;
  document.querySelectorAll('.tab').forEach((button) => button.classList.toggle('active', button.dataset.tab === state.tab));
  renderTab(selected); renderDecision(selected);
}
function evidenceCard(item) {
  return `<div class="evidence-item" data-evidence="${esc(item.id)}"><strong><span class="evidence-id">${esc(item.id)}</span>${esc(pretty(item.kind))}</strong><p>${esc(item.claim)}</p><small>${esc(item.source)} · strength ${pct(item.strength)} · ${item.entity_ids.map(esc).join(', ')}</small></div>`;
}
function renderTab(item) {
  const target = $('tab-content');
  if (state.tab === 'overview') {
    const latest = item.recommendations.at(-1);
    target.innerHTML = `<div class="two-col"><div><section class="card"><span class="eyebrow">INVESTIGATION SUMMARY</span><h3>What the graph reveals</h3><p>${item.patterns.length ? `The investigation detected ${item.patterns.map(pretty).map(esc).join(', ')}. ` : 'No explicit graph fraud pattern was detected. '}${esc(latest?.reason || '')}</p></section><section class="card"><h3>Evidence that matters</h3><div class="evidence-list">${item.evidence.slice(-4).map(evidenceCard).join('') || '<p>No evidence retrieved.</p>'}</div></section></div><div><section class="card"><h3>Competing hypotheses <span class="muted">· heuristic weights</span></h3><div class="summary-list">${Object.entries(item.hypotheses).map(([name,value]) => `<div class="summary-line"><b>${esc(pretty(name))}</b><span>${pct(value)}</span></div>`).join('')}</div></section><section class="card"><h3>Decision progression</h3><div class="summary-list">${item.recommendations.map((rec, index) => `<div class="summary-line"><b>${index === 0 ? 'INITIAL' : 'UPDATED'} · ${esc(pretty(rec.action))}</b><span>Risk ${pct(rec.risk)} · confidence ${pct(rec.confidence)} · ${esc(rec.policy_reference)}</span></div>`).join('')}</div></section><section class="card"><h3>Why investigation stopped</h3><p>${esc(item.stop_reason)}</p></section></div></div>`;
  } else if (state.tab === 'graph') {
    target.innerHTML = `<section class="card"><h3>Connected investigation graph</h3><div class="graph-wrap" id="graph-wrap"></div><p class="graph-help">Scroll to zoom. Drag to pan. Select a node to inspect its evidence. Graph paths come from the bounded transaction neighborhood.</p></section>`;
    renderGraph(item);
  } else if (state.tab === 'evidence') {
    target.innerHTML = `<section class="card"><h3>Evidence ledger <span class="muted">(${item.evidence.length})</span></h3><div class="evidence-list">${item.evidence.map(evidenceCard).join('') || '<p>No evidence recorded.</p>'}</div></section>`;
  } else if (state.tab === 'timeline') {
    target.innerHTML = `<section class="card"><h3>Agent trace</h3><div class="trace-list">${item.trace.map((event) => `<div class="trace-item"><time>${new Date(event.at).toLocaleTimeString()}</time><div><strong>${esc(pretty(event.state))}${event.tool ? ` · ${esc(event.tool)}` : ''}</strong><p>${esc(event.reason)} — ${esc(event.result)}${event.latency_ms == null ? '' : ` · ${event.latency_ms} ms`}</p></div></div>`).join('')}</div></section>`;
  } else if (state.tab === 'memory') {
    target.innerHTML = `<section class="card"><h3>Related resolved cases</h3><p style="margin-bottom:16px">Historical outcomes provide context. Similarity is a heuristic from entity overlap and pattern match.</p><div class="memory-list">${item.related_cases.length ? item.related_cases.map((prior) => `<div class="evidence-item"><strong>${esc(prior.id)} · ${esc(pretty(prior.pattern))} · ${pct(prior.similarity)} match</strong><p>${esc(prior.summary)}</p><small>Outcome: ${esc(pretty(prior.outcome))} · action: ${esc(pretty(prior.action))} · shared entities: ${prior.entity_ids.map(esc).join(', ')}</small></div>`).join('') : '<p>No related resolved cases found.</p>'}</div></section>`;
  } else if (state.tab === 'policy') {
    const rec = item.recommendations.at(-1);
    target.innerHTML = `<section class="card"><h3>Action authorization</h3><div class="summary-list"><div class="summary-line"><b>Proposed action</b><span>${esc(pretty(rec.action))}</span></div><div class="summary-line"><b>Policy rule</b><span>${esc(rec.policy_reference)}</span></div><div class="summary-line"><b>Approval route</b><span>${rec.approval_required ? 'Named human analyst required' : 'No human approval required for proposal'}</span></div><div class="summary-line"><b>Execution state</b><span>${esc(pretty(rec.status))}. External bank actions are simulated in this build.</span></div></div></section>`;
  }
}
function renderDecision(item) {
  const rec = item.recommendations.at(-1);
  const pending = rec?.status === 'pending_approval';
  const waiting = item.status === 'WAITING_FOR_EVIDENCE';
  const closed = item.status === 'CLOSED';
  $('decision-content').innerHTML = `<div class="right-label">CURRENT ASSESSMENT</div><div class="risk-row"><span>Risk</span><strong>${pct(item.risk)}</strong></div><div class="bar"><i style="width:${pct(item.risk)}"></i></div><div class="risk-row"><span>Confidence</span><strong>${pct(item.confidence)}</strong></div><div class="bar confidence"><i style="width:${pct(item.confidence)}"></i></div><div class="right-label">NEXT BEST ACTION</div><div class="action-box"><strong>${esc(pretty(rec?.action || 'None'))}</strong><p>${esc(rec?.reason || '')}</p></div><div class="right-label">POLICY GATE</div><div class="approval-note">${rec?.approval_required ? `Human approval required · ${esc(rec.policy_reference)}` : `Proposal allowed · ${esc(rec?.policy_reference || '')}`}. Bank actions are simulated.</div><div class="right-label">MISSING EVIDENCE</div><p>${item.missing_evidence.length ? item.missing_evidence.map(pretty).map(esc).join(' · ') : 'No requested evidence remains.'}</p>${closed ? '<div class="right-label">CASE CLOSED</div><p>This outcome is available as case memory.</p>' : `<div class="decision-controls">${waiting ? '<button class="button primary" data-action="confirmed">Customer confirmed transaction</button><button class="button danger" data-action="denied">Customer denied transaction</button>' : ''}${pending ? '<label for="analyst-id" class="muted">Analyst ID for policy approval</label><input class="field" id="analyst-id" placeholder="e.g. analyst-7"><button class="button primary" data-action="approve">Approve proposed action</button><button class="button secondary" data-action="reject">Reject action</button>' : ''}<form id="close-form" class="mini-form"><label for="outcome">Resolve case</label><select class="field" name="outcome" id="outcome"><option value="inconclusive">Inconclusive</option><option value="confirmed_fraud">Confirmed fraud</option><option value="cleared">Cleared</option></select><input class="field" name="analyst_feedback" maxlength="2000" placeholder="Analyst findings (optional)"><button class="button secondary" type="submit">Close and save to memory</button></form></div>`}`;
}
function renderGraph(item) {
  const wrap = $('graph-wrap'); const nodes = item.graph.nodes || []; const edges = item.graph.edges || [];
  if (!nodes.length) { wrap.textContent = 'No graph neighborhood available.'; return; }
  const seed = nodes.find((node) => node.id === item.transaction_id) || nodes[0];
  const others = nodes.filter((node) => node.id !== seed.id);
  const positions = {[seed.id]: {x: 390, y: 205}};
  others.forEach((node, index) => { const angle = -Math.PI / 2 + (2 * Math.PI * index / Math.max(others.length, 1)); positions[node.id] = {x: 390 + Math.cos(angle) * 235, y: 205 + Math.sin(angle) * 150}; });
  const colors = {Transaction:'#7ee0cf',Account:'#88b7ef',Device:'#ffb365',Merchant:'#b9a1ee'};
  const lineSvg = edges.map((edge) => {const a=positions[edge.source], b=positions[edge.target]; return a&&b ? `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#51717b" stroke-width="2" opacity=".75"/>` : '';}).join('');
  const nodeSvg = nodes.map((node) => {const p=positions[node.id], color=colors[node.type]||'#ccd9de', marked=state.highlighted.includes(node.id); return `<g data-node="${esc(node.id)}" style="cursor:pointer"><circle cx="${p.x}" cy="${p.y}" r="${node.id===seed.id?31:marked?28:24}" fill="#10242d" stroke="${color}" stroke-width="${marked?4:2}"/><text x="${p.x}" y="${p.y+4}" text-anchor="middle" fill="${color}" font-family="DM Sans,sans-serif" font-size="11" font-weight="700">${esc(node.id.slice(0,12))}</text><text x="${p.x}" y="${p.y+45}" text-anchor="middle" fill="#a7c1c9" font-family="DM Sans,sans-serif" font-size="10">${esc(node.type)}</text></g>`;}).join('');
  wrap.innerHTML = `<svg viewBox="0 0 780 410" role="img" aria-label="Investigation graph">${lineSvg}${nodeSvg}</svg><div class="graph-tip" id="graph-tip">Select a node to inspect evidence</div>`;
  const svg = wrap.querySelector('svg'); let box={x:0,y:0,w:780,h:410}; let drag=null;
  const apply=()=>svg.setAttribute('viewBox',`${box.x} ${box.y} ${box.w} ${box.h}`);
  svg.addEventListener('wheel',(event)=>{event.preventDefault();const scale=event.deltaY>0?1.12:.89;const newW=Math.max(300,Math.min(1500,box.w*scale));const newH=newW*410/780;box.x+=(box.w-newW)/2;box.y+=(box.h-newH)/2;box.w=newW;box.h=newH;apply();},{passive:false});
  svg.addEventListener('pointerdown',(event)=>{drag={x:event.clientX,y:event.clientY,box:{...box}};svg.setPointerCapture(event.pointerId);});
  svg.addEventListener('pointermove',(event)=>{if(!drag)return;const rect=svg.getBoundingClientRect();box.x=drag.box.x-(event.clientX-drag.x)*box.w/rect.width;box.y=drag.box.y-(event.clientY-drag.y)*box.h/rect.height;apply();});
  svg.addEventListener('pointerup',()=>drag=null);
  svg.addEventListener('click',(event)=>{const selected=event.target.closest('[data-node]');if(!selected)return;const id=selected.dataset.node;const related=item.evidence.filter((e)=>e.entity_ids.includes(id));$('graph-tip').textContent=`${id} · ${related.length} evidence item${related.length===1?'':'s'}${related.length?` · ${related.map((e)=>e.id).join(', ')}`:''}`;});
}
async function updateCase(path, payload) {
  const selected = state.selected;
  const updated = await request(`/api/cases/${encodeURIComponent(selected.id)}${path}`, {method:'POST',body:JSON.stringify(payload)});
  await refresh(updated.id);
}
document.addEventListener('click', async (event) => {
  const caseButton = event.target.closest('[data-case]');
  if (caseButton) {state.selected=state.cases.find((item)=>item.id===caseButton.dataset.case);state.highlighted=[];render();return;}
  const tab = event.target.closest('[data-tab]');
  if (tab) {state.tab=tab.dataset.tab;render();return;}
  const evidence = event.target.closest('[data-evidence]');
  if (evidence && state.selected) {state.highlighted=state.selected.evidence.find((item)=>item.id===evidence.dataset.evidence)?.entity_ids || [];state.tab='graph';render();return;}
  const action = event.target.closest('[data-action]');
  if (!action || !state.selected) return;
  try {
    if (['confirmed','denied'].includes(action.dataset.action)) await updateCase('/evidence',{kind:'customer_confirmation',value:action.dataset.action});
    else await updateCase('/decision',{decision:action.dataset.action,analyst_id:$('analyst-id')?.value?.trim() || ''});
    flash('Case updated and decision history preserved.');
  } catch(error) {flash(error.message,true);}
});
document.addEventListener('submit', async (event) => {
  if (event.target.id === 'new-form') {
    event.preventDefault();const id=$('transaction-id').value.trim();if(!id)return;
    try {const created=await request('/api/investigations',{method:'POST',body:JSON.stringify({transaction_id:id,trigger:'analyst_request'})});$('transaction-id').value='';state.tab='overview';await refresh(created.id);flash(`Investigation ${created.id} opened.`);} catch(error){flash(error.message,true);}
  } else if (event.target.id === 'close-form') {
    event.preventDefault();const form=new FormData(event.target);
    try {await updateCase('/close',{outcome:form.get('outcome'),analyst_feedback:form.get('analyst_feedback')});flash('Case resolved and added to memory.');} catch(error){flash(error.message,true);}
  }
});
async function init() {
  try {const health=await request('/api/health');state.mode=health.mode;const demo=health.mode==='synthetic_demo';$('mode-badge').textContent=demo?'SYNTHETIC DEMO':'TIGERGRAPH CONNECTED';$('engine-status').textContent=demo?'Synthetic fixture mode':'TigerGraph configured';$('demo-hint').textContent=demo?'Synthetic demo transaction: T100. No benchmark data is loaded.':'Enter an imported transaction ID.';await refresh();}
  catch(error){$('mode-badge').textContent='SERVICE UNAVAILABLE';$('engine-status').textContent='Connection failed';flash(error.message,true);}
}
init();
