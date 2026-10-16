# 3. Requirements

This chapter describes all requirements for normly. All requirements are uniquely identifiable, verifiable and formulated so that they can be carried directly into development, testing and acceptance. The requirements take into account the MVP status (open-source, standalone web application with an open-source LLM) as well as later scaling and the separation between the free core and the commercial layer.

## 3.1 External interfaces

This section describes all external interfaces of normly through which the system interacts with users, websites, third-party systems and external services. The goal is to specify all input and output points so that integration, operation and testing are unambiguously possible.

### 3.1.1 User interfaces

This section describes the logical user interfaces of normly as well as the basic interaction patterns, operating concepts and standards that are binding for all user interfaces, regardless of the concrete visual design.

#### REQ-UI-001 — Chat interface of the standalone web application

**Statement:** The system must provide a standalone chat interface as part of the open-source web application. Embedding via browser plugin or script in websites of norm vendors is not intended.  
**Rationale:** normly is a standalone application; operators of their own instance should be able to customize appearance and configuration.  
**Acceptance criteria:**

- Appearance (colors, typography, logo) is customizable via configuration

- The interface runs in its own instance without external dependencies

**Acceptance test:** A self-hosted instance provides the chat interface with its own configuration.

**Further information:** Replaces the earlier white-label approach, see ADR-001.

#### REQ-UI-002 — Chat-based interaction

**Statement:** The UI must enable chat-based interaction with the language model, including text input, answer display and loading states.  
**Rationale:** Chat is the primary interaction paradigm for LLM-based systems.  
**Acceptance criteria:**

- Text input with submission via button or Enter

- Visual loading indicator during the model response

- At least one complete question-answer cycle in the browser

**Further information:** Modeled on ChatGPT / Perplexity UX

#### REQ-UI-003 — Citations and linking

**Statement:** The UI must display the standards used as the source for each answer. For freely available content, the link points to the original source location; for paid standards, to the publisher's point of purchase.  
**Rationale:** Traceability of the answer, legal protection, and referral to the publisher as a source of revenue (affiliate, see section 3.4).  
**Acceptance criteria:**

- Every answer contains at least one citation

- For free content, the link leads to the original source location; for paid content, to the publisher's point of purchase

**Acceptance test:** For both kinds of source, the link demonstrably leads to the correct target.

**Further information:** See section 3.4 Compliance and REQ-PART-002 (attribution).

#### REQ-UI-004 — WCAG conformance

**Statement:** The user interface must be at least WCAG 2.1 AA conformant.  
**Rationale:** Accessibility is legally and ethically required.  
**Acceptance criteria:**

- Keyboard operability

- Screen reader compatibility

- Contrasts according to WCAG

**Further information:** Applies to all UI components

#### REQ-UI-005 — Display and management of the chat history

**Statement:** The user interface must enable users to view their previous chat conversations, reopen them and switch between multiple chat sessions, comparable to the chat history function of modern AI chat applications.

**Rationale:** When working with complex normative content, users expect to be able to retrace, continue or reference earlier questions and answers.

**Acceptance criteria:**

- A clear list of past chats is available in the UI

- Chats are sorted by creation date

- A selected chat can be reopened and continued (exception if documents were uploaded - see requirement REQ-INT-002C)

- The display remains performant even with a larger number of chats

**Acceptance test:** A user can create at least three separate chat sessions, close them, reopen them later and continue the dialogue.

**Further information:**

- The persistence of the chat history can be configurable per user or per tenant

- Data protection and deletion concepts must be taken into account in accordance with the security and compliance requirements

- The chat history is stored only for signed-in users (REQ-ACC-004); anonymous conversations live only in the browser tab and are not stored on the server. The person can delete stored histories individually or all at once (ADR-027)

### 3.1.2 Hardware interfaces

This section describes any requirements for hardware interfaces. No explicit hardware integrations are currently planned for normly.

### 3.1.3 Software interfaces

This section specifies all software interfaces to external systems, including website integrations, authentication services, data sources for norms, and the connection to language models and other third-party systems.

Normly supports two integration modes for norm documents:

1.  Vendor-based advance integration of complete norm collections

2.  User-based, temporary document uploads for session-related model enrichment

#### REQ-INT-001 — Public API for integration into third-party software

**Statement:** The system must provide a **documented, public HTTP API** through which third-party systems (e.g. CAD, ERP and expert systems) can send requests to normly. The API is part of the free core and specified under Apache-2.0; the finished integrations into specific third-party systems belong to the commercial layer.  
**Rationale:** Integration into existing specialist software is the central USP of the commercial layer. An open, stable API ensures that add-on services can dock on without forking the core and that no dependency on browser extensions arises.

**Acceptance criteria:**

- The API is fully documented and versioned as an OpenAPI specification

- A third-party system can send requests and process answers with citations without knowledge of the internal implementation

- No installation of browser extensions or scripts by end users required

**Acceptance test:** A reference client successfully calls the API against two consecutive versions.

**Further information:** Specification under Apache-2.0, see REQ-OSS-001 and REQ-COM-001.

#### REQ-INT-002 — Interface to norm databases

**Statement:** The system must be able to import norm documents (PDF, XML) automatically from the publishers' databases, provided there is a contractual basis for this under category C of the source register.  
**Rationale:** Scalable data maintenance without manual uploads. The restriction to contractually obtained collections follows from REQ-PIPE-008.  
**Acceptance criteria:**

- Import via API or SFTP

- Metadata import (title (DE and ENG), version, publication date, validity)

**Acceptance test:** Automated import of a norm collection via the partner portal.

**Further information:** See section 3.6.2 Data management, 3.12 Processing chain and REQ-PART-001.

#### REQ-INT-002A — User-based document upload and temporary model enrichment

**Statement:** The system must support an integration mode in which norm documents are not provided completely in advance by the norm vendor, but can be uploaded by the end user themselves, in order to enrich the language model **temporarily and per session or per user** for answering questions.

**Rationale:** Not all norm vendors make their complete norm collections available for advance processing. In order to still offer added value, normly must enable users to interact exclusively with the documents they have lawfully acquired and uploaded, comparable to the approach of NotebookLM.

**Acceptance criteria:**

- Users can upload norm documents (e.g. PDF, XML) via the application

- The uploaded documents are processed exclusively for the respective user or the respective session

- The language model answers questions only on the basis of the uploaded content

- No persistent training of the global model with these documents takes place

**Acceptance test:** A user uploads a purchased norm and can immediately afterwards ask questions in a chat whose answers are based exclusively on the uploaded document.

**Further information:**

- Functionally comparable to Google NotebookLM

- Technical implementation e.g. via temporary vectorization / retrieval-augmented generation (RAG)

- Relevant distinction from REQ-INT-002 (vendor-centric advance integration)

#### REQ-INT-002B — Isolation of user-specific documents

**Statement:** The system must ensure that documents uploaded by users are processed in strict isolation from other users and from the global data collection.

**Rationale:** Avoidance of data leaks and copyright infringements.

**Acceptance criteria:**

- No user can query the content of other uploads

- Security audit confirms isolation

#### REQ-INT-002C — Time-limited storage of uploaded documents

**Statement:** The system must support a configurable time limit for the storage of user-uploaded documents in order to reduce server storage space.  
**Rationale:** Reduction of legal risks and storage requirements.

**Acceptance criteria:**

- Automatic deletion after a defined period

- Document is no longer retrievable after expiry

**Further information:** Default 7 days

#### REQ-INT-003 — SSO authentication

**Statement:** The system must support single sign-on with existing member areas of organizations. SSO is optional and must not be a prerequisite for using freely available content.  
**Rationale:** Seamless user experience without additional logins for organizations that run their own user management. The optionality follows from REQ-ACC-001.  
**Acceptance criteria:**

- Support for common standards (OAuth2, SAML)

- Login via external identity system successful

**Further information:** Further sign-in options such as email or with Google must also be possible.

#### REQ-INT-004 — LLM interface

**Statement:** The system must communicate with an external LLM (e.g. Llama 3.1) via a clearly defined interface.  
**Rationale:** Interchangeability of the model and later migration to its own LLM.  
**Acceptance criteria:**

- Abstraction layer present

- Model change without UI adjustment

- LLM can be replaced without loss of functionality

**Further information:** See section 3.6

## 3.2 Functional requirements

This section describes the functional capabilities of normly from the perspective of external observers. It defines which functions the system provides, which inputs are processed, how it responds to them, and which outputs or error states can arise.

### REQ-FUNC-001 — Answering norm-based questions

**Statement:** The system must answer user questions exclusively on the basis of the available norms.  
**Rationale:** Avoidance of hallucinations and legal risks.

**Acceptance criteria:**

- Answer contains only content from referenced norms

**Further information:** Relevant to AI safety

### REQ-FUNC-002 — Paraphrasing instead of full text

**Statement:** The system must not reproduce copyright-protected norm texts as full text. Paraphrases and short excerpts marked as quotations are permitted, insofar as a license agreement with the rights holder expressly allows this. For content that may be freely passed on (e.g. official works under § 5 UrhG (German Copyright Act)), this restriction does not apply.  
**Rationale:** Copyright protection. Without this clarification, the requirement contradicts the output rights from the planned license agreements.  
**Acceptance criteria:** Answers are clearly paraphrased

**Acceptance test:**

- Plagiarism check without matches

- Mandatory for all answers

### REQ-FUNC-003 — Error and fallback answers

**Statement:** The system must deliver an explanatory fallback answer for unclear or unanswerable questions.  
**Rationale:** Trust and transparency.

**Acceptance criteria:**

- No invented content when the data basis is missing

- Test with deliberately unanswerable questions

**Further information:** Relevant to human-in-the-loop; depending on the implementation effort, this function is to be questioned for the MVP.

## 3.3 Non-functional requirements

This section describes the qualitative properties that the system must fulfill to ensure a reliable, secure and scalable user experience. These requirements constrain or qualify the functional behavior.

### 3.3.1 Performance

This section defines requirements for response times, throughput and responsiveness of the system under normal and expected load conditions.

#### REQ-PERF-001 — Chat response time

**Statement:** The system must deliver a first answer within 2–4 seconds after data availability.  
**Rationale:** Expectation of a modern chat UX.  
**Acceptance criteria:** 95 % of requests \<4 seconds

**Acceptance test:**

- Load test with a defined data set

**Further information:** Applies to the MVP

### 3.3.2 Security

This section describes the security-relevant requirements for authentication, authorization, data processing, communication and development processes in order to adequately protect user and system data.

Security is ensured differently at different levels:

**Authentication & authorization**

- Password hashing (e.g. bcrypt) and multi-factor authentication (MFA).

- Principle of least privilege: users receive only the minimum necessary rights.

- Magic-link login (OTP) conceivable

**Input validation & output encoding**

- Parameterized queries/prepared statements against SQL injection.

- Input sanitization and output encoding (e.g. HTML escaping) against XSS/CSRF.

**Encryption & data transmission**

- TLS 1.3 for all communication (HTTPS only), including the connections between internal services and to the database. Encryption of data at rest according to section 3.13.

- Secrets management: credentials are held exclusively in the STACKIT Secrets Manager, not in the source code, not in configuration files and not permanently in environment variables. Repositories and build artifacts are automatically checked for accidentally included credentials.

**Development processes**

- Secure coding standards, automated SAST/DAST tests in the CI/CD pipeline.

- Regular pen tests, threat modeling and dependency scanning (SCA).

### 3.3.3 Reliability and observability

This section defines requirements for the stability of the system and for logging, monitoring and error handling, in order to enable safe operation and effective error analysis.

To have consistent monitoring of the software and of user behavior, all requests, results, events, etc. should be logged at system level.

If errors occur that relate directly to the user (e.g. incorrect input), these should be communicated to the user.

### 3.3.4 Availability

This section describes requirements for the temporal availability of the system and for measures to ensure a defined minimum uptime.

The software (and thus the associated servers) should have an **uptime of 99%**.

## 3.4 Compliance

The development of normly is substantially guided by the available norms and guidelines. Depending on the contractual situation with the norm-setting associations, these can be loaded into the language model in advance (since they are completely available to us) or only uploaded situationally.

When outputting chat answers, care must be taken that an original 1:1 reproduction of the source material never takes place, in order to avoid copyright infringement. The (cited) sources used must be listed in each case and linked to the original form.

**Important:** The link to the original norm always points to the vendor's respective shop link. Remuneration for this referral (affiliate model) can be considered at this point. Personalized advertising is excluded.

## 3.5 Design and implementation

This section describes binding requirements and constraints for the design, the implementation, and the build, deployment and distribution process of normly.

The requirements defined here ensure that the system can be operated securely, maintainably, scalably and in conformity with the goals of data and technology sovereignty.

They apply to all environments (development, test, staging and production) and supplement the functional and non-functional requirements of the preceding sections with concrete specifications for technical implementation and operation.

### 3.5.1 Installation (Deployment)

This section defines requirements for the provisioning, configuration and recovery of the normly software in all target environments.

#### REQ-INST-001 — Deployment on German StackIT infrastructure

**Statement:** The system must be operated in all environments (production, test, staging and development environments) exclusively on **server infrastructure of StackIT (Schwarz Gruppe) located in Germany**.

**Rationale:** Ensuring data sovereignty, legal sovereignty and independence from non-European cloud providers.

**Acceptance criteria:**

- All compute, storage and network resources come from StackIT

- Server locations are in Germany

**Acceptance test:** Infrastructure and contract review confirms exclusive use of STACKIT services in Germany.

**Further information:** Applies without restriction to LLM inference, vector databases, logging and monitoring as well as to operations, user data and the norms knowledge base. Since ADR-021 (2026-09-14), an exception applies to source code, CI/CD and container registry of the free core: these reside on GitHub (`github.com/normly/web-app`), see REQ-GIT-001 and REQ-BUILD-002. The server, data and operations infrastructure itself remains unaffected by this and exclusively on STACKIT.

#### REQ-INST-002 — Automated deployment

**Statement:** The system must be deployable fully automatically, without manual intervention in target environments.

**Rationale:** Reduction of errors, faster releases and reproducible environments.

**Acceptance criteria:**

- Deployment takes place via script or pipeline

- No manual server setup required

**Acceptance test:** A new system can be provisioned automatically from an empty environment.

**Further information:** Infrastructure as Code recommended. Implementation: ADR-024 (`normly-deploy`).

#### REQ-INST-003 — Configuration management via environment variables

**Statement:** Environment-specific configurations (e.g. endpoints, feature flags) must be provided via environment variables or central configuration services. Credentials and key material are held exclusively in the STACKIT Secrets Manager, not in environment variables.

**Rationale:** Separation of code and configuration increases security and maintainability.

**Acceptance criteria:**

- No secrets in the source code

- Different environments can be operated without code changes

**Acceptance test:** Code review shows no hard-coded configuration values.

**Further information:** See section 3.3.2 as well as REQ-SEC-002.

#### REQ-INST-004 — Rollback capability

**Statement:** The system must provide the ability to automatically roll back a deployment to a previous stable version.

**Rationale:** Minimization of downtime in the case of faulty releases.

**Acceptance criteria:**

- At least one previous version can be restored at any time

**Acceptance test:** A rollback is carried out successfully in a test environment.

**Further information:** Blue-green or comparable strategies permitted. Implementation: ADR-024 (`normly-deploy`); the rollback restores images and data state and discards user data since the rollout (with warning and confirmation).

### 3.5.2 Build and Delivery

This section defines requirements for build processes, artifact creation, integrity and shipping of the software.

#### REQ-BUILD-001 — Reproducible builds

**Statement:** Builds of the system must be reproducible, so that the same source code produces identical artifacts under the same conditions.

**Rationale:** Traceability, security and debuggability.

**Acceptance criteria:**

- Versioned dependencies

- Build without external, non-deterministic influences

**Acceptance test:** Two builds from an identical commit produce identical artifacts.

**Further information:** Applies to backend, frontend and ML components. Implementation since ADR-023 (2026-10-08): uv workspace with `uv.lock`, base images pinned by digest, model weights pinned by commit; the same Git tag builds from the same inputs (lock file, image digests, model commits, locked build backend). Bit-identical images (acceptance test) are thus not yet achieved: timestamps in layers and the apt packages of the base layer are not pinned — open item.

#### REQ-BUILD-002 — CI/CD infrastructure for the free core

**Statement:** Build, test and CI/CD processes for the free core run on **GitHub Actions** in the repository `normly/web-app`. For operations, deployment, secrets management and the norms knowledge base, the restriction to STACKIT or equivalent, non-US infrastructure continues to apply unchanged.

**Rationale:** ADR-021 (2026-09-14) — for the source code and CI of the open core, easier collaboration outweighs the sovereignty advantage of a single STACKIT platform. The protection of operational data, credentials and prompts against extraterritorial access remains unaffected by this, since these are not part of the CI process on GitHub.

**Acceptance criteria:**

- Build and test of the free core run on GitHub Actions

- Secrets Manager, production deployment and operations runners for everything except the core build remain exclusively in STACKIT

**Acceptance test:** A tooling review confirms that no operations or deployment step runs outside STACKIT and that no STACKIT operations credentials are stored in the GitHub CI.

**Further information:** Until `.forgejo/workflows/ci.yml` is ported to `.github/workflows/`, no CI runs on GitHub yet (as of 2026-09-14). See REQ-GIT-001.

#### REQ-BUILD-003 — Automated quality assurance in the build

**Statement:** Builds may only complete successfully if defined quality criteria (tests, linting, security checks) are met.

**Rationale:** Avoidance of unstable or insecure releases.

**Acceptance criteria:**

- Failed tests prevent shipping

**Acceptance test:** The pipeline aborts on test failures.

**Further information:** See also section 3.5.4 Maintainability.

### 3.5.3 Distribution

This section describes requirements for the distribution, scaling and separation of the system components across multiple environments.

#### REQ-DIST-001 — Clear separation of environments

**Statement:** Production, staging, test and development environments must be operated strictly separately from each other.

**Rationale:** Avoidance of data leaks and unintended changes in the production system.

**Acceptance criteria:**

- Separate infrastructure and configurations

- No shared databases

**Acceptance test:** An architecture review confirms the separation of environments.

**Further information:** Also applies to ML data and logs. **Temporary deviation (ADR-022, 2026-09-23):** In Phase 1, only one production environment exists on STACKIT; the local Compose setup takes on the role of the staging environment. To be lifted as soon as there are users whom a faulty deployment would affect.

#### REQ-DIST-002 — Scalable distribution of the system components

**Statement:** The system must be distributed in such a way that individual components (e.g. chat backend, LLM inference, document processing) can be scaled independently of each other.

**Rationale:** Cost efficiency and performance with growing usage.

**Acceptance criteria:**

- Horizontal scaling of individual services possible

**Acceptance test:** A load test shows successful scaling of individual components.

**Further information:** Microservice or modular architecture recommended.

#### REQ-DIST-003 — Optional multi-tenancy for managed hosting

**Statement:** The system should optionally be able to operate multiple organizations (tenants) logically separated within the same deployment structure. Multi-tenancy is a prerequisite for the managed hosting offering of the commercial layer, not for operating a single instance of the free core.

**Rationale:** Basic prerequisite for the managed hosting offering of the commercial layer. For operating a single instance of the free core, multi-tenancy is not required and must not be a prerequisite.

**Acceptance criteria:**

- Separation of configuration, appearance and data per tenant

- The free core is fully runnable without multi-tenancy enabled

**Acceptance test:** Two organizations can be operated in parallel without overlaps; a single instance runs without tenant configuration.

**Further information:** Relevant for UI, data management and billing. For the separation of licensed collections, see REQ-PART-004 and REQ-SEC-003.

#### REQ-DIST-004 — Versioned shipping of the application

**Statement:** The application must be shipped as versioned, signed container images, supplemented by a runnable Compose setup that starts the application, database and basic configuration in one invocation. The free knowledge base is not part of the image, but is provided as an independently versioned dump and obtained on first start. Code and data are versioned separately and can be updated independently of each other.

**Rationale:** An open-source core that no one except the project itself can operate is practically not open. The container image is the proof of self-hostability and at the same time the basis of our own deployments and of the managed hosting offering. The separation of code and data is necessary because norm editions change considerably more often than the application code.

**Acceptance criteria:**

- One Compose invocation starts a runnable instance without manual rework; the image size remains independent of the size of the knowledge base; data versions are individually referenceable and interchangeable; images are signed and obtainable via a publicly readable route.

**Acceptance test:** An empty environment is put into operation without prior knowledge, solely on the basis of the documentation; a change of the data version takes place without rebuilding the image.

**Further information:** Since ADR-021 (2026-09-14), the primary registry for the free core is the GitHub Container Registry (GHCR) in the repository `normly/web-app` — supersedes the previous state (STACKIT Container Registry exclusively, ADR-019/ADR-010 addendum). The publicly readable retrieval in the acceptance criteria is to be solved via anonymous read access to GHCR. Helm charts for operation on Kubernetes may follow in addition. Caching strategies are to be taken into account. Build, signing (cosign keyless) and tagging of the images are governed by ADR-023. Implementation of the knowledge base dump: ADR-025.

### 3.5.4 Maintainability

To make onboarding further developers easier, to reduce the time for bug fixes and to speed up development, the following development principles are to be observed:

**Area**

**Specification**

**Modular architecture**

Divide code into independent, interchangeable modules for easy maintenance and extension.

**Low code complexity (Cyclomatic Complexity \<10)**

Limits branching in functions to keep code readable and testable.

**Coding standards (e.g. PSR-12)**

Uniform formatting rules for consistent, team-ready code.

**Interfaces**

Define clear, standardized APIs/contracts between modules.

**Developer Observability (logging, monitoring, tracing)**

Structured logs, metrics and traces for fast error diagnosis.

**Documentation**

Complete description of components, APIs and algorithms.

Documentation is done as "Docs as Code" in the Git repository with Markdown templates and automated generation (e.g. MkDocs/Sphinx). Each component receives READMEs with architecture, APIs, algorithms and examples; API docs via OpenAPI/Swagger.

A Swagger instance for documenting the API is mandatory.

**Automated tests (\>80% coverage)**

Unit/integration tests cover the majority of the code.

**CI/CD pipelines**

Automated builds/tests/deployments for fast releases.

**Technical Debt Management**

Regular refactoring and debt tracking prevent accumulation

**Open Source**

The code should be available as open source - in a publicly viewable repository.

Open source frameworks used are to be listed and linked separately and cleanly.

### 3.5.5 Reusability

The software should be reusable through modular, loosely coupled components. The implementation of DRY principles (Don't Repeat Yourself), a central repository for code and requirements with version control in STACKIT Git, and standardized APIs/interfaces are to be provided for.

### 3.5.6 Portability

normly is designed as a web application in order to run in all common browser versions. Responsive design is to be adhered to at all times. The application is at the same time installable as a Progressive Web App and enables push notifications.

Backward compatibility is to be ensured down to the following versions:

|                 |                                     |
|-----------------|-------------------------------------|
| **Browser**     | **Backward compatible down to version** |
| Google Chrome   | 143                                 |
| Microsoft Edge  | 142                                 |
| Mozilla Firefox | 145                                 |
| Apple Safari    | 26                                  |
| Opera           | 125                                 |

Mobile provision initially takes place as a Progressive Web App (PWA) on the same codebase as the desktop application. A native app is only required once licensed full texts are provided offline — not depending on the availability of a dedicated language model. Section 3.15 governs the details.

### 3.5.7 Costs

The goal is to have, at the beginning, an MVP solution whose free core is publicly usable and on the basis of which first commercial services (managed hosting, integrations, reports) can be sold, in order to be able to show initial ARR.

### 3.5.8 Deadline

The development of a first testable prototype is completed by May/June 2026. A first, sellable MVP product is to be reached at the end of Q2, beginning of Q3 2026.

### 3.5.9 Physical requirements

In order to be able to ensure, as a USP, 100% independence from American or Chinese offerings, the entire deployment is to be ensured on server infrastructure of [<u>Stack IT</u>](https://stackit.com/de). This also applies to development, build and deployment environments. Since ADR-021, source code, CI/CD and container registry of the free core reside on GitHub (REQ-GIT-001, REQ-BUILD-002). For language models, ADR-022 applies: exclusively open-weight models with an OSI-approved license, operated on STACKIT infrastructure; no request reaches the model vendor.

### 3.5.10 Design requirements

In order to limit the development costs for design to a minimum, we will rely on and apply freely available sources. These include:

- Frontend design: [<u>Shadcn</u>](https://ui.shadcn.com/), [Github repo of Shadcn-ui](https://github.com/shadcn-ui/ui)

The following serve above all as inspiration for the presentation to the end user:

- Perplexity

- ChatGPT

- NotebookLM

## 3.6 AI/ML

This section defines requirements that apply specifically to systems whose core consists of machine learning or data-driven components. These requirements complement the functional, non-functional and qualitative aspects covered in the preceding sections. However, they address ML-specific considerations regarding lifecycle and data quality.

### 3.6.1 Model specifications

In order to be able to ensure fast and cost-effective development, we will initially rely on open source LLMs. It is to be ensured that German and English are supported with priority. Followed by French, Spanish and Italian.

- Language model: [<u>Llama 3.1</u>](https://ai.meta.com/blog/meta-llama-3-1/) (open source and permits commercial use for own products). Currently leading, but can be replaced.

### 3.6.2 Data management

Data management is of central importance for normly. With increasing scale, many tens of thousands of documents are to be expected whose information must be processed. In addition, documents (norms) are updated, extended or declared invalid. Ensuring data integrity is therefore crucial!

The current approximate number of norms and, associated with it, (estimated text pages) is as follows:

|                |                          |
|----------------|--------------------------|
| **Country**    | **Total number of norms** |
| Germany        | 38,000+                  |
| Italy          | 48,000+                  |
| China          | 200,000+                 |
| Japan          | 25,000+                  |
| USA            | 40,000+                  |
| France         | 30,000+                  |
| United Kingdom | 27,000+                  |
| India          | 20,000+                  |
| Russia         | 30,000+                  |

Just under half a million norms are therefore to be expected. At an average of 40 pages per norm, this corresponds to over 20 million pages of technical information (plus graphs, tables, drawings and formulas).

These figures cover exclusively the German-speaking region. The target horizon of normly is worldwide coverage. Worldwide, an order of magnitude of several million norm documents is to be expected, corresponding to a mid three-digit million range of text pages and several billion text sections for retrieval. Data management is therefore to be designed for this target size from the start. In particular, graph and metadata storage on the one hand and the vector index on the other hand are to be encapsulated in such a way that they can be scaled and replaced independently of each other.

### 3.6.3 Human-in-the-Loop

The language model only provides summaries and answers the questions asked on the basis of the available norms. normly does not provide legally based legal advice. The human must still verify the answers.

### 3.6.4 Model lifecycle and operations

The language models are to be continually adapted to the latest available versions. In the course of internationalization, further languages are required in addition to German and English (start languages).

## 3.7 Open source and governance

This chapter defines requirements for the licensing, rights framework and governance of the open-source core, as well as for the delimitation from the commercial layer.

### REQ-OSS-001 — License model of the free core

**Statement:** The source code of the core is under the GNU Affero General Public License 3.0 (AGPL-3.0). Client SDKs and the API specification are under Apache-2.0. The freely available content and the reference graph are under an open data license (ODbL or CC-BY-SA).

**Rationale:** The AGPL closes the network-use gap and prevents third parties from operating the core as a closed service. The permissive license for SDKs and API specification ensures maximum reach.

**Acceptance criteria:** LICENSE file present per repository; license notice in all source files; data license stated in the publication.

**Acceptance test:** A license review confirms consistent labeling of all components.

### REQ-OSS-002 — Separation of free core and commercial layer

**Statement:** The free core must not have any dependency on proprietary components and must be fully runnable without them. Commercial modules attach exclusively via documented extension points.

**Rationale:** Without this separation, the open-core model is robust neither in terms of license law nor towards the community.

**Acceptance criteria:** The core can be built, tested and operated without commercial modules; no imports from proprietary packages in the core.

**Acceptance test:** Build of the core without commercial repositories succeeds; dependency check in the pipeline without findings.

### REQ-OSS-003 — Contribution model (DCO)

**Statement:** External contributions are accepted via the Developer Certificate of Origin (DCO). Every commit carries a Signed-off-by line. No transfer of rights (CLA) takes place.

**Rationale:** The DCO lowers the barrier for contributors and supports the aim of freely accessible knowledge about norms. The consequence that a later commercial exception license to the AGPL is thereby ruled out was knowingly accepted.

**Acceptance criteria:** DCO check as a mandatory step in the pipeline; CONTRIBUTING file describes the procedure.

**Acceptance test:** A merge request without Signed-off-by is automatically rejected.

### REQ-OSS-004 — Community governance and security process

**Statement:** The project maintains a documented group of maintainers, a code of conduct and a security policy with a defined reporting channel and response deadline.

**Rationale:** Transparent governance is a prerequisite for trust and for the participation of third parties.

**Acceptance criteria:** CODE_OF_CONDUCT, SECURITY and GOVERNANCE present in the repository; reporting channel for vulnerabilities named.

**Acceptance test:** A test report via the reporting channel is answered within the defined deadline.

### REQ-OSS-005 — License compliance of dependencies

**Statement:** For every release, a Software Bill of Materials (SBOM) is generated and the licenses of all dependencies are checked automatically. Licenses incompatible with the AGPL cause the build to abort.

**Rationale:** Avoidance of license violations and of legal uncertainty for downstream users.

**Acceptance criteria:** SBOM per release as an artifact; license scan as a mandatory step in the pipeline.

**Acceptance test:** An injected incompatible dependency entry makes the build fail.

### REQ-OSS-006 — Trademark rights

**Statement:** The normly trademark is not part of the open-source license. A separate trademark policy applies to the use of the trademark by third parties.

**Rationale:** The trademark is the asset through which quality and provenance are controlled; it must remain controllable independently of the code license.

**Acceptance criteria:** Trademark policy published in the repository; notice in the LICENSE file.

**Acceptance test:** A legal review confirms the separation of code license and trademark license.

## 3.8 Source code management and Git workflow

This chapter defines requirements for the platform, process and safeguarding of source code management.

### REQ-GIT-001 — GitHub as the primary platform for the core source code

**Status:** Revised by ADR-021 (2026-09-14); supersedes the previous version (STACKIT Git as the sole platform, ADR-019).

**Statement:** The primary platform for source code, contributions, CI/CD and container registry of the free core is GitHub (`github.com/normly/web-app`). Operations, deployment, secrets management and the norms knowledge base remain separate from this and exclusively on STACKIT (see REQ-INST-001, REQ-BUILD-002). STACKIT Git (`jwokittel/normly-webapp`) is no longer used for source code and is no longer intended for the knowledge base (ADR-025); the knowledge base resides as a dump in STACKIT Object Storage.

**Rationale:** ADR-021 — easier collaboration for the open core source code outweighs the sovereignty advantage of a single STACKIT platform for code, CI and registry. The sovereignty restriction from chapter 2.3 continues to apply unchanged to operations, data and secrets.

**Acceptance criteria:** Source code, pipelines and container registry of the free core reside on GitHub; no operations or deployment credential is stored there.

**Acceptance test:** An infrastructure review confirms that operations, deployment and secrets management run exclusively on STACKIT and that the GitHub side is free of operations credentials.

### REQ-GIT-002 — Contribution path via GitHub

**Status:** Revised by ADR-021 (2026-09-14). Was obsolete from 2026-09-05 to 2026-09-14 (ADR-019); GitHub is now no longer a mere contribution facade but the primary platform according to REQ-GIT-001.

**Statement:** External as well as internal contributions (issues, pull requests) go through GitHub in the repository `normly/web-app`. There is no second contribution path maintained in parallel.

**Rationale:** Visibility and a low barrier to contribution; see ADR-021 for the full rationale of the platform switch.

**Acceptance criteria:** Contributions are accepted exclusively via GitHub.

**Acceptance test:** A review confirms that no second actively maintained issue tracker or contribution path exists.

### REQ-GIT-003 — Branch and release strategy

**Statement:** A documented branching process applies, with a protected main branch, semantic versioning (SemVer), a uniform commit format and signed release tags.

**Rationale:** Traceability of changes and reliable versions for downstream users.

**Acceptance criteria:** Direct pushes to the main branch are prevented; every release carries a signed tag.

**Acceptance test:** An attempt to push directly to the main branch is rejected.

### REQ-GIT-004 — Merge request policy

**Statement:** Changes reach the main branch exclusively via merge requests. Prerequisites are at least one subject-matter approval, a successful pipeline and the consent of the responsible code owners.

**Rationale:** Quality assurance and the four-eyes principle; protection against unintended regressions.

**Acceptance criteria:** Merging without approval or with a failed pipeline is technically not possible.

**Acceptance test:** A merge request with a red pipeline status cannot be merged.

### REQ-GIT-005 — Supply chain integrity

**Statement:** Commits and build artifacts are signed. For every release, proof of provenance and an SBOM are published.

**Rationale:** Protection against tampering and a prerequisite for traceability in regulated environments.

**Acceptance criteria:** Signature verification as a mandatory step before rollout; artifacts stored signed in the GitHub Container Registry (ADR-021, ADR-023: cosign keyless, SLSA provenance and SBOM per image).

**Acceptance test:** An unsigned artifact is rejected by the shipping process.

**As of (2026-10-08):** Signature, provenance and SBOM per image are implemented with ADR-023. The verification as a mandatory step before the start on the target environment is implemented with the rollout script `normly-deploy` (ADR-024, 2026-10-09).

## 3.9 Reference graph

This chapter defines requirements for the structure, licensing and use of the norm reference graph.

### REQ-GRAPH-001 — Open norm reference graph

**Statement:** The system maintains a machine-readable reference graph over standards. It records stable identifiers, references between standards, replacement chains and chains of withdrawn norms, editions, and references from laws and regulations to norms. Schema and content of the free part are published under an open data license with share-alike effect (ODbL).

**Rationale:** The reference graph is normly's actual unique selling point. Its openness is not a waiver of protection: the database maker's right under §§ 87a ff. UrhG in conjunction with the share-alike clause prevents third parties from turning the graph into a closed product. At the same time, the openness establishes the role as neutral infrastructure towards the standardization bodies.

**Acceptance criteria:** Complete dump in an open, documented format; schema versioned and public; license notice carried along in machine-readable form.

**Acceptance test:** A third party can read in the published dump without further inquiry and reproduce reference chains.

### REQ-GRAPH-002 — Layering of free and commercial graph share

**Statement:** Schema, identifiers, references between publicly accessible standards, replacement chains and validity states are published freely. Reserved for the commercial layer are: currency guarantee with SLA and change notification, references down to section level within licensed norms, confidence ratings and evidence citations for audit purposes, and industry-specific enrichments.

**Rationale:** References that map the internal structure of protected norms must not be published freely, depending on the license agreement. At the same time, commercial customers pay for reliability and currency, not for the data collection as such; a periodic dump and an SLA-backed API are different products.

**Acceptance criteria:** Every edge and every node of the graph carries a provenance and license classification per jurisdiction according to REQ-GRAPH-006; the free export contains, per jurisdiction, exclusively elements that are freely licensable there.

**Acceptance test:** An export of the free share demonstrably contains no section references subject to licensing.

### REQ-GRAPH-003 — Graph-first query processing

**Statement:** Queries are resolved against the reference graph first. A language model is only invoked when the query requires synthesis over running text. Structural questions (replacement, validity, reference relationships) are to be answered deterministically and without a model call.

**Rationale:** Structural questions can be answered exactly from the graph. A model call would be more expensive, slower and more error-prone here; especially with validity and replacement questions, hallucinations have particularly serious consequences.

**Acceptance criteria:** Classification of every query before processing; deterministic answer with citation for structural questions; caching of recurring queries.

**Acceptance test:** A defined set of structural questions is answered completely without a model call and with correct citations.

### REQ-GRAPH-004 — Technology independence of graph storage

**Statement:** Access to the reference graph takes place exclusively via an abstracted interface within the application. The concrete storage technology is interchangeable and must not leak into the domain logic. For the start, an open-source database that can be operated at STACKIT is used.

**Rationale:** Operators of their own instances should be able to operate the free core without additional license costs and without an externally hosted special-purpose database. A later migration to a dedicated graph database must remain possible without intervening in the domain logic.

**Acceptance criteria:** No database-specific queries outside the access layer; swapping the storage technology is covered by tests.

**Acceptance test:** An architecture review confirms that the domain logic has no knowledge of the concrete graph technology.

### REQ-GRAPH-005 — Internationalization of the reference graph

**Statement:** The reference graph is to be designed for worldwide coverage from the start. Required are: a globally collision-free identifier scheme that maps publisher, document number, edition and part number separately; a language-independent node identity in which one standard forms one node and national adoptions and translations are kept as relationships and attributes, respectively; multilingual designations per node.

**Rationale:** A later rebuild of the identifier scheme is the most expensive legacy burden imaginable. A standard such as EN ISO 9001 is adopted by several national bodies in different languages; without language-independent identity, duplicates arise that make reference chains unusable.

**Acceptance criteria:** Identifier scheme documented and versioned; national adoptions are mapped as a relationship to the original document; designations in several languages can be kept per node.

**Acceptance test:** A standard with adoptions by at least three national bodies is represented as one node with assigned adoptions.

### REQ-GRAPH-006 — Jurisdiction-specific license classification

**Statement:** The licensability and publishability of nodes and edges are classified and kept per jurisdiction. Exports and API responses are filtered on the basis of the jurisdiction applicable in each case.

**Rationale:** The freely publishable share is not globally uniform: § 5 UrhG applies only in Germany, the situation for norms incorporated into laws by reference differs per legal system, and for harmonized European norms the legal situation is to be assessed separately due to the decision of the Court of Justice of the European Union (CJEU) in case C-588/21. A global classification would be either unlawful or unnecessarily restrictive.

**Acceptance criteria:** Classification per jurisdiction stored in the data model; export filter selectable; provenance of the legal assessment documented and dated.

**Acceptance test:** Two exports for different jurisdictions demonstrably deliver different scopes, each of them permissible.

## 3.10 Content partnerships and remuneration

This chapter defines requirements for the supply of licensed norm content by publishing organizations and for its traceable remuneration.

### REQ-PART-001 — Partner portal for content supply

**Statement:** For publishing organizations, a portal with an associated interface is provided through which norm content is supplied in full text. Common exchange formats are supported (at least PDF and XML). Per delivery, publisher, document identifier, edition, language, jurisdiction and the contractually granted rights of use are captured as metadata. Deliveries are versioned; withdrawing individual documents or entire collections must be possible at any time and takes immediate effect on the answering of queries.

**Rationale:** The supply of full texts is the prerequisite for the decisive leap in the data collection. A defined, traceable supply path lowers the hurdle for publishers and is part of the negotiating position. The ability to withdraw at any time is the prerequisite for publishers keeping control over their works, and thus a condition for concluding the contract.

**Acceptance criteria:** Supply, status tracking and withdrawal can be carried out via the portal without technical support from normly; every delivery is assigned to a contract; rights metadata are mandatory fields.

**Acceptance test:** A publisher delivers a collection, retrieves its processing status and withdraws a document; from that point on, the withdrawn document is no longer used for answering.

### REQ-PART-002 — Source attribution per answer

**Statement:** For every generated answer, it is logged which sources were used and with which share they contributed to the answer. The share is measured by the number of passages per source that actually went into the answer, relative to the total number of passages that went into it. Passages that were retrieved but not used are disregarded. If a query is answered entirely from the reference graph, this is captured as a separate category.

**Rationale:** The attribution data are the basis of any revenue share and cannot be reconstructed retroactively. They must therefore be collected from the start of operation, regardless of whether a remuneration contract already exists. The capture belongs in the free core because it is required for the citation anyway; only the evaluation is commercial.

**Acceptance criteria:** Per answer, there is an attribution record with source, number of passages and resulting share; the shares per answer add up to 100 percent; the capture is active independently of existing contracts.

**Acceptance test:** For an answer that uses passages from three different publishers, the distribution is shown correctly and traceably.

### REQ-PART-003 — Revenue share and auditable billing

**Statement:** On the basis of the attribution data, a proportional remuneration amount is determined per billing period and publisher. The basis is the contractually agreed share of the attributable revenue, distributed according to the attribution share per REQ-PART-002. Publishers receive a billing report that shows period, query volume, attribution share, calculation basis and resulting amount and can be exported in machine-readable form.

**Rationale:** A publisher expecting a revenue share will want to check the numbers. Without an independently traceable calculation, the negotiation is about trust instead of a percentage. An auditable billing considerably improves the negotiating position and defuses the conflict that normly is perceived as a competitor for sales revenue.

**Acceptance criteria:** Billing reports can be fully derived from the logged individual records; the calculation rule is documented and versioned; a sample of individual answers can be traced through to the report.

**Acceptance test:** An external audit recalculates a billing period from the raw data and arrives at the same result.

### REQ-PART-004 — Protection and separation of licensed full-text collections

**Statement:** Licensed full-text collections are kept logically separate per publisher and are processed exclusively within the scope of the stored rights of use. A collection must not be used for instances or tenants for which no corresponding authorization exists. The free core and the freely published exports contain no licensed full-text content.

**Rationale:** Without reliable separation, no publisher is willing to provide full texts. The separation is at the same time the prerequisite for the free core remaining open source and freely distributable, while licensed collections only take effect in authorized instances.

**Acceptance criteria:** Authorization check on every access to licensed collections; accesses are logged; free exports are checked automatically against licensed content.

**Acceptance test:** An instance without authorization demonstrably receives no content from a licensed collection; a free export demonstrably contains no full-text passages subject to licensing.

## 3.11 Commercial add-on services

This chapter defines requirements for the commercial layer, which builds on the free core and is intended to be spun off into a separate company.

### REQ-COM-001 — Extension interface

**Statement:** The core provides a stable, versioned extension interface through which commercial modules can be connected without a fork.

**Rationale:** Prerequisite for core and commercial layer being able to be developed further separately.

**Acceptance criteria:** Extension points documented and versioned; an example module can be integrated without changes to the core.

**Acceptance test:** A reference module is operated successfully against two consecutive core versions.

### REQ-COM-002 — Integration into third-party software

**Statement:** For CAD, ERP and expert systems, integrations are provided that work via the core's public API.

**Rationale:** Central USP of the commercial layer and largest expected revenue driver.

**Acceptance criteria:** At least one integration into a widespread specialist system is operational and documented.

**Acceptance test:** An end user can submit a query from within the third-party system and receives an answer with citation.

### REQ-COM-003 — Usage-based billing

**Statement:** Commercial API accesses are authenticated via keys, limited with quotas and billed based on usage.

**Rationale:** Viable revenue model for integrations without restricting free access.

**Acceptance criteria:** Key management, quota check and auditable billing data in place.

**Acceptance test:** A test period is billed completely and traceably.

### REQ-COM-004 — Verifiable answers and audit trail

**Statement:** For compliance instances, query, sources used, model version and point in time are logged in an audit-proof manner and made exportable.

**Rationale:** Liability certainty is the actual reason commercial customers pay, not access to knowledge.

**Acceptance criteria:** Complete audit record per answer; export in a machine-readable format.

**Acceptance test:** An audit export can be unambiguously assigned to a concrete answer.

### REQ-COM-005 — Exclusion of personalized advertising

**Statement:** Personalized advertising based on search queries, chat histories or user profiles is ruled out. Permitted are context-free directory entries and references to sources of supply for the original documents.

**Rationale:** Personalized advertising is incompatible with the neutrality of the Trägerorganisation and the data-protection promise of the free core.

**Acceptance criteria:** No profiling for advertising purposes; directory entries are marked as paid.

**Acceptance test:** A data-protection review confirms that no advertising-related user profiles arise.

## 3.12 Data acquisition and processing chain

This chapter describes the path by which content of different provenance — freely available sources, licensed partner deliveries and collections without a clarified legal situation — is transferred into a uniform data collection.

### REQ-PIPE-001 — Uniform processing chain

**Statement:** Content of all provenance types passes through the same processing chain. The provenance type is a property of the record, not a separate processing path. The chain is divided into: source register, ingest adapters, identity resolution, rights classification, structure extraction, reference extraction, segmentation and embedding, output.

**Rationale:** Separate processing paths per provenance type drift apart, and the rights check would sit in several places. A single chain with provenance-dependent control is auditable and extensible.

**Acceptance criteria:** New sources are connected exclusively via an adapter; from identity resolution onward, processing is independent of the provenance type.

**Acceptance test:** A new source is connected without steps behind the adapter having to be adapted.

### REQ-PIPE-002 — Source register

**Statement:** Every source is registered before its first processing. The entry comprises publisher, retrieval path, legal basis of use, jurisdiction, check date and the person responsible for the check. Without a register entry, no acquisition takes place. The legal basis is to be assigned to one of the following exhaustively defined categories: (A) official works and legal texts whose use follows from § 5 UrhG or a corresponding provision of the respective jurisdiction; (B) standards under a free license of the publisher; (C) data obtained by contract, stating the contract reference; (D) other publicly accessible sources, exclusively after a documented case-by-case review including the check per REQ-PIPE-003 and with a responsible person named. Sources that cannot be assigned to any of these categories are not acquired.

**Rationale:** The register is the documentary record of the provenance and the legal basis of the entire collection. It is the prerequisite for being able to provide information to publishers and supervisory bodies.

**Acceptance criteria:** A register entry is a mandatory prerequisite of every ingest run; changes are historized; the category assignment is a mandatory field and cannot be saved without a valid value.

**Acceptance test:** An acquisition run without a valid register entry or without a category assignment is rejected.

### REQ-PIPE-003 — Check for rights reservations

**Statement:** Before the automated acquisition of freely accessible sources, it is checked whether a machine-readable rights reservation within the meaning of § 44b Abs. 3 UrhG exists. The result is logged with date and location in the source register and re-checked at intervals to be determined.

**Rationale:** Text and data mining is only permitted as long as no rights reservation has been declared. An undocumented check weakens the negotiating position towards precisely the organizations with which license agreements are sought.

**Acceptance criteria:** Check result per source present, dated and evidenced; re-check scheduled.

**Acceptance test:** For every active source, the check result can be retrieved with date and location.

### REQ-PIPE-004 — Rights classification as processing gate

**Statement:** After identity resolution, it is determined per document and jurisdiction which processing steps are permitted: processing, full-text indexing, quoting of passages, free export. Documents without classification are not processed further. A missing classification does not count as provisional permission.

**Rationale:** The rights classification is the only point at which the permissible use is decided. A central check is more reliable than distributed checks in individual steps.

**Acceptance criteria:** Every downstream step checks the classification; unclassified documents remain in a waiting state.

**Acceptance test:** A document without classification demonstrably reaches neither index nor export.

### REQ-PIPE-005 — Lineage and cascading withdrawal

**Statement:** Every derived artifact — section, segment, embedding, graph edge, export file — carries a reference to the source delivery from which it originated. If a delivery is withdrawn or a rights classification is restricted, all derived artifacts are automatically removed or blocked.

**Rationale:** Without a continuous lineage chain, the ability to withdraw promised in REQ-PART-001 cannot be honored. Such a chain cannot be established retroactively; it must be carried along from the start.

**Acceptance criteria:** Lineage reference on all derived artifacts; withdrawal runs as a traceable process with a log.

**Acceptance test:** After withdrawal of a document, its segments, embeddings, graph edges and export shares are demonstrably removed.

### REQ-PIPE-006 — Repeatability and content addressing

**Statement:** All processing steps are idempotent and can be repeated any number of times. Raw files are stored content-addressed, so that unchanged re-deliveries are recognized and not processed again.

**Rationale:** Extraction methods will evolve; the collection must be able to be reprocessed without producing different results or duplicates.

**Acceptance criteria:** A repeated run over the same input state produces no different result; unchanged deliveries are skipped.

**Acceptance test:** A complete reprocessing of the collection delivers an identical result.

### REQ-PIPE-008 — Exclusion of commercially exploited catalog collections

**Statement:** Catalog and metadata collections of publishers who exploit them commercially themselves are obtained exclusively via category C of the source register, that is, on a contractual basis. Automated acquisition of such collections via category D is ruled out. This applies regardless of whether the collections are publicly accessible.

**Rationale:** A norm catalog is a protected database; § 87b UrhG prohibits not only the extraction of substantial parts but also the repeated and systematic extraction of insubstantial parts, insofar as it conflicts with normal exploitation. Systematic harvesting with periodic reconciliation fulfills this criterion. The strategic side weighs more heavily: normly negotiates with the same organizations about voluntary provision in return for a revenue share. Access without a contract directly contradicts this position and endangers the negotiations.

**Acceptance criteria:** Category D adapters technically cannot be configured for sources that are marked as a commercially exploited catalog collection; the marking is kept in the source register.

**Acceptance test:** The attempt to connect a source marked as commercially exploited via category D is rejected and logged.

### REQ-PIPE-009 — Initial collection from freely accessible sources

**Statement:** The initial build-up of catalog and reference graph takes place from sources of categories A and B. These include in particular the lists of harmonized norms in the Official Journal of the European Union via EUR-Lex, references from laws and regulations, the standards registers of DGUV and BAuA, the work programmes of the European standardization bodies and freely available catalog data of international bodies.

**Rationale:** These sources carry a reliable initial collection without legal risk and at the same time contain the most valuable part for the reference graph: the references from the law to norms. The graph can thus be built before the first license agreement and strengthens the negotiating position instead of burdening it.

**Acceptance criteria:** Catalog and graph can be put into operation without sources of categories C and D; provenance per entry demonstrable.

**Acceptance test:** An initial collection is built exclusively from sources of categories A and B and can be evaluated.

### REQ-PIPE-007 — Manual review of identity resolution

**Statement:** For cases in which the automatic assignment of a document to a node does not succeed unambiguously, a review interface is available. Unresolved cases block the further processing of the affected document, not that of the rest of the collection.

**Rationale:** Publishers write norm numbers inconsistently; complete automation of the assignment is not achievable. Wrong assignments make reference chains unusable and are hard to detect.

**Acceptance criteria:** Unclear cases are submitted for review instead of being decided heuristically; decisions are logged and can be undone.

**Acceptance test:** An ambiguous case is submitted, decided, and the decision is documented traceably.

<img src="media/media/image3.png" style="width:6.27014in;height:7.89583in" />

Figure 2: Processing chain

## 3.13 Verschlüsselung und Schutz lizenzierter Inhalte

Dieses Kapitel ergänzt die allgemeinen Sicherheitsanforderungen aus Kapitel 3.3.2 um Vorgaben zur Verschlüsselung ruhender Daten, zur Schlüsselverwaltung sowie zum Schutz vertraglich bezogener Volltextbestände.

### REQ-SEC-001 — Verschlüsselung ruhender Daten

**Statement:** Alle persistierten Daten werden verschlüsselt abgelegt: Datenbankinhalte, Objektspeicher, Suchindizes, Protokolldaten und sämtliche Sicherungskopien. Dies gilt unabhängig davon, ob es sich um frei verfügbare oder um lizenzierte Inhalte handelt.

**Rationale:** Die bisherigen Anforderungen decken ausschließlich die Transportverschlüsselung ab. Sobald lizenzierte Volltexte im Bestand liegen, ist die Verschlüsselung ruhender Daten Gegenstand jeder Vertragsprüfung durch die Herausgeber. Eine einheitliche Behandlung aller Bestände vermeidet zudem, dass die Schutzwirkung von einer korrekten Klassifikation abhängt.

**Akzeptanzkriterium:** Verschlüsselung ist für alle Speicherorte nachweisbar aktiv; unverschlüsselte Ablagen sind technisch ausgeschlossen; Sicherungskopien sind einbezogen.

**Abnahmekriterium:** Ein Sicherheitsaudit weist für jeden Speicherort den aktiven Verschlüsselungszustand nach.

### REQ-SEC-002 — Schlüsselverwaltung

**Statement:** Schlüssel werden im STACKIT Secrets Manager verwaltet und niemals gemeinsam mit den durch sie geschützten Daten abgelegt. Es gelten dokumentierte Rotationsfristen, eine Trennung der Zugriffsrechte zwischen Betrieb und Anwendung sowie eine vollständige Protokollierung jedes Zugriffs auf Schlüsselmaterial. Der Verlust einzelner Schlüssel darf nicht zum Verlust des Gesamtbestands führen.

**Rationale:** Verschlüsselung ohne belastbares Schlüsselkonzept ist eine Zusage ohne Substanz. Die Trennung von Schlüssel und Daten sowie die Protokollierung sind Voraussetzung dafür, gegenüber Herausgebern und Auditoren nachweisfähig zu sein.

**Akzeptanzkriterium:** Rotationsfristen dokumentiert und technisch durchgesetzt; Zugriffe auf Schlüsselmaterial protokolliert; Rollentrennung wirksam.

**Abnahmekriterium:** Eine Schlüsselrotation wird ohne Betriebsunterbrechung durchgeführt und ist im Protokoll nachvollziehbar.

### REQ-SEC-003 — Herausgeberspezifische Datenschlüssel und kryptographisches Löschen

**Statement:** Vertraglich bezogene Volltextbestände werden je Herausgeber mit einem eigenen Datenschlüssel verschlüsselt. Bei Beendigung eines Vertrages oder beim Rückzug eines Bestandes nach REQ-PART-001 wird der zugehörige Schlüssel vernichtet. Die betroffenen Daten sind damit auch in bestehenden Sicherungskopien dauerhaft unlesbar. Die Vernichtung wird protokolliert und dem Herausgeber bestätigt.

**Rationale:** Die in REQ-PART-001 zugesagte Rückziehbarkeit lässt sich für Sicherungskopien nicht durch Löschen einlösen: Bestehende Sicherungen enthalten die Inhalte weiterhin, und ihre selektive Bereinigung ist praktisch nicht durchführbar. Das kryptographische Löschen schließt diese Lücke und ist zugleich das stärkste Argument in Lizenzverhandlungen — nach Vertragsende sind die Inhalte technisch nicht mehr lesbar, nicht lediglich als gelöscht markiert.

**Akzeptanzkriterium:** Ein Datenschlüssel je Herausgeber; kein Bestand ist mit einem gemeinsamen Schlüssel verschlüsselt; Vernichtung ist ein protokollierter Vorgang mit Bestätigung.

**Abnahmekriterium:** Nach Vernichtung eines Schlüssels sind die zugehörigen Inhalte weder im Produktivbestand noch in einer Sicherungskopie lesbar; die Bestätigung liegt dem Herausgeber vor.

### REQ-SEC-004 — Schutz vor Massenextraktion

**Statement:** Zugriffe auf lizenzierte Bestände werden durch Ratenbegrenzung, Kontingente und Anomalieerkennung geschützt. Auffällige Zugriffsmuster, die auf eine systematische Extraktion hindeuten, führen zu Drosselung oder Sperrung und werden protokolliert. Zugriffsprotokolle sind je Herausgeber auswertbar.

**Rationale:** Herausgeber sorgen sich weniger um unbefugten Zugriff von außen als darum, dass berechtigte Nutzer den Bestand systematisch abziehen. Ohne wirksamen Schutz gegen Massenextraktion ist die Zusage aus REQ-PART-004 nicht belastbar und eine Volltextbereitstellung nicht verhandelbar.

**Akzeptanzkriterium:** Ratenbegrenzung und Kontingente je Zugang aktiv; Anomalieerkennung mit definierten Schwellwerten; Auswertung je Herausgeber möglich.

**Abnahmekriterium:** Ein simulierter Extraktionsversuch wird erkannt, gedrosselt und protokolliert.

## 3.14 Geschützte Anzeige und Offline-Nutzung

Dieses Kapitel definiert Anforderungen an die Anzeige lizenzierter Volltexte. Ziel ist, dass Inhalte innerhalb der Anwendung vollständig nutzbar sind — auch offline — ohne dass daraus weitergebbare Kopien entstehen. Der Schutz wirkt abschreckend und nachverfolgbar, nicht absolut; diese Einschränkung ist bewusst und gegenüber Herausgebern offen zu benennen.

### REQ-DRM-001 — Anzeige ohne herausgebbare Datei

**Statement:** Lizenzierte Volltexte werden ausschließlich innerhalb der Anwendung angezeigt. Es wird keine vollständige, eigenständig verwendbare Dokumentdatei an den Endnutzer ausgeliefert. Die Anzeige erfolgt abschnittsweise und bedarfsgesteuert; ein Export als PDF oder gleichwertiges Format ist für lizenzierte Inhalte nicht vorgesehen. Ebenso ist das markieren von Text in den Volltexten nicht möglich, um copy&paste zu vermeiden.

**Rationale:** Der wirtschaftliche Schaden für die Herausgeber entsteht nicht durch das Lesen, sondern durch die Weitergabe vollständiger Dateien. Wer keine Datei erhält, kann keine weitergeben. Dies ist zugleich das Argument, mit dem normly den Herausgebern hilft, die Verbreitung nicht lizenzierter PDF-Kopien zurückzudrängen: ein bequemer legaler Zugang ist wirksamer als jede Rechtsverfolgung.

**Akzeptanzkriterium:** Kein Endpunkt liefert lizenzierte Inhalte als vollständige Datei aus; die Anzeige erfolgt in Teilabrufen; Abrufe sind protokolliert.

**Abnahmekriterium:** Ein Prüfversuch zeigt, dass sich aus den ausgelieferten Daten keine vollständige Dokumentdatei rekonstruieren lässt, ohne die Anwendung zu umgehen.

### REQ-DRM-002 — Offline-Nutzung mit befristeter Berechtigung

**Statement:** Nutzer können lizenzierte Inhalte für die Offline-Nutzung vorhalten. Die lokale Ablage erfolgt verschlüsselt, gebunden an Nutzer und Gerät, mit befristeter Gültigkeit. Nach Ablauf der Frist ist eine erneute Berechtigung erforderlich. Endet die Lizenz des Nutzers oder wird der Bestand nach REQ-PART-001 zurückgezogen, verliert die lokale Ablage ihre Gültigkeit.

**Rationale:** Offline-Verfügbarkeit ist für die Zielgruppe wesentlich — auf Baustellen und in Werkshallen ist keine verlässliche Verbindung gegeben. Ohne Offline-Fähigkeit bleibt die PDF-Kopie für die Nutzer die praktischere Lösung, und der Zweck der Anforderung wird verfehlt.

**Akzeptanzkriterium:** Lokale Ablage verschlüsselt und an Nutzer und Gerät gebunden; Gültigkeitsdauer konfigurierbar; Entzug der Berechtigung wirkt bei der nächsten Verbindung.

**Abnahmekriterium:** Ein offline vorgehaltener Inhalt ist nach Ablauf der Frist ohne erneute Berechtigung nicht mehr lesbar und außerhalb der Anwendung zu keinem Zeitpunkt lesbar.

### REQ-DRM-003 — Nutzerbezogene Kennzeichnung

**Statement:** Angezeigte lizenzierte Inhalte tragen eine nutzerbezogene Kennzeichnung, sichtbar sowie in nicht ohne Weiteres entfernbarer Form. Anhand einer aufgefundenen Kopie muss sich der Zugang bestimmen lassen, über den sie entstanden ist.

**Rationale:** Bildschirmfotos, Abfotografieren und Texterkennung lassen sich technisch nicht verhindern. Erreichbar ist Nachverfolgbarkeit: Wer weiß, dass eine Weitergabe auf ihn zurückfällt, gibt seltener weiter. Für Herausgeber ist gerade dies der Mehrwert gegenüber der heutigen Situation, in der eine kursierende PDF-Kopie keiner Quelle zuzuordnen ist.

**Akzeptanzkriterium:** Kennzeichnung je Zugang eindeutig; in der Anzeige nicht abschaltbar; Zuordnung aus einer Kopie reproduzierbar.

**Abnahmekriterium:** Aus einem Bildschirmfoto einer Anzeige lässt sich der zugehörige Zugang eindeutig bestimmen.

### REQ-DRM-004 — Zuordnung der Schutzkomponenten zur kommerziellen Schicht

**Statement:** Die geschützte Anzeige, die verschlüsselte Offline-Ablage und die Kennzeichnung sind Bestandteil der kommerziellen Schicht und nicht des quelloffenen Kerns. Der Kern stellt hierfür ausschließlich Schnittstellen bereit. Frei verfügbare Inhalte unterliegen diesen Beschränkungen nicht und bleiben ohne Einschränkung exportierbar.

**Rationale:** Ein Schutzmechanismus, dessen Quellcode vollständig offenliegt, bietet keinen wirksamen Schutz — die Umgehung wäre aus dem Quelltext unmittelbar ableitbar. Die Zuordnung zur kommerziellen Schicht löst diesen Widerspruch, ohne die Quelloffenheit des Kerns einzuschränken. Zugleich stellt sie sicher, dass der freie Kern nicht durch Beschränkungen belastet wird, die für seine Inhalte gar nicht erforderlich sind.
**Akzeptanzkriterium:** Der Kern ist ohne die Schutzkomponenten vollständig lauffähig; frei verfügbare Inhalte sind ohne Beschränkung abrufbar und exportierbar.
**Abnahmekriterium:** Eine Instanz des freien Kerns läuft ohne die Schutzkomponenten und liefert frei verfügbare Inhalte uneingeschränkt aus.

## 3.15 Mobile Bereitstellung

Dieses Kapitel definiert, über welche Wege normly auf mobilen Geräten bereitgestellt wird. Die Aufteilung folgt der Grenze zwischen freiem Kern und kommerzieller Schicht: Frei verfügbare Inhalte werden über eine Progressive Web App bereitgestellt, lizenzierte Volltexte erfordern eine native Anwendung.

### REQ-MOB-001 — Progressive Web App als primärer mobiler Zugang

**Statement:** Die Anwendung wird als installierbare Progressive Web App bereitgestellt, auf derselben Codebasis wie die Desktop-Anwendung. Frei verfügbare Inhalte sind über einen Service Worker offline nutzbar. Die PWA ist Bestandteil des freien Kerns.

**Rationale:** Eine gemeinsame Codebasis vermeidet doppelten Aufwand und deckt den gesamten Bedarf bis zum ersten Volltextvertrag ab. Für frei verfügbare Inhalte bestehen keine Schutzanforderungen, die über die Möglichkeiten des Browsers hinausgehen.

**Akzeptanzkriterium:** Installierbar auf Android und iOS; frei verfügbare Inhalte offline abrufbar; keine getrennte mobile Codebasis.

**Abnahmekriterium:** Die Anwendung wird auf einem mobilen Gerät installiert und im Flugmodus mit frei verfügbaren Inhalten genutzt.

### REQ-MOB-002 — Native Anwendung für lizenzierte Offline-Inhalte

**Statement:** Die Offline-Bereitstellung lizenzierter Volltexte nach REQ-DRM-002 erfolgt ausschließlich über eine native Anwendung für Android und iOS. Diese nutzt die hardwaregestützte Schlüsselablage des Betriebssystems und die verfügbaren Mechanismen zur Einschränkung von Bildschirmaufnahmen. Die native Anwendung ist Bestandteil der kommerziellen Schicht. Diese Zuordnung betrifft Eigentum, Lizenzierung und Wartung, nicht den Zugang für Nutzer: Die Anwendung ist kostenfrei beziehbar und nutzbar. Frei verfügbare Inhalte sind darin ohne Anmeldung und ohne Entgelt abrufbar. Kostenpflichtig sind ausschließlich lizenzierte Volltexte und deren geschützte Offline-Bereitstellung.

**Rationale:** Im Browser existiert kein Ort, an dem ein Schlüssel geschützt abgelegt werden kann; lokale Speicher sind einsehbar. Die in REQ-DRM-002 geforderte Bindung an Nutzer und Gerät ist dort nicht umsetzbar. Native Plattformen bieten mit Keychain und Keystore eine belastbare Grundlage.

**Akzeptanzkriterium:** Schlüsselablage über die Plattformmechanismen; Bindung an Nutzer und Gerät nachweisbar; freier Kern bleibt ohne native Anwendung vollständig nutzbar; die Anwendung ist ohne Konto und ohne Zahlung installier- und nutzbar.

**Abnahmekriterium:** Ein lizenzierter Inhalt ist offline ausschließlich innerhalb der nativen Anwendung lesbar.

### REQ-MOB-003 — Abstrahierte Offline-Schicht

**Statement:** Der Zugriff auf lokal vorgehaltene Inhalte erfolgt über eine einheitliche Abstraktion, deren Implementierung je Plattform ausgetauscht wird. Die Anwendungslogik unterscheidet nicht zwischen Browser- und nativer Ablage.

**Rationale:** Ohne diese Trennung müsste die Offline-Logik für die native Anwendung vollständig neu gebaut werden. Die Abstraktion ist zu Beginn nahezu kostenlos und später nur mit erheblichem Aufwand nachrüstbar. Sie ist zugleich Voraussetzung dafür, dass beide Anwendungen dieselben frei verfügbaren Inhalte gleichwertig bereitstellen.

**Akzeptanzkriterium:** Keine plattformspezifischen Speicherzugriffe außerhalb der Abstraktionsschicht; Austausch durch Tests abgedeckt.

**Abnahmekriterium:** Architektur-Review bestätigt, dass die Anwendungslogik keine Kenntnis der konkreten Ablageform besitzt.

### REQ-MOB-004 — Vertriebswege und Lizenzverträglichkeit

**Statement:** Die native Anwendung der kommerziellen Schicht wird kostenfrei über die Plattform-Stores von Apple und Google vertrieben; Entgelte fallen ausschließlich für den Zugang zu lizenzierten Inhalten an. Sie ist ein eigenständiger Client, der ausschließlich über die unter Apache-2.0 spezifizierte API mit dem Server kommuniziert, und unterliegt nicht der AGPL. Ergänzend kann ein quelloffener Client des freien Kerns über F-Droid bereitgestellt werden.

**Rationale:** Die Nutzungsbedingungen des Apple App Store gelten als unvereinbar mit den Bedingungen von AGPL und GPL. Die Trennung in einen eigenständigen Client über eine permissiv lizenzierte Schnittstelle löst diesen Konflikt, ohne die Quelloffenheit des Kerns einzuschränken. F-Droid setzt vollständig quelloffene, reproduzierbare Builds voraus und kommt daher nur für den freien Client in Betracht.

**Akzeptanzkriterium:** Keine AGPL-lizenzierten Bestandteile in der Store-Anwendung; Kommunikation ausschließlich über die öffentliche API; Lizenzprüfung dokumentiert.

**Abnahmekriterium:** Eine Lizenzprüfung bestätigt die Trennung von freiem Kern und Store-Anwendung.

## 3.16 Zugang und Kontopflicht

Dieses Kapitel regelt, welche Funktionen ohne Konto nutzbar sind und ab wann eine Anmeldung erforderlich wird. Maßgeblich ist nicht der Zugangsweg, sondern die Lizenzklassifikation der Inhalte.

### REQ-ACC-001 — Anonyme Basisnutzung

**Statement:** Suche, Abfrage des Referenzgraphen und Anzeige frei verfügbarer Inhalte sind ohne Konto und ohne Anmeldung nutzbar. Eine Registrierung ist für den Kernzweck der Anwendung nicht erforderlich. Dies gilt für alle Zugangswege gleichermaßen: Webanwendung, Progressive Web App und native Anwendung.

**Rationale:** Eine Registrierungspflicht ist die höchste Hürde in der Nutzerreise und steht im Widerspruch zur Vision eines frei zugänglichen Normenwissens. Zudem sollen Betreiber eigener Instanzen keine Nutzerverwaltung vorhalten müssen, um frei verfügbare Regelwerke bereitzustellen. Ohne Konto entstehen zugleich keine personenbezogenen Daten, die geschützt werden müssten.

**Akzeptanzkriterium:** Vollständiger Frage-Antwort-Zyklus ohne Anmeldung durchführbar; keine Registrierungsaufforderung vor der ersten Nutzung.

**Abnahmekriterium:** Eine frisch installierte Instanz beantwortet eine Anfrage zu einem frei verfügbaren Regelwerk ohne Anmeldung.

### REQ-ACC-002 — Inhaltliche Begrenzung anonymer Zugänge

**Statement:** Anonyme Zugänge erreichen ausschließlich Inhalte, die nach REQ-PIPE-004 als frei lizenzierbar klassifiziert sind. Lizenzierte Volltexte sind ohne authentifizierten und berechtigten Zugang technisch nicht erreichbar. Die Antwortlänge ist begrenzt; ein systematischer Abruf aufeinanderfolgender Abschnitte ist ausgeschlossen.

**Rationale:** Gegenüber Herausgebern muss belegbar sein, dass lizenzierte Inhalte über anonyme Zugänge grundsätzlich nicht erreichbar sind — unabhängig von Kontingenten oder Ratenbegrenzung. Diese strukturelle Zusage ist in Verhandlungen belastbarer als eine reine Registrierungspflicht, die den Zugriff lediglich zurechenbar machen würde.

**Akzeptanzkriterium:** Kein anonymer Zugriffspfad auf lizenzierte Bestände; Antwortlänge konfigurierbar begrenzt; keine Abrufreihenfolge über zusammenhängende Abschnitte.

**Abnahmekriterium:** Ein Prüfversuch belegt, dass lizenzierte Inhalte über keinen anonymen Zugang erreichbar sind.

### REQ-ACC-003 — Kontingent für anonyme Nutzung

**Statement:** Anonyme Zugänge unterliegen einem begrenzten Anfragekontingent je Zeitfenster. Die Zählung erfolgt serverseitig anhand eines vergebenen Sitzungsmerkmals in Verbindung mit der Herkunftsadresse, nicht über clientseitig gespeicherte Werte. Bei Erreichen des Kontingents wird auf die Anmeldung verwiesen.

**Rationale:** Das Kontingent begrenzt die Inferenzkosten der anonymen Nutzung und schafft einen sachlichen Anlass zur Registrierung, ohne sie zu erzwingen. Eine clientseitige Zählung wäre durch Zurücksetzen des Browsers wirkungslos. Da eine adressbasierte Begrenzung durch Adresswechsel umgehbar bleibt, ist sie kein Schutzmechanismus gegen Massenextraktion; diese Aufgabe erfüllt REQ-SEC-004.

**Akzeptanzkriterium:** Kontingent konfigurierbar; Zählung serverseitig; Zurücksetzen clientseitiger Daten hebt die Begrenzung nicht auf; gemeinsame Infrastruktur mit REQ-SEC-004.

**Abnahmekriterium:** Nach Ausschöpfung des Kontingents führt das Löschen der Browserdaten nicht zu weiteren freien Anfragen.

### REQ-ACC-004 — Kontopflichtige Funktionen

**Statement:** Ein Konto ist erforderlich für: erhöhte Anfragekontingente, gespeicherte Verläufe und Merklisten, das Hochladen eigener Dokumente, den Zugang zu lizenzierten Inhalten, die Offline-Nutzung nach REQ-DRM-002 sowie sämtliche kostenpflichtigen Dienste. Diese Aufzählung ist abschließend; weitere Funktionen dürfen nicht ohne Anpassung dieser Anforderung mit einer Kontopflicht versehen werden.

**Rationale:** Eine abschließende Aufzählung verhindert, dass die Kontopflicht schrittweise auf Funktionen ausgeweitet wird, die sie nicht benötigen. Alle genannten Funktionen setzen eine zurechenbare Identität voraus — sei es für Kontingente, Abrechnung, Gerätebindung oder die nutzerbezogene Kennzeichnung nach REQ-DRM-003.

**Akzeptanzkriterium:** Keine Kontopflicht außerhalb der genannten Funktionen; die Zuordnung ist im Berechtigungsmodell abgebildet.

**Abnahmekriterium:** Eine Prüfung der Zugriffspfade bestätigt, dass keine weitere Funktion eine Anmeldung erzwingt.
