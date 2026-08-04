package artifact

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"errors"
	"testing"
)

func TestPackFilesAndValidate(t *testing.T) {
	archive, err := PackFiles(map[string][]byte{
		"SKILL.md":        []byte("# Skill"),
		"references/a.md": []byte("reference"),
	})
	if err != nil {
		t.Fatal(err)
	}
	files, err := Validate(archive)
	if err != nil {
		t.Fatal(err)
	}
	if len(files) != 2 || files[0].Path != "SKILL.md" || files[1].Path != "references/a.md" {
		t.Fatalf("unexpected files: %+v", files)
	}
}

func TestReadFilesReturnsCompleteContent(t *testing.T) {
	archive, err := PackFiles(map[string][]byte{
		"SKILL.md":        []byte("# Skill"),
		"assets/logo.bin": []byte{0, 1, 2},
	})
	if err != nil {
		t.Fatal(err)
	}
	files, err := ReadFiles(archive)
	if err != nil {
		t.Fatal(err)
	}
	if len(files) != 2 || files[0].Path != "SKILL.md" || !bytes.Equal(files[1].Content, []byte{0, 1, 2}) {
		t.Fatalf("unexpected content files: %+v", files)
	}
}

func TestPackFilesRequiresRootSkillMD(t *testing.T) {
	_, err := PackFiles(map[string][]byte{"nested/SKILL.md": []byte("x")})
	if !errors.Is(err, ErrInvalidArchive) {
		t.Fatalf("expected ErrInvalidArchive, got %v", err)
	}
}

func TestValidateRejectsUnsafeTarEntries(t *testing.T) {
	tests := []struct {
		name     string
		header   tar.Header
		contents []byte
	}{
		{name: "traversal", header: tar.Header{Name: "../evil", Mode: 0o644, Typeflag: tar.TypeReg, Size: 1}, contents: []byte("x")},
		{name: "symlink", header: tar.Header{Name: "link", Typeflag: tar.TypeSymlink, Linkname: "/etc/passwd"}},
		{name: "hardlink", header: tar.Header{Name: "hard", Typeflag: tar.TypeLink, Linkname: "SKILL.md"}},
		{name: "special", header: tar.Header{Name: "device", Typeflag: tar.TypeChar}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			data := rawArchive(t, tar.Header{Name: "SKILL.md", Mode: 0o644, Typeflag: tar.TypeReg, Size: 1}, []byte("x"), tt.header, tt.contents)
			if _, err := Validate(data); !errors.Is(err, ErrInvalidArchive) {
				t.Fatalf("expected ErrInvalidArchive, got %v", err)
			}
		})
	}
}

func rawArchive(t *testing.T, entries ...any) []byte {
	t.Helper()
	var out bytes.Buffer
	gz := gzip.NewWriter(&out)
	tw := tar.NewWriter(gz)
	for i := 0; i < len(entries); i += 2 {
		header := entries[i].(tar.Header)
		if err := tw.WriteHeader(&header); err != nil {
			t.Fatal(err)
		}
		if data := entries[i+1].([]byte); len(data) > 0 {
			if _, err := tw.Write(data); err != nil {
				t.Fatal(err)
			}
		}
	}
	if err := tw.Close(); err != nil {
		t.Fatal(err)
	}
	if err := gz.Close(); err != nil {
		t.Fatal(err)
	}
	return out.Bytes()
}
