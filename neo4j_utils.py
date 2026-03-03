"""
Neo4j query helpers for the Streamlit curation app.
Sync driver - simpler for Streamlit's execution model.
"""
from neo4j import GraphDatabase
from datetime import datetime

# ── Queries ──────────────────────────────────────────────────────────────────

GET_UNMAPPED_TERMS = """
    MATCH (v:VendorTerm)
    WHERE NOT (v)-[:MAPS_TO]->()
    RETURN
        v.vendor_name  AS vendor,
        v.vendor_term  AS term,
        v.vendor_code  AS code,
        v.batch_id     AS batch_id,
        toString(v.created_at) AS ingested_at
    ORDER BY vendor, term
"""

SEARCH_CONCEPTS = """
    WITH $search_term AS searchText
    WITH genai.vector.encode(
        searchText, 'OpenAI',
        {model: 'text-embedding-3-small', token: $token}
    ) AS embedding
    CALL db.index.vector.queryNodes('concept_embedding', 5, embedding)
    YIELD node AS c, score
    OPTIONAL MATCH (v:VendorTerm)-[:MAPS_TO]->(c)
    OPTIONAL MATCH (c)-[r]-(related:Concept)
    RETURN
        c.concept_id    AS concept_id,
        c.concept_name  AS concept_name,
        c.domain_id     AS domain,
        c.vocabulary_id AS vocabulary,
        round(score * 100) / 100 AS score,
        collect(DISTINCT {
            vendor: v.vendor_name,
            term:   v.vendor_term
        })[0..5] AS already_mapped,
        collect(DISTINCT {
            rel:     type(r),
            concept: related.concept_name
        })[0..8] AS related_concepts
    ORDER BY score DESC
"""

WRITE_PROPOSE = """
    MATCH (c:Concept {concept_id: $concept_id})
    MERGE (v:VendorTerm {vendor_term: $vendor_term, vendor_name: $vendor_name})
    ON CREATE SET v.vendor_code = $vendor_code, v.created_at = datetime()
    MERGE (v)-[r:MAPS_TO]->(c)
    SET r.status      = 'proposed',
        r.source      = 'ui_curation',
        r.proposed_by = $username,
        r.proposed_at = datetime()
    RETURN v.vendor_term AS term, c.concept_name AS concept, r.status AS status
"""

WRITE_CONFIRM = """
    MATCH (c:Concept {concept_id: $concept_id})
    MATCH (v:VendorTerm {vendor_term: $vendor_term, vendor_name: $vendor_name})
    MERGE (v)-[r:MAPS_TO]->(c)
    SET r.status       = 'verified',
        r.source       = 'ui_curation',
        r.confirmed_by = $username,
        r.confirmed_at = datetime()
    RETURN v.vendor_term AS term, c.concept_name AS concept, r.status AS status
"""

WRITE_SKIP = """
    MATCH (v:VendorTerm {vendor_term: $vendor_term, vendor_name: $vendor_name})
    SET v.review_status = 'skipped',
        v.skipped_by    = $username,
        v.skipped_at    = datetime()
    RETURN v.vendor_term AS term, v.review_status AS status
"""
# Add this query constant
SEARCH_VENDOR_TERMS = """
    WITH $search_term AS searchText
    WITH genai.vector.encode(
        searchText, 'OpenAI',
        {model: 'text-embedding-3-small', token: $token}
    ) AS embedding
    CALL db.index.vector.queryNodes('vendor_term_embedding', 5, embedding)
    YIELD node AS v, score
    MATCH (v)-[:MAPS_TO]->(c:Concept)
    RETURN
        v.vendor_name  AS vendor,
        v.vendor_term  AS vendor_term,
        v.vendor_code  AS vendor_code,
        c.concept_id   AS concept_id,
        c.concept_name AS concept_name,
        c.domain_id    AS domain,
        c.vocabulary_id AS vocabulary,
        round(score * 100) / 100 AS score
    ORDER BY score DESC
"""
GET_PROPOSED_MAPPINGS = """
    MATCH (v:VendorTerm)-[r:MAPS_TO]->(c:Concept)
    WHERE r.status = 'proposed'
    RETURN
        v.vendor_name           AS vendor,
        v.vendor_term           AS term,
        v.vendor_code           AS code,
        c.concept_id            AS concept_id,
        c.concept_name          AS concept_name,
        c.domain_id             AS domain,
        c.vocabulary_id         AS vocabulary,
        r.proposed_by           AS proposed_by,
        toString(r.proposed_at) AS proposed_at,
        r.source                AS source
    ORDER BY r.proposed_at DESC
"""
WRITE_PROMOTE = """
    MATCH (v:VendorTerm {vendor_term: $vendor_term, vendor_name: $vendor_name})
          -[r:MAPS_TO]->(c:Concept {concept_id: $concept_id})
    WHERE r.status = 'proposed'
    SET r.status          = 'verified',
        r.confirmed_by    = $username,
        r.confirmed_at    = datetime(),
        r.previous_status = 'proposed'
    RETURN v.vendor_term AS term, c.concept_name AS concept, r.status AS status
"""

WRITE_REJECT = """
    MATCH (v:VendorTerm {vendor_term: $vendor_term, vendor_name: $vendor_name})
          -[r:MAPS_TO]->(c:Concept {concept_id: $concept_id})
    SET r.status        = 'rejected',
        r.rejected_by   = $username,
        r.rejected_at   = datetime(),
        r.reject_reason = $reason
    RETURN v.vendor_term AS term, c.concept_name AS concept, r.status AS status
"""

# ── Driver helper ─────────────────────────────────────────────────────────────

def get_driver(uri, username, password):
    return GraphDatabase.driver(uri, auth=(username, password))

def get_unmapped_terms(driver, database):
    with driver.session(database=database) as s:
        return [dict(r) for r in s.run(GET_UNMAPPED_TERMS)]

def search_concepts(driver, database, search_term, openai_key):
    with driver.session(database=database) as s:
        return [dict(r) for r in s.run(
            SEARCH_CONCEPTS,
            search_term=search_term,
            token=openai_key
        )]
# Add this function
def search_vendor_terms(driver, database, search_term, openai_key):
    with driver.session(database=database) as s:
        return [dict(r) for r in s.run(
            SEARCH_VENDOR_TERMS,
            search_term=search_term,
            token=openai_key
        )]

def write_propose(driver, database, vendor_term, vendor_name, vendor_code,
                  concept_id, username):
    with driver.session(database=database) as s:
        r = s.run(WRITE_PROPOSE,
                  vendor_term=vendor_term, vendor_name=vendor_name,
                  vendor_code=vendor_code, concept_id=concept_id,
                  username=username)
        return dict(r.single())

def write_confirm(driver, database, vendor_term, vendor_name,
                  concept_id, username):
    with driver.session(database=database) as s:
        r = s.run(WRITE_CONFIRM,
                  vendor_term=vendor_term, vendor_name=vendor_name,
                  concept_id=concept_id, username=username)
        return dict(r.single())

def write_skip(driver, database, vendor_term, vendor_name, username):
    with driver.session(database=database) as s:
        r = s.run(WRITE_SKIP,
                  vendor_term=vendor_term, vendor_name=vendor_name,
                  username=username)
        return dict(r.single())

def get_proposed_mappings(driver, database):
    with driver.session(database=database) as s:
        return [dict(r) for r in s.run(GET_PROPOSED_MAPPINGS)]

def write_promote(driver, database, vendor_term, vendor_name, concept_id, username):
    with driver.session(database=database) as s:
        r = s.run(WRITE_PROMOTE, vendor_term=vendor_term, vendor_name=vendor_name,
                  concept_id=concept_id, username=username)
        return dict(r.single())

def write_reject(driver, database, vendor_term, vendor_name, concept_id, username, reason):
    with driver.session(database=database) as s:
        r = s.run(WRITE_REJECT, vendor_term=vendor_term, vendor_name=vendor_name,
                  concept_id=concept_id, username=username, reason=reason)
        return dict(r.single())