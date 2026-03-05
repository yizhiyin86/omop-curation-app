# OMOP Curation Queue — Local App

## Setup
```bash
cd omop-curation-app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your credentials
```

## Seed test data
Run `seed_test_data.cypher` in Neo4j Browser first — creates 20 unmapped
VendorTerms across Flatiron, IQVIA, Optum.

## Run
```bash
streamlit run app.py
```

## Workflow
1. Fill sidebar + click **Connect & Load Queue**
2. Pick a term from the left table
3. Click **Search OMOP Concepts** → see top-5 vector matches
4. **Confirm** (verified) or **Propose** (needs senior review) or **Skip**
5. Term disappears from queue; audit trail written to MAPS_TO relationship