import client from './client'

export const getTrendingCategories = async () => {
  const response = await client.get('/api/trending-categories')
  return response.data
}

export const refreshTrendingCategories = async () => {
  const response = await client.post('/api/trending-categories/refresh')
  return response.data
}
