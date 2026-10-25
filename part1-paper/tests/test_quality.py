import unittest

from literature_search.formats import export_records
from literature_search.quality import distribution_advisories, enrich_records, merge_records, title_similarity


def record(record_id, title, author="Ada Smith", doi=None, year=2025, source="openalex", abstract=""):
    return {
        "record_id": record_id, "title": title, "authors": [author], "year": year,
        "venue": "Economics Journal", "source": source, "doi": doi,
        "external_ids": {}, "source_record_ids": {source: record_id}, "url": "https://example.org/paper",
        "abstract": abstract, "abstract_snippet": None, "jel_codes": [], "methods": [],
        "publication_types": ["article"], "fields_of_study": [], "data_context": None,
        "citation_count": 5, "reference_count": None, "influential_citation_count": None,
        "is_open_access": False, "open_access_pdf_url": None, "retrieval_source": source,
        "retrieval_sources": [source], "retrieval_query": "sandbox innovation", "dedupe_key": None,
        "relevance_note": None, "verification_status": "metadata-only", "source_specific": {},
    }


class QualityTests(unittest.TestCase):
    def test_fuzzy_title_author_deduplication(self):
        left = record("a", "Regulatory Sandboxes and FinTech Innovation")
        right = record("b", "Regulatory Sandbox & Fintech Innovation", source="core")
        self.assertGreaterEqual(title_similarity(left["title"], right["title"]), 0.9)
        merged, reasons = merge_records([left, right])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["retrieval_sources"], ["core", "openalex"])
        self.assertEqual(reasons["normalized-title"], 1)

    def test_economics_quality_scoring(self):
        item = record("a", "Regulatory Sandbox and Firm Innovation",
                      abstract="We use panel data and a difference-in-differences event study with patent outcomes.")
        enriched = enrich_records([item], "regulatory sandbox innovation", [
            {"concept": "policy", "terms": ["regulatory sandbox"]},
            {"concept": "outcome", "terms": ["innovation"]},
        ], ["difference-in-differences"])
        self.assertEqual(enriched[0]["quality_scores"]["topic_relevance"], 30)
        self.assertGreater(enriched[0]["quality_scores"]["method_value"], 0)
        self.assertIn("difference-in-differences", enriched[0]["methods"])

    def test_distribution_advisory(self):
        records = [record(str(index), f"Paper {index}", year=2025) for index in range(6)]
        enrich_records(records, "innovation")
        dimensions = {item["dimension"] for item in distribution_advisories(records)}
        self.assertIn("time", dimensions)

    def test_reference_exports(self):
        records = [record("a", "Sandbox Innovation", doi="10.1/example")]
        ris, _, extension = export_records(records, "ris")
        bib, _, _ = export_records(records, "bibtex")
        enw, _, _ = export_records(records, "enw")
        self.assertEqual(extension, "ris")
        self.assertIn("DO  - 10.1/example", ris)
        self.assertIn("doi = {10.1/example}", bib)
        self.assertIn("%R 10.1/example", enw)


if __name__ == "__main__":
    unittest.main()
