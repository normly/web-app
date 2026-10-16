# 1. Introduction

## 1.1 Purpose of this document

This document serves to give the developers at *normly* as precise an overview as possible of what *normly* is, where the product should develop and which features are envisaged.

All of this serves to make it possible to provide a cost and effort estimate.

While the SRS defines what the system must be able to do, the SDD specifies how the system should be built.

## 1.2 Product scope and vision

The product normly pursues the following vision:

*EN: “AI-powered Norms and Standards. Open to everyone.”  
DE: “KI-unterstützte Normen und Standards, offen für jeden.”*

The purpose of normly is to make knowledge about norms and standards as freely accessible as is legally permissible. The freely available core comprises only content that may be passed on (among others official works under § 5 UrhG (German Copyright Act), DGUV Regeln, BAuA technical rules, EU directives via EUR-Lex and open standards), complemented by an open, machine-readable reference graph that maps which standards reference each other, what was superseded, and which legal provision references which norm. Copyrighted full texts are not freely passed on. Until now, technical norms and standards must be purchased individually. They define the generally recognized state of the art. Although they do not have the same status as laws, they are drawn on in accidents, violations or other legal disputes. They thus have a law-like character.  
With the rise of LLMs, user behavior is changing noticeably: whereas PDFs used to be purchased to get the answer to a technical question, **users enjoy and expect** to always have the option of working with the (sometimes very extensive) documents via chatbots. Analyses show that more and more users turn to solutions such as ChatGPT or Perplexity, even though these have no access to the norm documents and can therefore only provide limited (or only partly correct) information.

To make this knowledge available to everyone in the world, normly should be developed using the latest LLM technologies.

The long-term goal is to be permitted to process norms in full text on the basis of license agreements with the publishing organizations. For this to be economically viable for the publishers, normly provides for revenue-dependent remuneration: the publishers share in the revenue attributable to the use of their content. normly thus does not appear as a competitor that displaces existing sales revenue, but as a channel that opens up new revenue and traceably passes it back.

The three steps towards achieving the product vision are the following:

1.  **Building an open-source normly core**  
    The core of normly is developed as a standalone, self-hostable web application under the AGPL-3.0 and made publicly viewable. It comprises the freely available knowledge base, the reference graph, the retrieval and answer logic, and a documented, public API. Client SDKs and the API specification are under Apache-2.0, the data under an open data license (e.g. ODbL or CC-BY-SA).[.](https://notebooklm.google/)

2.  **Building commercial add-on services**  
    To finance the further development of normly, commercial add-on services are built that concern not access to knowledge but process, liability certainty and integration: audit trails and verifiable answers, SLA-backed APIs, on-premises operation, integrations into third-party and CAD software, and analytics reports for norm vendors. These services are not part of the free core.

3.  **Development of a dedicated normlyLLM**  
    Development of a dedicated language model specialized in norms and guidelines. These have the particularity that relationships in graphs and tables must be recognized correctly. Once this model is available, a dedicated chatbot should reach a potential audience of millions, since it has been trained on the basis of norms and standards worldwide. Provided that a corresponding agreement with the norm-setting associations is in place.

## 1.3 Definitions, acronyms and abbreviations

The definitions, acronyms and abbreviations used in this document are explained below.

|          |                                     |
|----------|-------------------------------------|
| **Term** | **Definition**                      |
| API      | Application Programming Interface   |
| ARR      | Annual Recurring Revenue            |
| LLM      | Large Language Model                |
| ML       | Machine Learning                    |
| MVP      | Minimal Viable Product              |
| SDD      | Software Design Description         |
| SRS      | Software Requirements Specification |
| UI       | User Interface                      |
| USP      | Unique Selling Point                |
