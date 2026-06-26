
// ── Chart defaults ──────────────────────────────────────────────────────────
const CD={
  responsive:true,maintainAspectRatio:false,
  plugins:{legend:{display:false},tooltip:{backgroundColor:'#1e2028',borderColor:'#2e3140',borderWidth:1,titleColor:'#8b90a0',bodyColor:'#d4d8e2',padding:8}},
  scales:{
    x:{grid:{color:'#1a1c22'},ticks:{color:'#5a5f72',font:{family:"'JetBrains Mono',monospace",size:10},maxRotation:0}},
    y:{grid:{color:'#1a1c22'},ticks:{color:'#5a5f72',font:{family:"'JetBrains Mono',monospace",size:10}},beginAtZero:true}
  }
};
function deep(a,b){const o={...a};for(const k in b){if(b[k]&&typeof b[k]==='object'&&!Array.isArray(b[k]))o[k]=deep(a[k]||{},b[k]);else o[k]=b[k];}return o;}
function mk(id,type,labels,datasets,ov={}){
  const el=document.getElementById(id);if(!el)return null;
  if(el._chart)el._chart.destroy();
  const c=new Chart(el,{type,data:{labels,datasets},options:deep(CD,ov)});
  el._chart=c;return c;
}
function pFmt(s){return s?`${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`:'—';}

// ── Cache refresh ────────────────────────────────────────────────────────────
async function refreshData(){
  const btn=document.getElementById('refreshBtn');
  btn.textContent='...';btn.disabled=true;
  await fetch('/api/cache/clear');
  window._perfLoaded=false;
  location.re
// ── Train Tab ─────────────────────────────────────────────────────────────────

async function loadTrain() {
  const content = document.getElementById('trainContent');
  const loading = document.getElementById('trainLoading');
  if (!content || !loading) return;
  loading.style.display = 'flex';
  content.style.display = 'none';
  try {
    const res = await fetch('/api/training/week');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const d = await res.json();
    if (d.error) throw new Error(d.error);
    loading.style.display = 'none';
    content.style.display = 'block';
    renderTrain(d);
  } catch (e) {
    loading.style.display = 'none';
    content.innerHTML = '<div style="padding:20px;color:var(--red);font-size:.75rem">Error loading training plan: ' + e.message + '</div>';
    content.style.display = 'block';
  }
}

function renderTrain(d) {
  const cacheEl = document.getElementById('trainCacheStatus');
  if (cacheEl && d.cache_status) {
    const cs = d.cache_status;
    const ago = cs.refreshed_at ? new Date(cs.refreshed_at).toLocaleDateString('en-US', {month:'short',day:'numeric'}) : 'never';
    cacheEl.textContent = cs.class_count + ' classes cached · last refreshed ' + ago;
  }
  const gcEl = document.getElementById('trainGCStatus');
  if (gcEl) {
    gcEl.innerHTML = d.google_connected
      ? '<span class="bk bkg">◆ Runna connected</span>'
      : '<a href="/google/login" style="color:var(--orange);font-size:.68rem;text-decoration:none;border:1px solid var(--orange);padding:2px 8px;border-radius:2px">Connect Runna calendar</a>';
  }
  const grid = document.getElementById('trainWeekGrid');
  if (!grid) return;
  grid.innerHTML = '';
  d.week.forEach(function(day) { grid.appendChild(buildTrainDayCard(day)); });
}

function buildTrainDayCard(day) {
  const card = document.createElement('div');
  card.className = 'train-day' + (day.is_today ? ' today' : '');

  const dayTypeColor = {
    rest:'var(--muted)', easy:'var(--yellow)', moderate:'var(--yellow)',
    hard:'var(--green)', long:'var(--green)'
  }[day.day_type] || 'var(--muted)';

  const sourceColor = {
    strava:'var(--orange)', runna:'var(--blue)', rest:'var(--muted)'
  }[day.source] || 'var(--muted)';

  const todayBadge = day.is_today
    ? ' <span style="font-family:var(--mono);font-size:.55rem;color:var(--orange);border:1px solid rgba(252,76,2,.3);padding:1px 5px;border-radius:2px">today</span>'
    : '';

  let bodyHtml = '';

  if (day.day_type !== 'rest' || day.source === 'strava') {
    const badgeBg = {strava:'rgba(252,76,2,.12)',runna:'rgba(59,130,246,.12)',rest:'rgba(90,96,112,.1)'}[day.source] || 'rgba(90,96,112,.1)';
    bodyHtml += '<div class="train-run-badge" style="background:' + badgeBg + ';color:' + sourceColor + ';border:1px solid ' + sourceColor + '33">'
      + (day.source==='strava' ? '● Strava' : day.source==='runna' ? '◆ Runna' : '○ Rest')
      + '</div>'
      + '<div class="train-run-name">' + (day.run_name || day.timing.label) + '</div>'
      + '<div class="train-run-meta" style="color:' + dayTypeColor + '">'
      + day.day_type.toUpperCase() + (day.run_miles > 0 ? ' · ' + day.run_miles + ' km' : '')
      + '</div>';
  }

  const pelo = day.peloton;
  if (pelo) {
    const catColor = {
      push:'var(--orange)', pull:'var(--blue)', legs:'var(--yellow)',
      core:'var(--green)', stretch:'var(--purple)', runners:'var(--orange)'
    }[pelo.category] || 'var(--purple)';

    bodyHtml += '<hr class="train-pelo-divider">';
    bodyHtml += '<div class="train-pelo-label" style="color:' + catColor + '">' + pelo.category.toUpperCase() + '</div>';

    if (pelo.main) {
      bodyHtml += '<div class="train-pelo-title">' + pelo.main.title + '</div>'
        + '<div class="train-pelo-meta">' + pelo.main.instructor + ' · ' + pelo.main.duration_min + ' min</div>'
        + '<div class="train-pelo-reason">' + pelo.reason + '</div>'
        + (pelo.main.url
          ? '<a class="train-pelo-link" href="' + pelo.main.url + '" target="_blank">Open in Peloton →</a>'
          : '<span style="font-size:.6rem;color:var(--muted)">Search in Peloton app</span>');
    }

    if (pelo.core_addon) {
      bodyHtml += '<div class="train-core-addon">'
        + '<div class="train-core-label">+ Core</div>'
        + '<div class="train-core-title">' + pelo.core_addon.title + '</div>'
        + '<div class="train-pelo-meta">' + pelo.core_addon.instructor + ' · ' + pelo.core_addon.duration_min + ' min</div>'
        + (pelo.core_addon.url ? '<a class="train-pelo-link" href="' + pelo.core_addon.url + '" target="_blank" style="margin-top:4px;display:inline-block">Open →</a>' : '')
        + '</div>';
    }
  } else if (day.day_type === 'rest' && day.source === 'rest') {
    bodyHtml += '<div class="train-rest-label">Rest day</div>';
  }

  card.innerHTML = '<div class="train-day-header">'
    + '<div class="train-day-dow">' + day.dow + todayBadge + '</div>'
    + '<div class="train-day-date">' + day.display_date + '</div>'
    + '</div>'
    + '<div class="train-day-body">' + bodyHtml + '</div>';

  return card;
}

async function refreshPelotonCache() {
  const btn = document.getElementById('trainRefreshBtn');
  const status = document.getElementById('trainCacheStatus');
  btn.disabled = true; btn.textContent = '↺ Refreshing...';
  try {
    const res = await fetch('/api/peloton/refresh', { method: 'POST' });
    const d = await res.json();
    if (d.ok) {
      status.textContent = d.status.class_count + ' classes cached · refreshed just now';
      window._trainLoaded = false;
      loadTrain();
    }
  } catch(e) {
    status.textContent = 'Refresh failed: ' + e.message;
  }
  btn.disabled = false; btn.textContent = '↺ Refresh library';
}



// ── Meals Tab ─────────────────────────────────────────────────────────────────

let _mealsDB       = null;
let _mealsPlan     = 'standard_7day';
let _mealsDay      = null;
let _fuelDayType   = null;  // today's fuel day type from /api/fuel/plan

const DAY_TYPE_COLOR_MEALS = {
  rest: 'var(--red)', easy: 'var(--yellow)', moderate: 'var(--yellow)',
  hard: 'var(--green)', long: 'var(--green)'
};

async function loadMeals() {
  const content = document.getElementById('mealsContent');
  const loading = document.getElementById('mealsLoading');
  if (!content || !loading) return;
  loading.style.display = 'flex';
  content.style.display = 'none';

  try {
    // Load meals DB and today's fuel day type in parallel
    const [mealsRes, fuelRes] = await Promise.all([
      fetch('/api/meals'),
      fetch('/api/fuel/plan'),
    ]);
    if (!mealsRes.ok) throw new Error('Meals data not found — make sure meals.json is in your Stride folder');
    _mealsDB = await mealsRes.json();

    // Get today's day type from fuel plan
    if (fuelRes.ok) {
      const fd = await fuelRes.json();
      const today = fd.days && fd.days.find(d => d.is_today);
      if (today) _fuelDayType = today.day_type;
    }

    loading.style.display = 'none';
    content.style.display = 'block';
    renderMealsPlan(_mealsPlan);
  } catch(e) {
    loading.style.display = 'none';
    content.innerHTML = '<div style="padding:20px;color:var(--red);font-size:.75rem">' + e.message + '</div>';
    content.style.display = 'block';
  }
}

function onMealsPlanChange() {
  _mealsPlan = document.getElementById('mealsPlanSelect').value;
  _mealsDay  = null;
  renderMealsPlan(_mealsPlan);
}

function renderMealsPlan(planKey) {
  const plan = _mealsDB && _mealsDB.plans && _mealsDB.plans[planKey];
  if (!plan) return;

  // Update description
  const descEl = document.getElementById('mealsPlanDesc');
  if (descEl) descEl.textContent = plan.description || '';

  // Build day tabs
  const tabsEl = document.getElementById('mealsDayTabs');
  if (!tabsEl) return;
  tabsEl.innerHTML = '';

  if (plan.type === 'periodized') {
    // 7-day periodized — tabs are day types
    const dayTypes = Object.keys(plan.days);
    dayTypes.forEach(function(dt) {
      const tab = document.createElement('div');
      tab.className = 'meals-day-tab' + (dt === (_mealsDay || _fuelDayType || 'easy') ? ' active' : '');
      const color = DAY_TYPE_COLOR_MEALS[dt] || 'var(--muted)';
      tab.innerHTML = '<span class="dot" style="background:' + color + '"></span>' + plan.days[dt].label;
      tab.onclick = function() {
        document.querySelectorAll('.meals-day-tab').forEach(function(t) { t.classList.remove('active'); });
        tab.classList.add('active');
        _mealsDay = dt;
        renderMealDay(plan, dt);
      };
      tabsEl.appendChild(tab);
    });
    // Show today's day type by default
    const defaultDay = _mealsDay || _fuelDayType || 'easy';
    renderMealDay(plan, defaultDay);

  } else if (plan.type === 'calendar') {
    // 30-day — tabs are weeks, then days
    const weeks = [...new Set(plan.days.map(function(d) { return d.week; }))].sort();
    weeks.forEach(function(w) {
      const tab = document.createElement('div');
      tab.className = 'meals-day-tab' + (w === 1 ? ' active' : '');
      tab.textContent = 'Week ' + w;
      tab.onclick = function() {
        document.querySelectorAll('.meals-day-tab').forEach(function(t) { t.classList.remove('active'); });
        tab.classList.add('active');
        renderMealsWeek(plan, w);
      };
      tabsEl.appendChild(tab);
    });
    renderMealsWeek(plan, 1);

  } else if (plan.type === 'library') {
    // Paleo — tabs by meal type
    const mealTypes = [...new Set(plan.meals.map(function(m) { return m.type; }))];
    mealTypes.forEach(function(mt) {
      const tab = document.createElement('div');
      tab.className = 'meals-day-tab' + (mt === 'breakfast' ? ' active' : '');
      tab.textContent = mt.charAt(0).toUpperCase() + mt.slice(1);
      tab.onclick = function() {
        document.querySelectorAll('.meals-day-tab').forEach(function(t) { t.classList.remove('active'); });
        tab.classList.add('active');
        renderMealsLibrary(plan, mt);
      };
      tabsEl.appendChild(tab);
    });
    renderMealsLibrary(plan, 'breakfast');
  }
}

function renderMealDay(plan, dayType) {
  const day = plan.days[dayType];
  if (!day) return;
  showDaySummary(day.meals);
  renderMealCards(day.meals);
}

function renderMealsWeek(plan, weekNum) {
  const weekDays = plan.days.filter(function(d) { return d.week === weekNum; });
  // Build inner day tabs
  const tabsEl = document.getElementById('mealsDayTabs');
  // Keep week tabs, add day sub-tabs below
  // For simplicity, show first day's meals and let user pick day
  const existing = Array.from(tabsEl.children);
  // Remove any day sub-tabs
  existing.forEach(function(t) {
    if (t.dataset.dtype === 'day') t.remove();
  });

  // Show all meals for the week as a flat grid, grouped by day
  const cards = document.getElementById('mealCards');
  const summary = document.getElementById('mealsDaySummary');
  if (summary) summary.style.display = 'none';
  if (!cards) return;
  cards.innerHTML = '';

  weekDays.forEach(function(day) {
    if (!day.meals || day.meals.length === 0) return;
    // Day header
    const header = document.createElement('div');
    header.style.cssText = 'grid-column:1/-1;font-family:var(--sans);font-size:.85rem;font-weight:700;color:var(--orange);padding:6px 0 4px;border-bottom:1px solid var(--border);margin-bottom:2px';
    header.textContent = day.day;
    cards.appendChild(header);
    day.meals.forEach(function(meal) {
      cards.appendChild(buildMealCard(meal));
    });
  });
}

function renderMealsLibrary(plan, mealType) {
  const meals = plan.meals.filter(function(m) { return m.type === mealType; });
  showDaySummary(null);
  renderMealCards(meals);
}

function showDaySummary(meals) {
  const summary = document.getElementById('mealsDaySummary');
  if (!summary) return;
  if (!meals || meals.length === 0) { summary.style.display = 'none'; return; }

  const totals = meals.reduce(function(acc, m) {
    return {
      cal:     acc.cal     + (m.cal     || 0),
      protein: acc.protein + (m.protein || 0),
      carbs:   acc.carbs   + (m.carbs   || 0),
      fat:     acc.fat     + (m.fat     || 0),
    };
  }, {cal:0, protein:0, carbs:0, fat:0});

  document.getElementById('mds-cal').textContent     = totals.cal;
  document.getElementById('mds-carbs').textContent   = Math.round(totals.carbs) + 'g';
  document.getElementById('mds-protein').textContent = Math.round(totals.protein) + 'g';
  document.getElementById('mds-fat').textContent     = Math.round(totals.fat) + 'g';

  const typeEl = document.getElementById('mds-type');
  if (typeEl && _fuelDayType && _mealsPlan === 'standard_7day') {
    typeEl.textContent = _fuelDayType.toUpperCase() + ' DAY';
    typeEl.style.color = DAY_TYPE_COLOR_MEALS[_fuelDayType] || 'var(--muted)';
  } else if (typeEl) {
    typeEl.textContent = '';
  }
  summary.style.display = 'flex';
}

function renderMealCards(meals) {
  const cards = document.getElementById('mealCards');
  if (!cards) return;
  cards.innerHTML = '';
  meals.forEach(function(meal) {
    cards.appendChild(buildMealCard(meal));
  });
}

function buildMealCard(meal) {
  const card = document.createElement('div');
  card.className = 'meal-card-s';

  const typeLabel = meal.type || 'Meal';
  const macroHtml =
    '<span style="color:var(--blue)">' + (meal.carbs || meal.c || 0) + 'g C</span> ' +
    '<span style="color:var(--green)">' + (meal.protein || meal.p || 0) + 'g P</span> ' +
    '<span style="color:var(--orange)">' + (meal.fat || meal.f || 0) + 'g F</span> ' +
    '<span style="color:var(--muted2)">' + (meal.cal || 0) + ' cal</span>';

  const desc = meal.desc || meal.description || '';
  const tags = meal.tags || [];
  const ingredients = meal.ingredients || [];
  const steps = meal.steps || [];
  const hasDetail = ingredients.length > 0 || steps.length > 0;

  const tagsHtml = tags.map(function(t) {
    return '<span class="meal-tag">' + t + '</span>';
  }).join('');

  card.innerHTML =
    '<div class="meal-card-header">' +
      '<span class="meal-card-label">' + typeLabel + '</span>' +
      '<div class="meal-card-macros">' + macroHtml + '</div>' +
    '</div>' +
    '<div class="meal-card-body">' +
      '<div class="meal-card-name">' + meal.name + '</div>' +
      (desc ? '<div class="meal-card-desc">' + desc + '</div>' : '') +
      (tagsHtml ? '<div class="meal-card-tags">' + tagsHtml + '</div>' : '') +
      (hasDetail ? '<div class="meal-expand" id="expand-' + Math.random().toString(36).substr(2,6) + '" style="display:none">' +
        (ingredients.length ? '<div class="meal-expand-title">Ingredients</div><ul>' + ingredients.map(function(i){ return '<li>' + i + '</li>'; }).join('') + '</ul>' : '') +
        (steps.length ? '<div class="meal-expand-title" style="margin-top:8px">Steps</div><ol>' + steps.map(function(s){ return '<li>' + s + '</li>'; }).join('') + '</ol>' : '') +
      '</div>' : '') +
      (hasDetail ? '<div style="font-family:var(--mono);font-size:.58rem;color:var(--muted);margin-top:6px;cursor:pointer" onclick="toggleMealExpand(this)">▸ Show ingredients & steps</div>' : '') +
    '</div>';

  return card;
}

function toggleMealExpand(el) {
  const body = el.parentElement;
  const expand = body.querySelector('.meal-expand');
  if (!expand) return;
  const open = expand.style.display !== 'none';
  expand.style.display = open ? 'none' : 'block';
  el.textContent = open ? '▸ Show ingredients & steps' : '▾ Hide';
}


load();
}

// ── Tabs ────────────────────────────────────────────────────────────────────
const tabNames={'overview':'Overview','performance':'Performance','info':'Guide','fuel':'Fuel','train':'Train','meals':'Meals'};
function switchTab(name){
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.dataset.tab===name));
  document.querySelectorAll('.tab-page').forEach(p=>p.classList.toggle('active',p.id==='tab-'+name));
  document.getElementById('tabBread').textContent=tabNames[name]||name;
  if(name==='performance' && !window._perfLoaded) loadPerformance();
  if(name==='fuel' && !window._fuelLoaded){ window._fuelLoaded=true; loadFuel(); }
  if(name==='train' && !window._trainLoaded){ window._trainLoaded=true; loadTrain(); }
  if(name==='meals' && !window._mealsLoaded){ window._mealsLoaded=true; loadMeals(); }
}

// ── Drawer ──────────────────────────────────────────────────────────────────
let drawerMap=null,drawerCharts=[],currentRunId=null;

function openRun(runId){
  if(runId===currentRunId)return;
  currentRunId=runId;
  const drawer=document.getElementById('drawer');
  document.querySelectorAll('.tab-page.active').forEach(p=>p.classList.add('drawer-open'));
  drawer.classList.add('open');
  history.pushState({drawerOpen:true,runId},'','#run-'+runId);
  document.getElementById('drawerBody').innerHTML='<div class="drawer-loading"><div class="spin"></div><div class="lmsg">loading run data...</div></div>';
  document.getElementById('drawerTitle').textContent='Loading...';
  drawerCharts.forEach(c=>c.destroy());drawerCharts=[];
  if(drawerMap){drawerMap.remove();drawerMap=null;}
  fetch(`/api/run/${runId}`)
    .then(async r=>{
      const text=await r.text();
      let data;
      try{data=JSON.parse(text);}
      catch(e){
        document.getElementById('drawerBody').innerHTML=`<div style="padding:16px;font-size:.75rem;color:var(--red)"><div style="margin-bottom:8px;font-weight:600">Server error</div><pre style="background:var(--bg2);border:1px solid var(--border);padding:10px;font-size:.65rem;color:var(--muted2);white-space:pre-wrap;overflow:auto">${text.slice(0,800)}</pre></div>`;
        return;
      }
      if(data.error){
        document.getElementById('drawerBody').innerHTML=`<div style="padding:16px;font-size:.75rem;color:var(--red)"><div style="margin-bottom:6px;font-weight:600">Error: ${data.error}</div>${data.traceback?`<pre style="background:var(--bg2);border:1px solid var(--border);padding:10px;font-size:.65rem;color:var(--muted2);white-space:pre-wrap;overflow:auto">${data.traceback}</pre>`:''}</div>`;
        return;
      }
      renderDrawer(data);
    })
    .catch(e=>{document.getElementById('drawerBody').innerHTML=`<div style="padding:16px;font-size:.75rem;color:var(--red)">Network error: ${e.message}</div>`;});
}
function closeDrawer(fromPopState){
  if(!currentRunId)return;
  currentRunId=null;
  document.getElementById('drawer').classList.remove('open');
  document.querySelectorAll('.tab-page').forEach(p=>p.classList.remove('drawer-open'));
  drawerCharts.forEach(c=>c.destroy());drawerCharts=[];
  if(drawerMap){drawerMap.remove();drawerMap=null;}
  if(!fromPopState && window.location.hash.startsWith('#run-')) history.back();
}

// Handle browser back/forward — close drawer instead of leaving page
window.addEventListener('popstate', e=>{
  if(!e.state || !e.state.drawerOpen) closeDrawer(true);
});
function renderDrawer(data){
  const s=data.summary,st=data.streams,tr=s.training;
  document.getElementById('drawerTitle').textContent=s.name;
  const zColors=['#5794f2','#73bf69','#fade2a','#f5a623','#f2495c'];
  let iLabel='—',iClass='or';
  if(tr.intensity_pct){const p=tr.intensity_pct;if(p<60){iLabel='Easy';iClass='gr';}else if(p<70){iLabel='Aerobic';iClass='bl';}else if(p<80){iLabel='Tempo';iClass='or';}else if(p<90){iLabel='Threshold';iClass='or';}else{iLabel='Max';iClass='rd';}}
  const hasPace=st.pace&&st.pace.length>0,hasHR=st.hr&&st.hr.length>0,hasElev=st.elevation&&st.elevation.length>0,hasMap=st.latlng&&st.latlng.length>1,hasSplits=s.splits&&s.splits.length>0;
  document.getElementById('drawerBody').innerHTML=`
    <div id="runMap"></div>
    <div style="margin-bottom:8px"><div style="font-size:.72rem;color:var(--muted)">${s.date} · ${s.time_start}</div>
      <div style="display:flex;gap:8px;margin-top:4px"><a href="${s.strava_url}" target="_blank" class="strava-link"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169"/></svg>View on Strava</a></div></div>
    <div class="meta-grid">
      <div class="meta-cell"><div class="meta-label">Distance</div><div class="meta-val or">${s.miles} km</div></div>
      <div class="meta-cell"><div class="meta-label">Avg Pace</div><div class="meta-val">${s.avg_pace}/km</div></div>
      <div class="meta-cell"><div class="meta-label">Moving Time</div><div class="meta-val">${s.moving_time}</div></div>
      <div class="meta-cell"><div class="meta-label">Elev Gain</div><div class="meta-val gr">${s.elev_gain} m</div></div>
      <div class="meta-cell"><div class="meta-label">Avg HR</div><div class="meta-val rd">${s.avg_hr}${s.avg_hr!=='—'?' bpm':''}</div></div>
      <div class="meta-cell"><div class="meta-label">Max HR</div><div class="meta-val rd">${s.max_hr}${s.max_hr!=='—'?' bpm':''}</div></div>
      <div class="meta-cell"><div class="meta-label">Cadence</div><div class="meta-val">${s.cadence}${s.cadence!=='—'?' spm':''}</div></div>
      <div class="meta-cell"><div class="meta-label">Calories</div><div class="meta-val">${s.calories}${typeof s.calories==='number'?' cal':''}</div></div>
    </div>
    <div style="font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:6px">Training Effect</div>
    <div class="training-block">
      <div class="t-cell"><div class="t-label">Training Load</div><div class="t-val">${tr.training_load||'—'}</div><div class="t-sub">TRIMP score</div></div>
      <div class="t-cell"><div class="t-label">Suffer Score</div><div class="t-val">${tr.suffer_score||'—'}</div><div class="t-sub">Strava relative effort</div></div>
      <div class="t-cell"><div class="t-label">Intensity</div><div class="t-val ${iClass}">${tr.intensity_pct?tr.intensity_pct+'%':'—'}</div><div class="t-sub">${iLabel}</div>
        <div class="zone-bar">${zColors.map((c,i)=>`<div class="zs" style="flex:1;background:${i<(tr.intensity_pct?Math.ceil(tr.intensity_pct/20):0)?c:'#2a2d36'}"></div>`).join('')}</div></div>
    </div>
    ${hasPace||hasHR||hasElev?`
    <div style="font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:6px">Data Over Distance</div>
    <div class="stream-charts">
      ${hasPace?`<div class="sc-panel"><div class="sc-title">Pace /km</div><div class="sc-wrap"><canvas id="dPaceChart"></canvas></div></div>`:''}
      ${hasHR?`<div class="sc-panel"><div class="sc-title">Heart Rate (bpm)</div><div class="sc-wrap"><canvas id="dHRChart"></canvas></div></div>`:''}
      ${hasElev?`<div class="sc-panel" style="grid-column:span 2"><div class="sc-title">Elevation (m)</div><div class="sc-wrap"><canvas id="dElevChart"></canvas></div></div>`:''}
    </div>`:''}
    ${hasSplits?`
    <div style="font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:6px">Km Splits</div>
    <div class="splits-panel"><table class="dt"><thead><tr><th>Km</th><th>Pace /km</th><th>HR</th><th>Elev Δ</th></tr></thead><tbody>
      ${s.splits.map(sp=>`<tr><td>${sp.split}</td><td class="tn">${sp.pace}</td><td class="tn">${sp.hr!=='—'?sp.hr+' bpm':'—'}</td><td class="tn" style="color:${sp.elev>0?'var(--green)':sp.elev<0?'var(--red)':'var(--muted)'}">${sp.elev>0?'+':''}${sp.elev} m</td></tr>`).join('')}
    </tbody></table></div>`:''}`;
  requestAnimationFrame(()=>{
    if(hasMap){
      drawerMap=L.map('runMap',{zoomControl:true,attributionControl:false});
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{maxZoom:19}).addTo(drawerMap);
      const line=L.polyline(st.latlng,{color:'#f5a623',weight:3,opacity:.9}).addTo(drawerMap);
      if(st.latlng.length>0){
        const si=L.divIcon({className:'',html:'<div style="width:10px;height:10px;border-radius:50%;background:#73bf69;border:2px solid #fff"></div>'});
        const ei=L.divIcon({className:'',html:'<div style="width:10px;height:10px;border-radius:50%;background:#f2495c;border:2px solid #fff"></div>'});
        L.marker(st.latlng[0],{icon:si}).addTo(drawerMap);
        L.marker(st.latlng[st.latlng.length-1],{icon:ei}).addTo(drawerMap);
      }
      drawerMap.fitBounds(line.getBounds(),{padding:[12,12]});
    } else {
      document.getElementById('runMap').innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted);font-size:.75rem">No GPS data available</div>';
    }
    const dLabels=st.distance.map(d=>d.toFixed(1));
    const so=deep({scales:{x:{ticks:{callback:(_,i)=>i%Math.ceil(dLabels.length/6)===0?dLabels[i]+'mi':'',font:{size:9}},grid:{color:'#1a1c22'}},y:{grid:{color:'#1a1c22'},ticks:{font:{size:9}}}}},{});
    if(hasPace&&document.getElementById('dPaceChart')){const c=mk('dPaceChart','line',dLabels,[{data:st.pace,borderColor:'#f5a623',backgroundColor:'rgba(245,166,35,.08)',borderWidth:1.5,fill:true,tension:0.3,pointRadius:0,spanGaps:true}],deep(so,{scales:{y:{reverse:true,ticks:{callback:v=>v?pFmt(v):''}}}},{plugins:{tooltip:{callbacks:{label:ctx=>ctx.parsed.y?` ${pFmt(ctx.parsed.y)}/km`:''}}}}));if(c)drawerCharts.push(c);}
    if(hasHR&&document.getElementById('dHRChart')){const c=mk('dHRChart','line',dLabels,[{data:st.hr,borderColor:'#f2495c',backgroundColor:'rgba(242,73,92,.08)',borderWidth:1.5,fill:true,tension:0.3,pointRadius:0,spanGaps:true}],so);if(c)drawerCharts.push(c);}
    if(hasElev&&document.getElementById('dElevChart')){const c=mk('dElevChart','line',dLabels,[{data:st.elevation,borderColor:'#73bf69',backgroundColor:'rgba(115,191,105,.12)',borderWidth:1.5,fill:true,tension:0.3,pointRadius:0,spanGaps:true}],so);if(c)drawerCharts.push(c);}
  });
}

// ── Overview load ────────────────────────────────────────────────────────────
async function load(){
  const res=await fetch('/api/stats');
  if(!res.ok){document.querySelector('.lmsg').textContent='Failed to load.';return;}
  const d=await res.json();
  const t=d.totals;
  document.getElementById('topAthl').textContent=d.athlete?.firstname||'';
  document.getElementById('s-wk-mi').textContent=t.week.miles+' km';
  document.getElementById('s-wk-sub').textContent=`${t.week.runs} run${t.week.runs!==1?'s':''} · ${t.week.time}`;
  document.getElementById('s-mo-mi').textContent=t.month.miles+' km';
  document.getElementById('s-mo-sub').textContent=`${t.month.runs} runs · ${t.month.time}`;
  document.getElementById('s-yr-mi').textContent=t.year.miles+' km';
  document.getElementById('s-yr-sub').textContent=`${t.year.runs} runs · ${t.year.time}`;
  document.getElementById('s-at-mi').textContent=t.all_miles+' km';
  document.getElementById('s-at-sub').textContent=`${t.all_runs} total runs`;
  document.getElementById('s-str').textContent=d.streaks.current+' days';
  document.getElementById('s-str-sub').textContent=`best: ${d.streaks.best} days`;

  // charts rendered after tiles are painted
  window._overviewData = d;
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer();});
  document.getElementById('loading').style.display='none';
  document.getElementById('dash-tab').style.display='block';
  requestAnimationFrame(()=>setTimeout(renderOverviewCharts, 0));
}

function renderOverviewCharts(){
  const d = window._overviewData;
  if(!d) return;
  const wkLabels=d.weekly_spark.labels.map(l=>{const dt=new Date(l+'T00:00');return dt.toLocaleDateString('en-US',{month:'short',day:'numeric'});});
  const wkChart=mk('wkChart','bar',wkLabels,
    [{data:d.weekly_spark.miles,backgroundColor:'rgba(87,148,242,0.65)',hoverBackgroundColor:'rgba(87,148,242,1)',borderRadius:2,borderSkipped:false}]);
  if(wkChart){
    document.getElementById('wkChart').addEventListener('click',e=>{
      const pts=wkChart.getElementsAtEventForMode(e,'nearest',{intersect:true},false);
      if(!pts.length)return;
      const idx=pts[0].index;
      const weekLabel=wkLabels[idx];
      const runDetails=d.weekly_spark.run_details && d.weekly_spark.run_details[idx];
      const totalMiles=d.weekly_spark.miles[idx];
      if(runDetails && runDetails.length>0){
        showWeekPopover(weekLabel, {miles:totalMiles, runs:runDetails.length, run_details:runDetails}, d);
      }
    });
  }
  mk('moChart','bar',d.monthly_chart.labels,
    [{data:d.monthly_chart.miles,backgroundColor:'rgba(115,191,105,0.65)',borderRadius:2,borderSkipped:false}]);

  const paceChart=mk('paceChart','line',d.pace_trend.labels,[{
    data:d.pace_trend.pace_sec,borderColor:'#f5a623',backgroundColor:'rgba(245,166,35,0.07)',
    borderWidth:1.5,fill:true,tension:0.35,pointRadius:4,pointBackgroundColor:'#f5a623',pointHoverRadius:7
  }],{scales:{y:{reverse:true,grid:{color:'#1a1c22'},ticks:{color:'#5a5f72',font:{size:10},callback:v=>{const m=Math.floor(v/60);return `${m}:${String(v%60).padStart(2,'0')}`;}}},x:{grid:{color:'#1a1c22'},ticks:{color:'#5a5f72',font:{size:10}}}},plugins:{tooltip:{callbacks:{label:ctx=>{const s=ctx.parsed.y;return ` ${Math.floor(s/60)}:${String(s%60).padStart(2,'0')} /km`;}}}}});
  if(paceChart){document.getElementById('paceChart').addEventListener('click',e=>{const pts=paceChart.getElementsAtEventForMode(e,'nearest',{intersect:true},false);if(pts.length>0){const id=d.pace_trend.run_ids[pts[0].index];if(id)openRun(id);}});}

  mk('distChart','bar',d.dist_dist.labels,[{data:d.dist_dist.counts,backgroundColor:['rgba(242,73,92,.7)','rgba(245,166,35,.7)','rgba(115,191,105,.7)','rgba(87,148,242,.7)','rgba(184,119,217,.7)'],borderRadius:2,borderSkipped:false}]);

  const pg=document.getElementById('prGrid');
  [{label:'Longest Run',val:d.prs.longest?d.prs.longest.miles+' km':'—',det:d.prs.longest?.date||'',id:d.prs.longest?.id},
   {label:'Fastest 5K',val:d.prs['5k']?.pace||'—',det:d.prs['5k']?d.prs['5k'].time+' · '+d.prs['5k'].date:'—',id:d.prs['5k']?.id},
   {label:'Fastest 10K',val:d.prs['10k']?.pace||'—',det:d.prs['10k']?d.prs['10k'].time+' · '+d.prs['10k'].date:'—',id:d.prs['10k']?.id},
   {label:'Half Marathon',val:d.prs.half?.pace||'—',det:d.prs.half?d.prs.half.time+' · '+d.prs.half.date:'no half yet',id:d.prs.half?.id}
  ].forEach(p=>{const el=document.createElement('div');el.className='pr-item';el.innerHTML=`<div class="pr-type">${p.label}</div><div class="pr-val">${p.val}</div><div class="pr-det">${p.det}</div>`;if(p.id)el.onclick=()=>openRun(p.id);else el.style.cursor='default';pg.appendChild(el);});

  const wb=document.getElementById('wkBody');
  d.weekly_table.forEach((w,i)=>{const tr=document.createElement('tr');const lid=w.run_ids&&w.run_ids.length>0?w.run_ids[w.run_ids.length-1]:null;if(lid){tr.className='clickable';tr.onclick=()=>openRun(lid);}tr.innerHTML=`<td>${w.week} ${i===0?'<span class="bk bkb">now</span>':''}</td><td class="tn">${w.runs}</td><td><span class="bk bkg">${w.miles} km</span></td><td class="tn">${w.pace}</td><td class="tn">${w.time}</td><td class="tn">${w.elev>0?w.elev+' m':'—'}</td>`;wb.appendChild(tr);});

  const rb=document.getElementById('rcBody');
  const isMobile=window.innerWidth<=768;
  d.recent.forEach(r=>{
    if(isMobile){
      // Card row spanning all columns on mobile
      const tr=document.createElement('tr');
      tr.className='clickable';
      tr.onclick=()=>openRun(r.id);
      tr.innerHTML='<td colspan="7" style="padding:10px 12px">'
        +'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
        +'<span style="font-weight:500;color:var(--text);font-size:.8rem">'+r.name+'</span>'
        +'<span class="bk bko">'+r.miles+' km</span>'
        +'</div>'
        +'<div style="display:flex;gap:12px;font-size:.7rem;color:var(--muted2)">'
        +'<span>'+r.date+'</span>'
        +'<span>'+r.pace+'/km</span>'
        +'<span>'+r.time+'</span>'
        +(r.hr!=='—'?'<span style="color:#f2495c">'+Math.round(r.hr)+' bpm</span>':'')
        +(r.elev>0?'<span style="color:#73bf69">'+r.elev+' m</span>':'')
        +'</div>'
        +'</td>';
      rb.appendChild(tr);
    } else {
      const tr=document.createElement('tr');
      tr.className='clickable';
      tr.onclick=()=>openRun(r.id);
      tr.innerHTML='<td><span class="run-link">'+r.name+'</span></td><td class="tn">'+r.date+'</td><td><span class="bk bko">'+r.miles+'</span></td><td class="tn">'+r.pace+'</td><td class="tn">'+r.time+'</td><td class="tn">'+(r.hr!=='—'?Math.round(r.hr)+' bpm':'—')+'</td><td class="tn">'+(r.elev>0?r.elev+' m':'—')+'</td>';
      rb.appendChild(tr);
    }
  });
}

// ── Performance tab load ────────────────────────────────────────────────────
let _prData=null, _activePR='5k';
async function loadPerformance(){
  window._perfLoaded=true;
  const res=await fetch('/api/performance');
  document.getElementById('perfLoading').style.display='none';
  if(!res.ok){document.getElementById('perfContent').innerHTML='<div style="padding:20px;color:var(--red);font-size:.75rem">Failed to load performance data.</div>';document.getElementById('perfContent').style.display='block';return;}
  const d=await res.json();
  document.getElementById('perfContent').style.display='block';
  _prData=d.pr_prog;

  // Status cards
  const tsb=d.current_tsb;
  const tsbEl=document.getElementById('p-tsb');
  tsbEl.textContent=tsb;
  tsbEl.className='tval '+(tsb>5?'gr':tsb<-10?'rd':'or');
  document.getElementById('p-tsb-sub').textContent=tsb>5?'✦ Fresh — good time to race':tsb<-10?'⚠ Fatigued — consider recovery':'→ Neutral';
  document.getElementById('p-tsb-sub').className='tdelta '+(tsb>5?'up':tsb<-10?'dn':'neu');

  document.getElementById('p-ctl').textContent=d.current_ctl;
  document.getElementById('p-ctl-sub').textContent='42-day rolling load';
  document.getElementById('p-atl').textContent=d.current_atl;
  document.getElementById('p-atl-sub').textContent='7-day rolling load';

  const sm=d.summary;
  if(sm.curr_pace){
    document.getElementById('p-pace').textContent=pFmt(sm.curr_pace)+'/km';
    document.getElementById('p-pace-sub').textContent=`vs ${pFmt(sm.prev_pace||0)}/km prior 8 wks`;
    if(sm.pace_delta!==null){
      const faster=sm.pace_delta>0;
      const secs=Math.abs(sm.pace_delta);
      document.getElementById('p-pace-delta').textContent=(faster?'▲ ':' ▼ ')+pFmt(secs)+' '+(faster?'faster':'slower')+' than prior period';
      document.getElementById('p-pace-delta').className='tdelta '+(faster?'up':'dn');
    }
  }

  // Fitness curve (CTL/ATL/TSB)
  mk('fitChart','line',d.fitness_curve.labels,[
    {label:'CTL',data:d.fitness_curve.ctl,borderColor:'#5794f2',backgroundColor:'rgba(87,148,242,.06)',borderWidth:2,fill:true,tension:0.4,pointRadius:0},
    {label:'ATL',data:d.fitness_curve.atl,borderColor:'#f5a623',backgroundColor:'transparent',borderWidth:1.5,fill:false,tension:0.4,pointRadius:0},
    {label:'TSB',data:d.fitness_curve.tsb,borderColor:'#73bf69',backgroundColor:'rgba(115,191,105,.06)',borderWidth:1,borderDash:[3,3],fill:false,tension:0.4,pointRadius:0},
  ],{plugins:{legend:{display:true,labels:{color:'#8b90a0',font:{family:"'JetBrains Mono',monospace",size:10},boxWidth:12}}},scales:{x:{grid:{color:'#1a1c22'},ticks:{color:'#5a5f72',font:{size:10},maxTicksLimit:10}},y:{grid:{color:'#1a1c22'},ticks:{color:'#5a5f72',font:{size:10}}}}});

  // Rolling pace
  if(d.weekly_pace.length>0){
    mk('rollingPaceChart','line',d.weekly_pace.map(w=>w.label),[{
      data:d.weekly_pace.map(w=>w.pace_sec),borderColor:'#f5a623',backgroundColor:'rgba(245,166,35,.08)',
      borderWidth:2,fill:true,tension:0.4,pointRadius:3,pointBackgroundColor:'#f5a623'
    }],{scales:{y:{reverse:true,grid:{color:'#1a1c22'},ticks:{color:'#5a5f72',font:{size:10},callback:v=>pFmt(v)}}},plugins:{tooltip:{callbacks:{label:ctx=>` ${pFmt(ctx.parsed.y)}/km`}}}});
  }

  // Aerobic efficiency
  if(d.eff_trend.length>0){
    mk('effChart','line',d.eff_trend.map(e=>e.label),[{
      data:d.eff_trend.map(e=>e.eff),borderColor:'#b877d9',backgroundColor:'rgba(184,119,217,.08)',
      borderWidth:2,fill:true,tension:0.4,pointRadius:4,pointBackgroundColor:'#b877d9'
    }],{plugins:{tooltip:{callbacks:{label:ctx=>{const e=d.eff_trend[ctx.dataIndex];return [` efficiency: ${e.eff}`,` avg pace: ${e.pace_fmt}/km`,` avg HR: ${e.hr} bpm`];}}}},scales:{x:{grid:{color:'#1a1c22'},ticks:{color:'#5a5f72',font:{size:10}}},y:{grid:{color:'#1a1c22'},ticks:{color:'#5a5f72',font:{size:10}},beginAtZero:false}}});
  }

  // PR progression
  showPR('5k');

  // Check Ollama status
  checkOllama();

  // Long runs
  if(d.long_run_chart.labels.length>0){
    mk('longRunChart','bar',d.long_run_chart.labels,[
      {data:d.long_run_chart.miles,backgroundColor:'rgba(87,148,242,.65)',borderRadius:2,borderSkipped:false,yAxisID:'y'},
    ],{scales:{x:{grid:{color:'#1a1c22'},ticks:{color:'#5a5f72',font:{size:9},maxRotation:45}},y:{grid:{color:'#1a1c22'},ticks:{color:'#5a5f72',font:{size:10}},beginAtZero:true}},plugins:{tooltip:{callbacks:{label:ctx=>` ${ctx.parsed.y} mi`}}}});
  }

  // Heatmap
  const grid=document.getElementById('heatmapGrid');
  grid.innerHTML='';
  d.heatmap.forEach(cell=>{
    const div=document.createElement('div');
    div.className=`hm-cell hm-${cell.level}`;
    div.title=cell.miles>0?`${cell.date}: ${cell.miles} km`:cell.date;
    grid.appendChild(div);
  });
  // month labels
  const mlEl=document.getElementById('hmMonthLabels');
  let lastMonth='';
  const months=[];
  d.heatmap.filter((_,i)=>i%7===0).forEach((cell,i)=>{
    const mo=cell.date.slice(0,7);
    if(mo!==lastMonth){months.push({label:new Date(cell.date+'T00:00').toLocaleDateString('en-US',{month:'short'}),i});lastMonth=mo;}
  });
  mlEl.innerHTML=months.map((m,idx)=>{
    const gap=idx===0?0:(m.i-(months[idx-1]?.i||0))*12;
    return `<span style="margin-left:${idx===0?0:gap-30}px">${m.label}</span>`;
  }).join('');
}

function showPR(key){
  _activePR=key;
  ['5k','10k','hm'].forEach(k=>{const btn=document.getElementById('pr'+k.replace('5k','5k').replace('10k','10k').replace('hm','Hm')+'Btn');if(btn){btn.style.color=k===key?'var(--orange)':'';btn.style.borderColor=k===key?'var(--orange)':'';}});
  if(!_prData)return;
  const pts=_prData[key]||[];
  if(pts.length===0){mk('prProgChart','line',[],[]);return;}
  mk('prProgChart','line',pts.map(p=>p.date),[{
    data:pts.map(p=>p.pace_sec),borderColor:'#f2495c',backgroundColor:'rgba(242,73,92,.08)',
    borderWidth:2,fill:true,tension:0.3,pointRadius:5,pointBackgroundColor:'#f2495c',pointHoverRadius:8
  }],{scales:{y:{reverse:true,grid:{color:'#1a1c22'},ticks:{color:'#5a5f72',font:{size:10},callback:v=>pFmt(v)}}},plugins:{tooltip:{callbacks:{label:ctx=>` PR: ${pFmt(ctx.parsed.y)}/km`}}}});
}

// ── AI Insights ─────────────────────────────────────────────────────────────
async function checkOllama(){
  try{
    const res=await fetch('/api/ollama/models');
    const data=await res.json();
    const el=document.getElementById('insightsPlaceholder');
    if(!el)return;
    if(data.available && data.models.length>0){
      el.innerHTML=`Ready · <span style="color:var(--orange)">Claude Haiku</span> · ~$0.0003 per analysis<br><span style="font-size:.65rem;opacity:.7">Click Generate insights to analyze your last 12 weeks of training</span>`;
      document.getElementById('insightBtn').disabled=false;
    } else {
      el.innerHTML=`Add <code style="color:var(--green);font-size:.7rem">ANTHROPIC_API_KEY=sk-ant-...</code> to your <code style="color:var(--green);font-size:.7rem">.env</code> file.<br><a href="https://console.anthropic.com" target="_blank" style="color:var(--blue)">Get a key at console.anthropic.com</a> · Claude Haiku costs ~$0.0003 per use<br><span style="font-size:.65rem;opacity:.7">Then restart the server</span>`;
      document.getElementById('insightBtn').disabled=true;
    }
  } catch(e){
    const el=document.getElementById('insightsPlaceholder');
    if(el) el.innerHTML='Could not check Ollama status.';
  }
}

async function loadInsights(){
  const btn=document.getElementById('insightBtn');
  btn.disabled=true; btn.textContent='Analyzing...';
  document.getElementById('insightsBody').innerHTML='<div class="insights-loading"><div class="spin"></div><div class="lmsg" id="insightProgress">Analyzing...</div></div>';
  let dots=0;
  const prog=setInterval(()=>{
    const el=document.getElementById('insightProgress');
    if(el){dots=(dots+1)%4; el.textContent='Analyzing your training data'+'.'.repeat(dots);}
  },600);
  try{
    const res=await fetch('/api/insights');
    clearInterval(prog);
    const data=await res.json();
    if(data.error){
      document.getElementById('insightsBody').innerHTML='<div style="padding:14px;color:var(--red);font-size:.75rem">'+data.error+'</div>';
      btn.disabled=false; btn.textContent='Generate insights';
      return;
    }
    const raw=data.insights||'';
    // Format: split on ** for bold, split on newlines for paragraphs
    const parts=raw.split('**');
    let html='';
    for(let i=0;i<parts.length;i++){
      html += i%2===1 ? '<strong>'+parts[i]+'</strong>' : parts[i].split('\n').join('<br>');
    }
    const modelTag=data.model ? '<span style="color:#5794f2">'+data.model+'</span>' : 'AI';
    document.getElementById('insightsBody').innerHTML='<div class="insights-box">'+html+'<div style="margin-top:12px;font-size:.62rem;color:#5a5f72">Based on '+data.weeks_analyzed+' weeks &middot; Powered by '+modelTag+'</div></div>';
    btn.textContent='Regenerate'; btn.disabled=false;
  } catch(e){
    clearInterval(prog);
    document.getElementById('insightsBody').innerHTML='<div style="padding:14px;color:#f2495c;font-size:.75rem">Error: '+e.message+'</div>';
    btn.disabled=false; btn.textContent='Generate insights';
  }
}


// ── Week popover ─────────────────────────────────────────────────────────────
function showWeekPopover(weekLabel, week, allData){
  // Remove any existing popover
  const existing=document.getElementById('weekPopover');
  if(existing)existing.remove();

  // Use pre-built run_details if available, otherwise fall back to recent lookup
  const runDetails = week.run_details || (week.run_ids||[]).map(id=>{
    const r=allData.recent.find(r=>r.id===id);
    return r || {id, name:'Run', miles:'?', pace:'—', date:'—'};
  });

  const pop=document.createElement('div');
  pop.id='weekPopover';
  pop.style.cssText='position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#1e2028;border:1px solid #2e3140;border-radius:4px;padding:16px;z-index:500;min-width:280px;max-width:400px;box-shadow:0 8px 32px rgba(0,0,0,.6)';

  // Header
  const hdr=document.createElement('div');
  hdr.style.cssText='display:flex;justify-content:space-between;align-items:center;margin-bottom:10px';
  hdr.innerHTML='<span style="font-family:Syne,sans-serif;font-weight:700;color:#d4d8e2;font-size:.85rem">Week of '+weekLabel+'</span>'
    +'<span style="font-size:.72rem;color:#73bf69">'+week.miles+' km · '+week.runs+' run'+(week.runs!==1?'s':'')+'</span>';
  pop.appendChild(hdr);

  // Run rows
  runDetails.forEach(r=>{
    const row=document.createElement('div');
    row.style.cssText='display:flex;justify-content:space-between;align-items:center;padding:8px;border-radius:2px;cursor:pointer;border-bottom:1px solid #252830';
    row.innerHTML='<span style="font-size:.78rem;color:#d4d8e2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px">'+r.name+'</span>'
      +'<span style="font-size:.75rem;color:#f5a623;margin-left:8px;white-space:nowrap">'+r.miles+' km &nbsp; '+r.pace+'/km</span>';
    row.addEventListener('mouseover',()=>{row.style.background='#252830';});
    row.addEventListener('mouseout',()=>{row.style.background='';});
    row.addEventListener('click',()=>{closePopover();openRun(r.id);});
    pop.appendChild(row);
  });

  // Footer
  const ftr=document.createElement('div');
  ftr.style.cssText='margin-top:10px;text-align:right';
  const closeBtn=document.createElement('button');
  closeBtn.textContent='close';
  closeBtn.style.cssText='background:none;border:1px solid #2e3140;color:#5a5f72;font-size:.68rem;padding:3px 10px;cursor:pointer;border-radius:2px;font-family:JetBrains Mono,monospace';
  closeBtn.addEventListener('click',closePopover);
  ftr.appendChild(closeBtn);
  pop.appendChild(ftr);

  const overlay=document.createElement('div');
  overlay.id='weekPopoverOverlay';
  overlay.style.cssText='position:fixed;inset:0;z-index:499;background:rgba(0,0,0,.4)';
  overlay.onclick=closePopover;

  document.body.appendChild(overlay);
  document.body.appendChild(pop);
}

function closePopover(){
  const p=document.getElementById('weekPopover');
  const o=document.getElementById('weekPopoverOverlay');
  if(p)p.remove();
  if(o)o.remove();
}

// ── Fuel Tab ─────────────────────────────────────────────────────────────────

let _fuelData = null;

async function loadFuel() {
  const content = document.getElementById('fuelContent');
  const loading = document.getElementById('fuelLoading');
  if (!content || !loading) return;

  loading.style.display = 'flex';
  content.style.display = 'none';

  try {
    const res = await fetch('/api/fuel/plan');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const d = await res.json();
    if (d.error) throw new Error(d.error);
    _fuelData = d;
    loading.style.display = 'none';
    content.style.display = 'block';
    renderFuel(d);
  } catch (e) {
    loading.style.display = 'none';
    content.innerHTML = `<div style="padding:20px;color:var(--red);font-size:.75rem">Error loading fuel plan: ${e.message}</div>`;
    content.style.display = 'block';
  }
}

function renderFuel(d) {
  renderFuelHeader(d);
  renderFuelCalendar(d.days);
  // Show today's detail by default
  const today = d.days.find(day => day.is_today);
  if (today) renderFuelDetail(today);
}

function renderFuelHeader(d) {
  // Weight display
  const weightEl = document.getElementById('fuelWeight');
  if (weightEl) weightEl.textContent = d.weight_lbs + ' kg';

  // Google Calendar status
  const gcEl = document.getElementById('fuelGCStatus');
  if (gcEl) {
    if (d.google_connected) {
      gcEl.innerHTML = '<span class="bk bkg">● Runna connected</span>';
    } else {
      gcEl.innerHTML = '<a href="/google/login" style="color:var(--orange);font-size:.68rem;text-decoration:none;border:1px solid var(--orange);padding:2px 8px;border-radius:2px">Connect Runna calendar</a>';
    }
  }

  // Today summary tiles
  const today = d.days.find(day => day.is_today);
  if (!today) return;
  const m = today.macros;
  const tiles = [
    { id: 'fuel-today-type',    val: today.timing.label,    cls: fuelTypeClass(today.day_type) },
    { id: 'fuel-today-cal',     val: m.calories + ' kcal',  cls: 'or' },
    { id: 'fuel-today-carbs',   val: m.carbs_g + 'g',       cls: 'bl' },
    { id: 'fuel-today-protein', val: m.protein_g + 'g',     cls: 'gr' },
    { id: 'fuel-today-fat',     val: m.fat_g + 'g',         cls: '' },
  ];
  tiles.forEach(t => {
    const el = document.getElementById(t.id);
    if (el) { el.textContent = t.val; el.className = 'tval sm ' + t.cls; }
  });
}

function fuelTypeClass(dayType) {
  return { rest: 'rd', easy: 'or', moderate: 'or', hard: 'gr', long: 'gr' }[dayType] || 'or';
}

function fuelColorStyle(color) {
  const map = {
    red:    'var(--red)',
    yellow: 'var(--yellow)',
    green:  'var(--green)',
  };
  return map[color] || 'var(--muted)';
}

function renderFuelCalendar(days) {
  const strip = document.getElementById('fuelStrip');
  if (!strip) return;
  strip.innerHTML = '';

  days.forEach(day => {
    const cell = document.createElement('div');
    cell.className = 'fuel-cell' + (day.is_today ? ' fuel-cell-today' : '') + (day.is_future ? ' fuel-cell-future' : '');
    cell.dataset.date = day.date;

    const dotColor = fuelColorStyle(day.color);
    const opacity  = day.is_past ? '0.55' : '1';

    // Show Peloton category label on rest days
    const cellTypeLabel = (day.day_type === 'rest' && day.peloton)
      ? day.peloton.category
      : day.day_type;
    const cellSubLabel = (day.day_type === 'rest' && day.peloton)
      ? '<div class="fuel-cell-pelo" style="opacity:' + opacity + '">🏋 pelo</div>'
      : '';

    cell.innerHTML = `
      <div class="fuel-cell-dow">${day.dow}</div>
      <div class="fuel-cell-date">${day.display_date}</div>
      <div class="fuel-cell-dot" style="background:${dotColor};opacity:${opacity}"></div>
      <div class="fuel-cell-type" style="color:${dotColor};opacity:${opacity}">${cellTypeLabel}</div>
      ${cellSubLabel}
      <div class="fuel-cell-cal" style="opacity:${opacity}">${day.macros.calories}</div>
    `;

    cell.addEventListener('click', () => {
      document.querySelectorAll('.fuel-cell').forEach(c => c.classList.remove('fuel-cell-active'));
      cell.classList.add('fuel-cell-active');
      renderFuelDetail(day);
    });

    if (day.is_today) cell.classList.add('fuel-cell-active');
    strip.appendChild(cell);
  });
}

function renderFuelDetail(day) {
  const panel = document.getElementById('fuelDetail');
  if (!panel) return;

  const m  = day.macros;
  const t  = day.timing;
  const dotColor = fuelColorStyle(day.color);

  const sourceLabel = {
    strava:    '● Strava',
    runna:     '◆ Runna',
    rest:      '○ Rest day',
    projected: '◈ Projected',
  }[day.source] || day.source;

  const sourceColor = {
    strava:    'var(--orange)',
    runna:     'var(--blue)',
    rest:      'var(--muted)',
    projected: 'var(--purple)',
  }[day.source] || 'var(--muted)';

  // Macro bar widths
  const total = m.carbs_g * 4 + m.protein_g * 4 + m.fat_g * 9;
  const carbW    = total > 0 ? Math.round((m.carbs_g * 4)   / total * 100) : 0;
  const proteinW = total > 0 ? Math.round((m.protein_g * 4) / total * 100) : 0;
  const fatW     = total > 0 ? Math.round((m.fat_g * 9)     / total * 100) : 0;

  panel.innerHTML = `
    <div class="fuel-detail-header">
      <div>
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
          <div style="font-family:var(--sans);font-size:1rem;font-weight:700;color:${dotColor}">${t.label}</div>
          <div style="font-size:.65rem;color:${sourceColor}">${sourceLabel}</div>
        </div>
        <div style="font-size:.7rem;color:var(--muted)">${day.display_date}${day.run_name ? ' · ' + day.run_name : ''}${day.run_miles > 0 ? ' · ' + day.run_miles + ' km' : ''}</div>
      </div>
      <div style="text-align:right">
        <div style="font-family:var(--sans);font-size:1.4rem;font-weight:700;color:var(--orange)">${m.calories}</div>
        <div style="font-size:.62rem;color:var(--muted)">kcal target</div>
      </div>
    </div>

    <div style="font-size:.68rem;color:var(--muted2);margin-bottom:10px;line-height:1.7">${t.summary}</div>

    <!-- Macro bars -->
    <div style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;font-size:.62rem;color:var(--muted);margin-bottom:4px">
        <span>Macros</span>
        <span>${m.carb_pct}% carbs · ${m.protein_pct}% protein · ${m.fat_pct}% fat</span>
      </div>
      <div style="display:flex;height:6px;border-radius:3px;overflow:hidden;gap:1px">
        <div style="width:${carbW}%;background:var(--blue)"></div>
        <div style="width:${proteinW}%;background:var(--green)"></div>
        <div style="width:${fatW}%;background:var(--orange)"></div>
      </div>
      <div class="fuel-macro-row">
        <div class="fuel-macro-cell">
          <div class="fuel-macro-label">Carbs</div>
          <div class="fuel-macro-val" style="color:var(--blue)">${m.carbs_g}g</div>
          <div class="fuel-macro-sub">${m.carb_pct}% · ${m.carbs_g * 4} kcal</div>
        </div>
        <div class="fuel-macro-cell">
          <div class="fuel-macro-label">Protein</div>
          <div class="fuel-macro-val" style="color:var(--green)">${m.protein_g}g</div>
          <div class="fuel-macro-sub">${m.protein_pct}% · ${m.protein_g * 4} kcal</div>
        </div>
        <div class="fuel-macro-cell">
          <div class="fuel-macro-label">Fat</div>
          <div class="fuel-macro-val" style="color:var(--orange)">${m.fat_g}g</div>
          <div class="fuel-macro-sub">${m.fat_pct}% · ${m.fat_g * 9} kcal</div>
        </div>
        <div class="fuel-macro-cell">
          <div class="fuel-macro-label">BMR</div>
          <div class="fuel-macro-val">${day.bmr}</div>
          <div class="fuel-macro-sub">base kcal</div>
        </div>
      </div>
    </div>

    <!-- Timing guidance -->
    ${t.pre || t.during || t.post ? `
    <div style="font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:6px">Timing</div>
    <div class="fuel-timing-grid">
      ${t.pre    ? `<div class="fuel-timing-cell"><div class="fuel-timing-label">PRE</div><div class="fuel-timing-text">${t.pre}</div></div>`    : ''}
      ${t.during ? `<div class="fuel-timing-cell"><div class="fuel-timing-label">DURING</div><div class="fuel-timing-text">${t.during}</div></div>` : ''}
      ${t.post   ? `<div class="fuel-timing-cell"><div class="fuel-timing-label">POST</div><div class="fuel-timing-text">${t.post}</div></div>`   : ''}
    </div>` : ''}

    <!-- Notes -->
    ${t.notes ? `
    <div style="margin-top:10px;background:var(--bg2);border:1px solid var(--border);border-radius:2px;padding:10px 12px">
      <div style="font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:4px">Coach note</div>
      <div style="font-size:.73rem;color:var(--muted2);line-height:1.8">${t.notes}</div>
    </div>` : ''}

    <!-- Peloton recommendation -->
    ${day.peloton && day.peloton.main ? `
    <div style="margin-top:10px;background:rgba(168,85,247,.06);border:1px solid rgba(168,85,247,.2);border-radius:2px;padding:10px 12px">
      <div style="font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;color:var(--purple);margin-bottom:6px">◆ Peloton Cross-Training</div>
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px">
        <div>
          <div style="font-size:.82rem;font-weight:600;color:var(--text);margin-bottom:1px">${day.peloton.main.title}</div>
          <div style="font-family:var(--mono);font-size:.62rem;color:var(--muted)">${day.peloton.main.instructor} · ${day.peloton.main.duration_min} min · ${day.peloton.category.toUpperCase()}</div>
        </div>
        ${day.peloton.main.url ? `<a href="${day.peloton.main.url}" target="_blank" style="font-family:var(--mono);font-size:.6rem;color:var(--purple);text-decoration:none;border:1px solid rgba(168,85,247,.3);padding:3px 8px;border-radius:2px;background:rgba(168,85,247,.08);white-space:nowrap;margin-left:8px">Open →</a>` : ''}
      </div>
      <div style="font-size:.68rem;color:var(--muted2);font-style:italic;margin-bottom:${day.peloton.core_addon ? '6px' : '0'}">${day.peloton.reason}</div>
      ${day.peloton.core_addon ? `
      <div style="margin-top:6px;padding:6px 8px;background:rgba(59,130,246,.07);border:1px solid rgba(59,130,246,.2);border-radius:2px">
        <div style="font-family:var(--mono);font-size:.55rem;text-transform:uppercase;letter-spacing:.08em;color:var(--blue);margin-bottom:2px">+ Core add-on</div>
        <div style="font-size:.72rem;color:var(--muted2)">${day.peloton.core_addon.title} · ${day.peloton.core_addon.instructor} · ${day.peloton.core_addon.duration_min} min</div>
        ${day.peloton.core_addon.url ? `<a href="${day.peloton.core_addon.url}" target="_blank" style="font-family:var(--mono);font-size:.58rem;color:var(--blue);text-decoration:none;border:1px solid rgba(59,130,246,.3);padding:2px 6px;border-radius:2px;background:rgba(59,130,246,.07);display:inline-block;margin-top:4px">Open →</a>` : ''}
      </div>` : ''}
    </div>` : ''}
  `;
}

// Weight update
async function updateWeight() {
  const input = document.getElementById('fuelWeightInput');
  if (!input) return;
  const val = parseFloat(input.value);
  if (!val || val < 100 || val > 400) {
    input.style.borderColor = 'var(--red)';
    return;
  }
  input.style.borderColor = 'var(--border2)';

  // Write to .env via new endpoint
  const res = await fetch('/api/fuel/weight', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ weight_lbs: val }),
  });
  if (res.ok) {
    document.getElementById('fuelWeight').textContent = val + ' kg';
    input.value = '';
    // Reload fuel plan with new weight
    window._fuelLoaded = false;
    loadFuel();
  }
}

// (fuel tab switching handled in main switchTab above)



// ── Train Tab ─────────────────────────────────────────────────────────────────

async function loadTrain() {
  const content = document.getElementById('trainContent');
  const loading = document.getElementById('trainLoading');
  if (!content || !loading) return;
  loading.style.display = 'flex';
  content.style.display = 'none';
  try {
    const res = await fetch('/api/training/week');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const d = await res.json();
    if (d.error) throw new Error(d.error);
    loading.style.display = 'none';
    content.style.display = 'block';
    renderTrain(d);
  } catch (e) {
    loading.style.display = 'none';
    content.innerHTML = '<div style="padding:20px;color:var(--red);font-size:.75rem">Error loading training plan: ' + e.message + '</div>';
    content.style.display = 'block';
  }
}

function renderTrain(d) {
  const cacheEl = document.getElementById('trainCacheStatus');
  if (cacheEl && d.cache_status) {
    const cs = d.cache_status;
    const ago = cs.refreshed_at ? new Date(cs.refreshed_at).toLocaleDateString('en-US', {month:'short',day:'numeric'}) : 'never';
    cacheEl.textContent = cs.class_count + ' classes cached · last refreshed ' + ago;
  }
  const gcEl = document.getElementById('trainGCStatus');
  if (gcEl) {
    gcEl.innerHTML = d.google_connected
      ? '<span class="bk bkg">◆ Runna connected</span>'
      : '<a href="/google/login" style="color:var(--orange);font-size:.68rem;text-decoration:none;border:1px solid var(--orange);padding:2px 8px;border-radius:2px">Connect Runna calendar</a>';
  }
  const grid = document.getElementById('trainWeekGrid');
  if (!grid) return;
  grid.innerHTML = '';
  d.week.forEach(function(day) { grid.appendChild(buildTrainDayCard(day)); });
}

function buildTrainDayCard(day) {
  const card = document.createElement('div');
  card.className = 'train-day' + (day.is_today ? ' today' : '');

  const dayTypeColor = {
    rest:'var(--muted)', easy:'var(--yellow)', moderate:'var(--yellow)',
    hard:'var(--green)', long:'var(--green)'
  }[day.day_type] || 'var(--muted)';

  const sourceColor = {
    strava:'var(--orange)', runna:'var(--blue)', rest:'var(--muted)'
  }[day.source] || 'var(--muted)';

  const todayBadge = day.is_today
    ? ' <span style="font-family:var(--mono);font-size:.55rem;color:var(--orange);border:1px solid rgba(252,76,2,.3);padding:1px 5px;border-radius:2px">today</span>'
    : '';

  let bodyHtml = '';

  if (day.day_type !== 'rest' || day.source === 'strava') {
    const badgeBg = {strava:'rgba(252,76,2,.12)',runna:'rgba(59,130,246,.12)',rest:'rgba(90,96,112,.1)'}[day.source] || 'rgba(90,96,112,.1)';
    bodyHtml += '<div class="train-run-badge" style="background:' + badgeBg + ';color:' + sourceColor + ';border:1px solid ' + sourceColor + '33">'
      + (day.source==='strava' ? '● Strava' : day.source==='runna' ? '◆ Runna' : '○ Rest')
      + '</div>'
      + '<div class="train-run-name">' + (day.run_name || day.timing.label) + '</div>'
      + '<div class="train-run-meta" style="color:' + dayTypeColor + '">'
      + day.day_type.toUpperCase() + (day.run_miles > 0 ? ' · ' + day.run_miles + ' km' : '')
      + '</div>';
  }

  const pelo = day.peloton;
  if (pelo) {
    const catColor = {
      push:'var(--orange)', pull:'var(--blue)', legs:'var(--yellow)',
      core:'var(--green)', stretch:'var(--purple)', runners:'var(--orange)'
    }[pelo.category] || 'var(--purple)';

    bodyHtml += '<hr class="train-pelo-divider">';
    bodyHtml += '<div class="train-pelo-label" style="color:' + catColor + '">' + pelo.category.toUpperCase() + '</div>';

    if (pelo.main) {
      bodyHtml += '<div class="train-pelo-title">' + pelo.main.title + '</div>'
        + '<div class="train-pelo-meta">' + pelo.main.instructor + ' · ' + pelo.main.duration_min + ' min</div>'
        + '<div class="train-pelo-reason">' + pelo.reason + '</div>'
        + (pelo.main.url
          ? '<a class="train-pelo-link" href="' + pelo.main.url + '" target="_blank">Open in Peloton →</a>'
          : '<span style="font-size:.6rem;color:var(--muted)">Search in Peloton app</span>');
    }

    if (pelo.core_addon) {
      bodyHtml += '<div class="train-core-addon">'
        + '<div class="train-core-label">+ Core</div>'
        + '<div class="train-core-title">' + pelo.core_addon.title + '</div>'
        + '<div class="train-pelo-meta">' + pelo.core_addon.instructor + ' · ' + pelo.core_addon.duration_min + ' min</div>'
        + (pelo.core_addon.url ? '<a class="train-pelo-link" href="' + pelo.core_addon.url + '" target="_blank" style="margin-top:4px;display:inline-block">Open →</a>' : '')
        + '</div>';
    }
  } else if (day.day_type === 'rest' && day.source === 'rest') {
    bodyHtml += '<div class="train-rest-label">Rest day</div>';
  }

  card.innerHTML = '<div class="train-day-header">'
    + '<div class="train-day-dow">' + day.dow + todayBadge + '</div>'
    + '<div class="train-day-date">' + day.display_date + '</div>'
    + '</div>'
    + '<div class="train-day-body">' + bodyHtml + '</div>';

  return card;
}

async function refreshPelotonCache() {
  const btn = document.getElementById('trainRefreshBtn');
  const status = document.getElementById('trainCacheStatus');
  btn.disabled = true; btn.textContent = '↺ Refreshing...';
  try {
    const res = await fetch('/api/peloton/refresh', { method: 'POST' });
    const d = await res.json();
    if (d.ok) {
      status.textContent = d.status.class_count + ' classes cached · refreshed just now';
      window._trainLoaded = false;
      loadTrain();
    }
  } catch(e) {
    status.textContent = 'Refresh failed: ' + e.message;
  }
  btn.disabled = false; btn.textContent = '↺ Refresh library';
}



// ── Meals Tab ─────────────────────────────────────────────────────────────────

let _mealsDB       = null;
let _mealsPlan     = 'standard_7day';
let _mealsDay      = null;
let _fuelDayType   = null;  // today's fuel day type from /api/fuel/plan

const DAY_TYPE_COLOR_MEALS = {
  rest: 'var(--red)', easy: 'var(--yellow)', moderate: 'var(--yellow)',
  hard: 'var(--green)', long: 'var(--green)'
};

async function loadMeals() {
  const content = document.getElementById('mealsContent');
  const loading = document.getElementById('mealsLoading');
  if (!content || !loading) return;
  loading.style.display = 'flex';
  content.style.display = 'none';

  try {
    // Load meals DB and today's fuel day type in parallel
    const [mealsRes, fuelRes] = await Promise.all([
      fetch('/api/meals'),
      fetch('/api/fuel/plan'),
    ]);
    if (!mealsRes.ok) throw new Error('Meals data not found — make sure meals.json is in your Stride folder');
    _mealsDB = await mealsRes.json();

    // Get today's day type from fuel plan
    if (fuelRes.ok) {
      const fd = await fuelRes.json();
      const today = fd.days && fd.days.find(d => d.is_today);
      if (today) _fuelDayType = today.day_type;
    }

    loading.style.display = 'none';
    content.style.display = 'block';
    renderMealsPlan(_mealsPlan);
  } catch(e) {
    loading.style.display = 'none';
    content.innerHTML = '<div style="padding:20px;color:var(--red);font-size:.75rem">' + e.message + '</div>';
    content.style.display = 'block';
  }
}

function onMealsPlanChange() {
  _mealsPlan = document.getElementById('mealsPlanSelect').value;
  _mealsDay  = null;
  renderMealsPlan(_mealsPlan);
}

function renderMealsPlan(planKey) {
  const plan = _mealsDB && _mealsDB.plans && _mealsDB.plans[planKey];
  if (!plan) return;

  // Update description
  const descEl = document.getElementById('mealsPlanDesc');
  if (descEl) descEl.textContent = plan.description || '';

  // Build day tabs
  const tabsEl = document.getElementById('mealsDayTabs');
  if (!tabsEl) return;
  tabsEl.innerHTML = '';

  if (plan.type === 'periodized') {
    // 7-day periodized — tabs are day types
    const dayTypes = Object.keys(plan.days);
    dayTypes.forEach(function(dt) {
      const tab = document.createElement('div');
      tab.className = 'meals-day-tab' + (dt === (_mealsDay || _fuelDayType || 'easy') ? ' active' : '');
      const color = DAY_TYPE_COLOR_MEALS[dt] || 'var(--muted)';
      tab.innerHTML = '<span class="dot" style="background:' + color + '"></span>' + plan.days[dt].label;
      tab.onclick = function() {
        document.querySelectorAll('.meals-day-tab').forEach(function(t) { t.classList.remove('active'); });
        tab.classList.add('active');
        _mealsDay = dt;
        renderMealDay(plan, dt);
      };
      tabsEl.appendChild(tab);
    });
    // Show today's day type by default
    const defaultDay = _mealsDay || _fuelDayType || 'easy';
    renderMealDay(plan, defaultDay);

  } else if (plan.type === 'calendar') {
    // 30-day — tabs are weeks, then days
    const weeks = [...new Set(plan.days.map(function(d) { return d.week; }))].sort();
    weeks.forEach(function(w) {
      const tab = document.createElement('div');
      tab.className = 'meals-day-tab' + (w === 1 ? ' active' : '');
      tab.textContent = 'Week ' + w;
      tab.onclick = function() {
        document.querySelectorAll('.meals-day-tab').forEach(function(t) { t.classList.remove('active'); });
        tab.classList.add('active');
        renderMealsWeek(plan, w);
      };
      tabsEl.appendChild(tab);
    });
    renderMealsWeek(plan, 1);

  } else if (plan.type === 'library') {
    // Paleo — tabs by meal type
    const mealTypes = [...new Set(plan.meals.map(function(m) { return m.type; }))];
    mealTypes.forEach(function(mt) {
      const tab = document.createElement('div');
      tab.className = 'meals-day-tab' + (mt === 'breakfast' ? ' active' : '');
      tab.textContent = mt.charAt(0).toUpperCase() + mt.slice(1);
      tab.onclick = function() {
        document.querySelectorAll('.meals-day-tab').forEach(function(t) { t.classList.remove('active'); });
        tab.classList.add('active');
        renderMealsLibrary(plan, mt);
      };
      tabsEl.appendChild(tab);
    });
    renderMealsLibrary(plan, 'breakfast');
  }
}

function renderMealDay(plan, dayType) {
  const day = plan.days[dayType];
  if (!day) return;
  showDaySummary(day.meals);
  renderMealCards(day.meals);
}

function renderMealsWeek(plan, weekNum) {
  const weekDays = plan.days.filter(function(d) { return d.week === weekNum; });
  // Build inner day tabs
  const tabsEl = document.getElementById('mealsDayTabs');
  // Keep week tabs, add day sub-tabs below
  // For simplicity, show first day's meals and let user pick day
  const existing = Array.from(tabsEl.children);
  // Remove any day sub-tabs
  existing.forEach(function(t) {
    if (t.dataset.dtype === 'day') t.remove();
  });

  // Show all meals for the week as a flat grid, grouped by day
  const cards = document.getElementById('mealCards');
  const summary = document.getElementById('mealsDaySummary');
  if (summary) summary.style.display = 'none';
  if (!cards) return;
  cards.innerHTML = '';

  weekDays.forEach(function(day) {
    if (!day.meals || day.meals.length === 0) return;
    // Day header
    const header = document.createElement('div');
    header.style.cssText = 'grid-column:1/-1;font-family:var(--sans);font-size:.85rem;font-weight:700;color:var(--orange);padding:6px 0 4px;border-bottom:1px solid var(--border);margin-bottom:2px';
    header.textContent = day.day;
    cards.appendChild(header);
    day.meals.forEach(function(meal) {
      cards.appendChild(buildMealCard(meal));
    });
  });
}

function renderMealsLibrary(plan, mealType) {
  const meals = plan.meals.filter(function(m) { return m.type === mealType; });
  showDaySummary(null);
  renderMealCards(meals);
}

function showDaySummary(meals) {
  const summary = document.getElementById('mealsDaySummary');
  if (!summary) return;
  if (!meals || meals.length === 0) { summary.style.display = 'none'; return; }

  const totals = meals.reduce(function(acc, m) {
    return {
      cal:     acc.cal     + (m.cal     || 0),
      protein: acc.protein + (m.protein || 0),
      carbs:   acc.carbs   + (m.carbs   || 0),
      fat:     acc.fat     + (m.fat     || 0),
    };
  }, {cal:0, protein:0, carbs:0, fat:0});

  document.getElementById('mds-cal').textContent     = totals.cal;
  document.getElementById('mds-carbs').textContent   = Math.round(totals.carbs) + 'g';
  document.getElementById('mds-protein').textContent = Math.round(totals.protein) + 'g';
  document.getElementById('mds-fat').textContent     = Math.round(totals.fat) + 'g';

  const typeEl = document.getElementById('mds-type');
  if (typeEl && _fuelDayType && _mealsPlan === 'standard_7day') {
    typeEl.textContent = _fuelDayType.toUpperCase() + ' DAY';
    typeEl.style.color = DAY_TYPE_COLOR_MEALS[_fuelDayType] || 'var(--muted)';
  } else if (typeEl) {
    typeEl.textContent = '';
  }
  summary.style.display = 'flex';
}

function renderMealCards(meals) {
  const cards = document.getElementById('mealCards');
  if (!cards) return;
  cards.innerHTML = '';
  meals.forEach(function(meal) {
    cards.appendChild(buildMealCard(meal));
  });
}

function buildMealCard(meal) {
  const card = document.createElement('div');
  card.className = 'meal-card-s';

  const typeLabel = meal.type || 'Meal';
  const macroHtml =
    '<span style="color:var(--blue)">' + (meal.carbs || meal.c || 0) + 'g C</span> ' +
    '<span style="color:var(--green)">' + (meal.protein || meal.p || 0) + 'g P</span> ' +
    '<span style="color:var(--orange)">' + (meal.fat || meal.f || 0) + 'g F</span> ' +
    '<span style="color:var(--muted2)">' + (meal.cal || 0) + ' cal</span>';

  const desc = meal.desc || meal.description || '';
  const tags = meal.tags || [];
  const ingredients = meal.ingredients || [];
  const steps = meal.steps || [];
  const hasDetail = ingredients.length > 0 || steps.length > 0;

  const tagsHtml = tags.map(function(t) {
    return '<span class="meal-tag">' + t + '</span>';
  }).join('');

  card.innerHTML =
    '<div class="meal-card-header">' +
      '<span class="meal-card-label">' + typeLabel + '</span>' +
      '<div class="meal-card-macros">' + macroHtml + '</div>' +
    '</div>' +
    '<div class="meal-card-body">' +
      '<div class="meal-card-name">' + meal.name + '</div>' +
      (desc ? '<div class="meal-card-desc">' + desc + '</div>' : '') +
      (tagsHtml ? '<div class="meal-card-tags">' + tagsHtml + '</div>' : '') +
      (hasDetail ? '<div class="meal-expand" id="expand-' + Math.random().toString(36).substr(2,6) + '" style="display:none">' +
        (ingredients.length ? '<div class="meal-expand-title">Ingredients</div><ul>' + ingredients.map(function(i){ return '<li>' + i + '</li>'; }).join('') + '</ul>' : '') +
        (steps.length ? '<div class="meal-expand-title" style="margin-top:8px">Steps</div><ol>' + steps.map(function(s){ return '<li>' + s + '</li>'; }).join('') + '</ol>' : '') +
      '</div>' : '') +
      (hasDetail ? '<div style="font-family:var(--mono);font-size:.58rem;color:var(--muted);margin-top:6px;cursor:pointer" onclick="toggleMealExpand(this)">▸ Show ingredients & steps</div>' : '') +
    '</div>';

  return card;
}

function toggleMealExpand(el) {
  const body = el.parentElement;
  const expand = body.querySelector('.meal-expand');
  if (!expand) return;
  const open = expand.style.display !== 'none';
  expand.style.display = open ? 'none' : 'block';
  el.textContent = open ? '▸ Show ingredients & steps' : '▾ Hide';
}


load();
