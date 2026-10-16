# Design: Deployment automation (STACKIT deployment, sub-project 4/4)

As of: 2026-10-09 · Status: implemented except for the live acceptance (Task 9). Roadmap and
fundamental decisions E1–E8:
`docs/superpowers/specs/2026-09-23-stackit-deployment-roadmap-design.md`.
Predecessor: `docs/superpowers/specs/2026-10-08-tp2-image-pipeline-design.md`
(implemented, release `v0.1.0`).

## Goal

New versions reach production without a build on the VM and without STACKIT credentials
on GitHub, can be rolled back, and the free
knowledge base is shipped versioned separately from the code. Fulfills
REQ-INST-002 (automated deployment), REQ-INST-004 (rollback),
REQ-DIST-004 and ADR-010 (data separate from the image).

Today the VM builds from `/opt/normly/src` (sync via `scripts/sync-to-vm.sh`),
there is no rollback point, and the knowledge base is created by ingestion
on the VM. This also blocks the downsizing to `g1a.2d` (TP1a).

## Decomposition

The owner deliberately chose **one** spec for all three parts (option C
of the decomposition question; the recommendation was to split off rollout first). The parts
are therefore kept separately acceptable and can be cut into sections of their own
or plans of their own in the plan:

1. Rollout and rollback (`normly-deploy`)
2. Database backup (`normly-backup`)
3. Knowledge base dump (`normly-kb export` / `import`)

## Decisions

| # | Question | Decision | Rejected |
|---|---|---|---|
| D1 | Rollout trigger | Manual invocation via SSH, script kept timer-capable | Timer with auto-rollout (migrations would run unattended, needs "highest tag" logic and a stability window) |
| D2 | Rollback and migrations | Rollback restores images **and** data to the state before the rollout, with a warning and confirmation | Images only (requires an expand/contract discipline for migrations that does not exist) |
| D3 | Backup target | `age`-encrypted on the VM, private bucket in STACKIT Object Storage, private key never on the VM | Server-side encryption only (key with the provider, next to the data); pre-rollout dumps only |
| D4 | Dump format | Parquet per table plus signed manifest, import through the repository layer | `pg_dump` of the knowledge base (see below) |
| D5 | Distribution | Publicly readable Object Storage bucket, calendar version, signed manifest | STACKIT Git repository (large binary files, anonymous access unwieldy); Git additionally as manifest history (second system) |
| D6 | Backup by data type | User data backed up daily, knowledge base not (can be reconstructed from the dump), Flex backup as operational safety net | Daily full dump (wasteful at double-digit GB) |

### Rationale D4: Parquet instead of `pg_dump`

The owner chose B against the original recommendation (A, `pg_dump`);
the reasons that support it:

- **ADR-006 / CLAUDE.md:** Database access runs only through the
  repository layer, so that the storage technology stays interchangeable.
  `pg_dump` is a Postgres artifact and bypasses it.
- **The dump is a public product** (REQ-DIST-004) that third parties
  import. A format not bound to our Alembic revision survives
  schema changes; with `pg_dump`, every self-hoster would have to find the matching
  application version.
- **Lineage:** A table-by-table export with the source delivery per row
  keeps the withdrawal of a delivery traceable in the dump as well.
- **Price:** more code (export, import, exchange schema), slower
  import, idempotency to be established ourselves. Parquet instead of NDJSON, because
  embeddings (1024 floats, ~4 KB per section) would otherwise become unwieldy.

## Part 1: Rollout and rollback (`normly-deploy`)

Shell script `scripts/normly-deploy`, runs on the VM without a
source code checkout, with a narrow directory (`compose.yaml`, `.env`).
It uses what `compose.yaml` already has: the `migrate` service before `api`,
`accounts` and `chat`, and the parametrization `NORMLY_IMAGE_TAG`.

**`normly-deploy deploy vX.Y.Z`**

0. A tag equal to the current one is rejected. If a
   failed rollout is recorded (`state/failed_rollout`), no
   new `deploy` starts until the rollback has run; the operator can
   deliberately override this by removing the file.
1. `cosign verify` for all five images against the GitHub OIDC identity of the
   release workflow. If a verification fails: abort, nothing changed.
   **Digest pinning:** The verified digest (`docker-manifest-digest` from the
   cosign output) is recorded (`releases/<tag>/verified-digests`).
   The assets come from `pipeline@<digest>`; after `pull`, the digest of
   every image must match the verified one, otherwise abort before `up`. A
   tag moved in the meantime thus does not bypass the verification.
2. Pre-rollout backup according to Part 2 (user data) together with the current tag and
   the dump version of the knowledge base. Without a confirmed upload, no rollout.
   If the dump version of the running release cannot be read,
   the rollout aborts; `none` is recorded only if `info` reports it.
3. `docker compose pull` with `NORMLY_IMAGE_TAG=vX.Y.Z`.
4. `migrate`, then `up -d`.
5. Wait for the `/health` endpoints of all services with a timeout (earmarked by TP1 for
   TP4).
6. On success: record the tag as `current`, the previous one as `previous`. On
   failure: clear message, **no** automatic way back; `previous` is
   set to the release running until then (rollback target) and the
   failed tag is recorded in `failed_rollout`.

**`normly-deploy rollback`:** first checks, before anything is changed, whether
the Alembic revision from `<backup>.meta.json` matches the Alembic head of the
**previous** image; on a mismatch, abort (dump and schema
would otherwise not fit together). Then it shows which data will be discarded (from the
pre-rollout dump until now), requires explicit confirmation and
then restores the state before the rollout. Because Alembic migrations only run
forward, the new schema would remain after a pure data restore;
the rollback therefore **rebuilds** the schema:

1. Stop the services.
2. Drop all tables (`DROP TABLE … CASCADE`; the list comes from the
   database itself, not from the previous image, so that tables of the
   newer release disappear as well; the schema remains so that pgvector is
   preserved) and recreate them with the `migrate` service of the **previous** image at its
   Alembic revision.
3. Import the knowledge base in the dump version of that time (stable IDs,
   see Part 3). This must happen **before** the user data, because the user data
   references knowledge base rows by foreign key (`watchlist` →
   `work`, `notification` → `edge`/`document`, `chat_message_citation` →
   `document`/`segment`).
4. Restore the retired IDs from the backup's tombstone file
   (`exchange import-tombstones`; user rows can point to tombstones
   that are in no dump; see ADR-026). Older backups without the file:
   warning, the rollback continues.
5. Restore the user data from the pre-rollout dump (`--data-only`; schema and
   dump come from the same Alembic revision).
6. Start `previous`, check health.

The duration of step 3 grows with the collection; the script states it in advance.
If the rollback fails after the drop, the script reports that the
database is incomplete, that `current_tag` remains unchanged and that the
identical invocation can be repeated safely. Once it completes successfully,
it deletes `failed_rollout`.

**Failure cases:** If `migrate` gets only halfway through, the pre-rollout dump is the
way out (the script says so). A lock file prevents parallel runs.
Emergency route for migrations on knowledge base tables and large collections: the
Flex restore.

**Not included:** Secrets via AppRole (TP3); the script reads
`/opt/normly/.env` as today. No timer; the interface allows one
later without rework.

## Part 2: Database backup (`normly-backup`)

Called by the rollout and by a daily systemd timer.

**Split by data type (D6):**

| Data | Property | Backup |
|---|---|---|
| User data (accounts, chats, watchlists, notifications, rate limiting) | small, irreplaceable | daily `pg_dump -Fc` of these tables only, `age`-encrypted, Object Storage |
| Knowledge base | large, reproducible | no dump of its own; state = most recently imported dump version |
| Entire database | operations | Flex backup (see finding) |

The assignment is recorded as an allowlist in the code
(`normly_core/exchange/tables.py`), with a test that assigns every ORM table to
exactly one group (a new table without an assignment makes the test
fail). There are three groups: **knowledge base** (`source`,
`delivery`, `work`, `document`, `document_designation`, `document_title`,
`rights_classification`, `edge`, `segment`, `embedding`,
`document_embedding`), **user data** (`account*`, `oauth_state`,
`watchlist`, `notification`, `rights_notification_baseline`,
`notified_edge`, `notified_retirement`, `chat_*`, `rate_limit_bucket`) and **pipeline state**
(`identity_resolution_case`: review queue of the local ingestion, empty in
production, neither exported nor backed up). User data references
knowledge base rows by foreign key; the dump must therefore keep the
**IDs unchanged** (prerequisite for rollback and restore).

**Prerequisite:** The knowledge base in production changes **only** through
dump import, never through ingestion on the VM. This is at the same time the
prerequisite for TP1a.

**Upload tool:** `rclone` (open source, one binary, S3-compatible
against STACKIT Object Storage); no US service, only a client.

**Procedure:** dump → encrypt on the VM with the public `age` key
(temporary file in a 0700 directory, no plaintext
afterwards) → upload to `backups/<UTC-timestamp>-<kind>.dump.age`
(`daily` or `pre-<tag>`) → second encrypted file
`<base>.tombstones.age` with the retired IDs (see ADR-026) →
checksum next to it, covering both files. A backup counts only
after a confirmed upload; cleanup runs only after that.

**Key:** The private `age` key lives in the Secrets Manager and as an
offline copy with the operator, **not** on the VM. The VM can write,
not read. Restore and rollback need the key briefly
(provided by the operator). Credentials for Object Storage come from
`/opt/normly/.env`.

**Retention (as of now, may change because of the Flex finding):** 7 daily,
2 monthly, 3 pre-rollout backups. Rationale: user data is small
(megabytes), the costs are secondary; 7 days cover the typical
discovery window of a single instance, monthly backups serve as an anchor for
damage detected late. Weekly backups are dropped (benefit beyond 7 days
small). An object lock is not
used for now (decision 2026-10-10, rationale see "Open items" and
ADR-024).

**Restore test:** Manual and documented, once after the build, then a
monthly reminder. An automatic test would need the private
key on a machine and would contradict the key concept.

### Finding: Flex backup (2026-10-09, screenshot of the portal)

- Daily backup at 11:45 (UTC), expiry after 30 days (start 08.10.,
  expiry 07.11.).
- Size currently 3.66 MB; the knowledge base is still missing.
- **Not checked:** point-in-time recovery (PITR), encryption
  of the Flex backups. Both are to be clarified in the STACKIT documentation before the build;
  PITR determines whether the daily dumps can be kept even
  shorter (guideline value 3).

## Part 3: Knowledge base dump

**Content:** Only free collections (categories A, B, D). Allowlist per table,
in addition every row must be cleared by the rights classification
(the single gate); missing classification means do not export. User data
and licensed collections are never included.

**Format:** Parquet per table (large tables in parts) and
`manifest.json` with: exchange schema version (independent of Alembic),
dump version (calendar, e.g. `2026.10.1`) and timestamp, embedding model
with pinned revision and dimension, included source deliveries with
publisher and category (the legal basis per document is in the
rows of `rights_classification`), checksum and row count per file. Every row
carries its source delivery (lineage).

**Personal names:** The export replaces `source.responsible_person` and
`rights_classification.classified_by` in every row with the role
`normly maintainers` (constant `PUBLISHED_ROLE`, in the export statement of the
repository layer, that is, at the gate). The dump never carries names; the code contains
only a placeholder, entered names live only in the operator's
database. Manifest and schema do not change. An import
overwrites the columns with the label, a renewed export stays
row-identical. A test checks that a unique name occurs in no row, no
Parquet file and not in the manifest.

**Export (`normly-kb export`):** locally at ingestion, through the
repository layer. The result is an uploadable directory; a version
is immutable and is never overwritten.

**Distribution (D5):** Publicly readable STACKIT Object Storage bucket,
`kb/<version>/`, plus `kb/latest`. The manifest is signed with a
maintainer key (no keyless certificate possible, because the dump
is created locally, not in CI); the public key lives in the
repository. **Tool: Ed25519 in Python (`cryptography`), verified in the import
itself.** Rationale: The import runs in the `pipeline` image and at the
self-hoster's; an additional binary (cosign, minisign) would enlarge the image
and create a second installation hurdle. Signature format and
verification are small enough to keep them testable in the core. The verification of the
images with cosign (Part 1) remains unaffected by this.

**Import (`normly-kb import <version>`):**

1. Load the manifest, verify the signature; otherwise abort.
2. Check the exchange schema version and embedding model; on a mismatch,
   abort with a clear message (no silently wrong embeddings).
3. Verify the checksums, import through the repository layer.
4. **Idempotent:** Repeating the same version produces no
   different state; rows are identified by stable keys,
   rows missing in the new version are handled according to ADR-026:
   citations in chats lose their section reference, content and derivations
   (designations, titles, rights classification, sections, embeddings)
   are deleted, `work`/`document`/`edge` remain as tombstones with
   `retired_at` (edges additionally revoked), missing deliveries receive
   `withdrawn_at`; then rows are inserted or updated (moves
   foreign keys, e.g. `document.work_id` after a work merge or
   `rights_classification.delivery_id` to a new delivery; if a row
   returns, `retired_at` becomes `NULL` again). A work merge exports the
   merged work together with its target, so that the redirect is
   preserved on import. The exchange is atomic, the application never sees a
   half collection. User data does not block the import; a dump without
   documents is rejected as long as the database holds documents (flag
   `--allow-empty`). See ADR-026.
5. The imported version is recorded in a small table;
   rollout and rollback read it there.

**First start of self-hosters:** A tool profile in `compose.yaml`
runs `normly-kb import latest` (REQ-DIST-004: "obtained on first
start").

**Not included:** Delta dumps. The format leaves them open without
building them.

## Documentation that goes along

- **ADR-024** "Rollout, rollback and backup on the single VM": D1, D2,
  D3, D6 with rationale and what was rejected.
- **ADR-025** "Knowledge base dump as exchange format": D4, D5.
- **ADR-021, addendum:** The statement that STACKIT Git is intended for the future
  hosting of the norms knowledge base is dropped; the knowledge base
  is distributed as a dump in Object Storage (ADR-025). As a dated
  addendum, not as a silent overwrite (pattern: ADR-020). To be updated along with it:
  the sentence in `CLAUDE.md`, REQ-GIT-005 in `docs/srs/03-requirements.md` and
  the ADR register. What happens to the STACKIT Git repository `normly-webapp`
  (archive or delete) is a separate decision of the
  owner and not part of this spec.
- **SRS:** references at REQ-INST-002, REQ-INST-004, REQ-DIST-004.
- **`docs/guide/`** (English, ADR-020): operations section for rollout,
  rollback, backup and restore; extend `self-hosting.md` with the dump import
  (the sentence "No versioned knowledge-base dump yet" is dropped).

## Open items

- Clarify PITR and encryption of the Flex backups (see finding); can
  change the retention.
- Object lock in the backup bucket: **decided on 2026-10-10, none for now.**
  According to the operator (to be checked against the STACKIT documentation),
  Object Lock needs a project-wide Compliance Lock and can only be chosen when
  the bucket is created, and can never be switched off afterwards. Reasons against:
  irreversibility before the first live acceptance; effect on the whole project;
  `normly-backup` deletes old backups itself and would fail until the end of the period;
  a lock over 90 days would retain deleted user data longer
  than the rollback replays the deletions (deletion log 90 days). Accepted
  residual risk: with stolen VM credentials, backups could be deleted
  (not read: `age`). To be examined: VM credentials without delete permission, cleanup
  of the retention from elsewhere. Reassessment after the live acceptance;
  later possibly a second bucket with a lock of ≤ 90 days.
- Cryptographic erasure at contract end (ADR-014): The daily dump
  contains user data, but no licensed collections. As soon as licensed
  collections live in Postgres, they must be excluded from backups or
  encrypted per publisher (task of the commercial layer).
- Size and duration of export and import can only be measured with a real collection;
  the rollback duration (re-import) is then shown in `normly-deploy`.
- Assignment of every table to knowledge base or user data (in the plan, with a
  test against forgotten tables).

## Verification 2026-10-11 (live acceptance, as of: Parts 1 and 2 green)

Carried out on the production VM (`normly-prod`), release `v0.2.0`.

**Confirmed:**

- Release: tag `v0.2.0`, the `Images` workflow ran green, the CI on `main` before it
  as well. The GHCR packages are public (pull without sign-in).
- Preparation: buckets `normly-backups` (private) and `normly-kb` (public)
  in the region `eu01`, without object lock (decision 2026-10-10, see
  "Open items"). rclone runs without `rclone.conf`, solely via
  `RCLONE_CONFIG_STACKIT_*` in the `.env`. `cosign` 2.5.2 from the
  release package (checksum verified), `age` and `postgresql-client` from the
  Ubuntu repository.
- Scripts: installation from the signed `pipeline` image via the digest as
  in the operations guide, signature verification passed.
- First deployment `normly-deploy deploy v0.2.0` over the old stack from
  `/opt/normly/src`: The release stack uses the same Compose project name
  (`normly`) and replaces the containers in place, the volumes remain.
  Result: `migrate` finished, five services `Healthy`, `app.normly.ai` answers
  with HTTP 200, `normly-deploy status` shows `current: 0.2.0`; `previous` and
  the pre-rollout backup are empty (intended for the first
  deployment). The migrations 0035 to 0037 ran without errors.
- First backup `normly-backup run --kind daily`: four objects in the bucket
  (`.dump.age`, `.meta.json`, `.sha256`, `.tombstones.age`). Timer
  `normly-backup.timer` enabled, next run 03:30 UTC.

**Findings:**

- The SMTP block was missing in the VM's `.env`: until then the app had sent no
  e-mails (verification, magic link, password reset,
  notifications). A mailbox with a European provider was
  set up and `NORMLY_SMTP_*` entered; the first real sending has
  not been checked yet.
- `NORMLY_KB_BASE_URL` must end in `.../kb`: the import fetches
  `<base>/latest` and `<base>/<version>/manifest.json`.
- The VM's backup access needs delete permission (`normly-backup prune`); a
  mitigation with credentials without delete permission remains open.
- `cleanup-user-data` has no dry-run mode. The timer `normly-cleanup.timer`
  is deliberately not enabled yet: with SMTP, the first run would send warning e-mails to
  abandoned registrations.

**Still open (needs data in the database):**

- Knowledge base dump end to end (export with the private signing key,
  upload to `kb/<version>/` and `kb/latest`, `kb-import`, negative tests).
  Then enter the real `NORMLY_KB_BASE_URL` in `docs/guide/self-hosting.md`
  (today a placeholder stands there, because no
  dump lives under the URL yet).
- Restore test on another machine with the private `age` key (the
  section "Restore test" in the operations guide has so far only been derived from the code)
  and monthly thereafter.
- Rollback drill to a second test tag, including the replay of
  user data deleted in the meantime.
- Enable `normly-cleanup.timer` as soon as there is user data.

## Non-goals

- Timer-driven auto-rollout, blue/green, canary.
- Secrets via AppRole (TP3).
- Delta dumps, incremental backups.
- Automated restore test.
- Decision about the STACKIT Git repository.
