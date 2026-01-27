import React, { useState, useEffect } from 'react'
import { getTrackedMarkets, deleteTrackedMarket, getMarketSnapshots } from '../api/markets'
import { getMarketShifts } from '../api/alerts'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts'
import './Watchlist.css'

function Watchlist() {
  const [markets, setMarkets] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedMarket, setSelectedMarket] = useState(null)
  const [snapshots, setSnapshots] = useState([])
  const [shifts, setShifts] = useState([])

  useEffect(() => {
    loadMarkets()
    const interval = setInterval(loadMarkets, 30000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (selectedMarket) {
      loadMarketData(selectedMarket.id)
    }
  }, [selectedMarket])

  const loadMarkets = async () => {
    try {
      const data = await getTrackedMarkets()
      setMarkets(data)
      if (!selectedMarket && data.length > 0) {
        setSelectedMarket(data[0])
      }
    } catch (error) {
      console.error('Error loading markets:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadMarketData = async (marketId) => {
    try {
      const [snapshotsData, shiftsData] = await Promise.all([
        getMarketSnapshots(marketId, 24),
        getMarketShifts(marketId)
      ])
      setSnapshots(snapshotsData)
      setShifts(shiftsData)
    } catch (error) {
      console.error('Error loading market data:', error)
    }
  }

  const handleDeleteMarket = async (marketId) => {
    if (window.confirm('Remove this market from watchlist?')) {
      try {
        await deleteTrackedMarket(marketId)
        setMarkets(markets.filter(m => m.id !== marketId))
        if (selectedMarket?.id === marketId) {
          const remaining = markets.filter(m => m.id !== marketId)
          setSelectedMarket(remaining[0] || null)
          setSnapshots([])
          setShifts([])
        }
      } catch (error) {
        console.error('Error deleting market:', error)
      }
    }
  }

  const formatProbability = (prob) => {
    return `${(prob * 100).toFixed(1)}%`
  }

  const formatDelta = (delta) => {
    const sign = delta >= 0 ? '+' : ''
    return `${sign}${(delta * 100).toFixed(1)}%`
  }

  const formatVolume = (volume) => {
    if (!volume) return 'N/A'
    if (volume >= 1000000) return `$${(volume / 1000000).toFixed(2)}M`
    if (volume >= 1000) return `$${(volume / 1000).toFixed(2)}K`
    return `$${volume.toFixed(2)}`
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
        prob: snap.prob * 100,
        volume: snap.volume || 0
      })
    })
    
    const merged = []
    const outcomeIds = Object.keys(byOutcome)
    const maxLength = Math.max(...Object.values(byOutcome).map(arr => arr.length), 0)
    
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

  // Prepare shifts data for visualization
  const shiftsChartData = React.useMemo(() => {
    return shifts
      .slice(0, 20) // Top 20 shifts
      .map(shift => ({
        time: new Date(shift.ts).toLocaleTimeString(),
        impact: shift.volume_impact || 0,
        delta: shift.delta * 100,
        volume: shift.volume || 0
      }))
      .reverse()
  }, [shifts])

  if (loading) {
    return <div className="loading">Loading watchlist...</div>
  }

  return (
    <div className="watchlist">
      <h1>My Watchlist</h1>
      <p className="subtitle">Track your predictions and monitor significant shifts</p>

      {markets.length === 0 ? (
        <div className="empty-state">
          <h2>No markets in your watchlist</h2>
          <p>Go to Trending to add markets to track</p>
        </div>
      ) : (
        <div className="watchlist-content">
          <div className="markets-sidebar">
            <h2>Tracked Markets ({markets.length})</h2>
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
                  <div className="market-stats">
                    <span>{shifts.length} shifts detected</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="market-details-panel">
            {selectedMarket ? (
              <>
                <div className="market-header-section">
                  <h2>{selectedMarket.title}</h2>
                  <div className="market-meta">
                    <span>Added: {new Date(selectedMarket.created_at).toLocaleDateString()}</span>
                  </div>
                </div>

                {snapshots.length > 0 && (
                  <div className="chart-section">
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

                <div className="shifts-section">
                  <h3>Significant Shifts ({shifts.length})</h3>
                  <p className="section-description">
                    Shifts are quantified by volume impact (magnitude of change × volume traded)
                  </p>

                  {shifts.length > 0 ? (
                    <>
                      {shiftsChartData.length > 0 && (
                        <div className="shifts-chart">
                          <h4>Volume Impact Over Time</h4>
                          <ResponsiveContainer width="100%" height={200}>
                            <BarChart data={shiftsChartData}>
                              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
                              <XAxis dataKey="time" stroke="#888" />
                              <YAxis stroke="#888" />
                              <Tooltip
                                contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #2a2a2a' }}
                                formatter={(value, name) => {
                                  if (name === 'impact') return `$${value.toFixed(2)}`
                                  if (name === 'delta') return `${value.toFixed(1)}%`
                                  if (name === 'volume') return formatVolume(value)
                                  return value
                                }}
                              />
                              <Bar dataKey="impact" fill="#00d4ff" />
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      )}

                      <div className="shifts-list">
                        {shifts.map(shift => (
                          <div
                            key={shift.id}
                            className={`shift-card ${shift.delta > 0 ? 'positive' : 'negative'} ${shift.status === 'acknowledged' ? 'acknowledged' : ''}`}
                          >
                            <div className="shift-header">
                              <div className="shift-time">
                                {new Date(shift.ts).toLocaleString()}
                              </div>
                              <div className={`shift-status ${shift.status}`}>
                                {shift.status}
                              </div>
                            </div>
                            <div className="shift-details">
                              <div className="prob-change">
                                <span className="prev">{formatProbability(shift.prev_prob)}</span>
                                <span className="arrow">→</span>
                                <span className="new">{formatProbability(shift.new_prob)}</span>
                                <span className={`delta ${shift.delta > 0 ? 'positive' : 'negative'}`}>
                                  {formatDelta(shift.delta)}
                                </span>
                              </div>
                              <div className="shift-metrics">
                                <div className="metric">
                                  <span className="label">Volume:</span>
                                  <span className="value">{formatVolume(shift.volume)}</span>
                                </div>
                                <div className="metric">
                                  <span className="label">Impact:</span>
                                  <span className="value highlight">
                                    {formatVolume(shift.volume_impact)}
                                  </span>
                                </div>
                                <div className="metric">
                                  <span className="label">Change:</span>
                                  <span className={`value ${shift.delta > 0 ? 'positive' : 'negative'}`}>
                                    {formatDelta(shift.delta)} ({shift.delta_percent.toFixed(1)}%)
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <div className="empty-state-small">
                      No shifts detected yet. Shifts will appear here when significant probability changes occur.
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="empty-state">Select a market to view details</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default Watchlist
