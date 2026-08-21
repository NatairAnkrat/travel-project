import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import * as groupsApi from '../api/groups'

export function GroupDetailPage() {
  const { groupId } = useParams<{ groupId: string }>()
  const { userId } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const membersQuery = useQuery({
    queryKey: ['group-members', groupId],
    queryFn: () => groupsApi.listMembers(groupId!),
    enabled: !!groupId,
  })

  const [inviteEmail, setInviteEmail] = useState('')
  const [inviting, setInviting] = useState(false)
  const [lastInviteToken, setLastInviteToken] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleInvite(e: FormEvent) {
    e.preventDefault()
    if (!groupId || !userId) return
    setInviting(true)
    setError(null)
    try {
      const { invitation_token } = await groupsApi.inviteMember(groupId, { email: inviteEmail, created_by: userId })
      setLastInviteToken(invitation_token)
      setInviteEmail('')
    } catch {
      setError('Failed to invite — you may not be a member of this group')
    } finally {
      setInviting(false)
    }
  }

  async function handleLeave() {
    if (!groupId || !userId) return
    try {
      await groupsApi.leaveGroup(groupId, userId)
      navigate('/groups')
    } catch {
      setError('Failed to leave — group owners cannot leave (transfer ownership isn\'t supported by the backend)')
    }
  }

  if (!groupId) return null

  return (
    <div className="page">
      <h1>Group members</h1>
      <p>
        <code>{groupId}</code>
      </p>

      {membersQuery.isLoading && <p>Loading…</p>}
      {membersQuery.isError && <p className="error">Failed to load members</p>}
      <ul className="list">
        {membersQuery.data?.map((m) => (
          <li key={m.userId}>
            {m.login} — {m.roleCode} ({m.status})
          </li>
        ))}
      </ul>

      <section className="card">
        <h2>Invite by email</h2>
        <form onSubmit={handleInvite}>
          <label>
            Email
            <input type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} required />
          </label>
          <button type="submit" disabled={inviting}>
            {inviting ? 'Inviting…' : 'Invite'}
          </button>
        </form>
        {lastInviteToken && (
          <p>
            Invitation token (share this with the invitee): <code>{lastInviteToken}</code>
          </p>
        )}
      </section>

      {error && <p className="error">{error}</p>}

      <div className="actions">
        <Link to={`/groups/${groupId}/travels/new`}>
          <button type="button">Plan a travel with this group</button>
        </Link>
        <button type="button" onClick={handleLeave}>
          Leave group
        </button>
        <button type="button" onClick={() => queryClient.invalidateQueries({ queryKey: ['group-members', groupId] })}>
          Refresh members
        </button>
      </div>
    </div>
  )
}
