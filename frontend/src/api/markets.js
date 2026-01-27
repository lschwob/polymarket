import client from './client'

export const getEvents = async (tagSlug = null, limit = 50) => {
  const params = tagSlug ? { tag_slug: tagSlug, limit } : { limit }
  const response = await client.get('/api/events', { params })
  return response.data.data || []
}

export const getMarketDetails = async (marketSlug) => {
  const response = await client.get(`/api/market/${marketSlug}`)
  return response.data
}

export const addTrackedMarket = async (market) => {
  const response = await client.post('/api/tracked-markets', market)
  return response.data
}

export const getTrackedMarkets = async () => {
  const response = await client.get('/api/tracked-markets')
  return response.data
}

export const deleteTrackedMarket = async (marketId) => {
  const response = await client.delete(`/api/tracked-markets/${marketId}`)
  return response.data
}

export const getMarketSnapshots = async (marketId, rangeHours = 24) => {
  const response = await client.get(`/api/markets/${marketId}/snapshots`, {
    params: { range_hours: rangeHours }
  })
  return response.data
}
