CREATE TABLE IF NOT EXISTS artifacts (
    digest character(64) PRIMARY KEY,
    media_type character varying(127) NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    archive bytea NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_artifacts (
    namespace character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    tag character varying(255) NOT NULL,
    digest character(64) NOT NULL REFERENCES artifacts (digest),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    PRIMARY KEY (namespace, name, tag),
    FOREIGN KEY (namespace, name, tag)
        REFERENCES skills (namespace, name, tag)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS skill_artifacts_digest
    ON skill_artifacts USING btree (digest);

CREATE OR REPLACE TRIGGER skill_artifacts_set_updated_at
    BEFORE UPDATE ON skill_artifacts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
