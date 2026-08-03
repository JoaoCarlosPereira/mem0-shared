package openmemory

import (
	"context"
	"strings"

	"github.com/agentregistry-dev/agentregistry/pkg/api/v1alpha1"
	"github.com/agentregistry-dev/agentregistry/pkg/registry/auth"
	"github.com/agentregistry-dev/agentregistry/pkg/types"
)

// Authz is fail-closed Mem0 authorization for the MVP store.
// Authenticated users may read/publish/edit/delete catalog artifacts.
// Deploy is denied unless the session is marked Admin.
type Authz struct{}

func NewAuthz() *Authz { return &Authz{} }

func (a *Authz) Check(_ context.Context, s auth.Session, verb auth.PermissionAction, resource auth.Resource) error {
	if s == nil {
		return auth.ErrUnauthenticated
	}
	if verb == auth.PermissionActionDeploy {
		om, ok := s.(*Session)
		if !ok || !om.Admin {
			return auth.ErrForbidden
		}
		return nil
	}
	for _, p := range s.Principal().User.Permissions {
		if p.Action == verb && (p.ResourcePattern == "*" || p.ResourcePattern == resource.Name) {
			return nil
		}
	}
	return auth.ErrForbidden
}

func (a *Authz) IsRegistryAdmin(_ context.Context, s auth.Session) bool {
	om, ok := s.(*Session)
	return ok && om != nil && om.Admin
}

// CatalogAuthorizer gates regular catalog operations through the configured
// Authz provider. mem0registry wires it for every non-Deployment kind so the
// batch apply endpoint stays fail-closed without blocking Skill/Prompt seeds.
func CatalogAuthorizer(provider auth.AuthzProvider) types.Authorizer {
	return func(ctx context.Context, in types.AuthorizeInput) error {
		if provider == nil {
			return nil
		}
		action := actionForVerb(in.Verb)
		resource := auth.Resource{
			Name: in.Name,
			Type: artifactTypeForKind(in.Kind),
		}
		return (&auth.Authorizer{Authz: provider}).Check(ctx, action, resource)
	}
}

func actionForVerb(verb string) auth.PermissionAction {
	switch verb {
	case "get", "list":
		return auth.PermissionActionRead
	case "delete":
		return auth.PermissionActionDelete
	case "apply":
		return auth.PermissionActionPublish
	default:
		return auth.PermissionActionEdit
	}
}

func artifactTypeForKind(kind string) auth.PermissionArtifactType {
	switch kind {
	case v1alpha1.KindAgent:
		return auth.PermissionArtifactTypeAgent
	case v1alpha1.KindMCPServer:
		return auth.PermissionArtifactTypeServer
	case v1alpha1.KindSkill:
		return auth.PermissionArtifactTypeSkill
	case v1alpha1.KindPrompt:
		return auth.PermissionArtifactTypePrompt
	case v1alpha1.KindRuntime:
		return auth.PermissionArtifactTypeRuntime
	default:
		return auth.PermissionArtifactType(strings.ToLower(kind))
	}
}

// DenyDeployAuthorizer rejects all Deployment handler verbs in the MVP.
func DenyDeployAuthorizer(_ context.Context, _ types.AuthorizeInput) error {
	return auth.ErrForbidden
}
