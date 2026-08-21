import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { NotWiredNotice } from '../components/NotWiredNotice'
import { ApiError } from '../lib/apiClient'

const emptyForm = {
  login: '',
  password: '',
  email: '',
  phone: '',
  firstName: '',
  lastName: '',
  languageId: '',
  currencyId: '',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
}

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await register({
        login: form.login,
        password: form.password,
        email: form.email,
        phone: form.phone || null,
        first_name: form.firstName,
        last_name: form.lastName,
        language_id: form.languageId,
        currency_id: form.currencyId,
        timezone: form.timezone,
      })
      navigate('/login')
    } catch (err) {
      setError(err instanceof ApiError && err.status === 409 ? 'Login or email already in use' : 'Registration failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="form-card">
      <h1>Register</h1>
      <label>
        Login
        <input value={form.login} onChange={(e) => set('login', e.target.value)} required />
      </label>
      <label>
        Email
        <input type="email" value={form.email} onChange={(e) => set('email', e.target.value)} required />
      </label>
      <label>
        Password
        <input type="password" value={form.password} onChange={(e) => set('password', e.target.value)} required minLength={8} />
      </label>
      <label>
        Phone (optional)
        <input value={form.phone} onChange={(e) => set('phone', e.target.value)} />
      </label>
      <label>
        First name
        <input value={form.firstName} onChange={(e) => set('firstName', e.target.value)} required />
      </label>
      <label>
        Last name
        <input value={form.lastName} onChange={(e) => set('lastName', e.target.value)} required />
      </label>

      <NotWiredNotice>
        there's no <code>/languages</code> or <code>/currencies</code> lookup endpoint anywhere in the backend, so
        these must be entered as raw UUIDs from the <code>languages</code>/<code>currencies</code> tables for now.
      </NotWiredNotice>
      <label>
        Language ID (uuid)
        <input value={form.languageId} onChange={(e) => set('languageId', e.target.value)} required placeholder="00000000-0000-0000-0000-000000000000" />
      </label>
      <label>
        Currency ID (uuid)
        <input value={form.currencyId} onChange={(e) => set('currencyId', e.target.value)} required placeholder="00000000-0000-0000-0000-000000000000" />
      </label>

      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={submitting}>
        {submitting ? 'Registering…' : 'Register'}
      </button>
    </form>
  )
}
