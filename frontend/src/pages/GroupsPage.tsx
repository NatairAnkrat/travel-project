import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { NotWiredNotice } from '../components/NotWiredNotice'
import * as groupsApi from '../api/groups'
import { getKnownGroups, rememberGroup } from '../lib/knownGroups'

export function GroupsPage() {
  const { userId } = useAuth()
  const navigate = useNavigate()
  const [groups, setGroups] = useState(getKnownGroups())

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [inviteToken, setInviteToken] = useState('')
  const [joining, setJoining] = useState(false)

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    if (!userId) return
    setCreating(true)
    setError(null)
    try {
      const { group_id } = await groupsApi.createGroup({ name, description: description || null, created_by: userId })
      rememberGroup({ id: group_id, name })
      setGroups(getKnownGroups())
      setName('')
      setDescription('')
    } catch {
      setError('Failed to create group')
    } finally {
      setCreating(false)
    }
  }

  async function handleAcceptInvite(e: FormEvent) {
    e.preventDefault()
    if (!userId) return
    setJoining(true)
    setError(null)
    try {
      await groupsApi.acceptInvitation(inviteToken, userId)
      setInviteToken('')
      // Accepting doesn't return the group id, so it can't be remembered
      // locally here — see the group members page for looking it up once
      // you know the id another way.
    } catch {
      setError('Failed to accept invitation (expired, wrong token, or already used)')
    } finally {
      setJoining(false)
    }
  }

  return (
    <div className="page">
      <h1>Your groups</h1>

      <NotWiredNotice>
        group-service has no "list my groups" endpoint, so this list is only what your browser remembers locally
        after you create or are shown a group — it won't reflect groups from another device, or groups you joined
        via invitation (accepting one doesn't return the group id).
      </NotWiredNotice>

      <ul className="list">
        {groups.map((g) => (
          <li key={g.id}>
            <Link to={`/groups/${g.id}`}>{g.name}</Link> <code>{g.id}</code>
          </li>
        ))}
        {groups.length === 0 && <li>No known groups yet — create one below.</li>}
      </ul>

      <section className="card">
        <h2>Create a group</h2>
        <form onSubmit={handleCreate}>
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            Description
            <input value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          <button type="submit" disabled={creating}>
            {creating ? 'Creating…' : 'Create group'}
          </button>
        </form>
      </section>

      <section className="card">
        <h2>Accept an invitation</h2>
        <form onSubmit={handleAcceptInvite}>
          <label>
            Invitation token
            <input value={inviteToken} onChange={(e) => setInviteToken(e.target.value)} required placeholder="uuid from an invite link" />
          </label>
          <button type="submit" disabled={joining}>
            {joining ? 'Joining…' : 'Accept'}
          </button>
        </form>
      </section>

      {error && <p className="error">{error}</p>}

      <button type="button" onClick={() => navigate('/profile/settings')}>
        Profile / settings
      </button>
    </div>
  )
}
