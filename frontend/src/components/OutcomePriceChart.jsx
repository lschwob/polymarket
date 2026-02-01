import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import './OutcomePriceChart.css'

function OutcomePriceChart({ data, outcomeName, range = '24h' }) {
  const chartData = React.useMemo(() => {
    if (!data || !Array.isArray(data)) return []
    return data.map((point) => ({
      time: point.timestamp
        ? new Date(point.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        : '',
      timestamp: point.timestamp,
      price: point.close ?? point.price ?? 0,
      open: point.open,
      high: point.high,
      low: point.low,
    }))
  }, [data])

  return (
    <div className="outcome-price-chart">
      <div className="chart-header">
        <h3>Price History – {outcomeName || 'Outcome'} ({range})</h3>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey="time"
            stroke="#6c757d"
            style={{ fontSize: '12px' }}
          />
          <YAxis
            stroke="#6c757d"
            domain={['auto', 'auto']}
            tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            style={{ fontSize: '12px' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#ffffff',
              border: '1px solid #e0e0e0',
              borderRadius: '6px',
            }}
            formatter={(value) => [`${(value * 100).toFixed(2)}%`, 'Price']}
            labelFormatter={(label) => label}
          />
          <Line
            type="monotone"
            dataKey="price"
            stroke="#1e88e5"
            strokeWidth={2}
            dot={false}
            name="Price"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default OutcomePriceChart
