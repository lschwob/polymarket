import { useState, useEffect, useRef } from 'react'

function useWebSocket(marketId, onMessage) {
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5

  useEffect(() => {
    if (!marketId) return

    const connect = () => {
      try {
        // Determine WebSocket URL based on environment
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const host = process.env.REACT_APP_API_URL 
          ? process.env.REACT_APP_API_URL.replace(/^https?/, protocol === 'wss:' ? 'wss' : 'ws')
          : `${protocol}//localhost:8000`
        
        const wsUrl = `${host}/ws/market/${marketId}`
        
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
          console.log(`WebSocket connected for market ${marketId}`)
          setConnected(true)
          setReconnecting(false)
          reconnectAttempts.current = 0
        }

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (onMessage) {
              onMessage(data)
            }
          } catch (error) {
            console.error('Error parsing WebSocket message:', error)
          }
        }

        ws.onerror = (error) => {
          console.error('WebSocket error:', error)
        }

        ws.onclose = () => {
          console.log(`WebSocket disconnected for market ${marketId}`)
          setConnected(false)
          
          // Attempt to reconnect
          if (reconnectAttempts.current < maxReconnectAttempts) {
            setReconnecting(true)
            reconnectAttempts.current += 1
            
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
            reconnectTimeoutRef.current = setTimeout(() => {
              connect()
            }, delay)
          } else {
            setReconnecting(false)
            console.error('Max reconnection attempts reached')
          }
        }
      } catch (error) {
        console.error('Error creating WebSocket connection:', error)
        setConnected(false)
        setReconnecting(false)
      }
    }

    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setConnected(false)
      setReconnecting(false)
    }
  }, [marketId, onMessage])

  const sendMessage = (message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }

  return { connected, reconnecting, sendMessage }
}

export default useWebSocket
