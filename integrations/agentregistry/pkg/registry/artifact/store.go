package artifact

import (
	"context"
	"io"
)

type SkillRef struct {
	Namespace string
	Name      string
	Tag       string
}

type Descriptor struct {
	Digest    string
	MediaType string
	Size      int64
}

type Artifact struct {
	Descriptor
	Archive []byte
}

// ArtifactStore persists complete, validated Skill archives. Implementations
// must associate one archive with each namespace/name/tag Skill identity.
type ArtifactStore interface {
	Put(ctx context.Context, ref SkillRef, archive []byte) (Descriptor, error)
	Get(ctx context.Context, ref SkillRef) (*Artifact, error)
	Open(ctx context.Context, ref SkillRef) (Descriptor, io.ReadCloser, error)
	ListFiles(ctx context.Context, ref SkillRef) ([]File, error)
}
