import React, { useState, useEffect } from 'react'
import { getTrackedMarkets, deleteTrackedMarket, getMarketSnapshots } from '../api/markets'
import { getAlerts, acknowledgeAlert } from '../api/alerts'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import './Dashboard.css'

function Dashboard() {
  const [markets, setMarkets] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedMarket, setSelectedMarket] = useState(null)
  const [snapshots, setSnapshots] = useState([])

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (selectedMarket) {
      loadSnapshots(selectedMarket.id)
    }
  }, [selectedMarket])

  const loadData = async () => {
    try {
      const [marketsData, alertsData] = await Promise.all([
        getTrackedMarkets(),
        getAlerts()
      ])
      setMarkets(marketsData)
      setAlerts(alertsData)
    } catch (error) {
      console.error('Error loading data:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadSnapshots = async (marketId) => {
    try {
      const data = await getMarketSnapshots(marketId, 24)
      setSnapshots(data)
    } catch (error) {
      console.error('Error loading snapshots:', error)
    }
  }

  const handleDeleteMarket = async (marketId) => {
    if (window.confirm('Remove this market from tracking?')) {
      try {
        await deleteTrackedMarket(marketId)
        setMarkets(markets.filter(m => m.id !== marketId))
        if (selectedMarket?.id === marketId) {
          setSelectedMarket(null)
          setSnapshots([])
        }
      } catch (error) {
        console.error('Error deleting market:', error)
      }
    }
  }

  const handleAcknowledgeAlert = async (alertId) => {
    try {
      await acknowledgeAlert(alertId)
      setAlerts(alerts.filter(a => a.id !== alertId))
    } catch (error) {
      console.error('Error acknowledging alert:', error)
    }
  }

  const formatProbability = (prob) => {
    return `${(prob * 100).toFixed(1)}%`
  }

  const formatDelta = (delta) => {
    const sign = delta >= 0 ? '+' : ''
    return `${sign}${(delta * 100).toFixed(1)}%`
  }

  // Group snapshots by outcome for chart
  const chartData = React.useMemo(() => {
    if (!snapshots.length) return []
    
    const byOutcome = {}
    snapshots.forEach(snap => {
      if (!byOutcome[snap.outcome_id]) {
        byOutcome[snap.outcome_id] = []
      }
      byOutcome[snap.outcome_id].push({
        time: new Date(snap.ts).toLocaleTimeString(),
        prob: snap.prob * 100
      })
    })
    
    // Merge into single array
    const merged = []
    const outcomeIds = Object.keys(byOutcome)
    const maxLength = Math.max(...Object.values(byOutcome).map(arr => arr.length))
    
    for (let i = 0; i < maxLength; i++) {
      const point = {}
      outcomeIds.forEach(oid => {
        if (byOutcome[oid][i]) {
          point[`outcome_${oid}`] = byOutcome[oid][i].prob
          point.time = byOutcome[oid][i].time
        }
      })
      if (Object.keys(point).length > 1) {
        merged.push(point)
      }
    }
    
    return merged
  }, [snapshots])

  if (loading) {
    return <div className="loading">Loading dashboard...</div>
  }

  return (
    <div className="dashboard">
      <h1>Dashboard</h1>

      <div className="dashboard-grid">
        <div className="markets-section">
          <h2>Tracked Markets ({markets.length})</h2>
          {markets.length === 0 ? (
            <div className="empty-state">
              No markets tracked. Go to Trending to add markets.
            </div>
          ) : (
            <div className="markets-list">
              {markets.map(market => (
                <div
                  key={market.id}
                  className={`market-card ${selectedMarket?.id === market.id ? 'selected' : ''}`}
                  onClick={() => setSelectedMarket(market)}
                >
                  <div className="market-header">
                    <h3>{market.title}</h3>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteMarket(market.id)
                      }}
                      className="delete-btn"
                    >
                      ×
                    </button>
                  </div>
                  <p className="market-slug">{market.market_slug}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="details-section">
          {selectedMarket ? (
            <div className="market-details">
              <h2>{selectedMarket.title}</h2>
              {snapshots.length > 0 && (
                <div className="chart-container">
                  <h3>Probability Trends (24h)</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                      <XAxis dataKey="time" stroke="#888" />
                      <YAxis stroke="#888" domain={[0, 100]} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #2a2a2a' }}
                        formatter={(value) => `${value.toFixed(1)}%`}
                      />
                      <Legend />
                      {Object.keys(chartData[0] || {}).filter(k => k !== 'time').map((key, idx) => (
                        <Line
                          key={key}
                          type="monotone"
                          dataKey={key}
                          stroke={['#00d4ff', '#ff6b6b', '#4ecdc4', '#ffe66d'][idx % 4]}
                          strokeWidth={2}
                          dot={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          ) : (
            <div className="empty-state">Select a market to view details</div>
          )}
        </div>
      </div>

      <div className="alerts-section">
        <h2>Alerts ({alerts.length})</h2>
        {alerts.length === 0 ? (
          <div className="empty-state">No active alerts</div>
        ) : (
          <div className="alerts-list">
            {alerts.map(alert => (
              <div key={alert.id} className={`alert-card ${alert.delta > 0 ? 'positive' : 'negative'}`}>
                <div className="alert-content">
                  <h4>{alert.market_title || `Market ${alert.market_id}`}</h4>
                  <div className="alert-details">
                    <span>Previous: {formatProbability(alert.prev_prob)}</span>
                    <span>→</span>
                    <span>Current: {formatProbability(alert.new_prob)}</span>
                    <span className={`delta ${alert.delta > 0 ? 'positive' : 'negative'}`}>
                      {formatDelta(alert.delta)}
                    </span>
                  </div>
                  {alert.volume && (
                    <div className="alert-volume">
                      Volume: {alert.volume.toLocaleString()} | Impact: {alert.volume_impact ? alert.volume_impact.toLocaleString() : 'N/A'}
                    </div>
                  )}
                  <div className="alert-time">
                    {new Date(alert.ts).toLocaleString()}
                  </div>
                </div>
                <button
                  onClick={() => handleAcknowledgeAlert(alert.id)}
                  className="ack-btn"
                >
                  Acknowledge
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default Dashboard
