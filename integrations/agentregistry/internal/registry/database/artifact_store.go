package database

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/agentregistry-dev/agentregistry/pkg/registry/artifact"
	pkgdb "github.com/agentregistry-dev/agentregistry/pkg/registry/database"
)

type PostgresArtifactStore struct {
	pool                *pgxpool.Pool
	artifactsTable      string
	skillArtifactsTable string
}

func NewPostgresArtifactStore(pool *pgxpool.Pool, schema pkgdb.Schema) *PostgresArtifactStore {
	return &PostgresArtifactStore{
		pool:                pool,
		artifactsTable:      schema.Qualify("artifacts"),
		skillArtifactsTable: schema.Qualify("skill_artifacts"),
	}
}

func (s *PostgresArtifactStore) Put(ctx context.Context, ref artifact.SkillRef, archive []byte) (artifact.Descriptor, error) {
	if err := validateArtifactRef(ref); err != nil {
		return artifact.Descriptor{}, err
	}
	if _, err := artifact.Validate(archive); err != nil {
		return artifact.Descriptor{}, err
	}
	sum := sha256.Sum256(archive)
	descriptor := artifact.Descriptor{
		Digest:    hex.EncodeToString(sum[:]),
		MediaType: artifact.MediaTypeTarGzip,
		Size:      int64(len(archive)),
	}
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return artifact.Descriptor{}, fmt.Errorf("begin skill artifact transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if _, err := tx.Exec(ctx, fmt.Sprintf(`
		INSERT INTO %s (digest, media_type, size_bytes, archive)
		VALUES ($1, $2, $3, $4)
		ON CONFLICT (digest) DO NOTHING`, s.artifactsTable),
		descriptor.Digest, descriptor.MediaType, descriptor.Size, archive); err != nil {
		return artifact.Descriptor{}, fmt.Errorf("store artifact bytes: %w", err)
	}
	if _, err := tx.Exec(ctx, fmt.Sprintf(`
		INSERT INTO %s (namespace, name, tag, digest)
		VALUES ($1, $2, $3, $4)
		ON CONFLICT (namespace, name, tag) DO UPDATE
		SET digest = EXCLUDED.digest
		WHERE %s.digest IS DISTINCT FROM EXCLUDED.digest`, s.skillArtifactsTable, s.skillArtifactsTable),
		ref.Namespace, ref.Name, ref.Tag, descriptor.Digest); err != nil {
		return artifact.Descriptor{}, fmt.Errorf("associate skill artifact: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return artifact.Descriptor{}, fmt.Errorf("commit skill artifact transaction: %w", err)
	}
	return descriptor, nil
}

func (s *PostgresArtifactStore) Get(ctx context.Context, ref artifact.SkillRef) (*artifact.Artifact, error) {
	if err := validateArtifactRef(ref); err != nil {
		return nil, err
	}
	var result artifact.Artifact
	err := s.pool.QueryRow(ctx, fmt.Sprintf(`
		SELECT a.digest, a.media_type, a.size_bytes, a.archive
		FROM %s sa
		JOIN %s a ON a.digest = sa.digest
		WHERE sa.namespace=$1 AND sa.name=$2 AND sa.tag=$3`, s.skillArtifactsTable, s.artifactsTable),
		ref.Namespace, ref.Name, ref.Tag,
	).Scan(&result.Digest, &result.MediaType, &result.Size, &result.Archive)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, pkgdb.ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("get skill artifact: %w", err)
	}
	if int64(len(result.Archive)) != result.Size {
		return nil, fmt.Errorf("get skill artifact: size mismatch for digest %s", result.Digest)
	}
	return &result, nil
}

func (s *PostgresArtifactStore) Open(ctx context.Context, ref artifact.SkillRef) (artifact.Descriptor, io.ReadCloser, error) {
	stored, err := s.Get(ctx, ref)
	if err != nil {
		return artifact.Descriptor{}, nil, err
	}
	return stored.Descriptor, io.NopCloser(bytes.NewReader(stored.Archive)), nil
}

func (s *PostgresArtifactStore) ListFiles(ctx context.Context, ref artifact.SkillRef) ([]artifact.File, error) {
	stored, err := s.Get(ctx, ref)
	if err != nil {
		return nil, err
	}
	files, err := artifact.Validate(stored.Archive)
	if err != nil {
		return nil, fmt.Errorf("list skill artifact files: %w", err)
	}
	return files, nil
}

func validateArtifactRef(ref artifact.SkillRef) error {
	if ref.Namespace == "" || ref.Name == "" || ref.Tag == "" {
		return errors.New("skill artifact reference requires namespace, name, and tag")
	}
	return nil
}
