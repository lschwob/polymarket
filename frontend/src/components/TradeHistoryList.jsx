import React from 'react'
import './TradeHistoryList.css'

function TradeHistoryList({ trades, limit = 50 }) {
  if (!trades || trades.length === 0) {
    return (
      <div className="trade-history-list">
        <div className="empty-state">No trades available</div>
      </div>
    )
  }
  
  const formatAddress = (address) => {
    if (!address) return 'Anonymous'
    return `${address.slice(0, 6)}...${address.slice(-4)}`
  }
  
  const formatAmount = (amount) => {
    if (!amount) return '0.00'
    if (amount >= 1000) return `$${(amount / 1000).toFixed(2)}K`
    return `$${amount.toFixed(2)}`
  }
  
  const formatTime = (timestamp) => {
    if (!timestamp) return 'N/A'
    const date = new Date(timestamp)
    return date.toLocaleTimeString()
  }
  
  return (
    <div className="trade-history-list">
      <div className="trade-history-header">
        <h3>Recent Trades</h3>
      </div>
      <div className="trades-table">
        <div className="trades-header">
          <span>Time</span>
          <span>User</span>
          <span>Side</span>
          <span>Price</span>
          <span>Amount</span>
        </div>
        <div className="trades-body">
          {trades.slice(0, limit).map((trade, idx) => (
            <div key={idx} className={`trade-row ${trade.side || 'buy'}`}>
              <span className="trade-time">{formatTime(trade.timestamp)}</span>
              <span className="trade-user">{formatAddress(trade.user_address || trade.user)}</span>
              <span className={`trade-side ${trade.side || 'buy'}`}>
                {trade.side === 'sell' ? 'SELL' : 'BUY'}
              </span>
              <span className="trade-price">${(trade.price || 0).toFixed(4)}</span>
              <span className="trade-amount">{formatAmount(trade.amount)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default TradeHistoryList
