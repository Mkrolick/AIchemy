# S3 DVC Remote Migration

This guide walks through moving the AIchemy DVC remote from a local-disk store to S3 (or a compatible object store: GCS, R2, MinIO, etc.). No code changes required.

## When to migrate

- Multiple developers need shared access to processed parquets and interim caches
- `~/aichemy-dvc-storage/` has grown past ~100GB
- You want cross-machine reproducibility for a specific commit (`git checkout <sha> && dvc checkout`)

## Prerequisites

- An S3 bucket (recommended: versioning enabled, intelligent-tiering for cost)
- AWS credentials available to each developer (env vars, `~/.aws/credentials`, or an SSO profile)
- DVC's S3 extras: `uv pip install 'dvc[s3]'` (or add `dvc[s3]` to `pyproject.toml` dev-dependencies)

## Migration steps

```bash
# 1. Install the S3 DVC backend
uv pip install 'dvc[s3]'

# 2. Point the shared remote name to the new URL.
# This writes to .dvc/config (committed to git).
uv run dvc remote modify local_store url s3://your-bucket/aichemy-dvc/

# 3. Any developer-specific override (e.g. an endpoint for MinIO) goes in
# .dvc/config.local (gitignored).
uv run dvc remote modify --local local_store endpointurl https://minio.example.com

# 4. Push existing artifacts to S3.
uv run dvc push

# 5. Commit the updated .dvc/config and DONE.
git add .dvc/config
git commit -m "Switch DVC remote to S3"
git push origin main
```

## Security considerations

- Never commit AWS credentials to git. Use env vars (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) or a named profile (`AWS_PROFILE=aichemy`) pointed at `~/.aws/credentials`.
- Enable bucket versioning. DVC is content-addressed so it won't overwrite, but versioning protects against accidental `dvc gc` on a shared remote.
- Consider a lifecycle policy to transition old objects to Glacier after ~90 days.

## Cost estimate

As of April 2026, S3 Standard is ~$0.023/GB/month in us-east-1. At 100GB of DVC cache, that's ~$2.30/month — a rounding error compared to researcher time.

## Rollback

DVC supports multiple remotes. If S3 is flaky, keep `local_store` AND add a new remote `s3_backup`, set `s3_backup` as default, use `dvc push -r local_store` to mirror. To roll back fully, flip the `[core] remote = ...` entry in `.dvc/config` back to `local_store`.
