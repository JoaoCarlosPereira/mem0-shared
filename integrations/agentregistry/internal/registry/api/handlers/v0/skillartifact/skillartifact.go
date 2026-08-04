// Package skillartifact owns the Skill artifact upload/download subresource.
package skillartifact

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"mime"
	"net/http"
	"net/url"
	"strconv"
	"strings"

	"github.com/danielgtaylor/huma/v2"

	"github.com/agentregistry-dev/agentregistry/pkg/api/v1alpha1"
	pkgdb "github.com/agentregistry-dev/agentregistry/pkg/registry/database"
	"github.com/agentregistry-dev/agentregistry/pkg/registry/resource"
	"github.com/agentregistry-dev/agentregistry/pkg/types"
)

const MediaType = "application/vnd.agentregistry.skill.v1.tar+gzip"

type Config struct {
	BasePrefix string
	Store      types.SkillArtifactStore
	Authorize  func(context.Context, resource.AuthorizeInput) error
}

type artifactInput struct {
	Namespace string `query:"namespace" doc:"Namespace (defaults to 'default')."`
	Name      string `path:"name"`
	Tag       string `path:"tag"`
}

type putArtifactInput struct {
	Namespace string `query:"namespace" doc:"Namespace (defaults to 'default')."`
	Name      string `path:"name"`
	Tag       string `path:"tag"`
	Digest    string `header:"Digest" doc:"Optional RFC 3230 SHA-256 digest (sha-256=<base64>)."`
	RawBody   []byte `contentType:"application/vnd.agentregistry.skill.v1.tar+gzip"`
}

type putArtifactOutput struct {
	ETag   string `header:"ETag"`
	Digest string `header:"Digest"`
}

func Register(api huma.API, cfg Config) {
	if cfg.Store == nil {
		return
	}
	path := strings.TrimRight(cfg.BasePrefix, "/") + "/skills/{name}/{tag}/artifact"

	huma.Register(api, huma.Operation{
		OperationID:   "put-skill-artifact",
		Method:        http.MethodPut,
		Path:          path,
		Summary:       "Upload an immutable Skill tar.gz artifact",
		Tags:          []string{"skills"},
		DefaultStatus: http.StatusCreated,
	}, func(ctx context.Context, in *putArtifactInput) (*putArtifactOutput, error) {
		key, err := resolveKey(in.Namespace, in.Name, in.Tag)
		if err != nil {
			return nil, err
		}
		if cfg.Authorize != nil {
			if err := cfg.Authorize(ctx, resource.AuthorizeInput{
				Verb: "update", Kind: v1alpha1.KindSkill,
				Namespace: key.Namespace, Name: key.Name, Tag: key.Tag,
			}); err != nil {
				return nil, err
			}
		}
		if len(in.RawBody) == 0 {
			return nil, huma.Error422UnprocessableEntity("artifact body must not be empty")
		}

		sum := sha256.Sum256(in.RawBody)
		if err := validateDigest(in.Digest, sum[:]); err != nil {
			return nil, huma.Error422UnprocessableEntity(err.Error())
		}
		artifact, err := cfg.Store.Put(ctx, key, bytes.NewReader(in.RawBody), types.SkillArtifactPutOptions{
			Size:   int64(len(in.RawBody)),
			SHA256: append([]byte(nil), sum[:]...),
		})
		if err != nil {
			return nil, mapStoreError(err, key, "store")
		}
		digest := artifact.SHA256
		if len(digest) == 0 {
			digest = sum[:]
		}
		return &putArtifactOutput{ETag: etag(digest), Digest: digestHeader(digest)}, nil
	})

	huma.Register(api, huma.Operation{
		OperationID: "get-skill-artifact",
		Method:      http.MethodGet,
		Path:        path,
		Summary:     "Download a Skill tar.gz artifact",
		Tags:        []string{"skills"},
	}, func(ctx context.Context, in *artifactInput) (*huma.StreamResponse, error) {
		key, err := resolveKey(in.Namespace, in.Name, in.Tag)
		if err != nil {
			return nil, err
		}
		if cfg.Authorize != nil {
			if err := cfg.Authorize(ctx, resource.AuthorizeInput{
				Verb: "get", Kind: v1alpha1.KindSkill,
				Namespace: key.Namespace, Name: key.Name, Tag: key.Tag,
			}); err != nil {
				return nil, err
			}
		}
		artifact, err := cfg.Store.Get(ctx, key)
		if err != nil {
			return nil, mapStoreError(err, key, "load")
		}
		if artifact.Content == nil || artifact.Size < 0 || len(artifact.SHA256) != sha256.Size {
			if artifact.Content != nil {
				_ = artifact.Content.Close()
			}
			return nil, huma.Error500InternalServerError("load Skill artifact", errors.New("artifact store returned invalid metadata"))
		}

		return &huma.StreamResponse{Body: func(hctx huma.Context) {
			defer artifact.Content.Close()
			hctx.SetHeader("Content-Type", MediaType)
			hctx.SetHeader("Content-Disposition", mime.FormatMediaType("attachment", map[string]string{
				"filename": key.Name + "-" + key.Tag + ".tar.gz",
			}))
			hctx.SetHeader("Content-Length", strconv.FormatInt(artifact.Size, 10))
			hctx.SetHeader("ETag", etag(artifact.SHA256))
			hctx.SetHeader("Digest", digestHeader(artifact.SHA256))
			hctx.SetHeader("X-Content-Type-Options", "nosniff")
			_, _ = io.Copy(hctx.BodyWriter(), artifact.Content)
		}}, nil
	})
}

func resolveKey(namespace, rawName, rawTag string) (types.SkillArtifactKey, error) {
	if namespace == "" {
		namespace = v1alpha1.DefaultNamespace
	}
	if rawName == "" || rawTag == "" {
		return types.SkillArtifactKey{}, huma.Error422UnprocessableEntity("Skill artifact name and tag are required")
	}
	name, err := url.PathUnescape(rawName)
	if err != nil {
		return types.SkillArtifactKey{}, huma.Error422UnprocessableEntity("invalid name path segment: " + err.Error())
	}
	tag, err := url.PathUnescape(rawTag)
	if err != nil {
		return types.SkillArtifactKey{}, huma.Error422UnprocessableEntity("invalid tag path segment: " + err.Error())
	}
	probe := &v1alpha1.Skill{Metadata: v1alpha1.ObjectMeta{Namespace: namespace, Name: name, Tag: tag}, Spec: v1alpha1.SkillSpec{Title: "artifact"}}
	if err := probe.Validate(); err != nil {
		return types.SkillArtifactKey{}, huma.Error422UnprocessableEntity("invalid Skill artifact identity: " + err.Error())
	}
	return types.SkillArtifactKey{Namespace: namespace, Name: name, Tag: tag}, nil
}

func validateDigest(value string, actual []byte) error {
	if value == "" {
		return nil
	}
	const prefix = "sha-256="
	if !strings.HasPrefix(value, prefix) || strings.Contains(value[len(prefix):], ",") {
		return fmt.Errorf("Digest must use sha-256=<base64>")
	}
	expected, err := base64.StdEncoding.DecodeString(strings.TrimSpace(strings.TrimPrefix(value, prefix)))
	if err != nil || len(expected) != sha256.Size {
		return fmt.Errorf("Digest contains an invalid SHA-256 value")
	}
	if !bytes.Equal(expected, actual) {
		return fmt.Errorf("Digest does not match the uploaded artifact")
	}
	return nil
}

func mapStoreError(err error, key types.SkillArtifactKey, operation string) error {
	switch {
	case errors.Is(err, pkgdb.ErrNotFound):
		return huma.Error404NotFound(fmt.Sprintf("Skill artifact %q/%q@%q not found", key.Namespace, key.Name, key.Tag))
	case errors.Is(err, pkgdb.ErrAlreadyExists):
		return huma.Error409Conflict(fmt.Sprintf("Skill artifact %q/%q@%q already exists", key.Namespace, key.Name, key.Tag))
	case errors.Is(err, pkgdb.ErrInvalidInput):
		return huma.Error422UnprocessableEntity("invalid Skill artifact: " + err.Error())
	default:
		return huma.Error500InternalServerError(operation+" Skill artifact", err)
	}
}

func digestHeader(digest []byte) string {
	return "sha-256=" + base64.StdEncoding.EncodeToString(digest)
}

func etag(digest []byte) string {
	return `"sha256:` + hex.EncodeToString(digest) + `"`
}
