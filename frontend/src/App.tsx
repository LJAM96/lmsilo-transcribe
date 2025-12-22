import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import JobDetails from './pages/JobDetails'
import Models from './pages/Models'
import Settings from './pages/Settings'
import History from './pages/History'
import LiveTranscribe from './pages/LiveTranscribe'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="jobs/:jobId" element={<JobDetails />} />
          <Route path="models" element={<Models />} />
          <Route path="history" element={<History />} />
          <Route path="live" element={<LiveTranscribe />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
