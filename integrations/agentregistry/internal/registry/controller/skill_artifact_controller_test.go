package controller

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"testing"

	"github.com/agentregistry-dev/agentregistry/pkg/api/v1alpha1"
	"github.com/agentregistry-dev/agentregistry/pkg/registry/artifact"
	pkgdb "github.com/agentregistry-dev/agentregistry/pkg/registry/database"
	"github.com/agentregistry-dev/agentregistry/pkg/registry/v1alpha1store"
)

type fakeSkillStore struct {
	status   map[string]json.RawMessage
	listRows []*v1alpha1.RawObject
}

func newFakeSkillStore() *fakeSkillStore {
	return &fakeSkillStore{status: map[string]json.RawMessage{}}
}

func (f *fakeSkillStore) key(ns, name, tag string) string { return ns + "/" + name + ":" + tag }

func (f *fakeSkillStore) Get(context.Context, string, string, string) (*v1alpha1.RawObject, error) {
	return nil, pkgdb.ErrNotFound
}

func (f *fakeSkillStore) List(context.Context, v1alpha1store.ListOpts) ([]*v1alpha1.RawObject, string, error) {
	return f.listRows, "", nil
}

func (f *fakeSkillStore) ApplyPatch(_ context.Context, ns, name, tag string, patch v1alpha1store.PatchOpts) error {
	key := f.key(ns, name, tag)
	out, err := patch.Status(f.status[key])
	if err != nil {
		return err
	}
	f.status[key] = out
	return nil
}

type fakeArtifactStore struct {
	artifacts map[artifact.SkillRef]*artifact.Artifact
	err       error
}

func (f *fakeArtifactStore) Put(context.Context, artifact.SkillRef, []byte) (artifact.Descriptor, error) {
	panic("unexpected Put")
}

func (f *fakeArtifactStore) Get(_ context.Context, ref artifact.SkillRef) (*artifact.Artifact, error) {
	if f.err != nil {
		return nil, f.err
	}
	stored, ok := f.artifacts[ref]
	if !ok {
		return nil, pkgdb.ErrNotFound
	}
	return stored, nil
}

func (f *fakeArtifactStore) Open(ctx context.Context, ref artifact.SkillRef) (artifact.Descriptor, io.ReadCloser, error) {
	stored, err := f.Get(ctx, ref)
	if err != nil {
		return artifact.Descriptor{}, nil, err
	}
	return stored.Descriptor, io.NopCloser(bytes.NewReader(stored.Archive)), nil
}

func (f *fakeArtifactStore) ListFiles(ctx context.Context, ref artifact.SkillRef) ([]artifact.File, error) {
	stored, err := f.Get(ctx, ref)
	if err != nil {
		return nil, err
	}
	return artifact.Validate(stored.Archive)
}

func (f *fakeSkillStore) skill(t *testing.T, ns, name, tag string) *v1alpha1.Skill {
	t.Helper()
	s := &v1alpha1.Skill{}
	if err := s.UnmarshalStatus(f.status[f.key(ns, name, tag)]); err != nil {
		t.Fatal(err)
	}
	return s
}

func TestSkillReconciled(t *testing.T) {
	skill := &v1alpha1.Skill{Metadata: v1alpha1.ObjectMeta{Generation: 3}}
	if skillReconciled(skill) {
		t.Fatal("unobserved Skill must reconcile")
	}
	skill.Status.ObservedGeneration = 3
	if !skillReconciled(skill) {
		t.Fatal("current generation must be reconciled regardless of ready state")
	}
}

func TestSkillEnqueueAllSkipsUndecodableRow(t *testing.T) {
	rawOf := func(name, spec string) *v1alpha1.RawObject {
		return &v1alpha1.RawObject{
			TypeMeta: v1alpha1.TypeMeta{APIVersion: v1alpha1.GroupVersion, Kind: v1alpha1.KindSkill},
			Metadata: v1alpha1.ObjectMeta{Namespace: "default", Name: name, Tag: "v1", Generation: 1},
			Spec:     json.RawMessage(spec),
		}
	}
	store := newFakeSkillStore()
	store.listRows = []*v1alpha1.RawObject{rawOf("bad", `not json`), rawOf("good", `{}`)}
	controller := &SkillController{Store: store}
	if err := controller.enqueueAll(context.Background()); err != nil {
		t.Fatal(err)
	}
	if controller.workQueue().Len() != 1 {
		t.Fatalf("expected one valid Skill queued, got %d", controller.workQueue().Len())
	}
}

func TestSkillReconcileUploadOnly(t *testing.T) {
	const ns, name, tag = "default", "demo", "v1"
	ref := artifact.SkillRef{Namespace: ns, Name: name, Tag: tag}
	archive, err := artifact.PackFiles(map[string][]byte{"SKILL.md": []byte("# Demo"), "references/a.md": []byte("a")})
	if err != nil {
		t.Fatal(err)
	}

	t.Run("missing artifact is not ready and ignores git provenance", func(t *testing.T) {
		store := newFakeSkillStore()
		controller := &SkillController{Store: store, Artifacts: &fakeArtifactStore{artifacts: map[artifact.SkillRef]*artifact.Artifact{}}}
		skill := &v1alpha1.Skill{
			Metadata: v1alpha1.ObjectMeta{Namespace: ns, Name: name, Tag: tag, Generation: 3},
			Spec:     v1alpha1.SkillSpec{Source: &v1alpha1.SkillSource{Repository: &v1alpha1.Repository{URL: "https://example.invalid/provenance"}}},
		}
		outcome, reason, err := controller.reconcile(context.Background(), skill)
		if err != nil {
			t.Fatal(err)
		}
		if outcome != "pending" || reason != "ArtifactMissing" {
			t.Fatalf("got (%q, %q), want (pending, ArtifactMissing)", outcome, reason)
		}
		got := store.skill(t, ns, name, tag)
		if got.Status.ObservedGeneration != 3 || got.Status.IsConditionTrue(skillReadyCondition) {
			t.Fatalf("unexpected status: %+v", got.Status)
		}
	})

	t.Run("valid associated artifact becomes ready", func(t *testing.T) {
		store := newFakeSkillStore()
		artifacts := &fakeArtifactStore{artifacts: map[artifact.SkillRef]*artifact.Artifact{
			ref: {Descriptor: artifact.Descriptor{Digest: "abcd", MediaType: artifact.MediaTypeTarGzip, Size: int64(len(archive))}, Archive: archive},
		}}
		controller := &SkillController{Store: store, Artifacts: artifacts}
		skill := &v1alpha1.Skill{Metadata: v1alpha1.ObjectMeta{Namespace: ns, Name: name, Tag: tag, Generation: 4}}
		outcome, reason, err := controller.reconcile(context.Background(), skill)
		if err != nil {
			t.Fatal(err)
		}
		if outcome != "ready" || reason != "ArtifactReady" {
			t.Fatalf("got (%q, %q), want (ready, ArtifactReady)", outcome, reason)
		}
		got := store.skill(t, ns, name, tag)
		if !got.Status.IsConditionTrue(skillReadyCondition) || got.Status.ResolvedSource == nil || got.Status.ResolvedSource.Artifact == nil {
			t.Fatalf("artifact readiness not recorded: %+v", got.Status)
		}
		if got.Status.ResolvedSource.Commit != "" {
			t.Fatalf("upload-only controller must not resolve git commit, got %q", got.Status.ResolvedSource.Commit)
		}
	})

	t.Run("invalid stored archive is terminal not ready", func(t *testing.T) {
		store := newFakeSkillStore()
		controller := &SkillController{Store: store, Artifacts: &fakeArtifactStore{artifacts: map[artifact.SkillRef]*artifact.Artifact{
			ref: {Descriptor: artifact.Descriptor{Digest: "bad", MediaType: artifact.MediaTypeTarGzip, Size: 3}, Archive: []byte("bad")},
		}}}
		skill := &v1alpha1.Skill{Metadata: v1alpha1.ObjectMeta{Namespace: ns, Name: name, Tag: tag, Generation: 5}}
		outcome, reason, err := controller.reconcile(context.Background(), skill)
		if err != nil {
			t.Fatal(err)
		}
		if outcome != "failed" || reason != "ArtifactInvalid" {
			t.Fatalf("got (%q, %q), want (failed, ArtifactInvalid)", outcome, reason)
		}
	})
}
