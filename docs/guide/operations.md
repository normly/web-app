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
  /opt/normly/bin/normly-backup-retention.py /opt/normly/bin/normly-cleanup
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
half-restored database. The cleanup timer needs no such care: `normly-cleanup`
skips its run while `state/deploy.lock` exists (see "Cleaning up user data").

Before it changes anything, the script runs three checks and refuses (nothing
changed) if any fails:

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
- The tombstone file of the backup (see "Backups") is downloaded, decrypted
  and validated (a JSON object, `format` 1, `rows` with exactly the five
  tables, each a list). If the backup's `meta.json` says `"tombstones": true`
  but `<base>.tombstones.age` is missing, the backup is treated as damaged and
  the rollback aborts. A backup from before the tombstone file existed has no
  such flag: the script prints a clear warning (a foreign-key error is
  possible while restoring user data that points at withdrawn documents) and
  the rollback continues.

- **Deletions since the backup.** Accounts and chats that users deleted after
  the backup would come back with the restore. The script reads them first,
  straight from the database with the host `psql` and `python3` (no release
  image has to start, which matters after a failed rollout): the rows of
  `deletion_log` with `deleted_at` later than the backup stamp minus 1 hour. The
  hour is a safety margin: a deletion logged
  shortly before the dump finished may or may not be inside it, and replaying
  one that is already gone is harmless (identifiers are never reused). The
  export goes to a file and is validated. If it cannot be made or is invalid,
  the rollback stops before the banner and changes nothing. If the database has
  no `deletion_log` table (a release from before the feature), the list is
  empty. The file feeds the banner and the next check. The core command
  `python -m normly_core.exchange export-deletions --since <ISO-8601>` makes the
  same document and stays available for manual use.
- **An interrupted rollback.** Before the `DROP`, the list to re-apply is saved
  to `/opt/normly/state/rollback-deletions.json` (mode 0600). If the run fails
  after the `DROP`, the deletion log is gone from the database and the work
  directory is removed, but this file stays, and the recovery message names it.
  The next rollback run validates it (a corrupt file stops the run before any
  change), says in the banner that it resumes an interrupted run, and merges it
  with the fresh export (by kind and identifier, the earliest time wins). The
  merged list is what is replayed. The file is deleted after the previous
  release started healthy.
- **Can the previous release replay deletions?** If the export has entries, the
  script runs `replay-deletions --check` in the **previous** release's image.
  Exit code 0 means supported; exit code 2 (unknown command) means not
  supported; any other failure aborts the rollback before the banner.

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

If deletions will be replayed, the banner says how many. If the previous
release cannot replay them (it predates this feature), the banner instead
warns: re-delete these by hand after the rollback, and shows their number and
the first 20 as `kind:id` (`account` or `chat_session`). The full list is
written later, see below.

It then prints what will be discarded and asks you to type the target tag
**without** the `v` (for example `0.1.0`); `--yes` skips the question for
scripted runs.

Then it:

1. stops the services, and takes the deletion export a **second** time (same
   source, same time, same validation): deletions made between the first export
   and the stop would otherwise be missed. This second file is the one that is
   replayed. If it fails, the rollback aborts **before** the `DROP`: the
   services are stopped, the database is unchanged, and the message prints a
   restart command that pins `NORMLY_IMAGE_TAG` to the stopped release (or run
   the rollback again). If the previous release cannot replay deletions and the
   second export still has entries, the file is copied to
   `/opt/normly/state/rollback-pending-deletions.json` (mode 0600) and a
   message names it; the file is deleted at the start of every rollback run, so
   it always belongs to the last run;
2. drops **all** tables in the `public` schema (the list is read from the
   database, so tables added by the newer release go too; the schema itself
   stays, so the pgvector extension survives);
3. runs `migrate` with the previous image;
4. imports the knowledge-base dump version recorded when the backup was taken
   (before the user data, because user data references knowledge-base rows by
   foreign key). The import fetches from `NORMLY_KB_BASE_URL`, so that variable
   must be set in `.env`. The duration grows with the size of the knowledge
   base;
5. restores the retired identifiers from the tombstone file
   (`python -m normly_core.exchange import-tombstones`, JSON on stdin, in the
   previous release's image), before the user data, because user rows such as
   watchlists and notifications may point at documents the older dump no
   longer contains. Rows are inserted with `ON CONFLICT DO NOTHING`, so
   existing rows are never changed. The inserted work, document and edge rows
   count as retired and have no rights classification, so every rights-gated
   read hides them; a later normal import that contains the row makes it
   active again. Only identifiers come back, never the content or rights of
   withdrawn documents. This step is skipped (with the warning above) for
   backups without a tombstone file;
6. restores the user data with `pg_restore --data-only`;
7. replays the deletions: `python -m normly_core.exchange replay-deletions`
   reads the second export on stdin, in the previous release's image, and
   deletes the accounts and chats again through the normal deletion functions.
   It is idempotent. Entries whose entity is already gone are counted as such
   and still written to the new deletion log, so a later rollback to an older
   backup stays complete. The step is skipped when there is nothing to replay,
   and replaced by the manual list above when the previous release does not
   support it;
8. starts the previous release and waits for it to become healthy.

**If the previous release could not replay deletions**, the restored database
contains the accounts and chats users had deleted. Delete them by hand from
`rollback-pending-deletions.json` (an `entries` list of `kind` and `entity_id`)
before you let users back in; the restored services are already running, so do
this promptly.

If a step fails after the tables were dropped, the script prints a recovery
message: the database is incomplete, services may be stopped or partly
running, `current_tag` is unchanged. Running the same `rollback` command again is safe, because it
rebuilds the schema from the backup each time. On success the failed-rollout
marker is cleared.

## Backups

`normly-backup` dumps **only the user-data tables** (`python -m
normly_core.exchange tables user` lists them): accounts, chats, watchlists,
notifications, rate-limit buckets, and the deletion log. The knowledge base is not backed up; it is
reproduced from its dump version. The only knowledge-base rows a backup adds
are the retired identifiers described below. Flex's own daily backup of the whole database
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
(prune) and **read** (rollback downloads `meta.json`, `dump.age` and
`tombstones.age` with rclone). What the VM cannot do is *decrypt*: the private age key is not there.
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

Each backup is four objects under `backups/` in the bucket, uploaded in this
order: `<stamp>-<kind>.meta.json` (Alembic revision, image tag, knowledge-base
version, and `"tombstones": true`), `<stamp>-<kind>.dump.age`,
`<stamp>-<kind>.tombstones.age`, and `<stamp>-<kind>.sha256`. The checksum
file covers both encrypted files, goes up last and is the commit marker: a
backup without it does not count.

The **tombstone file** holds the identifier rows of withdrawn works, documents
and edges (those with `retired_at`) plus the rows they reference by foreign
key within `source`, `delivery`, `work`, `document` and `edge`, as JSON
(`format` 1, `created_at`, `rows` per table, all columns including
`retired_at` and `revoked_at`). It never contains content, rights
classifications or user data. A retired edge's `revoked_at` is the time of the
import that retired it, not the time of the producer's revocation. The file may
contain `source.responsible_person`; on a production instance that is the
published role label, and the file is only ever written inside the
age-encrypted backup. `normly-backup` creates it inside the container
(`python -m normly_core.exchange export-tombstones`, stdout), checks it on the
host before encrypting (an empty or malformed export aborts the backup, and
nothing is uploaded) and removes the plaintext right after encryption.

**Retention** (applied by `normly-backup prune`): the newest backup of each of
the 7 most recent days with a daily backup; the newest daily backup of each of
the 2 most recent calendar months; the 3 newest pre-rollout backups. Retention
applies to all objects of a backup. Prune deletes `.sha256`, `meta.json`,
`tombstones.age` and `dump.age` in that order and skips objects that are not
in the listing, so older backups without a tombstone file are handled. It only
counts committed backups and deletes uncommitted leftovers once they are older
than one day.

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
rclone copyto stackit:normly-backups/backups/$BASE.tombstones.age ./$BASE.tombstones.age
rclone copyto stackit:normly-backups/backups/$BASE.sha256   ./$BASE.sha256
rclone copyto stackit:normly-backups/backups/$BASE.meta.json ./$BASE.meta.json
sha256sum -c $BASE.sha256
cat $BASE.meta.json        # alembic_revision, image_tag, kb_version, tombstones

# 2. Decrypt both files (the tombstone file like the dump)
age -d -i normly-backup.key -o $BASE.dump $BASE.dump.age
age -d -i normly-backup.key -o $BASE.tombstones.json $BASE.tombstones.age

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

# 6. Restore the retired identifiers BEFORE the user data: user rows may point
#    at documents the older dump no longer contains.
docker run --rm -i --network host --entrypoint python \
  -e NORMLY_DATABASE_URL="$APPURL" \
  ghcr.io/normly/web-app/pipeline:0.2.0 \
  -m normly_core.exchange import-tombstones < $BASE.tombstones.json

# 7. Restore the user data
pg_restore --dbname="$PGURL" --data-only --exit-on-error $BASE.dump

# 8. Replay the deletions made since the backup, as a rollback does.
#    Export them on the PRODUCTION VM (the release that wrote the log), from
#    one hour before the backup stamp on (BASE 20261009T033000Z ->
#    2026-10-09T02:30:00+00:00):
#    (the running release is pinned: Compose would default to the unsigned "edge")
TAG="$(cat /opt/normly/state/current_tag)"
cd /opt/normly/current && sudo NORMLY_IMAGE_TAG="$TAG" docker compose run --rm --no-deps -T \
  --entrypoint python pipeline -m normly_core.exchange export-deletions \
  --since 2026-10-09T02:30:00+00:00 > deletions.json
#    Copy deletions.json to the test machine, then apply it to the test database
#    with the image of the release named in meta.json:
docker run --rm -i --network host --entrypoint python \
  -e NORMLY_DATABASE_URL="$APPURL" \
  ghcr.io/normly/web-app/pipeline:0.2.0 \
  -m normly_core.exchange replay-deletions < deletions.json
#    prints "replayed deletions: N applied, M already gone"

# 9. Look at it
psql "$PGURL" -c "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname"
psql "$PGURL" -c 'SELECT count(*) FROM account'
```

Step 8 proves that deleted accounts and chats stay deleted after a restore:
the accounts and chats listed in `deletions.json` must be gone from the test
database afterwards. If the release named in `meta.json` predates this feature,
`replay-deletions` does not exist in its image (the call fails with a usage
error); delete the listed identifiers by hand instead. If the production database has no
`deletion_log` table yet, there is nothing to replay.

Replace `NORMLY_KB_BASE_URL` with the real public dump URL. If `kb_version` is
`none`, skip step 5. A backup from before the tombstone file existed has no
`.tombstones.age` (and no `"tombstones": true` in its `meta.json`); skip the
tombstone download, decryption and import, and expect a foreign-key error in step 7 if user data points at
withdrawn documents. For exact counts, run `SELECT count(*)` for each table
that `python -m normly_core.exchange tables user` lists and compare with
production. Clean up afterwards: `docker rm -f restore-test`, and delete the
decrypted dump.

## Cleaning up user data

`python -m normly_core.pipeline cleanup-user-data` enforces the retention
periods for user data. It is idempotent, prints counters only (no personal
data) and runs once a day from the systemd timer `normly-cleanup` (04:00 UTC,
`Persistent=true`, so a missed run is caught up). The timer starts
`/opt/normly/bin/normly-cleanup`, which runs the command in the release named by
`/opt/normly/state/current_tag` (it refuses to run without that file, and
`normly-backup` does the same; neither ever runs the unsigned `edge` image)
(`docker compose run --rm --no-deps -T pipeline cleanup-user-data`). The unit
files ship in the signed image and were copied to `/etc/systemd/system/` in
"Installing the scripts"; enable the timer as the backup timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now normly-cleanup.timer
systemctl list-timers normly-cleanup.timer
```

To run it by hand: `sudo /opt/normly/bin/normly-cleanup`. The output is one
line, for example `sessions=3 tokens=7 unverified_accounts=0
notifications_read=12 notifications_unread=0 anonymous_chats=0 deletion_log=0`.

The script skips the run (message on stderr, exit code 0) while
`/opt/normly/state/deploy.lock` exists, because a deploy or rollback drops and
restores tables. It only **checks** for the lock and does not take it. A stale
lock from a crashed run (see "Rolling back") therefore makes the timer skip
silently every day until you remove the lock; check `journalctl -u
normly-cleanup` after an incident.

The periods are named constants in `core/src/normly_core/retention.py`:

| Data | Deleted when |
|---|---|
| expired account sessions | 7 days after expiry |
| one-time account tokens (verification, reset, magic link) | 24 hours after expiry or use |
| abandoned registrations, with their tokens and chats | email never verified, created more than 30 days ago, **no** Google identity and **no** session row at all |
| notifications | read: 60 days after creation; unread: 365 days after creation |
| deletion log entries | 90 days |
| chats without an account (legacy data) | on every run |

An account that was never verified but is in use (a Google account, or a
password account that has logged in) is **not** an abandoned registration and is
never removed by this command. Chats of accounts have no retention period: the
user deletes them, or the account. The reasoning is in
[ADR-027](../adr/README.md#adr-027-lebenszyklus-der-nutzerdaten). The periods
are project decisions and should be reviewed by a data-protection professional.

## Deletions and backups

A deletion takes effect in the database at once. In backups the data stays
until they expire:

| Backup | Deleted data can remain for |
|---|---|
| PostgreSQL Flex daily backup | 30 days |
| own `age`-encrypted backups | up to roughly two months (7 daily, the newest of each of the last 2 calendar months, and the 3 newest pre-rollout backups; see "Backups") |

The deletion log (table `deletion_log`; kind `account` or `chat_session`,
identifier and time, no personal data) is how deletions survive a rollback or a
restore: it is part of the user-data backup, written in the same transaction as
each deletion, and pruned after 90 days. A pre-rollout backup can be older than
that if no rollout followed for a long time; a restore from a backup older than
90 days cannot re-apply deletions from the time since.

### Emergency restore from the Flex backup

The scripted rollback does this for you; restoring from PostgreSQL Flex (clone
or point-in-time restore in the STACKIT portal) does not. Do the following
yourself, in this order:

1. Before you restore (the live database is still the one that holds the log),
   export the deletions made since the restore point, one hour earlier than the
   point to be safe, in the current release:

   ```bash
   cd /opt/normly/current
   TAG="$(cat /opt/normly/state/current_tag)"    # pin the running release
   sudo NORMLY_IMAGE_TAG="$TAG" docker compose run --rm --no-deps -T --entrypoint python pipeline \
     -m normly_core.exchange export-deletions \
     --since 2026-10-09T02:30:00+00:00 > /root/deletions.json
   ```

   `--since` takes an ISO-8601 time with a timezone. Check that the file is a
   JSON document with an `entries` list. Keep it safe: it holds identifiers
   only, but treat it as internal.
2. Restore the database from Flex and point `NORMLY_DATABASE_URL` at it. If
   the restored schema is older than the running release, run the migrations of
   the release that matches it first.
3. Apply the deletions again, with the image of the release that matches the
   restored schema:

   ```bash
   # TAG = the release that matches the restored schema
   sudo NORMLY_IMAGE_TAG="$TAG" docker compose run --rm --no-deps -T --entrypoint python pipeline \
     -m normly_core.exchange replay-deletions < /root/deletions.json
   ```

   It prints `replayed deletions: N applied, M already gone`. If that release
   predates this feature, the command does not exist: delete the listed
   accounts and chat sessions by hand.
4. Start the services and delete `/root/deletions.json` when you are done.

If the live database is lost, there is no log to export; the deletions since
the restore point cannot be re-applied from it.

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
export NORMLY_IMAGE_TAG="$(cat /opt/normly/state/current_tag)"   # never the "edge" default
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
export NORMLY_IMAGE_TAG="$(cat /opt/normly/state/current_tag)"   # never the "edge" default
docker compose run --rm kb-import              # kb/latest
docker compose run --rm kb-import 2026.10.1    # a fixed version
```

The signature of the manifest is checked right after the manifest arrives and
before any table file is downloaded, so a spoofed bucket cannot make the
client fetch an unbounded amount of data. The import then verifies the
signature again, the exchange schema version, the embedding
model name **and** revision, the vector dimension and every file checksum before
it writes. It is atomic and idempotent. A takedown always wins and user data never
blocks an import: what the new version no longer contains loses its content
(designations, titles, rights classification, segments, embeddings are deleted),
while works, documents and edges stay as tombstones marked `retired_at` (edges
are also revoked) and missing deliveries are marked withdrawn. User data such as
watchlists, notifications and chat history is kept; chat citations only lose
their segment reference. A tombstone that returns in a later dump becomes active
again. Watchers of a withdrawn document get a "no longer available"
notification the next time `notify-watchers` runs, but only watchers whose
watch is older than the withdrawal and who have notifications enabled. An import of a dump without
any documents is refused while the database holds documents; pass
`--allow-empty` to apply it deliberately
([ADR-026](../adr/README.md#adr-026-umgang-mit-nutzerdaten-beim-wissensbestand-import)).

The dump contains no personal names: the export replaces
`source.responsible_person` and `rights_classification.classified_by` with the
role `normly maintainers` in every row. The dump never carries names;
whatever names an ingestion operator enters live only in that operator's own
database. An import writes the role label into those columns, so a production database that imports the public dump carries the label, not names.
Never import a dump into an ingestion database: the upsert overwrites the names
there irrevocably.

`python -m normly_core.exchange verify (--from DIR | --fetch VERSION)
[--public-key PATH]` runs the same checks without a database; `normly-deploy
rollback` uses it as a preflight. `python -m normly_core.exchange info`
prints the imported dump version (or `none`); the rollout and the backup
record it.
