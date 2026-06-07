import './App.css'
import { Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage.jsx'
import AboutPage from './pages/AboutPage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'
import SignalsFeedPage from './pages/SignalsPage.jsx'
import Layout from './components/Layout.jsx'
import PaperTradingPage from './pages/PaperTradingPage.jsx'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />}/>
        <Route path="about" element={<AboutPage />}/>
        <Route path="signals" element={<SignalsFeedPage />}/>
        <Route path="/paper/" element={<PaperTradingPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App