import client from './client'

export const getAlerts = async (status = null, includeAll = false) => {
  const params = {}
  if (status) params.status = status
  if (includeAll) params.include_all = true
  const response = await client.get('/api/alerts', { params })
  return response.data
}

export const getMarketShifts = async (marketId) => {
  const response = await client.get(`/api/markets/${marketId}/shifts`)
  return response.data
}

export const acknowledgeAlert = async (alertId) => {
  const response = await client.post(`/api/alerts/ack/${alertId}`)
  return response.data
}
