package openmemory

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/agentregistry-dev/agentregistry/pkg/registry/auth"
)

const agentTokenPrefix = "omtk_"

// Authn validates Mem0 Shared credentials (session JWT HS256 and/or omtk_ tokens).
type Authn struct {
	JWTSecret   []byte
	Pool        *pgxpool.Pool // optional; required for omtk_ lookup
	AdminEmails map[string]struct{}
	AllowLegacy bool // when true, Bearer "local" is accepted (LAN legacy)

	poolOnce sync.Once
	poolErr  error
}

func NewAuthnFromEnv(pool *pgxpool.Pool) (*Authn, error) {
	secret := strings.TrimSpace(os.Getenv("AUTH_JWT_SECRET"))
	if secret == "" {
		return nil, errors.New("AUTH_JWT_SECRET is required for mem0registry")
	}
	admins := map[string]struct{}{}
	for _, e := range strings.Split(os.Getenv("AUTH_ADMIN_EMAILS"), ",") {
		e = strings.ToLower(strings.TrimSpace(e))
		if e != "" {
			admins[e] = struct{}{}
		}
	}
	legacy := strings.TrimSpace(os.Getenv("MEM0_AUTH_ALLOW_LEGACY")) == "1"
	return &Authn{
		JWTSecret:   []byte(secret),
		Pool:        pool,
		AdminEmails: admins,
		AllowLegacy: legacy,
	}, nil
}

func (a *Authn) Authenticate(ctx context.Context, headers func(string) string, query url.Values) (auth.Session, error) {
	raw := bearerToken(headers("Authorization"))
	if raw == "" {
		raw = strings.TrimSpace(query.Get("token"))
	}
	if raw == "" {
		return nil, auth.ErrUnauthenticated
	}
	if a.AllowLegacy && raw == "local" {
		return &Session{UserID: "legacy", Email: "", Name: "legacy", Method: "legacy", Admin: false}, nil
	}
	if strings.HasPrefix(raw, agentTokenPrefix) {
		return a.authenticateAgentToken(ctx, raw)
	}
	return a.authenticateJWT(raw)
}

func (a *Authn) authenticateJWT(raw string) (auth.Session, error) {
	tok, err := jwt.Parse(raw, func(t *jwt.Token) (any, error) {
		if t.Method.Alg() != jwt.SigningMethodHS256.Alg() {
			return nil, fmt.Errorf("unexpected alg %s", t.Method.Alg())
		}
		return a.JWTSecret, nil
	}, jwt.WithValidMethods([]string{jwt.SigningMethodHS256.Alg()}))
	if err != nil || !tok.Valid {
		return nil, auth.ErrUnauthenticated
	}
	claims, ok := tok.Claims.(jwt.MapClaims)
	if !ok {
		return nil, auth.ErrUnauthenticated
	}
	sub, _ := claims["sub"].(string)
	if sub == "" {
		// numeric sub from some issuers
		if n, ok := claims["sub"].(float64); ok {
			sub = fmt.Sprintf("%.0f", n)
		}
	}
	if sub == "" {
		return nil, auth.ErrUnauthenticated
	}
	email, _ := claims["email"].(string)
	name, _ := claims["name"].(string)
	_, admin := a.AdminEmails[strings.ToLower(email)]
	return &Session{UserID: sub, Email: email, Name: name, Method: "jwt", Admin: admin}, nil
}

func (a *Authn) authenticateAgentToken(ctx context.Context, raw string) (auth.Session, error) {
	pool, err := a.pool(ctx)
	if err != nil || pool == nil {
		return nil, auth.ErrUnauthenticated
	}
	sum := sha256.Sum256([]byte(raw))
	digest := hex.EncodeToString(sum[:])
	var userID string
	var revoked *time.Time
	err = pool.QueryRow(ctx, `
		SELECT user_id::text, revoked_at
		FROM public.agent_tokens
		WHERE token_hash = $1
		LIMIT 1
	`, digest).Scan(&userID, &revoked)
	if err != nil || userID == "" || revoked != nil {
		return nil, auth.ErrUnauthenticated
	}
	return &Session{UserID: userID, Method: "agent_token", Admin: false}, nil
}

func (a *Authn) pool(ctx context.Context) (*pgxpool.Pool, error) {
	if a.Pool != nil {
		return a.Pool, nil
	}
	a.poolOnce.Do(func() {
		dsn := strings.TrimSpace(os.Getenv("AGENT_REGISTRY_DATABASE_URL"))
		if dsn == "" {
			dsn = strings.TrimSpace(os.Getenv("DATABASE_URL"))
		}
		if dsn == "" {
			a.poolErr = errors.New("no DATABASE_URL for agent token lookup")
			return
		}
		p, err := pgxpool.New(ctx, dsn)
		if err != nil {
			a.poolErr = err
			return
		}
		a.Pool = p
	})
	return a.Pool, a.poolErr
}

func bearerToken(h string) string {
	h = strings.TrimSpace(h)
	if h == "" {
		return ""
	}
	const p = "Bearer "
	if len(h) > len(p) && strings.EqualFold(h[:len(p)], p) {
		return strings.TrimSpace(h[len(p):])
	}
	return ""
}
