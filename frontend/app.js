/* ═══════════════════════════════════════════════
   MRUDA Intelligence Surface — Application Logic
   ═══════════════════════════════════════════════ */

const API = '';  // Same origin

// ── State ──
const state = {
  currentInsight: null,
  previousInsight: null,
  intelligence: null,  // AI-generated intelligence layer
  lastSyncTime: null,
  isSyncing: false,
  heroIndex: 0,
  heroInterval: null,
};

// ── Currency Symbols ──
const CURRENCY_SYMBOLS = {
  INR: '₹', USD: '$', EUR: '€', GBP: '£', JPY: '¥',
  AUD: 'A$', CAD: 'C$', SGD: 'S$', AED: 'د.إ',
};

function currencySymbol(code) {
  return CURRENCY_SYMBOLS[code] || code + ' ';
}

// ═══════════════════════════════════════════════
// API Layer
// ═══════════════════════════════════════════════

async function fetchLatestInsight() {
  try {
    const res = await fetch(`${API}/insights/latest`);
    const data = await res.json();
    if (data.status === 'success' && data.insight) return data.insight;
    return null;
  } catch (e) {
    console.error('Failed to fetch insight:', e);
    return null;
  }
}

async function fetchIntelligence() {
  try {
    const res = await fetch(`${API}/generate-intelligence`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (data.status === 'success' || data.status === 'partial') return data;
    return null;
  } catch (e) {
    console.error('Failed to fetch intelligence:', e);
    return null;
  }
}

async function triggerSync() {
  const res = await fetch(`${API}/run-analysis`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date_range: 'last_7d', force: true }),
  });
  return await res.json();
}

async function askMRUDA(question) {
  const payload = { question: question };
  const res = await fetch(`${API}/generate-summary`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  return data.summary || data.detail || 'No response.';
}

// ═══════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════

function relativeTime(isoString) {
  const then = new Date(isoString);
  const now = new Date();
  const mins = Math.floor((now - then) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function formatNumber(val, decimals = 2) {
  if (val === 0) return '0';
  if (Math.abs(val) >= 1000) return val.toLocaleString('en-IN', { maximumFractionDigits: decimals });
  return val.toFixed(decimals);
}

function getKPI(kpis, name) {
  const k = kpis.find(k => k.name === name);
  return k ? k.value : null;
}

function getTrend(trends, metricName) {
  return trends.find(t => t.metric_name === metricName) || null;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ═══════════════════════════════════════════════
// LAYER 1 — Intelligence Header
// ═══════════════════════════════════════════════

function renderHeader(insight) {
  const syncText = document.getElementById('sync-text');
  const syncDot = document.getElementById('sync-dot');
  const dataWindowText = document.getElementById('data-window-text');
  const confidenceValue = document.getElementById('confidence-value');
  const confidenceTooltip = document.getElementById('confidence-tooltip');

  const timeAgo = relativeTime(insight.generated_at);
  const confidence = insight.confidence_score;
  const dataStability = confidence >= 0.8 ? 'Data stable' : 'Data building';
  syncText.textContent = `Synced ${timeAgo} · ${dataStability}`;

  syncDot.className = 'intel-header__dot';
  if (confidence < 0.6) syncDot.classList.add('intel-header__dot--risk');
  else if (confidence < 0.8) syncDot.classList.add('intel-header__dot--building');

  const formatDate = (d) => {
    const parts = d.split('-');
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${months[parseInt(parts[1]) - 1]} ${parseInt(parts[2])}`;
  };
  dataWindowText.textContent = `${formatDate(insight.date_range_start)} – ${formatDate(insight.date_range_end)}`;

  confidenceValue.textContent = `Confidence: ${Math.round(confidence * 100)}%`;
  const bd = insight.confidence_breakdown;
  confidenceTooltip.innerHTML =
    `Data Completeness: ${Math.round(bd.data_completeness * 100)}%<br>` +
    `Metric Coverage: ${Math.round(bd.metric_coverage * 100)}%<br>` +
    `Sample Size: ${Math.round(bd.sample_size_factor * 100)}%<br>` +
    `Volume Stability: ${Math.round(bd.volume_stability * 100)}%`;
}

// ═══════════════════════════════════════════════
// LAYER 2 — One Sentence Truth (AI-Driven Rotation)
// ═══════════════════════════════════════════════

function renderHeroTruth(insight, intelligence) {
  const sentence = document.getElementById('hero-sentence');
  const chips = document.getElementById('hero-chips');
  const basis = document.getElementById('hero-basis');

  const kpis = insight.kpis;
  const roas = insight.meta_summary.roas_context;
  const trends = insight.trend_signals;
  const engagement = getKPI(kpis, 'engagement_rate');
  const allInsufficient = trends.every(t => !t.previous_period_available);
  const summary = insight.meta_summary;

  // AI-driven hero lines with rotation
  if (intelligence && intelligence.hero_lines && intelligence.hero_lines.length > 0) {
    state.heroIndex = 0;
    sentence.textContent = intelligence.hero_lines[0];
    sentence.style.opacity = '1';

    // Clear previous interval
    if (state.heroInterval) clearInterval(state.heroInterval);

    // Rotate every 6 seconds with fade
    if (intelligence.hero_lines.length > 1) {
      state.heroInterval = setInterval(() => {
        sentence.style.opacity = '0';
        setTimeout(() => {
          state.heroIndex = (state.heroIndex + 1) % intelligence.hero_lines.length;
          sentence.textContent = intelligence.hero_lines[state.heroIndex];
          sentence.style.opacity = '1';
        }, 400);
      }, 6000);
    }
  } else {
    // Fallback static
    sentence.textContent = 'Performance data available. Review the signals below.';
  }

  // Chips
  chips.innerHTML = '';
  if (engagement && engagement > 10) {
    chips.innerHTML += `<span class="chip chip--strong">🟢 Engagement Strong</span>`;
  } else if (engagement && engagement > 5) {
    chips.innerHTML += `<span class="chip chip--watch">🟡 Engagement Moderate</span>`;
  }

  if (roas && !roas.applicable) {
    const reasonLabels = {
      'lead_generation_campaign': 'Lead Gen Objective',
      'awareness_objective': 'Awareness Objective',
      'no_conversion_value_tracked': 'No Conversion Tracking',
    };
    chips.innerHTML += `<span class="chip chip--watch">🟡 ${reasonLabels[roas.reason] || 'Attribution Incomplete'}</span>`;
  }

  if (allInsufficient) {
    chips.innerHTML += `<span class="chip chip--building">⚪ Baseline Building</span>`;
  } else {
    const positiveCount = trends.filter(t => t.signal === 'improving').length;
    if (positiveCount > trends.length / 2) {
      chips.innerHTML += `<span class="chip chip--strong">🟢 Momentum Positive</span>`;
    }
  }

  basis.textContent = `Based on ${summary.total_impressions.toLocaleString('en-IN')} impressions and ${summary.total_clicks.toLocaleString('en-IN')} clicks.`;
}

// ═══════════════════════════════════════════════
// LAYER 3 — Delta Strip
// ═══════════════════════════════════════════════

function renderDeltaStrip(insight) {
  const strip = document.getElementById('delta-strip');
  const cs = currencySymbol(insight.currency);
  const kpis = insight.kpis;
  const trends = insight.trend_signals;

  const metrics = [
    { key: 'ctr', label: 'CTR', format: v => `${formatNumber(v)}%` },
    { key: 'cpc', label: 'CPC', format: v => `${cs}${formatNumber(v)}` },
    { key: 'engagement_rate', label: 'Engagement', format: v => `${formatNumber(v)}%` },
    { key: 'spend', label: 'Spend', format: v => `${cs}${formatNumber(v, 0)}`, trendKey: 'spend' },
  ];

  strip.innerHTML = '';
  metrics.forEach(m => {
    const kpiVal = getKPI(kpis, m.key);
    const trend = getTrend(trends, m.trendKey || m.key);
    const value = kpiVal !== null ? m.format(kpiVal) : '—';

    let changeHTML = '';
    if (!trend || !trend.previous_period_available) {
      changeHTML = `<span class="delta-item__change delta-item__change--building">Baseline building</span>`;
    } else if (trend.direction === 'up') {
      changeHTML = `<span class="delta-item__change delta-item__change--up">▲ +${formatNumber(trend.change_pct)}%</span>`;
    } else if (trend.direction === 'down') {
      changeHTML = `<span class="delta-item__change delta-item__change--down">▼ ${formatNumber(trend.change_pct)}%</span>`;
    } else {
      changeHTML = `<span class="delta-item__change delta-item__change--flat">▬ Stable</span>`;
    }

    strip.innerHTML += `
      <div class="delta-item">
        <div class="delta-item__label">${m.label}</div>
        <div class="delta-item__value">${value}</div>
        ${changeHTML}
      </div>
    `;
  });
}

// ═══════════════════════════════════════════════
// LAYER 4 — Signal Grid (AI-Driven Cards)
// ═══════════════════════════════════════════════

function renderSignalGrid(insight, intelligence) {
  const grid = document.getElementById('signal-grid');
  const cs = currencySymbol(insight.currency);
  const kpis = insight.kpis;
  const trends = insight.trend_signals;
  const roas = insight.meta_summary.roas_context;
  const allInsufficient = trends.every(t => !t.previous_period_available);

  const ctr = getKPI(kpis, 'ctr');
  const engagement = getKPI(kpis, 'engagement_rate');
  const videoCompletion = getKPI(kpis, 'video_completion_rate');
  const cpc = getKPI(kpis, 'cpc');
  const cpm = getKPI(kpis, 'cpm');

  const ci = intelligence ? intelligence.card_insights : {};

  // Card configs
  const cards = [
    {
      key: 'creative_resonance',
      title: 'Creative Resonance',
      status: (ctr && ctr > 2 || engagement && engagement > 10) ? 'Strong' : (ctr && ctr >= 1 ? 'Moderate' : 'Building'),
      statusClass: (ctr && ctr > 2 || engagement && engagement > 10) ? 'strong' : (ctr && ctr >= 1 ? 'watch' : 'building'),
      metrics: [
        { name: 'CTR', value: ctr !== null ? `${formatNumber(ctr)}%` : '—' },
        { name: 'Engagement', value: engagement !== null ? `${formatNumber(engagement)}%` : '—' },
        { name: 'Video Completion', value: videoCompletion !== null ? `${formatNumber(videoCompletion)}%` : '—' },
      ],
      fallbackInsight: 'Audience response is strong.',
    },
    {
      key: 'cost_efficiency',
      title: 'Cost Efficiency',
      status: (() => {
        const t = getTrend(trends, 'cpc');
        if (!t || !t.previous_period_available) return 'Building';
        if (t.signal === 'alert') return 'Watch';
        return 'Healthy';
      })(),
      statusClass: (() => {
        const t = getTrend(trends, 'cpc');
        if (!t || !t.previous_period_available) return 'building';
        if (t.signal === 'alert') return 'watch';
        return 'strong';
      })(),
      metrics: [
        { name: 'CPC', value: cpc !== null ? `${cs}${formatNumber(cpc)}` : '—' },
        { name: 'CPM', value: cpm !== null ? `${cs}${formatNumber(cpm)}` : '—' },
      ],
      fallbackInsight: 'Trend analysis activates after next sync.',
    },
    {
      key: 'conversion_alignment',
      title: 'Conversion Alignment',
      status: roas && !roas.applicable ? 'Not Applicable' : 'Building',
      statusClass: roas && !roas.applicable ? 'watch' : 'building',
      metrics: [
        { name: 'ROAS', value: roas && !roas.applicable ? 'N/A' : (getKPI(kpis, 'roas') !== null ? formatNumber(getKPI(kpis, 'roas')) : '—') },
        { name: 'Conversions', value: insight.meta_summary.total_conversions.toLocaleString('en-IN') },
      ],
      fallbackInsight: roas && !roas.applicable ? 'This campaign optimizes for leads. Revenue attribution is not enabled.' : 'Awaiting conversion data.',
    },
    {
      key: 'growth_momentum',
      title: 'Growth Momentum',
      status: allInsufficient ? 'Building' : 'Active',
      statusClass: allInsufficient ? 'building' : 'strong',
      metrics: [],
      fallbackInsight: allInsufficient ? 'Trend intelligence building.' : 'Performance momentum active.',
    },
  ];

  grid.innerHTML = cards.map(card => {
    const aiInsight = ci[card.key];
    const oneLiner = aiInsight ? aiInsight.one_liner : card.fallbackInsight;
    const deepAnalysis = aiInsight ? aiInsight.deep_analysis : '';
    const hasDeepAnalysis = deepAnalysis && deepAnalysis.length > 20;

    let metricsHTML = '';
    if (card.metrics.length > 0) {
      metricsHTML = `<div class="signal-card__metrics">
        ${card.metrics.map(m => `
          <div class="signal-card__metric">
            <span class="signal-card__metric-name">${m.name}</span>
            <span class="signal-card__metric-value">${m.value}</span>
          </div>
        `).join('')}
      </div>`;
    }

    return `
      <div class="signal-card ${hasDeepAnalysis ? 'signal-card--expandable' : ''}"
           ${hasDeepAnalysis ? `onclick="openCardModal('${escapeHtml(card.title)}', this)"` : ''}
           ${hasDeepAnalysis ? `data-analysis="${escapeHtml(deepAnalysis)}"` : ''}>
        <div class="signal-card__header">
          <span class="signal-card__title">${card.title}</span>
          <span class="signal-card__status signal-card__status--${card.statusClass}">${card.status}</span>
        </div>
        ${metricsHTML}
        <p class="signal-card__insight">${oneLiner}</p>
        ${hasDeepAnalysis ? '<span class="signal-card__expand-hint">Click to expand analysis →</span>' : ''}
      </div>
    `;
  }).join('');
}

// ═══════════════════════════════════════════════
// Card Modal
// ═══════════════════════════════════════════════

function openCardModal(title, cardEl) {
  const analysis = cardEl.dataset.analysis;
  if (!analysis) return;

  // Create modal
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

  const formatted = formatDeepAnalysis(analysis);

  overlay.innerHTML = `
    <div class="modal-card">
      <div class="modal-card__header">
        <h2 class="modal-card__title">${title}</h2>
        <button class="modal-card__close" onclick="this.closest('.modal-overlay').remove()">✕</button>
      </div>
      <div class="modal-card__body">${formatted}</div>
    </div>
  `;

  document.body.appendChild(overlay);
}

function formatDeepAnalysis(text) {
  return text
    .replace(/### (.*)/g, '<h3>$1</h3>')
    .replace(/## (.*)/g, '<h2>$1</h2>')
    .replace(/# (.*)/g, '<h1>$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^\- (.*)/gm, '<li>$1</li>')
    .replace(/^\d+\. (.*)/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

// ═══════════════════════════════════════════════
// LAYER 5 — Strategic Moves (AI-Driven)
// ═══════════════════════════════════════════════

function renderStrategicMoves(insight, intelligence) {
  const list = document.getElementById('moves-list');

  // Use AI-generated moves if available
  if (intelligence && intelligence.strategic_moves && intelligence.strategic_moves.length > 0) {
    list.innerHTML = intelligence.strategic_moves.slice(0, 3).map((m, i) => `
      <div class="move-card">
        <div class="move-card__number">${i + 1}</div>
        <div class="move-card__content">
          <div class="move-card__title">${escapeHtml(m.title)}</div>
          <div class="move-card__reasoning">${escapeHtml(m.reasoning)}</div>
          ${m.action_items && m.action_items.length > 0 ? `
            <ul class="move-card__actions">
              ${m.action_items.map(a => `<li>${escapeHtml(a)}</li>`).join('')}
            </ul>
          ` : ''}
        </div>
        <span class="move-card__confidence move-card__confidence--${m.confidence.toLowerCase()}">${m.confidence}</span>
      </div>
    `).join('');
    return;
  }

  // Fallback: static recommendations
  const cs = currencySymbol(insight.currency);
  const kpis = insight.kpis;
  const ctr = getKPI(kpis, 'ctr');
  const cpc = getKPI(kpis, 'cpc');
  const engagement = getKPI(kpis, 'engagement_rate');
  const videoCompletion = getKPI(kpis, 'video_completion_rate');
  const roas = insight.meta_summary.roas_context;

  const moves = [];
  if (ctr && ctr > 2 && cpc) {
    moves.push({ title: 'Scale Budget Gradually', reasoning: `Creative efficiency supports expansion.`, confidence: 'High' });
  }
  if (engagement && engagement > 10 && videoCompletion && videoCompletion > 15) {
    moves.push({ title: 'Launch Retargeting Audience', reasoning: 'Build pool from video viewers.', confidence: 'High' });
  }
  if (videoCompletion && videoCompletion < 30) {
    moves.push({ title: 'Improve Video Opening', reasoning: `Completion at ${formatNumber(videoCompletion)}%.`, confidence: 'Medium' });
  }
  if (roas && !roas.applicable) {
    moves.push({ title: 'Enable Conversion Tracking', reasoning: 'Measure true campaign impact.', confidence: 'High' });
  }

  const topMoves = moves.slice(0, 3);
  if (topMoves.length === 0) {
    list.innerHTML = `<p style="color: var(--text-tertiary); font-size: 0.88rem;">No specific recommendations at this time.</p>`;
    return;
  }
  list.innerHTML = topMoves.map((m, i) => `
    <div class="move-card">
      <div class="move-card__number">${i + 1}</div>
      <div class="move-card__content">
        <div class="move-card__title">${m.title}</div>
        <div class="move-card__reasoning">${m.reasoning}</div>
      </div>
      <span class="move-card__confidence move-card__confidence--${m.confidence.toLowerCase()}">${m.confidence}</span>
    </div>
  `).join('');
}

// ═══════════════════════════════════════════════
// LAYER 6 — Conversation
// ═══════════════════════════════════════════════

function initConversation() {
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send');
  const suggestions = document.querySelectorAll('.conversation__suggestion');

  sendBtn.addEventListener('click', () => sendMessage());
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendMessage(); });

  suggestions.forEach(btn => {
    btn.addEventListener('click', () => {
      input.value = btn.dataset.q;
      sendMessage();
    });
  });
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const messages = document.getElementById('chat-messages');
  const question = input.value.trim();
  if (!question) return;

  messages.innerHTML += `
    <div class="message message--user">
      <div class="message__text">${escapeHtml(question)}</div>
    </div>
  `;
  input.value = '';

  const loadingId = 'loading-' + Date.now();
  messages.innerHTML += `
    <div class="message message--loading" id="${loadingId}">
      <span class="loading-text">Analyzing<span class="loading-dots"></span></span>
    </div>
  `;
  messages.scrollTop = messages.scrollHeight;

  try {
    const response = await askMRUDA(question);
    const loadingEl = document.getElementById(loadingId);
    if (loadingEl) loadingEl.remove();

    const formattedResponse = formatDeepAnalysis(response);
    const signalContext = buildSignalContext();

    messages.innerHTML += `
      <div class="message message--ai">
        <div class="message__text">${formattedResponse}</div>
        <button class="message__signals-toggle" onclick="toggleSignals(this)">
          ▸ Supporting signals
        </button>
        <div class="message__signals">${signalContext}</div>
      </div>
    `;
  } catch (e) {
    const loadingEl = document.getElementById(loadingId);
    if (loadingEl) loadingEl.remove();
    messages.innerHTML += `
      <div class="message message--ai">
        <div class="message__text">Unable to generate response. Please try again.</div>
      </div>
    `;
  }
  messages.scrollTop = messages.scrollHeight;
}

function toggleSignals(btn) {
  const signalsEl = btn.nextElementSibling;
  signalsEl.classList.toggle('expanded');
  btn.textContent = signalsEl.classList.contains('expanded') ? '▾ Hide signals' : '▸ Supporting signals';
}

function buildSignalContext() {
  if (!state.currentInsight) return 'No signal data available.';
  const i = state.currentInsight;
  const cs = currencySymbol(i.currency);
  let ctx = `<strong>Snapshot:</strong> ${i.date_range_start} to ${i.date_range_end}<br>`;
  ctx += `Currency: ${i.currency} | Confidence: ${Math.round(i.confidence_score * 100)}%<br>`;
  ctx += `Spend: ${cs}${formatNumber(i.meta_summary.total_spend)} | `;
  ctx += `Impressions: ${i.meta_summary.total_impressions.toLocaleString('en-IN')} | `;
  ctx += `Clicks: ${i.meta_summary.total_clicks.toLocaleString('en-IN')}<br>`;
  if (i.meta_summary.roas_context && !i.meta_summary.roas_context.applicable) {
    ctx += `ROAS: Not applicable (${i.meta_summary.roas_context.reason.replace(/_/g, ' ')})`;
  }
  return ctx;
}

// ═══════════════════════════════════════════════
// Sync Controls
// ═══════════════════════════════════════════════

function initSyncControls() {
  const syncBtn = document.getElementById('sync-btn');
  const emptySyncBtn = document.getElementById('empty-sync-btn');
  syncBtn.addEventListener('click', handleSync);
  if (emptySyncBtn) emptySyncBtn.addEventListener('click', handleSync);
}

async function handleSync() {
  if (state.isSyncing) return;
  state.isSyncing = true;

  const syncBtn = document.getElementById('sync-btn');
  const syncText = document.getElementById('sync-text');
  syncBtn.disabled = true;
  syncBtn.classList.add('syncing');
  syncBtn.textContent = '↻ Analyzing…';
  syncText.textContent = 'Analyzing…';

  try {
    await triggerSync();
    state.lastSyncTime = new Date().toISOString();
    await loadAndRender();
    syncBtn.textContent = '↻ Sync';
  } catch (e) {
    console.error('Sync failed:', e);
    syncBtn.textContent = '↻ Retry';
  } finally {
    state.isSyncing = false;
    syncBtn.disabled = false;
    syncBtn.classList.remove('syncing');
  }
}

// ═══════════════════════════════════════════════
// Intelligence Loading State
// ═══════════════════════════════════════════════

function showIntelligenceLoading() {
  // Show shimmer on hero
  const sentence = document.getElementById('hero-sentence');
  sentence.innerHTML = '<span class="shimmer-text">Generating intelligence…</span>';

  // Show shimmer on cards
  const cards = document.querySelectorAll('.signal-card__insight');
  cards.forEach(c => { c.innerHTML = '<span class="shimmer-text">Thinking…</span>'; });
}

// ═══════════════════════════════════════════════
// Master Render
// ═══════════════════════════════════════════════

async function loadAndRender() {
  const insight = await fetchLatestInsight();
  const emptyState = document.getElementById('empty-state');
  const intelLayers = document.getElementById('intel-layers');

  if (!insight) {
    emptyState.style.display = 'block';
    intelLayers.style.display = 'none';
    return;
  }

  // Store state
  state.previousInsight = state.currentInsight;
  state.currentInsight = insight;

  emptyState.style.display = 'none';
  intelLayers.style.display = 'block';

  // Render structural layers immediately (data-driven, instant)
  renderHeader(insight);
  renderHeroTruth(insight, null);  // Fallback until AI loads
  renderDeltaStrip(insight);
  renderSignalGrid(insight, null);  // Fallback
  renderStrategicMoves(insight, null);  // Fallback

  // Fetch AI intelligence in background (takes a few seconds)
  showIntelligenceLoading();
  const intelligence = await fetchIntelligence();

  if (intelligence) {
    state.intelligence = intelligence;
    // Re-render AI-powered layers
    renderHeroTruth(insight, intelligence);
    renderSignalGrid(insight, intelligence);
    renderStrategicMoves(insight, intelligence);
  }
}

// ═══════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
  initSyncControls();
  initConversation();
  await loadAndRender();
});
