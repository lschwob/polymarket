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

export const getMarketDetail = async (marketId) => {
  const response = await client.get(`/api/markets/${marketId}/detail`)
  return response.data
}

export const getMarketTrades = async (marketId, limit = 100, offset = 0) => {
  const response = await client.get(`/api/markets/${marketId}/trades`, {
    params: { limit, offset }
  })
  return response.data
}

export const getMarketOrderBook = async (marketId) => {
  const response = await client.get(`/api/markets/${marketId}/order-book`)
  return response.data
}

export const getMarketPriceHistory = async (marketId, interval = '1m', rangeHours = 24) => {
  const response = await client.get(`/api/markets/${marketId}/price-history`, {
    params: { interval, range_hours: rangeHours }
  })
  return response.data
}

export const getMarketVolumeChart = async (marketId, rangeHours = 24) => {
  const response = await client.get(`/api/markets/${marketId}/volume-chart`, {
    params: { range_hours: rangeHours }
  })
  return response.data
}

export const getOutcomePriceHistory = async (marketId, outcomeTokenId, rangeHours = 24) => {
  const response = await client.get(
    `/api/markets/${marketId}/outcomes/${encodeURIComponent(outcomeTokenId)}/price-history`,
    { params: { range_hours: rangeHours } }
  )
  return response.data
}