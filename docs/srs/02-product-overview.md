# 2. Product overview

The following gives an overview of the product.

## 2.1 Product perspective

We distinguish the product status in different phases.

normly follows an open-core model. The free core and the commercial layer are organizationally and technically separate: the core contains no dependency on proprietary components and remains fully runnable without them.

<img src="media/media/image1.png" style="width:6.27014in;height:8.24375in" />

Figure 1: Development phases

**Free core (open source)  
**The freely available knowledge base, the reference graph and the application itself are open source, self-hostable and usable without license costs. In addition, users can temporarily upload their own lawfully acquired documents in order to work on them within a session.

**Commercial layer  
**Paid services build on the free core: managed hosting with SLA, compliance instances with audit trail, integrations into third-party software, analytics reports for norm vendors, and instances in which a vendor's contractually licensed norm collections are pre-processed.

<u>Information:</u> It is planned to spin off the commercial layer into a separate company (GmbH), while the free core, the data and the trademark are held by a non-profit Trägerorganisation. This spin-off is currently preferred, but not yet accepted. Licensing between the Trägerorganisation and the GmbH must take place on customary market terms.

In MVP status, the free core is provided as a standalone web application.

normly is implemented neither as a browser plugin for end users nor as a web widget to be embedded in vendor websites, but as a standalone, self-hostable web application with a public API. Integration into third-party software (e.g. CAD and expert systems) takes place via this API and is part of the commercial layer.

**Example of embedding the White Label LM:** DIN's [<u>norm management software Nautos</u>](https://nautos.de/login) has over 20,000 accounts. Depending on their subscription status, customers can use the software in their browser.

**Example of embedding the White Label GPT:** [<u>The VDI provides each of its members</u>](https://www.vdi.de/) with a personal user area (Mein VDI). Depending on their status, members should be able to use the plugin in their member area to interact with all VDI norms. Only paraphrased answers are generated, since the full text must not be displayed for the time being.

Once MVP status has been successfully validated and is in use, the next development stage is launched. This includes opening up revenue sources via the commercial layer. Personalized advertising is ruled out: it is incompatible with the neutrality of the Trägerorganisation and with the data protection promise of the free core. Advertising may only be served contextually, i.e. for example via the context of a norm that was used for answers, but not on the basis of personal chat inputs.

## 2.2 Product functions

This section describes the core functions of the product at a high level. Detailed requirements are covered in section 3.

**IMPORTANT:** <u>Not all functions are needed yet for the start (MVP status)!</u> For the sake of completeness, and to give a better understanding of the target state, all functions are nevertheless listed here.  
A first impression of what the target version can look like is already available at [<u>app.normly.ai</u>](http://app.normly.ai/).  
MVP-specific functions are therefore specially highlighted.

**Language model**

- An open-weight language model under an OSI-approved license, operated on STACKIT, is used (ADR-022).

- Operating the model in isolation can rule out any outflow of information.

- Part of normly's vision is that a dedicated language model specialized in legal texts is developed later.

**User management**

- If norm-setting associations have an existing member area (e.g. VDI, VDE or DIN), SSO will probably be used.

- For later scaling, it should be noted that users can also register themselves to create an account.

- Subscription model: In Phase 2, a subscription model is implemented for the commercial layer (managed hosting, SLA, integrations). Use of the free core remains unaffected by this and free of charge.

**Interfaces**

- The main interfaces will be to the associations' web interfaces (member area).

- The transfer of norms (documents) for the White Label LM is central, and how this can be done is to be specified in detail.

- Stripe payment function: To be able to implement a subscription model from Phase 2, an interface to Stripe will then be needed to receive payments automatically.

**Analytics and reports (commercial layer)**

- From Phase 2, analytics and reporting functions are offered as a paid service. They are entirely part of the commercial layer and not part of the free core.

- In addition, a directory of conformity-relevant products is planned, in which manufacturers, service providers can book paid entries. Personalized advertising based on search queries or chat histories is ruled out.

**Norm insights**

- Analytics reports require the capture of aggregated usage data. Collection takes place exclusively in the commercial layer, can be deactivated in the free core and must not create personal profiles. Anonymous usage data may be collected, for example to be able to state how many users open a specific norm, or which part of a norm is used particularly often and is therefore highly relevant.

- Norm vendors should also be offered a further (paid) service. They can buy detailed reports that show them in great detail how and by which user group their norms are used.

- A further paid service for end users is based on AI-supported recommendations on how norms should be applied in the workplace, or which practice-oriented recommendations are made as a result of amendments.

**Norm management**

- In later phases, users should be able to monitor their favorite norms. This means being notified of updates, etc.

**Third-party integrations**

- In Phase 3, a third-party integration should then take place. This means that users in expert systems, such as Autodesk, can interact directly with normlyGPT without having to leave the software. Billing is usage-based via API calls. **This step represents the largest revenue growth and is the central USP of the commercial layer (GmbH to be spun off). The integration takes place via the public API of the free core, without restricting its open-source nature.** A dedicated language model is not strictly a prerequisite for this; the integration is also possible on the basis of the open-source model of the free core.

## 2.3 Product constraints

This chapter describes binding framework conditions and constraints that influence the design, the implementation and the operation of normly.

**Technological constraints**

- normly must be implemented as a standalone, self-hostable, web-based application. A white-label web widget to be embedded in vendor websites is not part of the product; integration into third-party systems takes place exclusively via the public API.

- The use of browser plugins for end users is not planned.  
  For MVP status, an open-weight language model under an OSI-approved license is used (ADR-022); a dedicated normlyLLM is not part of the initial development phase.

**Infrastructure and hosting constraints**

- The production environment is operated exclusively on server infrastructure of StackIT (Schwarz Gruppe) located in Germany.

- Development and testing may take place anywhere, in particular locally on the machines of contributors from the open-source community (Compose setup). No user data, production credentials or licensed content are used there.

- The use of US cloud or SaaS providers (e.g. AWS, Azure, Google Cloud) for operation, user data, the norms knowledge base, credentials or deployment is not permitted. Exception since ADR-021: source code, CI/CD and the container registry of the free core reside on GitHub (`github.com/normly/web-app`). No operations or deployment credentials are kept there.

**Legal and contractual constraints**

- Norms and guidelines are subject to copyright restrictions and must not be reproduced verbatim.

- Depending on the contractual situation with norm vendors, content may either be fully pre-processed or only be uploaded temporarily by users.

- normly does not constitute legally binding advice.

**Functional constraints (MVP)**

- Monetization functions (subscriptions, billing, reports) are part of the commercial layer and not fully implemented in the MVP. Personalized advertising is permanently ruled out.

- Third-party integrations (e.g. CAD or expert systems) are not part of the MVP.

## 2.4 User characteristics

This chapter describes the primary user groups of normly and their characteristics, needs and usage contexts that influence the requirements.

**End users (domain users)**

- Typical users are engineers, technicians, safety officers, quality managers and students.

- Users have specialist domain knowledge, but not necessarily in-depth knowledge of the respective norm structure.

- Use is situational, to clarify concrete technical questions.

- Fast, understandable, paraphrased answers with a clear citation are expected.

**Administrative users (norm vendors)**

- Employees of norm vendors or associations who integrate normly into their website.

- Technical knowledge is present, but integration should be possible with minimal implementation effort.

- Configuration options (branding, access control) are expected, as well as **usage and analytics reports in the longer term** (as we have already shown in the normly dummy).

**Accessibility and internationalization**

- Users may have different physical or cognitive impairments; accessible UI concepts are therefore required.

- In the longer term, normly targets an international audience; multilingualism is therefore a central usage scenario. The frontend is English by default – German possible from the start. Users will later have to be able to interact with normly in their native language, even if the source content is not available in that native language.

## 2.5 Assumptions and dependencies

This chapter describes assumptions and external dependencies on which the planning, development and operation of normly are based.

**Assumptions**

- Norm vendors are generally willing to make their existing metadata available to normly, provided that legal and contractual framework conditions are met.

- End users have the legal right to upload norms, provided these are not provided centrally by the vendor.

- Open-weight language models under an OSI-approved license achieve sufficient quality for MVP use.

**Technical dependencies**

- Availability and stability of the StackIT infrastructure.

- Availability of suitable open-weight LLMs under an OSI-approved license on STACKIT.

- Performance of retrieval and vectorization mechanisms for large volumes of documents.

**Organizational dependencies**

- Contract negotiations with norm vendors influence the scope and type of the available content.

- Legal assessments (copyright, liability, data protection) may influence the scope of functions and the UI design.

**Risks if assumptions are wrong**

- Delays or restrictions in concluding contracts may reduce the scope of functions.

- Changes in the licensing or in the STACKIT offering of open-weight LLMs may require technical adjustments.

- Unexpected scaling requirements may lead to performance or cost risks.
