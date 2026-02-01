import React from 'react'
import { Link } from 'react-router-dom'
import './UserActivityCard.css'

function UserActivityCard({ activity }) {
  const isTrade = activity.activity_type === 'TRADE'
  const isRedeem = activity.activity_type === 'REDEEM'
  const time = activity.timestamp
    ? new Date(activity.timestamp).toLocaleString(undefined, {
        dateStyle: 'short',
        timeStyle: 'short',
      })
    : ''

  return (
    <div className={`user-activity-card ${activity.activity_type?.toLowerCase()}`}>
      <div className="user-activity-icon">
        {isTrade && (
          <span className={`side-badge ${(activity.side || '').toLowerCase()}`}>
            {activity.side === 'BUY' ? 'BUY' : activity.side === 'SELL' ? 'SELL' : 'TRADE'}
          </span>
        )}
        {isRedeem && <span className="side-badge redeem">REDEEM</span>}
      </div>
      <div className="user-activity-body">
        <div className="user-activity-market">
          {activity.market_title || activity.market_slug || 'Unknown market'}
        </div>
        {isTrade && activity.outcome && (
          <div className="user-activity-outcome">{activity.outcome}</div>
        )}
        <div className="user-activity-meta">
          <span className="user-activity-size">
            {isRedeem ? `$${Number(activity.usdc_size).toLocaleString(undefined, { minimumFractionDigits: 2 })}` : null}
            {isTrade
              ? `${Number(activity.size).toLocaleString(undefined, { maximumFractionDigits: 0 })} @ ${activity.price != null ? (activity.price * 100).toFixed(1) : '—'}%`
              : null}
          </span>
          {isTrade && activity.usdc_size != null && (
            <span className="user-activity-usdc">${Number(activity.usdc_size).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          )}
        </div>
        <div className="user-activity-time">{time}</div>
        {activity.market_id != null && (
          <Link to={`/market/${activity.market_id}`} className="user-activity-link">
            View market →
          </Link>
        )}
      </div>
    </div>
  )
}

export default UserActivityCard
