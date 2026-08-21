import { useState } from 'react'
import { NotWiredNotice } from '../components/NotWiredNotice'

/**
 * UI-only. auth-service writes a user_settings row at registration but no
 * service exposes a GET/PATCH for it — there's nothing to fetch or save here
 * yet. Kept as a stub so the shape of the screen exists; wire it up once a
 * settings endpoint exists on the backend.
 */
export function ProfileSettingsPage() {
  const [theme, setTheme] = useState('light')
  const [distanceUnit, setDistanceUnit] = useState('km')
  const [emailNotifications, setEmailNotifications] = useState(true)
  const [pushNotifications, setPushNotifications] = useState(true)

  return (
    <div className="page">
      <h1>Profile settings</h1>
      <NotWiredNotice>
        there is no GET/PATCH endpoint for <code>user_settings</code> anywhere in the backend. These controls
        don't load or save anything — this screen exists purely to show the intended shape.
      </NotWiredNotice>

      <form className="form-card" onSubmit={(e) => e.preventDefault()}>
        <label>
          Theme
          <select value={theme} onChange={(e) => setTheme(e.target.value)}>
            <option value="light">light</option>
            <option value="dark">dark</option>
          </select>
        </label>
        <label>
          Distance unit
          <select value={distanceUnit} onChange={(e) => setDistanceUnit(e.target.value)}>
            <option value="km">km</option>
            <option value="mi">mi</option>
          </select>
        </label>
        <label>
          <input type="checkbox" checked={emailNotifications} onChange={(e) => setEmailNotifications(e.target.checked)} />
          Email notifications
        </label>
        <label>
          <input type="checkbox" checked={pushNotifications} onChange={(e) => setPushNotifications(e.target.checked)} />
          Push notifications
        </label>
        <button type="submit" disabled>
          Save (disabled — not wired up)
        </button>
      </form>
    </div>
  )
}
