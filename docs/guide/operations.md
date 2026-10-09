# Operations

How to run a normly production VM: rolling out a release, rolling it back,
backing up user data, and publishing knowledge-base dumps. The design and its
reasons are in [ADR-024](../adr/README.md#adr-024-rollout-rollback-und-sicherung-auf-der-einzel-vm)
(rollout, rollback, backup) and [ADR-025](../adr/README.md#adr-025-wissensbestand-dump-als-austauschformat)
(knowledge-base dump). For a plain Compose setup without a VM, see
[Self-Hosting](self-hosting.md).

The model in one paragraph: the VM never builds. A human runs
`normly-deploy deploy vX.Y.Z` over SSH; the script verifies the signed images,
takes a backup of the user data, pulls the images and starts them. Rolling
back restores the images **and** the data to the state before the rollout.
No credentials for the VM exist on GitHub.

## Prerequisites on the VM

| Tool | Used for |
|---|---|
| `docker` with Compose v2.20 or newer | running the release (`--wait-timeout` needs 2.20) |
| `cosign` | verifying image signatures before anything starts |
| `age` | encrypting backups (VM: public key only) and decrypting them (rollback) |
| `rclone` | uploading and downloading backups (S3-compatible, STACKIT Object Storage) |
| `postgresql-client` | `pg_dump`, `psql`, `pg_restore` |
| `python3` | digest parsing and the retention policy (standard library only) |

On Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y age rclone postgresql-client python3
# Docker Engine with the Compose plugin: https://docs.docker.com/engine/install/ubuntu/
# cosign: https://docs.sigstore.dev/cosign/system_config/installation/
docker compose version   # must print v2.20 or newer
cosign version
```

Two limits to know about:

- `pg_dump`, `psql` and `pg_restore` run **on the host**, not in a container.
  `NORMLY_DATABASE_URL` in `/opt/normly/.env` therefore has to resolve from the
  host. That is the case for a managed database such as PostgreSQL Flex; it is
  not the case for the bundled `postgres` service (its host name only exists
  inside the Compose network).
- The database password appears in the arguments of those processes while they
  run. This assumes a VM that only the operator uses. Hardening is deferred.

## Directory layout

```text
/opt/normly/
  .env          configuration and secrets (read by the scripts and by Compose)
  bin/          normly-deploy, normly-backup, normly-backup-retention.py
  releases/     one directory per deployed tag, taken from the signed pipeline image
  state/        current_tag, previous_tag, pre_rollout_backup, pre_rollout_kb_version,
                failed_rollout (only after a failed rollout), deploy.lock (during a run)
  current       symlink to releases/<current tag>
```

## Installing the scripts

The scripts ship inside the signed `pipeline` image. Verify the image first,
then copy them out. Replace `0.2.0` with the release you install:

```bash
sudo mkdir -p /opt/normly/bin /opt/normly/releases /opt/normly/state
cosign verify \
  --certificate-identity-regexp '^https://github\.com/normly/web-app/\.github/workflows/images\.yml@refs/tags/v0\.2\.0$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/normly/web-app/pipeline:0.2.0

for f in normly-deploy normly-backup normly-backup-retention.py; do
  docker run --rm --entrypoint cat ghcr.io/normly/web-app/pipeline:0.2.0 \
    /app/deploy/scripts/$f | sudo tee /opt/normly/bin/$f > /dev/null
  sudo chmod 755 /opt/normly/bin/$f
done
```

The first installation is a manual step, because the script that verifies
releases cannot verify itself. Later releases carry their own copy in
`releases/<tag>/scripts/`; update `/opt/normly/bin` from there after a
successful deploy if the scripts changed.

Create `/opt/normly/.env` from `.env.example` (production-style settings, see
[Self-Hosting](self-hosting.md#production-style-setup)) and add the backup
variables below.

## Deploying a release

Cut the release first ([Releasing](releasing.md)), then on the VM:

```bash
/opt/normly/bin/normly-deploy deploy v0.2.0
```

What happens, in order:

1. The tag must differ from the current one, and no failed rollout may be
   recorded (see below).
2. `cosign verify` runs for all five images against the identity
   `images.yml@refs/tags/v0.2.0`. If any check fails, nothing is changed. The
   verified digests are written to `releases/v0.2.0/verified-digests`.
3. Compose file and assets are extracted from the **verified**
   `pipeline@<digest>` into `releases/v0.2.0/`.
4. The script reads the knowledge-base version the running release uses, then
   takes a pre-rollout backup (`normly-backup run --kind pre-v0.2.0`). If the
   upload is not confirmed, there is no rollout.
5. `docker compose pull`, then the pulled digests are compared with the
   verified ones. A tag that was re-pointed in the meantime stops the run
   before anything starts.
6. `docker compose up -d --wait`: the one-shot `migrate` service runs first,
   then the services start, and the script waits until they report healthy
   (up to `NORMLY_HEALTH_TIMEOUT` seconds, default 600).
7. On success the state files and the `current` symlink are updated.

`status` shows what the script has recorded:

```bash
/opt/normly/bin/normly-deploy status
```

**There is no automatic rollback.** If the new release does not become healthy,
the script records the failed tag in `state/failed_rollout`, keeps the old tag
as the rollback target, and tells you so. It refuses further `deploy` calls
until you have rolled back. To override that deliberately, remove the marker
file (`/opt/normly/state/failed_rollout`); the error message says so.

If `migrate` fails half-way, the pre-rollout backup is the way back.

## Rolling back

Rollback returns the images **and the data** to the state before the last
rollout.

> **Data loss.** Everything written to the user-data tables since the
> pre-rollout backup is discarded: new accounts, chats, watchlists,
> notifications. The script says so and asks for confirmation.

You need the private `age` key for this run only. Bring it from the Secrets
Manager or your offline copy; do not leave it on the VM afterwards:

```bash
/opt/normly/bin/normly-deploy rollback --age-identity /root/normly-backup.key
shred -u /root/normly-backup.key
```

Before it changes anything, the script compares the `alembic_revision` in the
backup's `meta.json` with the Alembic head of the **previous** image and
refuses to continue on a mismatch (a dump and a schema that do not fit
together). It then prints what will be discarded and asks you to type the
target tag; `--yes` skips the question for scripted runs.

Then it:

1. stops the services;
2. drops **all** tables in the `public` schema (the list is read from the
   database, so tables added by the newer release go too; the schema itself
   stays, so the pgvector extension survives);
3. runs `migrate` with the previous image;
4. imports the knowledge-base dump version recorded when the backup was taken
   (before the user data, because user data references knowledge-base rows by
   foreign key). The import fetches from `NORMLY_KB_BASE_URL`, so that variable
   must be set in `.env`. The duration grows with the size of the knowledge
   base;
5. restores the user data with `pg_restore --data-only`;
6. starts the previous release and waits for it to become healthy.

If a step fails after the tables were dropped, the script prints a recovery
message: the database is incomplete, services are stopped, `current_tag` is
unchanged. Running the same `rollback` command again is safe, because it
rebuilds the schema from the backup each time. On success the failed-rollout
marker is cleared.

## Backups

`normly-backup` dumps **only the user-data tables** (`python -m
normly_core.exchange tables user` lists them): accounts, chats, watchlists,
notifications, rate-limit buckets. The knowledge base is not backed up; it is
reproduced from its dump version. Flex's own daily backup of the whole database
(30 days) remains the operational safety net.

Add to `/opt/normly/.env`:

| Variable | Meaning |
|---|---|
| `NORMLY_BACKUP_AGE_RECIPIENT` | the age **public** key (`age1…`); the VM can write backups but not read them |
| `NORMLY_BACKUP_REMOTE` | an rclone path to the private bucket, e.g. `stackit:normly-backups` |
| `NORMLY_DATABASE_URL` | as for the application; must resolve from the host (see above) |

Configure the rclone remote (for example `stackit`) for S3-compatible STACKIT
Object Storage in `~/.config/rclone/rclone.conf` of the user that runs the
scripts, with the access keys of a bucket user that may write and list but
need not read. Create the bucket as **private**.

Generate the key pair once, on the operator's machine, not on the VM:

```bash
age-keygen -o normly-backup.key        # prints the public key (age1...)
```

Put `normly-backup.key` into the Secrets Manager and keep an offline copy.
Only the public key goes into `.env`. Losing the private key makes every backup
unreadable, so test the offline copy (see "Restore test").

Enable the daily timer (03:30 UTC; it runs the backup, then prune). The unit
files are not part of the images; take them from a checkout of the release tag:

```bash
git clone --depth 1 --branch v0.2.0 https://github.com/normly/web-app.git /tmp/normly-src
sudo cp /tmp/normly-src/deploy/systemd/normly-backup.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now normly-backup.timer
systemctl list-timers normly-backup.timer
```

Manual runs: `normly-backup run [--kind daily|pre-<tag>]` (the last line of
output is the backup's base name) and `normly-backup prune`.

Each backup is three objects under `backups/` in the bucket, uploaded in this
order: `<stamp>-<kind>.meta.json` (Alembic revision, image tag, knowledge-base
version), `<stamp>-<kind>.dump.age`, and `<stamp>-<kind>.sha256`. The checksum
file goes up last and is the commit marker: a backup without it does not
count.

**Retention** (applied by `normly-backup prune`): the newest backup of each of
the 7 most recent days with a daily backup; the newest daily backup of each of
the 2 most recent calendar months; the 3 newest pre-rollout backups. Prune
only counts committed backups and deletes uncommitted leftovers once they are
older than one day.

## Restore test

Do this once after setting up the backups, then monthly. It needs the private
key on a machine other than the production VM, and a throw-away database.

```bash
# 1. Pick a backup and download it
rclone lsf stackit:normly-backups/backups | tail
BASE=20261009T033000Z-daily
rclone copyto stackit:normly-backups/backups/$BASE.dump.age ./$BASE.dump.age
rclone copyto stackit:normly-backups/backups/$BASE.sha256   ./$BASE.sha256
sha256sum -c $BASE.sha256

# 2. Decrypt
age -d -i normly-backup.key -o $BASE.dump $BASE.dump.age

# 3. Prepare an empty database (PostgreSQL 16 with pgvector) and create the
#    schema with the migrations of the release named in the backup's meta.json
createdb normly_restore_test
psql normly_restore_test -c 'CREATE EXTENSION IF NOT EXISTS vector'
docker run --rm --network host --entrypoint python \
  -e NORMLY_DATABASE_URL=postgresql+psycopg:///normly_restore_test \
  ghcr.io/normly/web-app/pipeline:0.2.0 -m normly_core.migrate

# 4. Restore the user data
pg_restore --dbname=normly_restore_test --data-only --exit-on-error $BASE.dump

# 5. Look at it
psql normly_restore_test -c "
  SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname"
psql normly_restore_test -c 'SELECT count(*) FROM account'
```

For exact counts, run `SELECT count(*)` for each table that
`python -m normly_core.exchange tables user` lists and compare with production.
Restoring into a database with no knowledge base can fail on foreign keys
that point into the knowledge base; import the matching dump first
(see "Knowledge-base dumps") for a complete test. Drop the throw-away
database and delete the decrypted dump when you are done.

## Knowledge-base dumps

The free knowledge base is published as a signed dump: one Parquet file (in
parts, if large) per table, a `manifest.json`, and an Ed25519 signature
`manifest.json.sig`. Only rows cleared by the rights classification are
exported (categories A, B and D, never commercial catalogues). Versions are
calendar versions such as `2026.10.1` and are immutable: an existing version is
never overwritten. In production the knowledge base changes only by importing a
dump, never by ingestion on the VM.

**Signing key.** Create it once, offline. The public key is committed to the
repository (`core/src/normly_core/exchange/keys/kb-signing.pub.pem`); the
private key stays with the maintainer.

```bash
python -m normly_core.exchange keygen --private kb-signing.key --public kb-signing.pub.pem
```

The key ceremony is still pending: until the public key is packaged with the
build, every import needs `--public-key PATH`, including the import that
`kb-import` and `normly-deploy rollback` run.

**Export** (on the machine that holds the ingested knowledge base, over the
repository layer; `NORMLY_DATABASE_URL` points at that database and
`NORMLY_EMBEDDING_MODEL_REVISION` is set in the `pipeline` image):

```bash
docker compose run --rm --entrypoint python \
  -v "$PWD/out:/out" -v "$PWD/kb-signing.key:/kb-signing.key:ro" \
  pipeline -m normly_core.exchange export \
  --version 2026.10.1 --out /out --private-key /kb-signing.key
# writes out/2026.10.1/{manifest.json,manifest.json.sig,<table files>}
```

**Publish** to the public-read STACKIT Object Storage bucket with `rclone`.
Upload the version directory first and `latest` last, so no client sees a
`latest` that points to an incomplete version:

```bash
rclone copy out/2026.10.1 stackit:normly-kb/kb/2026.10.1
echo 2026.10.1 > latest
rclone copyto latest stackit:normly-kb/kb/latest
```

`kb/latest` is a one-line text file holding the version. Consumers set
`NORMLY_KB_BASE_URL` to the bucket's public `…/kb` URL (https; plain http is
accepted only for localhost) and run:

```bash
docker compose run --rm kb-import              # kb/latest
docker compose run --rm kb-import 2026.10.1    # a fixed version
```

The import verifies the signature, the exchange schema version, the embedding
model name **and** revision, the vector dimension and every file checksum before
it writes. It is atomic and idempotent. It stops without changes if user data
still references a knowledge-base row that the new version removes, and names
the blocking references. How to resolve such cases is an open product decision
([ADR-025](../adr/README.md#adr-025-wissensbestand-dump-als-austauschformat)).

Before the first public dump, one open point must be settled: the dump
currently contains personal names (`source.responsible_person`,
`rights_classification.classified_by`).

`python -m normly_core.exchange info` prints the imported dump version (or
`none`); the rollout and the backup record it.
