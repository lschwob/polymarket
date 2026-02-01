import React, { useState, useEffect } from 'react'
import {
  getTrackedUsers,
  addTrackedUser,
  removeTrackedUser,
  getUserActivity,
  getUserSummary,
  getUserMarkets,
  refreshUserActivity,
} from '../api/users'
import UserActivityCard from '../components/UserActivityCard'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import './UserTracker.css'

function UserTracker() {
  const [users, setUsers] = useState([])
  const [selectedUser, setSelectedUser] = useState(null)
  const [summary, setSummary] = useState(null)
  const [activities, setActivities] = useState([])
  const [markets, setMarkets] = useState([])
  const [loading, setLoading] = useState(true)
  const [addAddress, setAddAddress] = useState('')
  const [addName, setAddName] = useState('')
  const [addError, setAddError] = useState(null)

  useEffect(() => {
    loadUsers()
    const interval = setInterval(loadUsers, 30000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (selectedUser) {
      loadUserData(selectedUser.address)
    } else {
      setSummary(null)
      setActivities([])
      setMarkets([])
    }
  }, [selectedUser])

  const loadUsers = async () => {
    try {
      const data = await getTrackedUsers()
      setUsers(data)
      if (!selectedUser && data.length > 0) {
        setSelectedUser(data[0])
      }
      if (selectedUser && !data.find((u) => u.address === selectedUser.address)) {
        setSelectedUser(data[0] || null)
      }
    } catch (error) {
      console.error('Error loading users:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadUserData = async (address) => {
    if (!address) return
    try {
      const [summaryData, activitiesData, marketsData] = await Promise.all([
        getUserSummary(address),
        getUserActivity(address, 100, 0),
        getUserMarkets(address),
      ])
      setSummary(summaryData)
      setActivities(activitiesData)
      setMarkets(marketsData)
    } catch (error) {
      console.error('Error loading user data:', error)
      setSummary(null)
      setActivities([])
      setMarkets([])
    }
  }

  const handleAddUser = async (e) => {
    e.preventDefault()
    setAddError(null)
    const addr = addAddress.trim()
    if (!addr) {
      setAddError('Enter an address')
      return
    }
    try {
      const created = await addTrackedUser(addr, addName.trim() || null)
      setAddAddress('')
      setAddName('')
      await loadUsers()
      setSelectedUser(created)
    } catch (error) {
      setAddError(error.response?.data?.detail || error.message || 'Failed to add user')
    }
  }

  const handleRemoveUser = async (address) => {
    if (!window.confirm('Remove this user from tracking?')) return
    try {
      await removeTrackedUser(address)
      await loadUsers()
      if (selectedUser?.address === address) {
        setSelectedUser(users.find((u) => u.address !== address) || null)
      }
    } catch (error) {
      console.error('Error removing user:', error)
    }
  }

  const handleRefresh = async () => {
    if (!selectedUser) return
    try {
      await refreshUserActivity(selectedUser.address)
      await loadUserData(selectedUser.address)
    } catch (error) {
      console.error('Error refreshing:', error)
    }
  }

  const volumeByDay = React.useMemo(() => {
    if (!activities.length) return []
    const byDay = {}
    activities.forEach((a) => {
      const day = a.timestamp ? a.timestamp.slice(0, 10) : ''
      if (!byDay[day]) byDay[day] = { day, volume: 0, count: 0 }
      byDay[day].volume += a.usdc_size || 0
      byDay[day].count += 1
    })
    return Object.values(byDay).sort((a, b) => a.day.localeCompare(b.day))
  }, [activities])

  const truncateAddress = (addr) => {
    if (!addr) return ''
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`
  }

  const isActiveNow = (lastAt) => {
    if (!lastAt) return false
    const t = new Date(lastAt).getTime()
    return Date.now() - t < 5 * 60 * 1000
  }

  if (loading) {
    return <div className="user-tracker loading">Loading...</div>
  }

  return (
    <div className="user-tracker">
      <h1>User Tracker</h1>
      <p className="subtitle">Track Polymarket users by address. Activity is polled every minute.</p>

      <div className="user-tracker-content">
        <aside className="users-sidebar">
          <h2>Tracked Users</h2>
          <form className="add-user-form" onSubmit={handleAddUser}>
            <input
              type="text"
              placeholder="0x..."
              value={addAddress}
              onChange={(e) => setAddAddress(e.target.value)}
              className="add-address-input"
            />
            <input
              type="text"
              placeholder="Name (optional)"
              value={addName}
              onChange={(e) => setAddName(e.target.value)}
              className="add-name-input"
            />
            <button type="submit" className="add-user-btn">Add</button>
            {addError && <div className="add-error">{addError}</div>}
          </form>
          <div className="users-list">
            {users.map((u) => (
              <div
                key={u.address}
                className={`user-card ${selectedUser?.address === u.address ? 'selected' : ''}`}
                onClick={() => setSelectedUser(u)}
              >
                <div className="user-card-header">
                  <span className="user-address">{truncateAddress(u.address)}</span>
                  <button
                    type="button"
                    className="delete-user-btn"
                    onClick={(e) => { e.stopPropagation(); handleRemoveUser(u.address) }}
                    aria-label="Remove"
                  >
                    ×
                  </button>
                </div>
                {(u.name || u.pseudonym) && (
                  <div className="user-name">{u.name || u.pseudonym}</div>
                )}
              </div>
            ))}
            {users.length === 0 && (
              <div className="empty-sidebar">Add an address to track (e.g. from polymarket.com/@username)</div>
            )}
          </div>
        </aside>

        <div className="user-detail-panel">
          {selectedUser ? (
            <>
              <div className="user-detail-header">
                <h2>{selectedUser.name || selectedUser.pseudonym || truncateAddress(selectedUser.address)}</h2>
                <span className="user-address-full">{selectedUser.address}</span>
                <button type="button" className="refresh-btn" onClick={handleRefresh}>
                  Refresh activity
                </button>
              </div>

              {summary && (
                <div className="summary-cards">
                  <div className="summary-card">
                    <div className="summary-label">Total volume</div>
                    <div className="summary-value">${Number(summary.total_volume_usdc || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
                  </div>
                  <div className="summary-card">
                    <div className="summary-label">Trades</div>
                    <div className="summary-value">{summary.trade_count ?? 0}</div>
                  </div>
                  <div className="summary-card">
                    <div className="summary-label">Redeems</div>
                    <div className="summary-value">{summary.redeem_count ?? 0}</div>
                  </div>
                  <div className="summary-card">
                    <div className="summary-label">Markets</div>
                    <div className="summary-value">{summary.markets_count ?? 0}</div>
                  </div>
                  {summary.win_rate_percent != null && (
                    <div className="summary-card">
                      <div className="summary-label">Win rate (proxy)</div>
                      <div className="summary-value">{summary.win_rate_percent}%</div>
                    </div>
                  )}
                  {summary.last_activity_at && (
                    <div className="summary-card">
                      <div className="summary-label">Last activity</div>
                      <div className="summary-value">
                        {isActiveNow(summary.last_activity_at) ? (
                          <span className="active-badge">Active now</span>
                        ) : (
                          new Date(summary.last_activity_at).toLocaleString()
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {volumeByDay.length > 0 && (
                <div className="chart-section">
                  <h3>Volume by day</h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={volumeByDay}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                      <XAxis dataKey="day" stroke="#6c757d" style={{ fontSize: '12px' }} />
                      <YAxis stroke="#6c757d" style={{ fontSize: '12px' }} tickFormatter={(v) => `$${v}`} />
                      <Tooltip formatter={(v) => [`$${Number(v).toLocaleString()}`, 'Volume']} />
                      <Bar dataKey="volume" fill="#1e88e5" name="Volume" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              <div className="activity-section">
                <h3>Activity timeline</h3>
                <div className="activity-list">
                  {activities.length === 0 && <div className="empty-activity">No activity stored yet. Click &quot;Refresh activity&quot; to fetch from Polymarket.</div>}
                  {activities.map((a) => (
                    <UserActivityCard key={a.id} activity={a} />
                  ))}
                </div>
              </div>

              {markets.length > 0 && (
                <div className="markets-section">
                  <h3>Markets</h3>
                  <ul className="markets-list-detail">
                    {markets.slice(0, 10).map((m, i) => (
                      <li key={m.market_slug || i}>
                        <span className="market-title">{m.market_title || m.market_slug}</span>
                        <span className="market-volume">${Number(m.volume || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className="empty-detail">Select a user or add one by address.</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default UserTracker
