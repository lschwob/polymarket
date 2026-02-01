import React, { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts'
import { getOutcomePriceHistory } from '../api/markets'
import OutcomePriceChart from './OutcomePriceChart'
import './OutcomeCard.css'

function OutcomeCard({
  outcome,
  onClick,
  selected,
  orderBook,
  priceHistory,
  change24h,
  marketId,
}) {
  const prob = outcome.prob ?? outcome.price ?? 0
  const probPercent = (prob * 100).toFixed(1)
  const [expandedOrderBook, setExpandedOrderBook] = useState(false)
  const [showChartModal, setShowChartModal] = useState(false)
  const [chartData, setChartData] = useState([])

  const trend = change24h != null ? (change24h > 0 ? 'up' : change24h < 0 ? 'down' : null) : null

  const sparklineData = React.useMemo(() => {
    if (!priceHistory || !Array.isArray(priceHistory)) return []
    return priceHistory.map((p) => ({
      price: p.close ?? p.price ?? 0,
      time: p.timestamp,
    })).slice(-24)
  }, [priceHistory])

  useEffect(() => {
    if (!showChartModal || !marketId || !outcome?.id) return
    let cancelled = false
    getOutcomePriceHistory(marketId, outcome.id, 24).then((res) => {
      if (!cancelled && res?.data) setChartData(res.data)
    })
    return () => { cancelled = true }
  }, [showChartModal, marketId, outcome?.id])

  const bids = (orderBook?.bids || []).slice(0, 5).sort((a, b) => (b.price ?? 0) - (a.price ?? 0))
  const asks = (orderBook?.asks || []).slice(0, 5).sort((a, b) => (a.price ?? 0) - (b.price ?? 0))

  const handleCardClick = (e) => {
    if (e.target.closest('.outcome-card-actions') || e.target.closest('.outcome-order-book')) return
    onClick?.()
  }

  return (
    <>
      <div
        className={`outcome-card ${selected ? 'selected' : ''}`}
        onClick={handleCardClick}
      >
        <div className="outcome-header">
          <h4 className="outcome-name">{outcome.name || outcome.title || 'Unknown'}</h4>
          <div className="outcome-prob">
            {probPercent}%
          </div>
        </div>
        <div className="outcome-price">
          ${prob.toFixed(3)}
          {change24h != null && (
            <span className={`outcome-change24h ${trend || ''}`}>
              {trend === 'up' && '+'}{change24h.toFixed(1)}%
            </span>
          )}
        </div>
        {trend && (
          <div className={`outcome-trend ${trend}`}>
            {trend === 'up' ? '↑' : '↓'}
          </div>
        )}
        {sparklineData.length > 0 && (
          <div className="outcome-sparkline">
            <ResponsiveContainer width="100%" height={36}>
              <LineChart data={sparklineData}>
                <XAxis dataKey="time" hide />
                <YAxis hide domain={['dataMin', 'dataMax']} />
                <Tooltip content={() => null} />
                <Line
                  type="monotone"
                  dataKey="price"
                  stroke="var(--accent-blue)"
                  strokeWidth={1}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        <div className="outcome-card-actions">
          {marketId && outcome?.id && (
            <button
              type="button"
              className="outcome-btn-chart"
              onClick={(e) => { e.stopPropagation(); setShowChartModal(true) }}
            >
              View price chart
            </button>
          )}
          {(bids.length > 0 || asks.length > 0) && (
            <button
              type="button"
              className="outcome-btn-orderbook"
              onClick={(e) => { e.stopPropagation(); setExpandedOrderBook((v) => !v) }}
            >
              {expandedOrderBook ? 'Hide' : 'Show'} order book
            </button>
          )}
        </div>
        {expandedOrderBook && (bids.length > 0 || asks.length > 0) && (
          <div className="outcome-order-book" onClick={(e) => e.stopPropagation()}>
            <div className="ob-side">
              <div className="ob-header">Bids</div>
              {bids.map((b, i) => (
                <div key={i} className="ob-row">
                  <span className="ob-price">{b.price?.toFixed(3) ?? '—'}</span>
                  <span className="ob-size">{b.size?.toFixed(0) ?? '—'}</span>
                </div>
              ))}
            </div>
            <div className="ob-side">
              <div className="ob-header">Asks</div>
              {asks.map((a, i) => (
                <div key={i} className="ob-row">
                  <span className="ob-price">{a.price?.toFixed(3) ?? '—'}</span>
                  <span className="ob-size">{a.size?.toFixed(0) ?? '—'}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      {showChartModal && (
        <div
          className="outcome-chart-modal-overlay"
          onClick={() => setShowChartModal(false)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Escape' && setShowChartModal(false)}
          aria-label="Close"
        >
          <div className="outcome-chart-modal" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="outcome-chart-modal-close"
              onClick={() => setShowChartModal(false)}
            >
              ×
            </button>
            <OutcomePriceChart
              data={chartData}
              outcomeName={outcome?.name || outcome?.title}
              range="24h"
            />
          </div>
        </div>
      )}
    </>
  )
}

export default OutcomeCard
