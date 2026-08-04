//go:build integration

package database

import (
	"context"
	"io"
	"testing"

	"github.com/agentregistry-dev/agentregistry/pkg/api/v1alpha1"
	"github.com/agentregistry-dev/agentregistry/pkg/registry/artifact"
	"github.com/agentregistry-dev/agentregistry/pkg/registry/v1alpha1store"
)

func TestPostgresArtifactStoreRoundTrip(t *testing.T) {
	pool := v1alpha1store.NewTestPool(t)
	skills := v1alpha1store.NewStore(pool, v1alpha1store.TestSchema(), "skills")
	ctx := context.Background()
	_, err := skills.Upsert(ctx, &v1alpha1.Skill{
		Metadata: v1alpha1.ObjectMeta{Namespace: "default", Name: "demo", Tag: "v1"},
		Spec:     v1alpha1.SkillSpec{Title: "Demo"},
	})
	if err != nil {
		t.Fatal(err)
	}

	archive, err := artifact.PackFiles(map[string][]byte{"SKILL.md": []byte("# Demo"), "references/a.md": []byte("a")})
	if err != nil {
		t.Fatal(err)
	}
	store := NewPostgresArtifactStore(pool, v1alpha1store.TestSchema())
	ref := artifact.SkillRef{Namespace: "default", Name: "demo", Tag: "v1"}
	descriptor, err := store.Put(ctx, ref, archive)
	if err != nil {
		t.Fatal(err)
	}
	if descriptor.Digest == "" || descriptor.Size != int64(len(archive)) {
		t.Fatalf("unexpected descriptor: %+v", descriptor)
	}
	files, err := store.ListFiles(ctx, ref)
	if err != nil {
		t.Fatal(err)
	}
	if len(files) != 2 {
		t.Fatalf("unexpected files: %+v", files)
	}
	gotDescriptor, reader, err := store.Open(ctx, ref)
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	got, err := io.ReadAll(reader)
	if err != nil {
		t.Fatal(err)
	}
	if gotDescriptor.Digest != descriptor.Digest || string(got) != string(archive) {
		t.Fatal("stored archive did not round-trip")
	}

	if err := skills.Delete(ctx, "default", "demo", "v1"); err != nil {
		t.Fatal(err)
	}
	if _, err := store.Get(ctx, ref); err == nil {
		t.Fatal("artifact must cascade-delete with Skill")
	}
}
