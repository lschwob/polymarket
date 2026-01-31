import React from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import './VolumeChart.css'

function VolumeChart({ data }) {
  const chartData = React.useMemo(() => {
    if (!data || !Array.isArray(data)) return []
    
    return data.map(item => ({
      name: item.outcome_name || `Outcome ${item.outcome_id}`,
      volume: item.volume || 0
    }))
  }, [data])
  
  return (
    <div className="volume-chart">
      <div className="chart-header">
        <h3>Volume by Outcome</h3>
      </div>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis 
            dataKey="name" 
            stroke="#6c757d"
            style={{ fontSize: '12px' }}
            angle={-45}
            textAnchor="end"
            height={80}
          />
          <YAxis 
            stroke="#6c757d"
            style={{ fontSize: '12px' }}
          />
          <Tooltip
            contentStyle={{ 
              backgroundColor: '#ffffff', 
              border: '1px solid #e0e0e0',
              borderRadius: '6px'
            }}
            formatter={(value) => `$${value.toLocaleString()}`}
          />
          <Bar dataKey="volume" fill="#1e88e5" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default VolumeChart
