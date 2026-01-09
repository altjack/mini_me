import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './lib/react-query'
import { AuthProvider } from './context/AuthContext'
import { PromoProvider } from './context/PromoContext'
import { BackfillProvider } from './context/BackfillContext'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BackfillProvider>
          <PromoProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </PromoProvider>
        </BackfillProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
