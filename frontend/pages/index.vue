<template>
  <div class="wrap">
    <header>
      <h1>Gold Weekly Intelligence</h1>
      <div class="asof" v-if="bias">as of {{ bias.as_of }}</div>
    </header>

    <section class="card" id="overview">
      <h2>Weekly Overview</h2>
      <div class="hero">
        <div class="score" :class="scoreClass">
          <span class="label">{{ bias?.label || '…' }}</span>
          <span class="num">{{ bias?.score ?? '—' }}</span>
        </div>
        <ul class="meta">
          <li>Reliability: {{ pct(bias?.reliability) }}</li>
          <li>4-week regime: {{ structure?.regime_4w || 'n/a' }}</li>
          <li>Developing regime: {{ structure?.regime_developing || 'n/a' }}</li>
          <li>Expected range: {{ rangeText }}</li>
        </ul>
      </div>
      <div class="fresh">
        <span v-for="(f, k) in bias?.data_freshness || {}" :key="k"
              :class="['pill', f.status]">{{ k }}: {{ f.status }}</span>
      </div>
    </section>

    <section class="card" id="structure">
      <h2>Market Structure <small>(daily-bar approximation)</small></h2>
      <div class="grid3">
        <div class="stat"><span>POC</span><b>{{ f(structure?.developing_tpo?.poc) }}</b></div>
        <div class="stat"><span>VAH</span><b>{{ f(structure?.developing_tpo?.vah) }}</b></div>
        <div class="stat"><span>VAL</span><b>{{ f(structure?.developing_tpo?.val) }}</b></div>
      </div>
      <div class="grid3">
        <div class="stat"><span>VWAP</span><b>{{ f(structure?.anchored_vwap) }}</b></div>
        <div class="stat"><span>Open range</span><b>{{ orText }}</b></div>
        <div class="stat"><span>POC migration</span><b>{{ structure?.value_area_migration || 'n/a' }}</b></div>
      </div>
      <div id="price-chart" class="chart"></div>
    </section>

    <section class="card" id="options">
      <h2>Options</h2>
      <div class="grid3">
        <div class="stat"><span>ATM IV</span><b>{{ f(options?.latest?.atm_iv, '%') }}</b></div>
        <div class="stat"><span>25Δ RR</span><b>{{ f(options?.latest?.rr25, ' pts') }}</b></div>
        <div class="stat"><span>CME snapshot</span><b>{{ snapshotBadge }}</b></div>
      </div>
      <div id="oi-heatmap" class="chart"></div>
      <div id="rr-chart" class="chart"></div>
    </section>

    <section class="card" id="macro">
      <h2>Macro &amp; Positioning</h2>
      <div class="grid3">
        <div class="stat"><span>Real yield 10Y</span><b>{{ lastOf('DFII10') }}</b></div>
        <div class="stat"><span>10Y nominal</span><b>{{ lastOf('DGS10') }}</b></div>
        <div class="stat"><span>Broad USD</span><b>{{ lastOf('DTWEXBGS') }}</b></div>
      </div>
      <div id="yields-chart" class="chart"></div>
      <div id="cot-chart" class="chart"></div>
      <div class="grid3">
        <div class="stat"><span>ETF 5-session</span><b>{{ etfSum }}</b></div>
        <div class="stat" v-if="etfRows.length"><span>latest</span><b>{{ etfRows[etfRows.length - 1]?.series }} {{ f(etfRows[etfRows.length - 1]?.value, 't') }}</b></div>
        <div class="stat" v-if="!etfRows.length"><span>ETF flows</span><b>manual import</b></div>
      </div>
      <ul class="cal" v-if="calRows.length">
        <li v-for="c in calRows" :key="c.date + c.event">
          {{ c.date }} {{ c.event }} <em>({{ c.impact || 'n/a' }})</em>
        </li>
      </ul>
      <p class="hint" v-else>Calendar: no upcoming events imported (manual CSV import).</p>
    </section>

    <section class="card" id="report">
      <h2>Weekly Intelligence Report</h2>
      <pre class="report">{{ report || 'Loading…' }}</pre>
    </section>

    <footer>
      <button @click="refreshAll" :disabled="busy">{{ busy ? 'Refreshing…' : 'Refresh now' }}</button>
      <span v-if="refreshMsg" class="pill ok">{{ refreshMsg }}</span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

const bias = ref<any>(null)
const structure = ref<any>(null)
const options = ref<any>(null)
const macro = ref<any>(null)
const report = ref<string>('')
const busy = ref(false)
const refreshMsg = ref('')

const api = (p: string) => fetch(`/api${p}`).then(r => r.json())

const scoreClass = computed(() => {
  const s = bias.value?.score
  if (s == null || bias.value?.label?.startsWith('insufficient')) return 'none'
  if (s >= 20) return 'bull'
  if (s <= -20) return 'bear'
  return 'flat'
})

const rangeText = computed(() => {
  const lo = options.value?.latest?.expected_range_low
  const hi = options.value?.latest?.expected_range_high
  return lo && hi ? `${Math.round(lo)}–${Math.round(hi)}` : 'n/a'
})

const orText = computed(() => {
  const o = structure.value?.opening_range
  return o ? `${f(o.low)}–${f(o.high)}` : 'n/a'
})

const snapshotBadge = computed(() => {
  const s = options.value?.cme_snapshot
  if (!s) return 'none'
  return s.source === 'cme-mock' ? `MOCK ${s.snapshot_date}` : `real ${s.snapshot_date}`
})

function f(v: any, suffix = ''): string {
  return v == null ? 'n/a' : `${typeof v === 'number' ? Math.round(v * 100) / 100 : v}${suffix}`
}
function pct(v: any): string { return v == null ? '—' : `${Math.round(v * 100)}%` }
function lastOf(series: string): string {
  const rows = macro.value?.series?.[series]
  return rows?.length ? String(rows[rows.length - 1].value) : 'n/a'
}

const etfRows = computed<any[]>(() => macro.value?.etf_flows || [])
const calRows = computed<any[]>(() => macro.value?.calendar || [])
const etfSum = computed(() => {
  const rows = etfRows.value
  if (!rows.length) return 'n/a'
  const byDate: Record<string, number> = {}
  for (const r of rows) byDate[r.as_of] = (byDate[r.as_of] || 0) + Number(r.value || 0)
  const dates = Object.keys(byDate).sort()
  const sum = dates.slice(-5).reduce((a, d) => a + byDate[d], 0)
  return `${sum >= 0 ? '+' : ''}${Math.round(sum * 10) / 10}t`
})

declare const LightweightCharts: any
declare const echarts: any

function priceChart() {
  const el = document.getElementById('price-chart')
  if (!el || !window || !(window as any).LightweightCharts) return
  const chart = LightweightCharts.createChart(el, { height: 260, layout: { background: { color: '#111318' }, textColor: '#cdd3dd' } })
  const rows = (macro.value?.gc_bars || []).map((r: any) => ({
    time: r.date, open: r.open, high: r.high, low: r.low, close: r.close,
  }))
  if (rows.length) {
    const series = chart.addCandlestickSeries()
    series.setData(rows)
  }
}

function oiChart() {
  const el = document.getElementById('oi-heatmap')
  if (!el || !(window as any).echarts) return
  const oi = options.value?.oi_by_strike || []
  const chart = echarts.init(el)
  chart.setOption({
    grid: { left: 60, right: 20, top: 30, bottom: 40 },
    tooltip: {},
    xAxis: { type: 'category', data: oi.map((o: any) => o.strike), name: 'strike' },
    yAxis: { type: 'value', name: 'net OI' },
    series: [{ type: 'bar', data: oi.map((o: any) => (o.call_oi || 0) - (o.put_oi || 0)),
               itemStyle: { color: (p: any) => (p.value >= 0 ? '#c0392b' : '#27ae60') } }],
  })
}

function rrChart() {
  const el = document.getElementById('rr-chart')
  if (!el || !(window as any).echarts || !options.value?.history?.length) return
  const rows = options.value.history
  const chart = echarts.init(el)
  chart.setOption({
    legend: { top: 0, textStyle: { color: '#cdd3dd' } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: rows.map((r: any) => r.as_of) },
    yAxis: { type: 'value' },
    series: [
      { name: '25Δ RR', type: 'line', data: rows.map((r: any) => r.rr25) },
      { name: 'ATM IV', type: 'line', data: rows.map((r: any) => r.atm_iv) },
    ],
  })
}

function yieldsChart() {
  const el = document.getElementById('yields-chart')
  if (!el || !(window as any).echarts) return
  const s = macro.value?.series || {}
  const chart = echarts.init(el)
  const seriesNames: Array<[string, string]> = [['DFII10', 'Real 10Y'], ['DGS10', 'Nominal 10Y'], ['DTWEXBGS', 'Broad USD']]
  chart.setOption({
    legend: { top: 0, textStyle: { color: '#cdd3dd' } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: (s.DFII10 || []).map((r: any) => r.date) },
    yAxis: { type: 'value' },
    series: seriesNames.filter(([k]) => (s[k] || []).length)
      .map(([k, name]) => ({ name, type: 'line', data: s[k].map((r: any) => r.value) })),
  })
}

function cotChart() {
  const el = document.getElementById('cot-chart')
  if (!el || !(window as any).echarts || !macro.value?.cot?.length) return
  const rows = macro.value.cot
  const chart = echarts.init(el)
  chart.setOption({
    legend: { top: 0, textStyle: { color: '#cdd3dd' } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: rows.map((r: any) => r.as_of) },
    yAxis: { type: 'value', name: 'contracts' },
    series: [
      { name: 'MM long', type: 'bar', data: rows.map((r: any) => r.mm_long) },
      { name: 'MM short', type: 'bar', data: rows.map((r: any) => -r.mm_short) },
    ],
  })
}

function drawAll() {
  nextTick(() => { priceChart(); oiChart(); rrChart(); yieldsChart(); cotChart() })
}

async function load() {
  const [b, st, opt, mac, rep] = await Promise.all([
    api('/bias'),
    api('/structure').catch(() => null),
    api('/options'),
    api('/macro'),
    fetch('/api/report/weekly').then(r => r.text()),
  ])
  bias.value = b; structure.value = st; options.value = opt; macro.value = mac; report.value = rep
  drawAll()
}

async function refreshAll() {
  busy.value = true
  try {
    const r = await fetch('/api/refresh', { method: 'POST' })
    const j = await r.json()
    refreshMsg.value = Object.entries(j)
      .filter(([k]) => k !== 'all_failed')
      .map(([k, v]) => `${k}:${(v as any).status}`).join(' ')
    await load()
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: #0b0d12; color: #e6e9ef;
       font-family: -apple-system, 'Segoe UI', Roboto, 'Noto Sans Thai', sans-serif; }
.wrap { max-width: 960px; margin: 0 auto; padding: 12px; }
header { display: flex; justify-content: space-between; align-items: baseline; }
h1 { font-size: 1.25rem; }
h2 { font-size: 1.05rem; margin: 0 0 10px; }
h2 small { color: #8b93a1; font-weight: 400; }
.asof { color: #8b93a1; font-size: .8rem; }
.card { background: #111318; border: 1px solid #1e222b; border-radius: 12px;
        padding: 14px; margin: 12px 0; }
.hero { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.score { display: flex; flex-direction: column; padding: 10px 18px; border-radius: 12px;
         background: #1a1e26; }
.score .num { font-size: 2rem; font-weight: 700; }
.score.bull { outline: 2px solid #27ae60; } .score.bear { outline: 2px solid #c0392b; }
.score.flat { outline: 2px solid #7f8c8d; } .score.none { outline: 2px dashed #7f8c8d; }
.meta { list-style: none; padding: 0; margin: 0; color: #aab2c0; font-size: .85rem; }
.grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 8px 0; }
.stat { background: #161a21; border-radius: 8px; padding: 8px; display: flex;
        flex-direction: column; }
.stat span { color: #8b93a1; font-size: .72rem; text-transform: uppercase; }
.stat b { font-size: 1.05rem; }
.fresh { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.pill { font-size: .7rem; padding: 2px 8px; border-radius: 999px; background: #1a1e26; }
.pill.ok { color: #7dcea0; } .pill.stale { color: #f4d03f; } .pill.missing, .pill.failed { color: #ec7063; }
.cal { list-style: none; margin: 8px 0 0; padding: 0; font-size: .85rem; }
.cal li { padding: 3px 0; border-bottom: 1px dashed #1a1e26; }
.cal em { color: #f4d03f; font-style: normal; font-size: .75rem; }
.hint { color: #8a93a5; font-size: .8rem; }
.chart { height: 260px; margin-top: 10px; }
.report { white-space: pre-wrap; font-family: ui-monospace, monospace; font-size: .8rem;
          line-height: 1.5; }
footer { display: flex; gap: 10px; align-items: center; padding: 12px 0 30px; }
button { background: #1f6feb; color: white; border: 0; border-radius: 8px;
         padding: 8px 16px; font-size: .9rem; }
button:disabled { opacity: .5; }
@media (max-width: 640px) {
  .grid3 { grid-template-columns: repeat(2, 1fr); }
  .chart { height: 220px; }
}
</style>
