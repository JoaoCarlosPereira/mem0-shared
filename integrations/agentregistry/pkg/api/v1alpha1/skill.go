package v1alpha1

// Skill is the typed envelope for kind=Skill resources.
type Skill struct {
	TypeMeta `json:",inline" yaml:",inline"`
	Metadata ObjectMeta  `json:"metadata" yaml:"metadata"`
	Spec     SkillSpec   `json:"spec" yaml:"spec"`
	Status   SkillStatus `json:"status,omitzero" yaml:"status,omitempty"`
}

func init() {
	MustRegisterKind[*Skill, SkillSpec](KindSkill)
}

// SkillSpec is the skill resource's declarative body.
type SkillSpec struct {
	Title       string       `json:"title,omitempty" yaml:"title,omitempty"`
	Description string       `json:"description,omitempty" yaml:"description,omitempty"`
	Language    string       `json:"language,omitempty" yaml:"language,omitempty"`
	Source      *SkillSource `json:"source,omitempty" yaml:"source,omitempty"`
}

// SkillSource is the legacy distribution origin of a Skill. Complete LAN
// packages are associated through the artifact subresource and do not need a
// Git repository.
type SkillSource struct {
	Repository *Repository `json:"repository,omitempty" yaml:"repository,omitempty"`
}

// SkillStatus is the Skill observed-state subresource, written by the Skill
// controller out of band of the API write. It embeds the shared Status
// (conditions + observedGeneration) and records either the package digest or
// the legacy Git source pin.
//
// Readiness: absence of Ready=True (or ResolvedSource==nil) means "not yet
// resolved". The controller sets Ready=False/Progressing on first observe,
// Ready=True/Resolved once the source is pinned, and Ready=False with a
// specific reason (SourceUnresolvable, SourceInvalid) on failure.
type SkillStatus struct {
	Status `json:",inline" yaml:",inline"`

	// ResolvedSource is the controller's immutable pin of the skill's git
	// source (the concrete commit the source ref resolved to).
	ResolvedSource *SkillResolvedSource `json:"resolvedSource,omitempty" yaml:"resolvedSource,omitempty"`
}

// SkillResolvedSource records the immutable package digest or concrete commit
// selected by the Skill controller. It is the reproducibility anchor used by
// install recipes and host materialization.
type SkillResolvedSource struct {
	// Commit is the resolved full git commit SHA.
	Commit   string                 `json:"commit,omitempty" yaml:"commit,omitempty"`
	Artifact *SkillResolvedArtifact `json:"artifact,omitempty" yaml:"artifact,omitempty"`
}

// SkillResolvedArtifact records the validated package associated with a Skill.
type SkillResolvedArtifact struct {
	Digest    string `json:"digest,omitempty" yaml:"digest,omitempty"`
	MediaType string `json:"mediaType,omitempty" yaml:"mediaType,omitempty"`
	Size      int64  `json:"size,omitempty" yaml:"size,omitempty"`
}
