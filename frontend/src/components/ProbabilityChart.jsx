import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import './ProbabilityChart.css'

function ProbabilityChart({ data, outcomes, range = '24h' }) {
  // Transform data for Recharts
  const chartData = React.useMemo(() => {
    if (!data || data.length === 0 || !outcomes || outcomes.length === 0) {
      return []
    }
    
    // Group by timestamp
    const byTime = {}
    
    data.forEach(point => {
      const timestamp = point.ts || point.timestamp
      if (!timestamp) return
      
      const date = new Date(timestamp)
      const timeKey = date.toISOString()
      const timeLabel = date.toLocaleTimeString()
      
      if (!byTime[timeKey]) {
        byTime[timeKey] = { time: timeLabel, timestamp: date.getTime() }
      }
      
      // Find matching outcome
      const outcome = outcomes.find(o => {
        const oId = o.id || o.outcome_id
        const pId = point.outcome_id
        return String(oId) === String(pId)
      })
      
      if (outcome) {
        const outcomeName = outcome.name || outcome.title || `Outcome ${outcome.id || outcome.outcome_id}`
        const prob = point.prob || 0
        byTime[timeKey][outcomeName] = prob * 100
      }
    })
    
    // Sort by timestamp
    return Object.values(byTime)
      .sort((a, b) => a.timestamp - b.timestamp)
      .map(item => {
        const { timestamp, ...rest } = item
        return rest
      })
  }, [data, outcomes])
  
  const colors = ['#1e88e5', '#43a047', '#e53935', '#ff9800', '#9c27b0', '#00bcd4']
  
  return (
    <div className="probability-chart">
      <div className="chart-header">
        <h3>Probability Trends ({range})</h3>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis 
            dataKey="time" 
            stroke="#6c757d"
            style={{ fontSize: '12px' }}
          />
          <YAxis 
            stroke="#6c757d"
            domain={[0, 100]}
            style={{ fontSize: '12px' }}
          />
          <Tooltip
            contentStyle={{ 
              backgroundColor: '#ffffff', 
              border: '1px solid #e0e0e0',
              borderRadius: '6px'
            }}
            formatter={(value) => `${value.toFixed(1)}%`}
          />
          <Legend />
          {outcomes?.map((outcome, idx) => {
            const outcomeName = outcome.name || outcome.title || `Outcome ${outcome.id}`
            return (
              <Line
                key={outcome.id || outcome.outcome_id}
                type="monotone"
                dataKey={outcomeName}
                stroke={colors[idx % colors.length]}
                strokeWidth={2}
                dot={false}
                name={outcomeName}
              />
            )
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default ProbabilityChart
