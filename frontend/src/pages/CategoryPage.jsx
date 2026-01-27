import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getEvents } from '../api/markets'
import { addTrackedMarket } from '../api/markets'
import './CategoryPage.css'

function CategoryPage() {
  const { tagSlug } = useParams()
  const navigate = useNavigate()
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [tracking, setTracking] = useState(new Set())

  useEffect(() => {
    loadEvents()
  }, [tagSlug])

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
      setTracking(new Set([...tracking, event.id]))
      alert(`Tracking ${event.title}`)
    } catch (error) {
      console.error('Error tracking market:', error)
      if (error.response?.status === 400) {
        alert('Market is already being tracked')
      }
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
            events.map((event) => (
              <div key={event.id} className="event-card">
                <div className="event-info">
                  <h3>{event.title}</h3>
                  <p className="event-slug">{event.slug || event.ticker}</p>
                  {event.volume && (
                    <div className="event-volume">
                      Volume: {event.volume.toLocaleString()}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => handleTrack(event)}
                  className={`track-btn ${tracking.has(event.id) ? 'tracked' : ''}`}
                  disabled={tracking.has(event.id)}
                >
                  {tracking.has(event.id) ? 'Tracked' : 'Track'}
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default CategoryPage
