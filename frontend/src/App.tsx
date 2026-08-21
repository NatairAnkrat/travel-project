import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import { RequireAuth } from './auth/RequireAuth'
import { NavBar } from './components/NavBar'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { GroupsPage } from './pages/GroupsPage'
import { GroupDetailPage } from './pages/GroupDetailPage'
import { TripPlanningPage } from './pages/TripPlanningPage'
import { TravelStatusPage } from './pages/TravelStatusPage'
import { ProfileSettingsPage } from './pages/ProfileSettingsPage'
import { FaqPage } from './pages/FaqPage'

function Home() {
  const { isAuthenticated } = useAuth()
  return <Navigate to={isAuthenticated ? '/groups' : '/login'} replace />
}

function App() {
  return (
    <>
      <NavBar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/faq" element={<FaqPage />} />
        <Route
          path="/groups"
          element={
            <RequireAuth>
              <GroupsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/groups/:groupId"
          element={
            <RequireAuth>
              <GroupDetailPage />
            </RequireAuth>
          }
        />
        <Route
          path="/groups/:groupId/travels/new"
          element={
            <RequireAuth>
              <TripPlanningPage />
            </RequireAuth>
          }
        />
        <Route
          path="/travels/:travelId/status/:kind/:jobId"
          element={
            <RequireAuth>
              <TravelStatusPage />
            </RequireAuth>
          }
        />
        <Route
          path="/profile/settings"
          element={
            <RequireAuth>
              <ProfileSettingsPage />
            </RequireAuth>
          }
        />
      </Routes>
    </>
  )
}

export default App
