# Security Policy

## Reporting a vulnerability

**Please do not report security vulnerabilities as a public issue.**

Report to: **security@normly.ai**

Helpful for us:

- Affected component and version
- Description and potential impact
- Steps to reproduce
- Your assessment of the severity

Encrypted reports are possible; the public key is at
`docs/security/pgp-key.asc` *(to be added)*.

## What you can expect

| | |
|---|---|
| Acknowledgement of receipt | within **3 business days** |
| Initial assessment | within **10 business days** |
| Status update | at least every **14 days** until resolved |

We follow coordinated disclosure: once fixed, we publish an advisory and
credit you as the finder, if you'd like that. There are usually **90 days**
between a fix and publication — considerably less for actively exploited
vulnerabilities.

## Scope

**In scope:** this repository's core, the public API, the processing
pipeline, authentication and authorization, the container images, and the
build and delivery paths.

**Especially relevant** are vulnerabilities that break one of the following
guarantees:

- Separation of licensed holdings between tenants
- Unreachability of licensed content through anonymous access
- Effectiveness of withdrawal for retracted holdings
- Protection against systematic bulk extraction

**Out of scope:** vulnerabilities in third-party dependencies (please report
those there; a note to us is still welcome), attacks that require physical
access or an already-compromised account, and reports from automated
scanners without demonstrated impact.

## Rules for security research

Permitted and welcome, as long as you test on your **own instance**, don't
access, modify, or delete other people's data, don't impair availability,
and don't publish findings before coordinated disclosure.

Anyone who follows these rules has nothing to fear from us legally.

## There is currently no bug bounty program.
