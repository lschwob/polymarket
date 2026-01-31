import React from 'react'
import './OrderBookTable.css'

function OrderBookTable({ orderBook }) {
  if (!orderBook || (!orderBook.bids?.length && !orderBook.asks?.length)) {
    return (
      <div className="order-book-table">
        <div className="empty-state">No order book data available</div>
      </div>
    )
  }
  
  const bids = orderBook.bids || []
  const asks = orderBook.asks || []
  
  // Sort bids descending, asks ascending
  const sortedBids = [...bids].sort((a, b) => (b.price || 0) - (a.price || 0))
  const sortedAsks = [...asks].sort((a, b) => (a.price || 0) - (b.price || 0))
  
  const maxRows = Math.max(sortedBids.length, sortedAsks.length, 10)
  
  return (
    <div className="order-book-table">
      <div className="order-book-header">
        <h3>{orderBook.outcome_name || 'Order Book'}</h3>
      </div>
      <div className="order-book-content">
        <div className="order-book-side">
          <div className="side-header">
            <span className="side-label">Bids</span>
            <span className="side-label">Size</span>
          </div>
          <div className="side-orders">
            {sortedBids.slice(0, maxRows).map((bid, idx) => (
              <div key={idx} className="order-row bid-row">
                <span className="order-price">{bid.price?.toFixed(4) || '0.0000'}</span>
                <span className="order-size">{bid.size?.toFixed(2) || '0.00'}</span>
              </div>
            ))}
            {sortedBids.length === 0 && (
              <div className="empty-orders">No bids</div>
            )}
          </div>
        </div>
        
        <div className="order-book-divider"></div>
        
        <div className="order-book-side">
          <div className="side-header">
            <span className="side-label">Asks</span>
            <span className="side-label">Size</span>
          </div>
          <div className="side-orders">
            {sortedAsks.slice(0, maxRows).map((ask, idx) => (
              <div key={idx} className="order-row ask-row">
                <span className="order-price">{ask.price?.toFixed(4) || '0.0000'}</span>
                <span className="order-size">{ask.size?.toFixed(2) || '0.00'}</span>
              </div>
            ))}
            {sortedAsks.length === 0 && (
              <div className="empty-orders">No asks</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default OrderBookTable
