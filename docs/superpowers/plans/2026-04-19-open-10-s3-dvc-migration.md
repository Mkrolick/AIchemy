# Open Item 10 — S3 DVC remote migration

**Goal:** Swap `local_store` DVC remote for S3 (or GCS) once the team / data size justifies it.

**When to do this:**
- Multiple developers need shared access to processed data
- Data-dir size >100GB (local remote becomes a disk-pressure risk)
- Reproducibility requirements demand immutable, versioned remote

## Tasks

- [ ] Create an S3 bucket with versioning + lifecycle policy (archive old commits after N days)
- [ ] `dvc remote modify --local local_store url s3://bucket-name/aichemy-dvc/`
- [ ] Configure AWS credentials (env vars or `~/.aws/credentials`)
- [ ] `dvc push` to migrate existing local artifacts
- [ ] Commit updated `.dvc/config` (shared URL can now safely be S3)
- [ ] Update README with S3 credential setup notes

No code changes; pure infra migration.
