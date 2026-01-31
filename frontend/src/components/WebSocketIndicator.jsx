import React from 'react'
import './WebSocketIndicator.css'

function WebSocketIndicator({ connected, reconnecting }) {
  return (
    <div className={`websocket-indicator ${connected ? 'connected' : 'disconnected'} ${reconnecting ? 'reconnecting' : ''}`}>
      <div className="indicator-dot"></div>
      <span className="indicator-text">
        {reconnecting ? 'Reconnecting...' : connected ? 'Live' : 'Disconnected'}
      </span>
    </div>
  )
}

export default WebSocketIndicator
