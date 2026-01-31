import React, { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { getEvents, getMarketDetails } from '../api/markets'
import { addTrackedMarket, getTrackedMarkets } from '../api/markets'
import OutcomeCard from '../components/OutcomeCard'
import './CategoryPage.css'

function CategoryPage() {
  const { tagSlug } = useParams()
  const navigate = useNavigate()
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [tracking, setTracking] = useState(new Set())
  const [expandedEvent, setExpandedEvent] = useState(null)
  const [eventDetails, setEventDetails] = useState({})

  useEffect(() => {
    loadEvents()
    loadTrackedMarkets()
  }, [tagSlug])

  const loadTrackedMarkets = async () => {
    try {
      const tracked = await getTrackedMarkets()
      const trackedSet = new Set(tracked.map(m => m.market_id || m.market_slug))
      setTracking(trackedSet)
    } catch (error) {
      console.error('Error loading tracked markets:', error)
    }
  }

  const loadEventDetails = async (eventSlug) => {
    if (eventDetails[eventSlug]) return // Already loaded
    
    try {
      const details = await getMarketDetails(eventSlug)
      setEventDetails(prev => ({
        ...prev,
        [eventSlug]: details
      }))
    } catch (error) {
      console.error('Error loading event details:', error)
    }
  }

  const loadEvents = async () => {
    try {
      setLoading(true)
      const data = await getEvents(tagSlug)
      setEvents(data)
    } catch (error) {
      console.error('Error loading events:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleTrack = async (event) => {
    try {
      await addTrackedMarket({
        market_slug: event.slug || event.ticker,
        market_id: event.id,
        title: event.title,
        tag_slug: tagSlug
      })
      setTracking(new Set([...tracking, event.id || event.slug]))
      alert(`Tracking ${event.title}`)
      loadTrackedMarkets()
    } catch (error) {
      console.error('Error tracking market:', error)
      if (error.response?.status === 400) {
        alert('Market is already being tracked')
      }
    }
  }

  const handleExpandEvent = async (event) => {
    const eventSlug = event.slug || event.ticker
    if (expandedEvent === event.id) {
      setExpandedEvent(null)
    } else {
      setExpandedEvent(event.id)
      await loadEventDetails(eventSlug)
    }
  }

  return (
    <div className="category-page">
      <div className="page-header">
        <button onClick={() => navigate('/')} className="back-btn">
          ← Back
        </button>
        <h1>Category: {tagSlug}</h1>
      </div>

      {loading ? (
        <div className="loading">Loading events...</div>
      ) : (
        <div className="events-list">
          {events.length === 0 ? (
            <div className="empty-state">No events found</div>
          ) : (
            events.map((event) => {
              const eventSlug = event.slug || event.ticker
              const details = eventDetails[eventSlug]
              const isExpanded = expandedEvent === event.id
              const isTracked = tracking.has(event.id) || tracking.has(eventSlug)
              
              return (
                <div key={event.id} className="event-card">
                  <div className="event-info">
                    <h3>{event.title}</h3>
                    <p className="event-slug">{event.slug || event.ticker}</p>
                    {event.volume && (
                      <div className="event-volume">
                        Volume: ${event.volume.toLocaleString()}
                      </div>
                    )}
                    {details?.description && (
                      <p className="event-description">{details.description}</p>
                    )}
                    
                    {isExpanded && details && (
                      <div className="event-expanded">
                        {details.outcomes && details.outcomes.length > 0 && (
                          <div className="event-outcomes">
                            <h4>Outcomes:</h4>
                            <div className="outcomes-grid">
                              {details.outcomes.map((outcome) => (
                                <OutcomeCard
                                  key={outcome.id || outcome.outcome_id}
                                  outcome={outcome}
                                />
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    
                    <button
                      onClick={() => handleExpandEvent(event)}
                      className="expand-btn"
                    >
                      {isExpanded ? '▼ Hide Details' : '▶ Show Details'}
                    </button>
                  </div>
                  <div className="event-actions">
                    <button
                      onClick={() => handleTrack(event)}
                      className={`track-btn ${isTracked ? 'tracked' : ''}`}
                      disabled={isTracked}
                    >
                      {isTracked ? 'Tracked' : 'Track'}
                    </button>
                    {isTracked && (
                      <Link 
                        to="/watchlist"
                        className="view-link"
                      >
                        View →
                      </Link>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}

export default CategoryPage
