import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import './ProbabilityChart.css'

function ProbabilityChart({ data, outcomes, range = '24h', priceHistory }) {
  // Build chart from price history (like Polymarket: price = probability). Primary source when available.
  const chartDataFromPriceHistory = React.useMemo(() => {
    if (!priceHistory || priceHistory.length === 0) return []
    const byTime = {}
    priceHistory.forEach(point => {
      const ts = point.timestamp
      if (ts == null) return
      const t = typeof ts === 'number' ? (ts < 1e12 ? ts * 1000 : ts) : new Date(ts).getTime()
      const date = new Date(t)
      const timeKey = date.getTime()
      const timeLabel = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' })
      if (!byTime[timeKey]) {
        byTime[timeKey] = { time: timeLabel, timestamp: timeKey }
      }
      const price = point.close ?? point.price ?? 0
      const name = point.outcome_name || `Outcome ${point.outcome_id || ''}`
      byTime[timeKey][name] = Math.min(100, Math.max(0, Number(price) * 100))
    })
    return Object.values(byTime)
      .sort((a, b) => a.timestamp - b.timestamp)
      .map(item => {
        const { timestamp, ...rest } = item
        return rest
      })
  }, [priceHistory])

  // Fallback: transform snapshot data for Recharts
  const chartDataFromSnapshots = React.useMemo(() => {
    if (!data || data.length === 0 || !outcomes || outcomes.length === 0) return []
    const byTime = {}
    data.forEach(point => {
      const timestamp = point.ts || point.timestamp
      if (!timestamp) return
      const date = new Date(timestamp)
      const timeKey = date.toISOString()
      const timeLabel = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' })
      if (!byTime[timeKey]) {
        byTime[timeKey] = { time: timeLabel, timestamp: date.getTime() }
      }
      const outcome = outcomes.find(o => {
        const oId = o.id || o.outcome_id
        const pId = point.polymarket_outcome_id ?? point.outcome_id
        return String(oId) === String(pId)
      })
      if (outcome) {
        const outcomeName = outcome.name || outcome.title || `Outcome ${outcome.id || outcome.outcome_id}`
        byTime[timeKey][outcomeName] = (point.prob || 0) * 100
      }
    })
    return Object.values(byTime)
      .sort((a, b) => a.timestamp - b.timestamp)
      .map(item => {
        const { timestamp, ...rest } = item
        return rest
      })
  }, [data, outcomes])

  const chartData = chartDataFromPriceHistory.length > 0 ? chartDataFromPriceHistory : chartDataFromSnapshots
  const seriesKeys = chartData.length > 0 ? Object.keys(chartData[0]).filter(k => k !== 'time') : []
  const colors = ['#1e88e5', '#43a047', '#e53935', '#ff9800', '#9c27b0', '#00bcd4']

  if (chartData.length === 0) {
    return (
      <div className="probability-chart">
        <div className="chart-header">
          <h3>Probability / Price Trends ({range})</h3>
        </div>
        <div className="chart-empty">No price history available for this period.</div>
      </div>
    )
  }

  return (
    <div className="probability-chart">
      <div className="chart-header">
        <h3>Probability / Price Trends ({range})</h3>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey="time"
            stroke="#6c757d"
            style={{ fontSize: '12px' }}
            interval="preserveStartEnd"
          />
          <YAxis
            stroke="#6c757d"
            domain={[0, 100]}
            tickFormatter={(v) => `${v}%`}
            style={{ fontSize: '12px' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e1e1e',
              border: '1px solid #333',
              borderRadius: '8px',
              color: '#fff'
            }}
            formatter={(value) => [`${Number(value).toFixed(1)}%`, '']}
            labelFormatter={(label) => label}
          />
          <Legend />
          {seriesKeys.map((key, idx) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={colors[idx % colors.length]}
              strokeWidth={2}
              dot={false}
              name={key}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default ProbabilityChart
