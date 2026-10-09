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
  bin/          normly-deploy, normly-backup, normly-backup-retention.py, normly-env.sh
  releases/     one directory per deployed tag, taken from the signed pipeline image
  state/        current_tag, previous_tag, pre_rollout_backup, pre_rollout_kb_version,
                failed_rollout (only after a failed rollout), deploy.lock (during a run)
  current       symlink to releases/<current tag>
```

## Installing the scripts

The scripts and the systemd units ship inside the signed `pipeline` image.
Verify the image, take its **digest** from the verification output, and copy
the files out of exactly that digest, not out of the tag (a tag can be
re-pointed between the check and the copy). Replace `0.2.0` with the release
you install:

```bash
sudo mkdir -p /opt/normly/bin /opt/normly/releases /opt/normly/state
DIGEST="$(cosign verify \
  --certificate-identity-regexp '^https://github\.com/normly/web-app/\.github/workflows/images\.yml@refs/tags/v0\.2\.0$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/normly/web-app/pipeline:0.2.0 \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["critical"]["image"]["docker-manifest-digest"])')"
echo "$DIGEST"      # sha256:...

CID="$(sudo docker create "ghcr.io/normly/web-app/pipeline@$DIGEST")"
sudo docker cp "$CID:/app/deploy/scripts/." /opt/normly/bin/
sudo docker cp "$CID:/app/deploy/systemd/." /etc/systemd/system/
sudo docker rm "$CID"
sudo chmod 755 /opt/normly/bin/normly-deploy /opt/normly/bin/normly-backup \
  /opt/normly/bin/normly-backup-retention.py
```

The first installation is a manual step, because the script that verifies
releases cannot verify itself. Later releases carry their own copy in
`releases/<tag>/scripts/` (the digests that were verified are in
`releases/<tag>/verified-digests`); update `/opt/normly/bin` from there after a
successful deploy if the scripts changed.

The scripts read `/opt/normly/.env` with their own small parser
(`normly-env.sh`), not with the shell, because Compose accepts values the shell
does not (`NORMLY_BRAND_COLOR_HSL=222 89% 55%`). They take only these keys
from the file, and nothing in it is evaluated:

- exactly `NORMLY_DATABASE_URL`, `NORMLY_BACKUP_AGE_RECIPIENT`,
  `NORMLY_BACKUP_REMOTE`, `NORMLY_KB_PUBLIC_KEY_FILE` and `NORMLY_KB_BASE_URL`;
- every key starting with `RCLONE_` or `AWS_` (rclone credentials).

Other variables the scripts understand, such as `NORMLY_BACKUP_BIN`, are
overrides of the process environment only; putting them in `.env` has no
effect. A variable that is already set in the environment of the call wins over
the file. If `python3` is missing or `.env` exists but cannot be read, the
scripts stop with a message instead of continuing with an empty configuration;
a missing `.env` file is allowed.

Compose and the scripts read `.env` in slightly different dialects:

- Compose interpolates `$` in unquoted and double-quoted values; the scripts
  read every value literally. A password containing `$` therefore has to be
  single-quoted (`PASSWORD='pa$word'`) to mean the same to both.
- After a quoted value, the scripts strip a trailing ` # comment`, as they do
  for unquoted values, and keep the value without the quotes.
- A UTF-8 byte order mark at the start of the file is ignored.

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
   verified digests are written to `releases/0.2.0/verified-digests`. Release
   directories, state files and backup names use the tag **without** the `v`.
3. Compose file and assets are extracted from the **verified**
   `pipeline@<digest>` into `releases/0.2.0/`.
4. The script reads the knowledge-base version the running release uses, then
   takes a pre-rollout backup (`normly-backup run --kind pre-0.2.0`). If the
   upload is not confirmed, there is no rollout. On the very first deploy
   (no current release yet) there is nothing to read and nothing to back up,
   so this step is skipped, and there is no rollback target either.
5. `docker compose pull`, then the pulled digests are compared with the
   verified ones. A tag that was re-pointed in the meantime stops the run
   before anything starts.
6. `docker compose up -d --wait`: the one-shot `migrate` service runs first,
   then the services start, and the script waits until they report healthy
   (up to `NORMLY_HEALTH_TIMEOUT` seconds, default 600).
7. On success the state files and the `current` symlink are updated.

**Transition for a VM that already holds a knowledge base.** The first
scripted deploy records the knowledge-base version through `info`, which reads
the import record. Before the first scripted deploy on such a VM, export the
knowledge base, publish it, and import it via `kb-import`, so that `info`
reports a version (see "Knowledge-base dumps"). Otherwise `none` is recorded
and a later rollback leaves the knowledge base empty.

`status` shows what the script has recorded:

```bash
/opt/normly/bin/normly-deploy status
```

**There is no automatic rollback.** If the new release does not become healthy,
the script records the failed tag in `state/failed_rollout`, keeps the old tag
as the rollback target, and tells you so. It refuses further `deploy` calls
until you have rolled back. To override that deliberately, remove the marker
file (`/opt/normly/state/failed_rollout`); the error message says so.

The override has a price. After `rm state/failed_rollout` and a fresh deploy,
`pre_rollout_backup` points to a backup taken at the **newer** schema, so the
scripted rollback's Alembic check will refuse. The older, valid pre-rollout
backup is still in the bucket (the 3 newest are kept) and can be restored by
the manual procedure in "Restore test".

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

Stop the backup timer while a rollback runs (`sudo systemctl stop
normly-backup.timer`, start it again afterwards): the timer does not take the
deploy lock, and a backup in the middle of a rollback would capture a
half-restored database.

Before it changes anything, the script runs two checks and refuses (nothing
changed) if either fails:

- The `alembic_revision` in the backup's `meta.json` must equal the Alembic
  head of the **previous** image (a dump and a schema that do not fit together
  are refused).
- If the knowledge-base version recorded at backup time is not `none`, the
  script verifies that dump first (`python -m normly_core.exchange verify
  --fetch <version>`, in the previous release's image, without touching the
  database): download from `NORMLY_KB_BASE_URL`, signature, exchange schema,
  embedding model and revision, checksums. If the dump or the public key
  cannot be verified, the rollback stops before the banner, the prompt, and
  the `DROP`.

**Public key.** The signature is checked against the public key, resolved in
this order: `--public-key PATH`, the environment variable
`NORMLY_KB_PUBLIC_KEY_FILE`, the key packaged with the build. Until the key
ceremony is done and the key is committed, nothing is packaged, so set
`NORMLY_KB_PUBLIC_KEY_FILE` in `/opt/normly/.env` to a path **on the VM** that
holds the PEM public key. If it is set, `normly-deploy` requires it to be a
file and mounts it read-only into the container for the verify and import
steps. Without a key, a rollback that has to re-import a knowledge base
refuses.

If the recorded knowledge-base version is `none`, the banner says so
explicitly: the knowledge base will be **empty** after the rollback, and only
the Flex backup can restore it. The confirmation is still required.

It then prints what will be discarded and asks you to type the target tag
**without** the `v` (for example `0.1.0`); `--yes` skips the question for
scripted runs.

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
message: the database is incomplete, services may be stopped or partly
running, `current_tag` is unchanged. Running the same `rollback` command again is safe, because it
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
| `NORMLY_BACKUP_AGE_RECIPIENT` | the age **public** key (`age1…`); the VM can encrypt backups but not decrypt them |
| `NORMLY_BACKUP_REMOTE` | an rclone path to the private bucket, e.g. `stackit:normly-backups` |
| `NORMLY_DATABASE_URL` | as for the application; must resolve from the host (see above) |
| `NORMLY_KB_PUBLIC_KEY_FILE` | optional, see "Rolling back": host path of the knowledge-base public key |

Configure the rclone remote (for example `stackit`) for S3-compatible STACKIT
Object Storage. The daily timer runs as **root** (the systemd units set no
`User=`), so the config belongs in root's `~/.config/rclone/rclone.conf`; for
manual runs it must be readable by the user who runs them. The bucket
credentials on the VM need **list and write** (upload, prune), **delete**
(prune) and **read** (rollback downloads `meta.json` and `dump.age` with
rclone). What the VM cannot do is *decrypt*: the private age key is not there.
Create the bucket as **private**.

Generate the key pair once, on the operator's machine, not on the VM:

```bash
age-keygen -o normly-backup.key        # prints the public key (age1...)
```

Put `normly-backup.key` into the Secrets Manager and keep an offline copy.
Only the public key goes into `.env`. Losing the private key makes every backup
unreadable, so test the offline copy (see "Restore test").

Enable the daily timer (03:30 UTC; it runs the backup, then prune). The unit
files ship in the signed image and were copied to `/etc/systemd/system/` in
"Installing the scripts" (later releases carry them in
`releases/<tag>/systemd/`):

```bash
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

The commands below were derived from the code and the scripts; they have not
been run end to end yet. Treat the first live run (the acceptance of the
deployment work) as their verification and correct this section if needed.

```bash
# 1. Pick a backup and download it
rclone lsf stackit:normly-backups/backups | tail
BASE=20261009T033000Z-daily
rclone copyto stackit:normly-backups/backups/$BASE.dump.age ./$BASE.dump.age
rclone copyto stackit:normly-backups/backups/$BASE.sha256   ./$BASE.sha256
rclone copyto stackit:normly-backups/backups/$BASE.meta.json ./$BASE.meta.json
sha256sum -c $BASE.sha256
cat $BASE.meta.json        # alembic_revision, image_tag, kb_version

# 2. Decrypt
age -d -i normly-backup.key -o $BASE.dump $BASE.dump.age

# 3. Start a throw-away PostgreSQL with pgvector, reachable over TCP
#    (any PostgreSQL 16 with the vector extension works; this is one way)
export TEST_PW="$(head -c 12 /dev/urandom | base64 | tr -d '/+=')"
docker run -d --name restore-test -e POSTGRES_PASSWORD="$TEST_PW" \
  -e POSTGRES_DB=normly_restore_test -p 127.0.0.1:55432:5432 pgvector/pgvector:pg16
sleep 10
export PGURL="postgresql://postgres:$TEST_PW@127.0.0.1:55432/normly_restore_test"
export APPURL="postgresql+psycopg://postgres:$TEST_PW@127.0.0.1:55432/normly_restore_test"
psql "$PGURL" -c 'CREATE EXTENSION IF NOT EXISTS vector'

# 4. Create the schema with the migrations of the release named in meta.json
#    (image_tag; --network host makes 127.0.0.1 the host)
docker run --rm --network host --entrypoint python \
  -e NORMLY_DATABASE_URL="$APPURL" \
  ghcr.io/normly/web-app/pipeline:0.2.0 -m normly_core.migrate

# 5. Import the knowledge base recorded in meta.json (kb_version) BEFORE the
#    user data: user data points into knowledge-base rows by foreign key.
#    Use --public-key or the key file while no key is packaged.
docker run --rm --network host --entrypoint python \
  -e NORMLY_DATABASE_URL="$APPURL" \
  -e NORMLY_KB_BASE_URL=https://example.invalid/kb \
  -e NORMLY_KB_PUBLIC_KEY_FILE=/kb-key.pem -v "$PWD/kb-signing.pub.pem:/kb-key.pem:ro" \
  ghcr.io/normly/web-app/pipeline:0.2.0 \
  -m normly_core.exchange import --fetch 2026.10.1     # the kb_version

# 6. Restore the user data
pg_restore --dbname="$PGURL" --data-only --exit-on-error $BASE.dump

# 7. Look at it
psql "$PGURL" -c "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname"
psql "$PGURL" -c 'SELECT count(*) FROM account'
```

Replace `NORMLY_KB_BASE_URL` with the real public dump URL. If `kb_version` is
`none`, skip step 5. For exact counts, run `SELECT count(*)` for each table
that `python -m normly_core.exchange tables user` lists and compare with
production. Clean up afterwards: `docker rm -f restore-test`, and delete the
decrypted dump.

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

The key ceremony is still pending. The public key is resolved as
`--public-key PATH`, then the environment variable `NORMLY_KB_PUBLIC_KEY_FILE`,
then the packaged key. Until a key is packaged, supply one yourself:

- `normly-deploy rollback`: set `NORMLY_KB_PUBLIC_KEY_FILE` in
  `/opt/normly/.env` to the key's path on the VM; the script mounts it into
  the container (see "Rolling back").
- `kb-import`: mount the key and point the variable at it:
  `docker compose run --rm -v /path/key.pem:/kb-key.pem:ro -e NORMLY_KB_PUBLIC_KEY_FILE=/kb-key.pem kb-import latest`
  (or pass `--public-key` to the underlying command).

**Export** (on the machine that holds the ingested knowledge base, over the
repository layer; `NORMLY_DATABASE_URL` points at that database and
`NORMLY_EMBEDDING_MODEL_REVISION` is set in the `pipeline` image). The output
directory is bind-mounted, so it must be writable by the container user: make
it world-writable for the run or add `--user "$(id -u):$(id -g)"`:

```bash
mkdir -p out && chmod 777 out
docker compose run --rm --entrypoint python \
  -v "$PWD/out:/out" -v "$PWD/kb-signing.key:/kb-signing.key:ro" \
  pipeline -m normly_core.exchange export \
  --version 2026.10.1 --out /out --private-key /kb-signing.key
# writes out/2026.10.1/{manifest.json,manifest.json.sig,<table files>}
```

The export commands here, like the restore test, were derived from the code and
are verified only in the live acceptance.

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

The signature of the manifest is checked right after the manifest arrives and
before any table file is downloaded, so a spoofed bucket cannot make the
client fetch an unbounded amount of data. The import then verifies the
signature again, the exchange schema version, the embedding
model name **and** revision, the vector dimension and every file checksum before
it writes. It is atomic and idempotent. It stops without changes if user data
still references a knowledge-base row that the new version removes, and names
the blocking references. How to resolve such cases is an open product decision
([ADR-025](../adr/README.md#adr-025-wissensbestand-dump-als-austauschformat)).

The dump contains no personal names: the export replaces
`source.responsible_person` and `rights_classification.classified_by` with the
role `normly maintainers` in every row. The real names exist only in the local
ingestion database. An import writes the role label into those columns, so a
production database that imports the public dump carries the label, not names.

`python -m normly_core.exchange verify (--from DIR | --fetch VERSION)
[--public-key PATH]` runs the same checks without a database; `normly-deploy
rollback` uses it as a preflight. `python -m normly_core.exchange info`
prints the imported dump version (or `none`); the rollout and the backup
record it.
