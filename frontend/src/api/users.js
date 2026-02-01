import client from './client'

export const addTrackedUser = async (address, name = null) => {
  const response = await client.post('/api/tracked-users', { address: address.trim(), name })
  return response.data
}

export const getTrackedUsers = async () => {
  const response = await client.get('/api/tracked-users')
  return response.data
}

export const removeTrackedUser = async (address) => {
  await client.delete(`/api/tracked-users/${encodeURIComponent(address.trim())}`)
}

export const getUserActivity = async (address, limit = 50, offset = 0, marketId = null) => {
  const params = { limit, offset }
  if (marketId != null) params.market_id = marketId
  const response = await client.get(`/api/users/${encodeURIComponent(address.trim())}/activity`, { params })
  return response.data
}

export const getUserSummary = async (address) => {
  const response = await client.get(`/api/users/${encodeURIComponent(address.trim())}/summary`)
  return response.data
}

export const getUserMarkets = async (address) => {
  const response = await client.get(`/api/users/${encodeURIComponent(address.trim())}/markets`)
  return response.data
}

export const refreshUserActivity = async (address) => {
  const response = await client.post(`/api/users/${encodeURIComponent(address.trim())}/refresh`)
  return response.data
}

export const getActivityFeed = async (marketIds = null, limit = 30) => {
  const params = { limit }
  if (marketIds != null && marketIds.length > 0) {
    params.market_ids = marketIds.join(',')
  }
  const response = await client.get('/api/activity/feed', { params })
  return response.data
}
