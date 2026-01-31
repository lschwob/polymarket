import React from 'react'
import './OutcomeCard.css'

function OutcomeCard({ outcome, onClick, selected }) {
  const prob = outcome.prob || outcome.price || 0
  const probPercent = (prob * 100).toFixed(1)
  
  // Determine trend (simplified - would need historical data for real trend)
  const trend = null // Could be 'up', 'down', or null
  
  return (
    <div 
      className={`outcome-card ${selected ? 'selected' : ''}`}
      onClick={onClick}
    >
      <div className="outcome-header">
        <h4 className="outcome-name">{outcome.name || outcome.title || 'Unknown'}</h4>
        <div className="outcome-prob">
          {probPercent}%
        </div>
      </div>
      <div className="outcome-price">
        ${prob.toFixed(3)}
      </div>
      {trend && (
        <div className={`outcome-trend ${trend}`}>
          {trend === 'up' ? '↑' : '↓'}
        </div>
      )}
    </div>
  )
}

export default OutcomeCard
