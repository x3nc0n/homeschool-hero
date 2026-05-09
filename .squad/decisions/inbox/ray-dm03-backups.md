# Ray DM-03 NAS Backup Runtime

- **Context:** DM-03 requires scheduled NAS backups over SMB or NFS, but Docker containers cannot reliably mount remote shares themselves without elevated host-specific setup.
- **Decision:** Treat `BACKUP_TARGET` as the mounted path inside the container, add `BACKUP_MOUNT_SOURCE` for the Docker bind mount, validate SMB/NFS metadata plus mount writability on startup, and auto-enable restic only when both the binary and `BACKUP_ENCRYPTION_KEY` are present.
- **Impact:** Operators can point Docker at a host-mounted NAS share for SMB or NFS, backups fail fast when the mount is missing or read-only, and the runtime still falls back to plain directory copies when restic is unavailable.
