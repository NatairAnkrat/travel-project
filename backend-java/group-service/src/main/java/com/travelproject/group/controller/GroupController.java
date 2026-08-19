package com.travelproject.group.controller;

import com.travelproject.group.dto.*;
import com.travelproject.group.repository.AuditLogRepository;
import com.travelproject.group.repository.GroupRepository;
import com.travelproject.group.repository.InvitationRepository;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/groups")
public class GroupController {

    private final GroupRepository groupRepository;
    private final InvitationRepository invitationRepository;
    private final AuditLogRepository auditLogRepository;

    public GroupController(GroupRepository groupRepository, InvitationRepository invitationRepository,
                            AuditLogRepository auditLogRepository) {
        this.groupRepository = groupRepository;
        this.invitationRepository = invitationRepository;
        this.auditLogRepository = auditLogRepository;
    }

    @PostMapping
    public ResponseEntity<Map<String, UUID>> createGroup(@RequestBody CreateGroupRequest req, HttpServletRequest http) {
        UUID groupId = groupRepository.createGroup(req.name(), req.description());

        UUID ownerRoleId = groupRepository.findRoleIdByCode("owner")
                .orElseThrow(() -> new IllegalStateException("group_roles missing 'owner' — seed it first"));
        groupRepository.addMember(groupId, req.createdBy(), ownerRoleId, "active");

        auditLogRepository.log(req.createdBy(), "travel_groups", groupId, "CREATE",
                "{\"name\":\"" + req.name() + "\"}", http.getRemoteAddr());

        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("group_id", groupId));
    }

    @PostMapping("/{groupId}/invitations")
    public ResponseEntity<Map<String, UUID>> invite(@PathVariable UUID groupId, @RequestBody InviteRequest req,
                                                      HttpServletRequest http) {
        if (!groupRepository.isMember(groupId, req.createdBy())) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
        }
        UUID token = invitationRepository.createInvitation(groupId, req.email(), req.createdBy());

        auditLogRepository.log(req.createdBy(), "invitations", token, "CREATE",
                "{\"email\":\"" + req.email() + "\",\"group_id\":\"" + groupId + "\"}", http.getRemoteAddr());

        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("invitation_token", token));
    }

    @PostMapping("/invitations/{token}/accept")
    public ResponseEntity<Void> acceptInvitation(@PathVariable UUID token, @RequestBody AcceptInviteRequest req,
                                                  HttpServletRequest http) {
        var invitation = invitationRepository.findByToken(token);
        if (invitation.isEmpty() || !"pending".equals(invitation.get().status())) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
        }
        var inv = invitation.get();
        if (inv.expiresAt().isBefore(java.time.OffsetDateTime.now())) {
            invitationRepository.updateStatus(inv.id(), "expired");
            return ResponseEntity.status(HttpStatus.GONE).build();
        }

        UUID memberRoleId = groupRepository.findRoleIdByCode("member")
                .orElseThrow(() -> new IllegalStateException("group_roles missing 'member' — seed it first"));
        groupRepository.addMember(inv.groupId(), req.userId(), memberRoleId, "active");
        invitationRepository.updateStatus(inv.id(), "accepted");

        auditLogRepository.log(req.userId(), "group_members", inv.groupId(), "CREATE", null, http.getRemoteAddr());

        return ResponseEntity.ok().build();
    }

    @PostMapping("/invitations/{token}/decline")
    public ResponseEntity<Void> declineInvitation(@PathVariable UUID token) {
        var invitation = invitationRepository.findByToken(token);
        if (invitation.isEmpty()) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
        }
        invitationRepository.updateStatus(invitation.get().id(), "declined");
        return ResponseEntity.ok().build();
    }
	
    @GetMapping("/{groupId}/members")
    public ResponseEntity<java.util.List<GroupMemberView>> listMembers(@PathVariable UUID groupId) {
        var members = groupRepository.listMembers(groupId).stream()
                .map(m -> new GroupMemberView(m.userId(), m.login(), m.roleCode(), m.status()))
                .toList();
        return ResponseEntity.ok(members);
    }

    @PostMapping("/{groupId}/leave")
    public ResponseEntity<Void> leaveGroup(@PathVariable UUID groupId, @RequestBody LeaveGroupRequest req,
                                            HttpServletRequest http) {
        var role = groupRepository.findMemberRole(groupId, req.userId());
        if (role.isEmpty()) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).build();
        }
        if ("owner".equals(role.get())) {
            // Владелец не может просто выйти — иначе группа осталась бы без ответственного.
            // Передача владения — отдельная операция, которой пока нет; блокируем выход явным 409
            return ResponseEntity.status(HttpStatus.CONFLICT).build();
        }

        groupRepository.removeMember(groupId, req.userId());
        auditLogRepository.log(req.userId(), "group_members", groupId, "DELETE", null, http.getRemoteAddr());

        return ResponseEntity.noContent().build();
    }
}