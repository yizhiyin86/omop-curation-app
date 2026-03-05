MATCH (v:VendorTerm {batch_id: "test_batch_2024_03"})
DETACH DELETE v
RETURN count(v) AS deleted;