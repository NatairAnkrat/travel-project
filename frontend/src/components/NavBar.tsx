import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function NavBar() {
  const { isAuthenticated, logout } = useAuth()
  if (!isAuthenticated) return null

  return (
    <nav className="nav-bar">
      <Link to="/groups">Groups</Link>
      <Link to="/faq">FAQ</Link>
      <Link to="/profile/settings">Profile</Link>
      <button type="button" onClick={() => logout()}>
        Log out
      </button>
    </nav>
  )
}
