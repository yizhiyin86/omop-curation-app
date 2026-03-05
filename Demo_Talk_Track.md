# Demo Slides Talk Track

## Slide-by-Slide Talk Track

---

### Slide 1: Live Demo: SME Curation Workflow
**Section Header:** (Title slide)

**Talk Track:**
*"Let me walk you through the SME curation workflow we built. This is a Streamlit frontend — I want to be clear upfront: I'm not selling you a Streamlit app. The point is to show how easy it is to build traceability when Neo4j is your system of record. Every action you'll see — search, confirm, reject, propose — is just a Cypher query. You could build this UI in React, Retool, whatever your team prefers."*

---

### Slide 2: Vector Search + Graph Traversal for Candidate Concepts
**Section Header:** Step 1: Discover

**Talk Track:**
They click Connect, which loads the curation queue — this triggers a query in the backend to find all unmapped terms for that vendor."
"The SME selects an unmapped vendor term — in this case from Flatiron — and triggers a search."
"What comes back isn't just vector similarity. The query does three things: first, it vector-encodes the search term and finds the top-K semantically similar OMOP concepts. Second, it traverses the graph to see which vendor terms from other sources — IQVIA, Optum — have already been mapped to those concepts. Third, it pulls related concepts — complications, hierarchies — giving the SME clinical context before they decide."
"This is the institutional memory piece. The SME doesn't just see a similarity score. They see: 'IQVIA already mapped a similar term to this concept six months ago,' plus what complications that concept carries. That context changes the decision."

---

### Slide 3: SME Confirms Mapping with Reason
**Section Header:** Step 2: Curate

**Talk Track:**
"The SME reviews the candidates. They see the domain — Condition, Drug, Measurement — the similarity score, the vocabulary source, and prior mappings from other vendors."
"They select a match and click confirm. In this demo, confirm doesn't require a reason — but reject does. That's a design choice you can adapt. If your workflow needs a reason on every decision, it's one line of code to add a reason field to the confirm action."
"The key point: whatever metadata you want to capture — reason, confidence level, reference source — it all goes on the relationship. The graph schema is flexible."

---

### Slide 4: MAPS_TO Relationship Created with Audit Trail
**Section Header:** Step 3: Persist

**Talk Track:**
*"When the SME clicks confirm, one Cypher query writes the MAPS_TO relationship with full audit properties: curator ID, timestamp, similarity score, reason, status."*

*"The relationship is the record of truth. It's queryable, auditable, permanent. If regulatory asks 'how did this term get mapped?' — you traverse the graph and the answer is there."*

---

### Slide 5: Search Previously Mapped Vendor Terms
**Section Header:** Institutional Memory

**Talk Track:**
"This is the institutional memory feature. The SME selects a term — Flatiron's 'Metformin 500mg Tablet' — and clicks 'Search Similar Vendor Terms.'"
"Neo4j lets you create multiple vector indexes — one on OMOP concepts, another on vendor terms. The first search tool queries the concept index. This tool queries the vendor term index. Same pattern, different index."
"Here's what the query does: it searches the vendor term index for semantically similar terms, then traverses the MAPS_TO relationship to see what concept each term already resolved to. Look at the results — IQVIA's 'Metformin HCl' already mapped to OMOP concept 1201628, domain Drug, vocabulary RxNorm. Optum's 'Glucophage' also maps to Metformin at 79% similarity."
"The SME can now click 'Confirm same mapping' to adopt the same concept that IQVIA already mapped to. Or they can click 'Propose same mapping' if they want another SME to review first."
"And if you want, you can configure the query to expand further — traverse from that concept back out to see all other vendor terms that also map there. The traversal pattern is configurable based on how much context you want to surface."
"That's the power of combining vector and graph. Vector search finds semantically similar terms across vendors. Graph relationships connect them to the same OMOP concept. One query, full context."


---

### Slide 6: Propose Mapping for Another SME to Review
**Section Header:** Collaborative Workflow

**Talk Track:**
*"Not every mapping is straightforward. Sometimes the SME isn't confident. Maybe it's a clinical edge case, or the similarity score is borderline."*

*"Instead of confirming, they can propose a mapping for someone else to review. The relationship is created with status 'proposed' — it's visible, but not final."*

*"This supports a two-person review workflow without any external ticketing system. The graph is the workflow."*

---

### Slide 7: Second SME Approves or Rejects Proposed Mapping
**Section Header:** Collaborative Workflow

**Talk Track:**
*"The second SME sees the proposed mapping in their queue. They can review the context — the similarity score, the reason provided, the related concepts — and either approve or reject."*

*"If they approve, the status changes to 'verified' with their curator ID and timestamp. If they reject, the status is 'rejected' with a reason."*

*"Either way, no information is lost. We know what was proposed, who proposed it, who reviewed it, and what they decided. That's the audit trail regulatory wants."*

---

### Slide 8: The Cypher Behind the UI
**Section Header:** Under the Hood

**Talk Track:**
*"Now let me show you what's actually happening. This is the Cypher query behind the search tool."*

*"Vector encode the search term — that's genai.vector.encode() running inside Neo4j, not client-side. Query the vector index for top-K candidates. Traverse to find existing vendor term mappings. Traverse again to find related concepts — complications, hierarchies."*

*"This entire operation is one Cypher query. The Streamlit app is just a thin wrapper. The intelligence is in the graph."*

*"The point: this is not hard. These are basic Cypher patterns. The value isn't in the query complexity — it's in what the graph structure enables."*

---

### Slide 9 Cypher Check - Updates
**Section Header:** Operational Visibility
**Talk Track:**
"This is the live graph — what we just did in the UI is already here. Five MAPS_TO relationships written, five VendorTerms connected to their OMOP Concepts."
"Look at the table. Status column shows a mix of 'proposed' and 'verified' — those are two different write paths from the same UI, stamped in the same second. actioned_by is curator_1, actioned_at is today."

"This is what operational visibility looks like. No separate audit table, no pipeline. The provenance is on the relationship, and Cypher surfaces it instantly."


### Slide 10 Aura Dashboard: Monitor Curation Progress
**Section Header:** Operational Visibility

**Talk Track:**
"This is Aura Dashboards — it's built directly into the Aura console under Tools. No BI tool license, no ETL pipeline, no Tableau connector. The graph is the data source."
"Every card you see here is a live Cypher query. Total mappings performed, the progress pie showing verified versus proposed versus unmapped, the curator activity charts, the unmapped terms queue — all live, all from the same graph we just wrote to."
"Here's what's notable for a team like yours: we didn't hand-write these charts. Aura's AI dashboard generator analyzes your database schema and proposes a full dashboard automatically Neo4j — then you refine with the built-in Cypher copilot. We went from zero to this in minutes."
"And because dashboards operate directly on your graph data via Cypher and are stored in Neo4j cloud storage Neo4j, there's nothing to deploy or maintain. The curation team gets operational visibility out of the box."
"This is the management layer for the term harmonization workflow — before you even think about Horizon 2."

---

## Key Messages to Reinforce

Throughout the demo, reinforce these points:

1. **Not selling the Streamlit app.** The frontend is replaceable. The value is in the graph structure and the Cypher patterns.

2. **Every action is a Cypher query.** Confirm, reject, propose — these are MERGE and SET operations with audit properties. Basic patterns.

3. **Institutional memory is built in.** Prior mappings, related concepts, curator decisions — all traversable, all queryable.

4. **Audit trail on relationships.** Status, curator, timestamp, reason — stored on the MAPS_TO relationship, not in a separate audit table.

5. **Graph makes cross-vendor lookup trivial.** Finding what IQVIA mapped to the same concept as Optum is one traversal, not a multi-join.

---

## Transition Back to Main Deck

After the demo:

*"That's the workflow. What you just saw is basic Cypher — vector search, traversal, write-back with audit properties. The hard part isn't the Neo4j work. The hard part is building the frontend, doing user testing, integrating with your existing systems. That's not what a POC is for."*

*"Let's go back to the deck and talk about the path forward."*

---

## Reference Links for Horizon 2 Discussion

| Use Case | Reference | URL |
|----------|-----------|-----|
| Patient Journey & OMOP in Neo4j | Neo4j Industry Use Cases | https://neo4j.com/developer/industry-use-cases/life-sciences/medical-care/patient-journey/ |
| OMOP CDM to Neo4j Graph Model | Peer-reviewed paper (Dec 2024) | https://pmc.ncbi.nlm.nih.gov/articles/PMC11617070/ |
| Merck, Bayer, Novartis case studies | GraphTalk Pharma 2025 Recap | https://neo4j.com/blog/developer/graphtalk-pharma-life-sciences-2025/ |
| Knowledge Graphs in Pharmacovigilance | ScienceDirect Scoping Review | https://www.sciencedirect.com/science/article/pii/S0149291824001449 |
