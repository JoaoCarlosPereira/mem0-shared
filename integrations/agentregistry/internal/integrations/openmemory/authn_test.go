package openmemory

import (
	"context"
	"net/url"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/stretchr/testify/require"

	"github.com/agentregistry-dev/agentregistry/pkg/api/v1alpha1"
	"github.com/agentregistry-dev/agentregistry/pkg/registry/auth"
	"github.com/agentregistry-dev/agentregistry/pkg/types"
)

func TestAuthenticateJWT_OK(t *testing.T) {
	secret := []byte("test-secret-32-bytes-minimum!!")
	a := &Authn{JWTSecret: secret, AdminEmails: map[string]struct{}{"admin@ex.com": {}}}
	tok := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		"sub":   "user-1",
		"email": "admin@ex.com",
		"name":  "Admin",
		"exp":   time.Now().Add(time.Hour).Unix(),
		"iat":   time.Now().Unix(),
	})
	raw, err := tok.SignedString(secret)
	require.NoError(t, err)

	s, err := a.Authenticate(context.Background(), func(string) string { return "Bearer " + raw }, url.Values{})
	require.NoError(t, err)
	om := s.(*Session)
	require.Equal(t, "user-1", om.UserID)
	require.True(t, om.Admin)
}

func TestAuthenticateJWT_Expired(t *testing.T) {
	secret := []byte("test-secret-32-bytes-minimum!!")
	a := &Authn{JWTSecret: secret}
	tok := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		"sub": "user-1",
		"exp": time.Now().Add(-time.Hour).Unix(),
	})
	raw, err := tok.SignedString(secret)
	require.NoError(t, err)
	_, err = a.Authenticate(context.Background(), func(string) string { return "Bearer " + raw }, url.Values{})
	require.ErrorIs(t, err, auth.ErrUnauthenticated)
}

func TestAuthenticate_Missing(t *testing.T) {
	a := &Authn{JWTSecret: []byte("x")}
	_, err := a.Authenticate(context.Background(), func(string) string { return "" }, url.Values{})
	require.ErrorIs(t, err, auth.ErrUnauthenticated)
}

func TestAuthenticate_AgentTokenWithoutPool(t *testing.T) {
	a := &Authn{JWTSecret: []byte("x")}
	_, err := a.Authenticate(context.Background(), func(string) string { return "Bearer omtk_abc" }, url.Values{})
	require.ErrorIs(t, err, auth.ErrUnauthenticated)
}

func TestAuthenticate_LegacyGated(t *testing.T) {
	a := &Authn{JWTSecret: []byte("x"), AllowLegacy: true}
	s, err := a.Authenticate(context.Background(), func(string) string { return "Bearer local" }, url.Values{})
	require.NoError(t, err)
	require.Equal(t, "legacy", s.(*Session).Method)

	a.AllowLegacy = false
	_, err = a.Authenticate(context.Background(), func(string) string { return "Bearer local" }, url.Values{})
	require.ErrorIs(t, err, auth.ErrUnauthenticated)
}

func TestAuthz_DeployDenied(t *testing.T) {
	z := NewAuthz()
	s := &Session{UserID: "u", Admin: false}
	err := z.Check(context.Background(), s, auth.PermissionActionDeploy, auth.Resource{Name: "x"})
	require.ErrorIs(t, err, auth.ErrForbidden)

	s.Admin = true
	require.NoError(t, z.Check(context.Background(), s, auth.PermissionActionDeploy, auth.Resource{Name: "x"}))
}

func TestAuthz_ReadAllowed(t *testing.T) {
	z := NewAuthz()
	s := &Session{UserID: "u"}
	require.NoError(t, z.Check(context.Background(), s, auth.PermissionActionRead, auth.Resource{Name: "skill"}))
	require.NoError(t, z.Check(context.Background(), s, auth.PermissionActionPublish, auth.Resource{Name: "skill"}))
}

func TestDenyDeployAuthorizer(t *testing.T) {
	err := DenyDeployAuthorizer(context.Background(), types.AuthorizeInput{Verb: "apply", Kind: "Deployment"})
	require.ErrorIs(t, err, auth.ErrForbidden)
}

func TestCatalogAuthorizer_AllowsAuthenticatedSkillApply(t *testing.T) {
	ctx := auth.AuthSessionTo(context.Background(), &Session{UserID: "u"})
	err := CatalogAuthorizer(NewAuthz())(ctx, types.AuthorizeInput{
		Verb: "apply",
		Kind: v1alpha1.KindSkill,
		Name: "mem0-cli",
		Tag:  "latest",
	})
	require.NoError(t, err)

	err = CatalogAuthorizer(NewAuthz())(context.Background(), types.AuthorizeInput{
		Verb: "apply",
		Kind: v1alpha1.KindSkill,
		Name: "mem0-cli",
		Tag:  "latest",
	})
	require.ErrorIs(t, err, auth.ErrUnauthenticated)
}

func TestNewAuthnFromEnv_RequiresSecret(t *testing.T) {
	t.Setenv("AUTH_JWT_SECRET", "")
	t.Setenv("MEM0_AUTH_ALLOW_LEGACY", "")
	_, err := NewAuthnFromEnv(nil)
	require.Error(t, err)
	require.Contains(t, err.Error(), "AUTH_JWT_SECRET")
}

func TestNewAuthnFromEnv_OK(t *testing.T) {
	t.Setenv("AUTH_JWT_SECRET", "unit-test-secret-value-32bytes!!")
	t.Setenv("AUTH_ADMIN_EMAILS", "a@ex.com, b@ex.com")
	t.Setenv("MEM0_AUTH_ALLOW_LEGACY", "1")
	a, err := NewAuthnFromEnv(nil)
	require.NoError(t, err)
	require.True(t, a.AllowLegacy)
	require.Contains(t, a.AdminEmails, "a@ex.com")
	require.Contains(t, a.AdminEmails, "b@ex.com")
}
