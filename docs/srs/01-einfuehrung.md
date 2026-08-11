# 1. Einführung

## 1.1 Zweck des Dokuments

Dieses Dokument dient dazu, den Entwicklern bei *normly* einen möglichst genauen Überblick darüber zu verschaffen, was *normly* ist, wohin das Produkt sich entwickeln soll und welche Features angedacht sind.

All das dient dazu, eine Kosten- und Aufwandsschätzung abgeben zu können.

Während die SRS definiert, was das System können muss, spezifiziert die SDD, wie das System gebaut werden soll.

## 1.2 Produkt Scope und Vision

Das Produkt normly verfolgt folgende Vision:

*EN: “AI-powered Norms and Standards. Open to everyone.”  
DE: “KI-unterstützte Normen und Standards, offen für jeden.”*

Der Zweck von normly besteht darin, Wissen über Normen und Regelwerke so weit frei zugänglich zu machen, wie es rechtlich zulässig ist. Der frei verfügbare Kern umfasst ausschließlich Inhalte, die weitergegeben werden dürfen (u. a. amtliche Werke nach § 5 UrhG, DGUV-Regeln, BAuA-Technische Regeln, EU-Richtlinien über EUR-Lex sowie offene Standards), ergänzt um einen offenen, maschinenlesbaren Referenzgraph, der abbildet, welche Regelwerke aufeinander verweisen, was ersetzt wurde und welche Rechtsvorschrift auf welche Norm verweist. Urheberrechtlich geschützte Volltexte werden nicht frei weitergegeben. Bisher müssen technische Normen und Regelwerke einzeln gekauft werden. Sie definieren den allgemein anerkannten Stand der Technik. Sie haben zwar nicht den gleichen Stand wie Gesetze, werden aber bei Unfällen, Verstößen oder anderen rechtlichen Auseinandersetzungen herangezogen. Sie genießen also einen Gesetzes-Charakter.  
Durch das Aufkommen von LLM ändert sich das Nutzerverhalten zusehends: Wurden früher PDFs gekauft, um die Antwort auf eine technische Frage zu erhalten, **genießen und erwarten die Nutzer** immer die Möglichkeit über Chatbots mit den (teils sehr umfangreichen) Dokumenten arbeiten zu können. Auswertungen zeigen, dass immer mehr Nutzer auf Lösungen wie ChatGPT oder Perpelxity zurückgreifen, obwohl diese keinen Zugang zu den Normen-Dokumenten haben und daher nur beschränkte (oder nur bedingt korrekte) Angaben machen können.

Um dieses Wissen jedem auf der Welt zur Verfügung zu stellen, soll normly, unter der Nutzung neuester LLM-Technologien, entwickelt werden.

Langfristiges Ziel ist es, Normen im Volltext auf Grundlage von Lizenzverträgen mit den herausgebenden Organisationen verarbeiten zu dürfen. Damit dies für die Herausgeber wirtschaftlich tragfähig ist, sieht normly eine umsatzabhängige Vergütung vor: Die Herausgeber werden an den Erlösen beteiligt, die auf Nutzung ihrer Inhalte zurückgehen. normly tritt damit nicht als Wettbewerber auf, der bestehende Verkaufserlöse verdrängt, sondern als Kanal, der neue Erlöse erschließt und nachvollziehbar zurückführt.

Die drei Schritte zur Erreichung der Produktvision sind folgende:

1.  **Aufbau eines quelloffenen normly-Kerns**  
    Der Kern von normly wird als eigenständige, selbst hostbare Webanwendung unter der AGPL-3.0 entwickelt und öffentlich einsehbar bereitgestellt. Er umfasst die frei verfügbare Wissensbasis, den Referenzgraph, die Retrieval- und Antwortlogik sowie eine dokumentierte, öffentliche API. Client-SDKs und die API-Spezifikation stehen unter Apache-2.0, die Daten unter einer offenen Datenlizenz (z. B. ODbL oder CC-BY-SA).[.](https://notebooklm.google/)

2.  **Aufbau kommerzieller Zusatzdienste**  
    Um die Weiterentwicklung von normly zu finanzieren, werden kommerzielle Zusatzdienste aufgebaut, die nicht den Zugang zum Wissen, sondern Prozess, Haftungssicherheit und Integration betreffen: Audit-Trails und nachweisfähige Antworten, SLA-gestützte APIs, On-Premises-Betrieb, Integrationen in Dritt- und CAD-Software sowie Auswertungsberichte für Normenanbieter. Diese Dienste sind nicht Bestandteil des freien Kerns.

3.  **Entwicklung eines eigenen normlyLLM**  
    Entwicklung eines eigenen Sprachmodells mit der Spezialisierung auf Normen und Richtlinien. Diese haben die Besonderheit, dass Zusammenhänge in Graphen und Tabellen korrekt erkannt werden müssen. Steht dieses Modell zur Verfügung, soll ein eigener Chatbot ein potenzielles Millionenpublikum erreichen, da es auf Basis weltweiter Normen und Standards trainiert worden ist. Eine entsprechende Vereinbarung mit den normengebenden Vereinen vorausgesetzt.

## 1.3 Definitionen, Akronyme und Abkürzungen

Im Folgenden werden in diesem Dokument verwendete Definitionen, Akronyme und Abkürzungen erklärt.

|          |                                     |
|----------|-------------------------------------|
| **Term** | **Definition**                      |
| AP       | Application Programming Interface   |
| ARR      | Annual Recurring Revenue            |
| LLM      | Large Language Model                |
| ML       | Machine Learning                    |
| MVP      | Minimal Viable Product              |
| SDD      | Software Design Description         |
| SRS      | Software Requirements Specification |
| UI       | User Interface                      |
| USP      | Unique Selling Point                |
