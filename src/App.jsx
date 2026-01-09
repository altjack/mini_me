import React, { memo, lazy, Suspense } from 'react';
import { Routes, Route, NavLink } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { StatsCard } from './components/StatsCard';
import { EmailGenerator } from './components/EmailGenerator';
import { BackfillPanel } from './components/BackfillPanel';
import { LoginPage } from './components/LoginPage';
import { useAuth } from './context/AuthContext';
import { LayoutDashboard, Home, BarChart3, LogOut, Loader2, Gift } from 'lucide-react';
import { useAppStats, useAppActions } from './hooks/useAppStats';

// Lazy load Dashboard component (heavy due to recharts)
const Dashboard = lazy(() => import('./components/Dashboard').then(module => ({
  default: module.Dashboard
})));

// Lazy load PromoDashboard component
const PromoDashboard = lazy(() => import('./components/PromoDashboard').then(module => ({
  default: module.PromoDashboard
})));

// Loading fallback for lazy-loaded components
const DashboardLoadingFallback = () => (
  <div className="min-h-[400px] flex items-center justify-center">
    <div className="flex flex-col items-center gap-3">
      <Loader2 className="animate-spin text-blue-600" size={32} />
      <p className="text-gray-500 text-sm">Loading dashboard...</p>
    </div>
  </div>
);

/**
 * HomePage component - memoized to prevent unnecessary re-renders
 */
const HomePage = memo(({ stats, loadingStats, onRefresh }) => {
  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h2 className="text-lg font-medium text-gray-700 mb-4">System Overview</h2>
        <StatsCard stats={stats} loading={loadingStats} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Email Generation */}
        <div className="lg:col-span-2">
          <EmailGenerator onActionComplete={onRefresh} />
        </div>

        {/* Right Column: Tools */}
        <div className="lg:col-span-1">
          <BackfillPanel onActionComplete={onRefresh} />

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
});

HomePage.displayName = 'HomePage';

/**
 * AuthenticatedApp - main app layout for authenticated users
 */
function AuthenticatedApp() {
  const { logout, user } = useAuth();
  
  // React Query hooks
  const { data: stats, isLoading: loadingStats } = useAppStats();
  const { invalidateStats } = useAppActions();

  // Listen for unauthorized events from API interceptor
  React.useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };

    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, [logout]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Toast Notifications */}
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#fff',
            color: '#363636',
          },
          success: {
            iconTheme: {
              primary: '#10b981',
              secondary: '#fff',
            },
          },
          error: {
            iconTheme: {
              primary: '#ef4444',
              secondary: '#fff',
            },
          },
        }}
      />

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
            <NavLink
              to="/promozioni"
              className={({ isActive }) =>
                `flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-amber-50 text-amber-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              <Gift size={18} className="mr-2" />
              Promozioni
            </NavLink>

            {/* User & Logout */}
            <div className="flex items-center ml-4 pl-4 border-l border-gray-200">
              {user && (
                <span className="text-sm text-gray-500 mr-3">
                  {user}
                </span>
              )}
              <button
                onClick={logout}
                className="flex items-center px-3 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-red-50 hover:text-red-600 transition-colors"
                title="Sign out"
                aria-label="Sign out from dashboard"
              >
                <LogOut size={18} aria-hidden="true" />
              </button>
            </div>
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
              onRefresh={invalidateStats}
            />
          }
        />
        <Route
          path="/dashboard"
          element={
            <Suspense fallback={<DashboardLoadingFallback />}>
              <Dashboard />
            </Suspense>
          }
        />
        <Route
          path="/promozioni"
          element={
            <Suspense fallback={<DashboardLoadingFallback />}>
              <PromoDashboard />
            </Suspense>
          }
        />
      </Routes>
    </div>
  );
}

/**
 * Main App component
 */
function App() {
  const { isAuthenticated, isLoading } = useAuth();

  // Show loading state while checking authentication
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="animate-spin text-blue-600" size={40} />
          <p className="text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return (
      <>
        <Toaster position="top-center" />
        <LoginPage />
      </>
    );
  }

  // Show main app if authenticated
  return <AuthenticatedApp />;
}

export default App;
