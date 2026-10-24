# SRS / SDD — normly

Software Requirements Specification and Software Design Description.
Split into chapters so that readers can read selectively instead of the whole document.

## Chapters

| File | Contents |
|---|---|
| [01-introduction.md](01-introduction.md) | Purpose of the document, product vision, definitions |
| [02-product-overview.md](02-product-overview.md) | Product perspective, functions, constraints, user groups, assumptions |
| [03-requirements.md](03-requirements.md) | All requirements, chapters 3.1–3.16 |
| [05-verification.md](05-verification.md) | Verification |
| [06-appendices.md](06-appendices.md) | Appendices |

## Chapter structure of the requirements

| | Chapter | Group |
|---|---|---|
| 3.1 | External interfaces | `REQ-UI`, `REQ-INT` |
| 3.2 | Functional requirements | `REQ-FUNC` |
| 3.3 | Non-functional requirements | `REQ-PERF` |
| 3.4 | Compliance | — |
| 3.5 | Design and implementation | `REQ-INST`, `REQ-BUILD`, `REQ-DIST` |
| 3.6 | AI/ML | — |
| 3.7 | Open source and governance | `REQ-OSS` |
| 3.8 | Source code management and Git workflow | `REQ-GIT` |
| 3.9 | Reference graph | `REQ-GRAPH` |
| 3.10 | Content partnerships and remuneration | `REQ-PART` |
| 3.11 | Commercial add-on services | `REQ-COM` |
| 3.12 | Data acquisition and processing chain | `REQ-PIPE` |
| 3.13 | Encryption and protection of licensed content | `REQ-SEC` |
| 3.14 | Protected display and offline use | `REQ-DRM` |
| 3.15 | Mobile provision | `REQ-MOB` |
| 3.16 | Access and account requirement | `REQ-ACC` |

## Related documents

- [../adr/](../adr/) — Architecture decisions with rationale
- [../normly_processing-chain.svg](../normly_processing-chain.svg) — Pipeline from the source to the output
- [../normly_development-phases.svg](../normly_development-phases.svg) — Phase plan

## Requirement index

78 requirements in 17 groups. All in [03-requirements.md](03-requirements.md).

### REQ-UI — User interface

| ID | Title | Section |
|---|---|---|
| [`REQ-UI-001`](03-requirements.md#req-ui-001-chat-interface-of-the-standalone-web-application) | Chat interface of the standalone web application | 3.1.1 |
| [`REQ-UI-002`](03-requirements.md#req-ui-002-chat-based-interaction) | Chat-based interaction | 3.1.1 |
| [`REQ-UI-003`](03-requirements.md#req-ui-003-citations-and-linking) | Citations and linking | 3.1.1 |
| [`REQ-UI-004`](03-requirements.md#req-ui-004-wcag-conformance) | WCAG conformance | 3.1.1 |
| [`REQ-UI-005`](03-requirements.md#req-ui-005-display-and-management-of-the-chat-history) | Display and management of the chat history | 3.1.1 |

### REQ-INT — Integration and interfaces

| ID | Title | Section |
|---|---|---|
| [`REQ-INT-001`](03-requirements.md#req-int-001-public-api-for-integration-into-third-party-software) | Public API for integration into third-party software | 3.1.3 |
| [`REQ-INT-002`](03-requirements.md#req-int-002-interface-to-norm-databases) | Interface to norm databases | 3.1.3 |
| [`REQ-INT-002A`](03-requirements.md#req-int-002a-user-based-document-upload-and-temporary-model-enrichment) | User-based document upload and temporary model enrichment | 3.1.3 |
| [`REQ-INT-002B`](03-requirements.md#req-int-002b-isolation-of-user-specific-documents) | Isolation of user-specific documents | 3.1.3 |
| [`REQ-INT-002C`](03-requirements.md#req-int-002c-time-limited-storage-of-uploaded-documents) | Time-limited storage of uploaded documents | 3.1.3 |
| [`REQ-INT-003`](03-requirements.md#req-int-003-sso-authentication) | SSO authentication | 3.1.3 |
| [`REQ-INT-004`](03-requirements.md#req-int-004-llm-interface) | LLM interface | 3.1.3 |

### REQ-FUNC — Functional requirements

| ID | Title | Section |
|---|---|---|
| [`REQ-FUNC-001`](03-requirements.md#req-func-001-answering-norm-based-questions) | Answering norm-based questions | 3.2 |
| [`REQ-FUNC-002`](03-requirements.md#req-func-002-paraphrasing-instead-of-full-text) | Paraphrasing instead of full text | 3.2 |
| [`REQ-FUNC-003`](03-requirements.md#req-func-003-error-and-fallback-answers) | Error and fallback answers | 3.2 |

### REQ-PERF — Performance

| ID | Title | Section |
|---|---|---|
| [`REQ-PERF-001`](03-requirements.md#req-perf-001-chat-response-time) | Chat response time | 3.3.1 |

### REQ-INST — Installation and deployment

| ID | Title | Section |
|---|---|---|
| [`REQ-INST-001`](03-requirements.md#req-inst-001-deployment-on-german-stackit-infrastructure) | Deployment on German StackIT infrastructure | 3.5.1 |
| [`REQ-INST-002`](03-requirements.md#req-inst-002-automated-deployment) | Automated deployment | 3.5.1 |
| [`REQ-INST-003`](03-requirements.md#req-inst-003-configuration-management-via-environment-variables) | Configuration management via environment variables | 3.5.1 |
| [`REQ-INST-004`](03-requirements.md#req-inst-004-rollback-capability) | Rollback capability | 3.5.1 |

### REQ-BUILD — Build and shipping

| ID | Title | Section |
|---|---|---|
| [`REQ-BUILD-001`](03-requirements.md#req-build-001-reproducible-builds) | Reproducible builds | 3.5.2 |
| [`REQ-BUILD-002`](03-requirements.md#req-build-002-cicd-infrastructure-for-the-free-core) | CI/CD infrastructure for the free core (ADR-021) | 3.5.2 |
| [`REQ-BUILD-003`](03-requirements.md#req-build-003-automated-quality-assurance-in-the-build) | Automated quality assurance in the build | 3.5.2 |

### REQ-DIST — Distribution

| ID | Title | Section |
|---|---|---|
| [`REQ-DIST-001`](03-requirements.md#req-dist-001-clear-separation-of-environments) | Clear separation of environments | 3.5.3 |
| [`REQ-DIST-002`](03-requirements.md#req-dist-002-scalable-distribution-of-the-system-components) | Scalable distribution of the system components | 3.5.3 |
| [`REQ-DIST-003`](03-requirements.md#req-dist-003-optional-multi-tenancy-for-managed-hosting) | Optional multi-tenancy for managed hosting | 3.5.3 |
| [`REQ-DIST-004`](03-requirements.md#req-dist-004-versioned-shipping-of-the-application) | Versioned shipping of the application | 3.5.3 |

### REQ-OSS — Open source and governance

| ID | Title | Section |
|---|---|---|
| [`REQ-OSS-001`](03-requirements.md#req-oss-001-license-model-of-the-free-core) | License model of the free core | 3.7 |
| [`REQ-OSS-002`](03-requirements.md#req-oss-002-separation-of-free-core-and-commercial-layer) | Separation of free core and commercial layer | 3.7 |
| [`REQ-OSS-003`](03-requirements.md#req-oss-003-contribution-model-dco) | Contribution model (DCO) | 3.7 |
| [`REQ-OSS-004`](03-requirements.md#req-oss-004-community-governance-and-security-process) | Community governance and security process | 3.7 |
| [`REQ-OSS-005`](03-requirements.md#req-oss-005-license-compliance-of-dependencies) | License compliance of dependencies | 3.7 |
| [`REQ-OSS-006`](03-requirements.md#req-oss-006-trademark-rights) | Trademark rights | 3.7 |

### REQ-GIT — Source code management and Git workflow

| ID | Title | Section |
|---|---|---|
| [`REQ-GIT-001`](03-requirements.md#req-git-001-github-as-the-primary-platform-for-the-core-source-code) | GitHub as the primary platform for the core source code (ADR-021) | 3.8 |
| [`REQ-GIT-002`](03-requirements.md#req-git-002-contribution-path-via-github) | Contribution path via GitHub (ADR-021) | 3.8 |
| [`REQ-GIT-003`](03-requirements.md#req-git-003-branch-and-release-strategy) | Branch and release strategy | 3.8 |
| [`REQ-GIT-004`](03-requirements.md#req-git-004-merge-request-policy) | Merge request policy | 3.8 |
| [`REQ-GIT-005`](03-requirements.md#req-git-005-supply-chain-integrity) | Supply chain integrity | 3.8 |

### REQ-GRAPH — Reference graph

| ID | Title | Section |
|---|---|---|
| [`REQ-GRAPH-001`](03-requirements.md#req-graph-001-open-norm-reference-graph) | Open norm reference graph | 3.9 |
| [`REQ-GRAPH-002`](03-requirements.md#req-graph-002-layering-of-free-and-commercial-graph-share) | Layering of free and commercial graph share | 3.9 |
| [`REQ-GRAPH-003`](03-requirements.md#req-graph-003-graph-first-query-processing) | Graph-first query processing | 3.9 |
| [`REQ-GRAPH-004`](03-requirements.md#req-graph-004-technology-independence-of-graph-storage) | Technology independence of graph storage | 3.9 |
| [`REQ-GRAPH-005`](03-requirements.md#req-graph-005-internationalization-of-the-reference-graph) | Internationalization of the reference graph | 3.9 |
| [`REQ-GRAPH-006`](03-requirements.md#req-graph-006-jurisdiction-specific-license-classification) | Jurisdiction-specific license classification | 3.9 |

### REQ-PART — Content partnerships and remuneration

| ID | Title | Section |
|---|---|---|
| [`REQ-PART-001`](03-requirements.md#req-part-001-partner-portal-for-content-supply) | Partner portal for content supply | 3.10 |
| [`REQ-PART-002`](03-requirements.md#req-part-002-source-attribution-per-answer) | Source attribution per answer | 3.10 |
| [`REQ-PART-003`](03-requirements.md#req-part-003-revenue-share-and-auditable-billing) | Revenue share and auditable billing | 3.10 |
| [`REQ-PART-004`](03-requirements.md#req-part-004-protection-and-separation-of-licensed-full-text-collections) | Protection and separation of licensed full-text collections | 3.10 |

### REQ-COM — Commercial add-on services

| ID | Title | Section |
|---|---|---|
| [`REQ-COM-001`](03-requirements.md#req-com-001-extension-interface) | Extension interface | 3.11 |
| [`REQ-COM-002`](03-requirements.md#req-com-002-integration-into-third-party-software) | Integration into third-party software | 3.11 |
| [`REQ-COM-003`](03-requirements.md#req-com-003-usage-based-billing) | Usage-based billing | 3.11 |
| [`REQ-COM-004`](03-requirements.md#req-com-004-verifiable-answers-and-audit-trail) | Verifiable answers and audit trail | 3.11 |
| [`REQ-COM-005`](03-requirements.md#req-com-005-exclusion-of-personalized-advertising) | Exclusion of personalized advertising | 3.11 |

### REQ-PIPE — Data acquisition and processing chain

| ID | Title | Section |
|---|---|---|
| [`REQ-PIPE-001`](03-requirements.md#req-pipe-001-uniform-processing-chain) | Uniform processing chain | 3.12 |
| [`REQ-PIPE-002`](03-requirements.md#req-pipe-002-source-register) | Source register | 3.12 |
| [`REQ-PIPE-003`](03-requirements.md#req-pipe-003-check-for-rights-reservations) | Check for rights reservations | 3.12 |
| [`REQ-PIPE-004`](03-requirements.md#req-pipe-004-rights-classification-as-processing-gate) | Rights classification as processing gate | 3.12 |
| [`REQ-PIPE-005`](03-requirements.md#req-pipe-005-lineage-and-cascading-withdrawal) | Lineage and cascading withdrawal | 3.12 |
| [`REQ-PIPE-006`](03-requirements.md#req-pipe-006-repeatability-and-content-addressing) | Repeatability and content addressing | 3.12 |
| [`REQ-PIPE-008`](03-requirements.md#req-pipe-008-exclusion-of-commercially-exploited-catalog-collections) | Exclusion of commercially exploited catalog collections | 3.12 |
| [`REQ-PIPE-009`](03-requirements.md#req-pipe-009-initial-collection-from-freely-accessible-sources) | Initial collection from freely accessible sources | 3.12 |
| [`REQ-PIPE-007`](03-requirements.md#req-pipe-007-manual-review-of-identity-resolution) | Manual review of identity resolution | 3.12 |

### REQ-SEC — Encryption and security

| ID | Title | Section |
|---|---|---|
| [`REQ-SEC-001`](03-requirements.md#req-sec-001-encryption-of-data-at-rest) | Encryption of data at rest | 3.13 |
| [`REQ-SEC-002`](03-requirements.md#req-sec-002-key-management) | Key management | 3.13 |
| [`REQ-SEC-003`](03-requirements.md#req-sec-003-publisher-specific-data-keys-and-cryptographic-erasure) | Publisher-specific data keys and cryptographic erasure | 3.13 |
| [`REQ-SEC-004`](03-requirements.md#req-sec-004-protection-against-bulk-extraction) | Protection against bulk extraction | 3.13 |

### REQ-DRM — Protected display and offline use

| ID | Title | Section |
|---|---|---|
| [`REQ-DRM-001`](03-requirements.md#req-drm-001-display-without-a-file-that-can-be-handed-out) | Display without a file that can be handed out | 3.14 |
| [`REQ-DRM-002`](03-requirements.md#req-drm-002-offline-use-with-time-limited-authorization) | Offline use with time-limited authorization | 3.14 |
| [`REQ-DRM-003`](03-requirements.md#req-drm-003-user-specific-marking) | User-specific marking | 3.14 |
| [`REQ-DRM-004`](03-requirements.md#req-drm-004-assignment-of-the-protection-components-to-the-commercial-layer) | Assignment of the protection components to the commercial layer | 3.14 |

### REQ-MOB — Mobile provision

| ID | Title | Section |
|---|---|---|
| [`REQ-MOB-001`](03-requirements.md#req-mob-001-progressive-web-app-as-primary-mobile-access) | Progressive Web App as primary mobile access | 3.15 |
| [`REQ-MOB-002`](03-requirements.md#req-mob-002-native-application-for-licensed-offline-content) | Native application for licensed offline content | 3.15 |
| [`REQ-MOB-003`](03-requirements.md#req-mob-003-abstracted-offline-layer) | Abstracted offline layer | 3.15 |
| [`REQ-MOB-004`](03-requirements.md#req-mob-004-distribution-channels-and-license-compatibility) | Distribution channels and license compatibility | 3.15 |

### REQ-ACC — Access and account requirement

| ID | Title | Section |
|---|---|---|
| [`REQ-ACC-001`](03-requirements.md#req-acc-001-anonymous-base-use) | Anonymous base use | 3.16 |
| [`REQ-ACC-002`](03-requirements.md#req-acc-002-content-limitation-of-anonymous-access) | Content limitation of anonymous access | 3.16 |
| [`REQ-ACC-003`](03-requirements.md#req-acc-003-quota-for-anonymous-use) | Quota for anonymous use | 3.16 |
| [`REQ-ACC-004`](03-requirements.md#req-acc-004-functions-requiring-an-account) | Functions requiring an account | 3.16 |
| [`REQ-ACC-005`](03-requirements.md#req-acc-005-cost-budget-for-language-model-use) | Cost budget for language-model use | 3.16 |
