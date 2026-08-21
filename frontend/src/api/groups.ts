import { groupApi } from '../lib/apiClient'
import type { CreateGroupRequest, GroupMemberView, InviteRequest } from './types'

export function createGroup(req: CreateGroupRequest): Promise<{ group_id: string }> {
  return groupApi('/api/v1/groups', { method: 'POST', body: req })
}

export function inviteMember(groupId: string, req: InviteRequest): Promise<{ invitation_token: string }> {
  return groupApi(`/api/v1/groups/${groupId}/invitations`, { method: 'POST', body: req })
}

export function acceptInvitation(token: string, userId: string): Promise<void> {
  return groupApi(`/api/v1/groups/invitations/${token}/accept`, { method: 'POST', body: { user_id: userId } })
}

export function declineInvitation(token: string): Promise<void> {
  return groupApi(`/api/v1/groups/invitations/${token}/decline`, { method: 'POST' })
}

export function listMembers(groupId: string): Promise<GroupMemberView[]> {
  return groupApi(`/api/v1/groups/${groupId}/members`)
}

export function leaveGroup(groupId: string, userId: string): Promise<void> {
  return groupApi(`/api/v1/groups/${groupId}/leave`, { method: 'POST', body: { user_id: userId } })
}
