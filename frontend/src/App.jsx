import React, { useState, useEffect } from 'react';
import { Routes, Route, NavLink } from 'react-router-dom';
import { StatsCard } from './components/StatsCard';
import { EmailGenerator } from './components/EmailGenerator';
import { BackfillPanel } from './components/BackfillPanel';
import { Dashboard } from './components/Dashboard';
import { api } from './services/api';
import { LayoutDashboard, Home, BarChart3 } from 'lucide-react';

function HomePage({ stats, loadingStats, fetchStats }) {
  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h2 className="text-lg font-medium text-gray-700 mb-4">System Overview</h2>
        <StatsCard stats={stats} loading={loadingStats} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Email Generation */}
        <div className="lg:col-span-2">
          <EmailGenerator onActionComplete={fetchStats} />
        </div>

        {/* Right Column: Tools */}
        <div className="lg:col-span-1">
          <BackfillPanel onActionComplete={fetchStats} />
          
          {/* Helper Info */}
          <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h3 className="font-medium text-gray-900 mb-2">System Status</h3>
            <div className="space-y-2 text-sm text-gray-600">
              <p>• Backend API: <span className="text-green-600 font-medium">Active</span></p>
              <p>• Database: <span className="text-green-600 font-medium">Connected</span></p>
              <p>• GA4 Connection: <span className="text-gray-500">Checked on demand</span></p>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

function App() {
  const [stats, setStats] = useState(null);
  const [loadingStats, setLoadingStats] = useState(true);

  const fetchStats = async () => {
    setLoadingStats(true);
    try {
      const res = await api.getStats();
      setStats(res.data);
    } catch (err) {
      console.error('Failed to fetch stats', err);
    } finally {
      setLoadingStats(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with Navigation */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center">
            <LayoutDashboard className="text-blue-600 mr-3" size={24} />
            <h1 className="text-xl font-bold text-gray-900">Automation Dashboard</h1>
          </div>
          
          {/* Navigation */}
          <nav className="flex items-center space-x-1">
            <NavLink
              to="/"
              className={({ isActive }) =>
                `flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              <Home size={18} className="mr-2" />
              Home
            </NavLink>
            <NavLink
              to="/dashboard"
              className={({ isActive }) =>
                `flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              <BarChart3 size={18} className="mr-2" />
              SWI Dashboard
            </NavLink>
          </nav>
        </div>
      </header>

      {/* Routes */}
      <Routes>
        <Route 
          path="/" 
          element={
            <HomePage 
              stats={stats} 
              loadingStats={loadingStats} 
              fetchStats={fetchStats} 
            />
          } 
        />
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </div>
  );
}

export default App;
