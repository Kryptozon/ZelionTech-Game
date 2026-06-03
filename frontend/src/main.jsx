import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { initTelegram } from './telegram'
import './index.css'

initTelegram()
createRoot(document.getElementById('root')).render(<App />)
