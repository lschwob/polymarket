import React, { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { getMarketDetail, getMarketTrades, getMarketOrderBook, getMarketPriceHistory, getMarketVolumeChart, getMarketSnapshots } from '../api/markets'
import OutcomeCard from '../components/OutcomeCard'
import ProbabilityChart from '../components/ProbabilityChart'
import VolumeChart from '../components/VolumeChart'
import OrderBookTable from '../components/OrderBookTable'
import TradeHistoryList from '../components/TradeHistoryList'
import WebSocketIndicator from '../components/WebSocketIndicator'
import useWebSocket from '../hooks/useWebSocket'
import './MarketDetailPage.css'

function MarketDetailPage() {
  const { marketId } = useParams()
  const navigate = useNavigate()
  const [market, setMarket] = useState(null)
  const [outcomes, setOutcomes] = useState([])
  const [trades, setTrades] = useState([])
  const [orderBooks, setOrderBooks] = useState([])
  const [priceHistory, setPriceHistory] = useState([])
  const [volumeChart, setVolumeChart] = useState([])
  const [snapshots, setSnapshots] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedOutcome, setSelectedOutcome] = useState(null)
  const [timeRange, setTimeRange] = useState('24h')
  const [priceInterval, setPriceInterval] = useState('1m')

  // WebSocket connection
  const handleWebSocketMessage = (data) => {
    if (data.type === 'market_update') {
      if (data.data.outcomes) {
        setOutcomes(data.data.outcomes)
      }
      if (data.data.recent_trades) {
        setTrades(prev => {
          const newTrades = [...data.data.recent_trades, ...prev]
          return newTrades.slice(0, 50)
        })
      }
    }
  }

  const { connected, reconnecting } = useWebSocket(parseInt(marketId), handleWebSocketMessage)

  useEffect(() => {
    loadMarketData()
    const interval = setInterval(loadMarketData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [marketId, timeRange, priceInterval])

  const loadMarketData = async () => {
    try {
      setLoading(true)
      const [detail, tradesData, orderBookData, priceHistoryData, volumeChartData, snapshotsData] = await Promise.all([
        getMarketDetail(marketId),
        getMarketTrades(marketId, 50),
        getMarketOrderBook(marketId),
        getMarketPriceHistory(marketId, priceInterval, parseInt(timeRange)),
        getMarketVolumeChart(marketId, parseInt(timeRange)),
        getMarketSnapshots(marketId, parseInt(timeRange))
      ])

      // Merge market data with additional info
      const marketWithDetails = {
        ...detail.market,
        description: detail.description,
        image: detail.image,
        end_date: detail.end_date,
        volume_24h: detail.volume_24h,
        liquidity: detail.liquidity
      }
      setMarket(marketWithDetails)
      setOutcomes(detail.outcomes || [])
      setTrades(tradesData || [])
      setOrderBooks(orderBookData.order_books || [])
      setPriceHistory(priceHistoryData.data || [])
      setVolumeChart(volumeChartData.data || [])
      setSnapshots(snapshotsData || [])

      if (detail.outcomes?.length > 0 && !selectedOutcome) {
        setSelectedOutcome(detail.outcomes[0].id)
      }
    } catch (error) {
      console.error('Error loading market data:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatVolume = (volume) => {
    if (!volume) return '$0'
    if (volume >= 1000000) return `$${(volume / 1000000).toFixed(2)}M`
    if (volume >= 1000) return `$${(volume / 1000).toFixed(2)}K`
    return `$${volume.toFixed(2)}`
  }

  if (loading && !market) {
    return <div className="loading">Loading market details...</div>
  }

  if (!market) {
    return (
      <div className="empty-state">
        <h2>Market not found</h2>
        <Link to="/watchlist">Back to Watchlist</Link>
      </div>
    )
  }

  return (
    <div className="market-detail-page">
      <div className="page-header">
        <button onClick={() => navigate('/watchlist')} className="back-btn">
          ← Back to Watchlist
        </button>
        <div className="header-right">
          <WebSocketIndicator connected={connected} reconnecting={reconnecting} />
        </div>
      </div>

      <div className="market-header-section">
        <h1>{market.title}</h1>
        {market.description && (
          <div className="market-description">
            <p>{market.description}</p>
          </div>
        )}
        <div className="market-meta">
          <span>Category: {market.tag_slug || 'N/A'}</span>
          <span>•</span>
          <span>Volume 24h: {formatVolume(market.volume_24h)}</span>
          <span>•</span>
          <span>Liquidity: {formatVolume(market.liquidity)}</span>
          {market.end_date && (
            <>
              <span>•</span>
              <span>Ends: {new Date(market.end_date).toLocaleDateString()}</span>
            </>
          )}
        </div>
      </div>

      <div className="outcomes-section">
        <h2>Outcomes</h2>
        {outcomes.length > 0 ? (
          <div className="outcomes-grid">
            {outcomes.map((outcome) => (
              <OutcomeCard
                key={outcome.id || outcome.outcome_id}
                outcome={outcome}
                selected={selectedOutcome === (outcome.id || outcome.outcome_id)}
                onClick={() => setSelectedOutcome(outcome.id || outcome.outcome_id)}
              />
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <p>No outcomes available for this market</p>
          </div>
        )}
      </div>

      <div className="charts-section">
        <div className="chart-controls">
          <div className="control-group">
            <label>Time Range:</label>
            <select value={timeRange} onChange={(e) => setTimeRange(e.target.value)}>
              <option value="1h">1 Hour</option>
              <option value="24h">24 Hours</option>
              <option value="7d">7 Days</option>
              <option value="30d">30 Days</option>
            </select>
          </div>
          <div className="control-group">
            <label>Interval:</label>
            <select value={priceInterval} onChange={(e) => setPriceInterval(e.target.value)}>
              <option value="1m">1 Minute</option>
              <option value="5m">5 Minutes</option>
              <option value="1h">1 Hour</option>
              <option value="1d">1 Day</option>
            </select>
          </div>
        </div>

        {snapshots.length > 0 && outcomes.length > 0 ? (
          <div className="chart-row">
            <div className="chart-container">
              <ProbabilityChart 
                data={snapshots} 
                outcomes={outcomes}
                range={timeRange}
              />
            </div>
          </div>
        ) : (
          <div className="empty-state">
            <p>No probability data available yet. Data will appear as the market is tracked.</p>
          </div>
        )}

        {volumeChart.length > 0 ? (
          <div className="chart-row">
            <div className="chart-container">
              <VolumeChart data={volumeChart} />
            </div>
          </div>
        ) : (
          <div className="empty-state">
            <p>No volume data available yet.</p>
          </div>
        )}
      </div>

      <div className="trading-section">
        <div className="trading-grid">
          <div className="order-book-section">
            <h2>Order Books</h2>
            {orderBooks.length > 0 ? (
              orderBooks.map((orderBook, idx) => (
                <OrderBookTable key={idx} orderBook={orderBook} />
              ))
            ) : (
              <div className="empty-state">No order book data available</div>
            )}
          </div>

          <div className="trades-section">
            <h2>Trade History</h2>
            <TradeHistoryList trades={trades} limit={50} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default MarketDetailPage
