import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getTrendingCategories, refreshTrendingCategories } from '../api/trending'
import './TrendingPage.css'

function TrendingPage() {
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    loadCategories()
  }, [])

  const loadCategories = async () => {
    try {
      setLoading(true)
      const data = await getTrendingCategories()
      setCategories(data)
    } catch (error) {
      console.error('Error loading categories:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    try {
      await refreshTrendingCategories()
      await loadCategories()
    } catch (error) {
      console.error('Error refreshing categories:', error)
    }
  }

  const filteredCategories = categories.filter(cat =>
    cat.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
    cat.slug.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="trending-page">
      <div className="page-header">
        <h1>Trending Categories</h1>
        <button onClick={handleRefresh} className="refresh-btn">
          Refresh
        </button>
      </div>

      <div className="search-container">
        <input
          type="text"
          placeholder="Search categories..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
      </div>

      {loading ? (
        <div className="loading">Loading categories...</div>
      ) : (
        <div className="categories-grid">
          {filteredCategories.length === 0 ? (
            <div className="empty-state">No categories found</div>
          ) : (
            filteredCategories.map((category) => (
              <div
                key={category.slug}
                className="category-card"
                onClick={() => navigate(`/category/${category.slug}`)}
              >
                <h3>{category.label}</h3>
                <p className="category-slug">{category.slug}</p>
                <div className="category-score">
                  Score: {category.score.toLocaleString()}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default TrendingPage
