package openmemory

import "github.com/agentregistry-dev/agentregistry/pkg/registry/auth"

// Session is an authenticated Mem0 Shared identity.
type Session struct {
	UserID string
	Email  string
	Name   string
	Method string // jwt | agent_token | legacy
	Admin  bool
}

func (s *Session) Principal() auth.Principal {
	perms := []auth.Permission{
		{Action: auth.PermissionActionRead, ResourcePattern: "*"},
		{Action: auth.PermissionActionPublish, ResourcePattern: "*"},
		{Action: auth.PermissionActionEdit, ResourcePattern: "*"},
		{Action: auth.PermissionActionDelete, ResourcePattern: "*"},
	}
	if s.Admin {
		perms = append(perms, auth.Permission{Action: auth.PermissionActionDeploy, ResourcePattern: "*"})
	}
	return auth.Principal{User: auth.User{Permissions: perms}}
}
