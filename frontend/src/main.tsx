import { StrictMode, lazy, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/globals.css'
import App from './App.tsx'

// The AI work bar (Alt+Space / Ctrl+Alt+A) loads index.html#companion.
// eslint-disable-next-line react/only-export-components
const CompanionApp = lazy(() => import('./CompanionApp.tsx'))
const isCompanion = window.location.hash === '#companion'
// The work bar window is transparent; its panel draws its own rounded background.
if (isCompanion) document.documentElement.classList.add('workbar')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isCompanion ? <Suspense fallback={null}><CompanionApp /></Suspense> : <App />}
  </StrictMode>,
)
