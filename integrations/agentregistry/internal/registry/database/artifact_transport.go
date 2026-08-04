package database

import (
	"bytes"
	"context"
	"crypto/sha256"
	"errors"
	"fmt"
	"io"

	"github.com/agentregistry-dev/agentregistry/pkg/registry/artifact"
	pkgdb "github.com/agentregistry-dev/agentregistry/pkg/registry/database"
	"github.com/agentregistry-dev/agentregistry/pkg/types"
)

// SkillArtifactTransportStore adapts the core ArtifactStore to the public HTTP
// transport contract without exposing PostgreSQL details to handlers.
type SkillArtifactTransportStore struct {
	store    artifact.ArtifactStore
	afterPut func(context.Context, artifact.SkillRef) error
}

func NewSkillArtifactTransportStore(store artifact.ArtifactStore, afterPut func(context.Context, artifact.SkillRef) error) *SkillArtifactTransportStore {
	return &SkillArtifactTransportStore{store: store, afterPut: afterPut}
}

func (s *SkillArtifactTransportStore) Put(ctx context.Context, key types.SkillArtifactKey, content io.Reader, opts types.SkillArtifactPutOptions) (types.SkillArtifact, error) {
	if content == nil {
		return types.SkillArtifact{}, fmt.Errorf("%w: artifact content is required", pkgdb.ErrInvalidInput)
	}
	data, err := io.ReadAll(io.LimitReader(content, artifact.MaxArchiveBytes+1))
	if err != nil {
		return types.SkillArtifact{}, fmt.Errorf("read skill artifact: %w", err)
	}
	if int64(len(data)) > artifact.MaxArchiveBytes {
		return types.SkillArtifact{}, fmt.Errorf("%w: artifact exceeds %d bytes", pkgdb.ErrInvalidInput, artifact.MaxArchiveBytes)
	}
	if opts.Size >= 0 && opts.Size != int64(len(data)) {
		return types.SkillArtifact{}, fmt.Errorf("%w: artifact size mismatch", pkgdb.ErrInvalidInput)
	}
	sum := sha256.Sum256(data)
	if len(opts.SHA256) > 0 && !bytes.Equal(opts.SHA256, sum[:]) {
		return types.SkillArtifact{}, fmt.Errorf("%w: artifact digest mismatch", pkgdb.ErrInvalidInput)
	}
	ref := artifact.SkillRef{Namespace: key.Namespace, Name: key.Name, Tag: key.Tag}
	descriptor, err := s.store.Put(ctx, ref, data)
	if err != nil {
		if errors.Is(err, artifact.ErrInvalidArchive) {
			return types.SkillArtifact{}, fmt.Errorf("%w: %v", pkgdb.ErrInvalidInput, err)
		}
		return types.SkillArtifact{}, err
	}
	if s.afterPut == nil {
		return types.SkillArtifact{}, errors.New("refresh skill artifact status: callback is required")
	}
	if err := s.afterPut(ctx, ref); err != nil {
		return types.SkillArtifact{}, fmt.Errorf("refresh skill artifact status: %w", err)
	}
	return types.SkillArtifact{Size: descriptor.Size, SHA256: sum[:]}, nil
}

func (s *SkillArtifactTransportStore) Get(ctx context.Context, key types.SkillArtifactKey) (types.SkillArtifact, error) {
	descriptor, content, err := s.store.Open(ctx, artifact.SkillRef{Namespace: key.Namespace, Name: key.Name, Tag: key.Tag})
	if err != nil {
		return types.SkillArtifact{}, err
	}
	digest, err := decodeDigest(descriptor.Digest)
	if err != nil {
		_ = content.Close()
		return types.SkillArtifact{}, err
	}
	return types.SkillArtifact{Content: content, Size: descriptor.Size, SHA256: digest}, nil
}

func decodeDigest(value string) ([]byte, error) {
	if len(value) != sha256.Size*2 {
		return nil, errors.New("invalid stored SHA-256 digest")
	}
	out := make([]byte, sha256.Size)
	for i := range out {
		hi, ok := fromHex(value[i*2])
		if !ok {
			return nil, errors.New("invalid stored SHA-256 digest")
		}
		lo, ok := fromHex(value[i*2+1])
		if !ok {
			return nil, errors.New("invalid stored SHA-256 digest")
		}
		out[i] = hi<<4 | lo
	}
	return out, nil
}

func fromHex(value byte) (byte, bool) {
	switch {
	case value >= '0' && value <= '9':
		return value - '0', true
	case value >= 'a' && value <= 'f':
		return value - 'a' + 10, true
	case value >= 'A' && value <= 'F':
		return value - 'A' + 10, true
	default:
		return 0, false
	}
}
