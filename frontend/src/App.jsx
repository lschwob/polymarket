import React from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import TrendingPage from './pages/TrendingPage'
import CategoryPage from './pages/CategoryPage'
import Dashboard from './pages/Dashboard'
import Watchlist from './pages/Watchlist'
import MarketDetailPage from './pages/MarketDetailPage'
import './App.css'

function App() {
  return (
    <Router>
      <div className="app">
        <nav className="navbar">
          <div className="nav-container">
            <Link to="/" className="nav-logo">
              Polymarket Tracker
            </Link>
            <div className="nav-links">
              <Link to="/" className="nav-link">Trending</Link>
              <Link to="/watchlist" className="nav-link">Watchlist</Link>
              <Link to="/dashboard" className="nav-link">Dashboard</Link>
            </div>
          </div>
        </nav>
        
        <main className="main-content">
          <Routes>
            <Route path="/" element={<TrendingPage />} />
            <Route path="/category/:tagSlug" element={<CategoryPage />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/market/:marketId" element={<MarketDetailPage />} />
            <Route path="/dashboard" element={<Dashboard />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App
