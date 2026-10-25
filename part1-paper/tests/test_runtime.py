import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from literature_search.runtime import (
    _merge_records,
    manual_search_url,
    search_arxiv,
    search_crossref,
    search_core,
    search_datacite,
    search_literature,
    search_nber,
    search_openalex,
    search_econbiz,
    search_plan,
    search_world_bank,
)


class SourceParserTests(unittest.TestCase):
    def test_crossref_parser(self):
        payload = {"message": {"items": [{"DOI": "10.1/example", "title": ["Sandbox Innovation"],
            "author": [{"given": "Ada", "family": "Smith"}], "published": {"date-parts": [[2025]]},
            "container-title": ["Economics Journal"], "URL": "https://doi.org/10.1/example",
            "is-referenced-by-count": 3, "reference-count": 8, "type": "journal-article"}]}}
        records, _ = search_crossref("sandbox innovation", 5, 2015, 2026, lambda _u, _t: json.dumps(payload).encode())
        self.assertEqual(records[0]["doi"], "10.1/example")
        self.assertEqual(records[0]["authors"], ["Ada Smith"])

    def test_datacite_parser(self):
        payload = {"data": [{"id": "10.2/example", "attributes": {"doi": "10.2/example",
            "titles": [{"title": "Open Research"}], "creators": [{"name": "Li, Ming"}],
            "publicationYear": 2024, "publisher": "Repository", "url": "https://example.org/work",
            "descriptions": [{"descriptionType": "Abstract", "description": "An abstract."}],
            "types": {"resourceTypeGeneral": "Text"}}}]}
        records, _ = search_datacite("open research", 5, None, None, lambda _u, _t: json.dumps(payload).encode())
        self.assertEqual(records[0]["year"], 2024)
        self.assertEqual(records[0]["abstract"], "An abstract.")

    def test_econbiz_parser(self):
        payload = {"hits": {"hits": [{
            "id": "econ-1", "title": "Regulatory Sandbox and Innovation",
            "creator": ["Smith, Ada"], "date": ["2024"],
            "series": ["Economic Working Papers"], "issn": ["1234-5678"],
            "identifier_url": ["https://doi.org/10.1/econ", "https://example.org/paper.pdf"],
            "subject": ["innovation policy"], "type_genre": ["Working Paper"],
        }]}}
        records, url = search_econbiz("sandbox innovation", 5, 2015, 2026, lambda _u, _t: json.dumps(payload).encode())
        self.assertEqual(records[0]["doi"], "10.1/econ")
        self.assertEqual(records[0]["issn"], ["1234-5678"])
        self.assertEqual(records[0]["open_access_pdf_url"], "https://example.org/paper.pdf")
        self.assertIn("sort=date+desc", url)

    def test_world_bank_parser(self):
        payload = {"documents": {"D1": {
            "id": "1", "display_title": "Global Experiences from Regulatory Sandboxes",
            "authors": [
                {"Author": "Appaya, Mandepanda Sharmista"},
                "{'author': 'Gradstein, Helen Luskin'}",
            ],
            "docdt": "2020-11-11T05:00:00Z", "docty": "Working Paper",
            "abstracts": {"cdata!": "Evidence from 73 sandboxes."},
            "url": "https://documents.worldbank.org/work", "pdfurl": "https://documents.worldbank.org/work.pdf",
        }, "facets": {}}}
        records, _ = search_world_bank("regulatory sandbox", 5, 2015, 2026, lambda _u, _t: json.dumps(payload).encode())
        self.assertEqual(records[0]["year"], 2020)
        self.assertEqual(records[0]["authors"], [
            "Appaya, Mandepanda Sharmista", "Gradstein, Helen Luskin",
        ])
        self.assertEqual(records[0]["abstract"], "Evidence from 73 sandboxes.")
        self.assertTrue(records[0]["is_open_access"])

    def test_core_parser(self):
        payload = {"results": [{
            "id": 123, "title": "Open Innovation", "authors": [{"name": "Ada Smith"}],
            "yearPublished": 2025, "doi": "10.3/example", "abstract": "CORE abstract.",
            "citationCount": 4, "downloadUrl": "https://api.core.ac.uk/v3/works/123/download",
            "links": {"type": "display", "url": "https://core.ac.uk/works/123"},
            "journals": [{"title": "Open Economics"}], "fieldOfStudy": ["Economics"]
        }]}
        records, _ = search_core("open innovation", 5, 2015, 2026, lambda _u, _t: json.dumps(payload).encode())
        self.assertEqual(records[0]["source_record_ids"]["core"], "123")
        self.assertEqual(records[0]["open_access_pdf_url"], "https://api.core.ac.uk/v3/works/123/download")

    def test_core_requests_only_the_needed_result_count(self):
        requested_urls = []

        def fake_get(url, _timeout):
            requested_urls.append(url)
            return b'{"results": []}'

        search_core("sandbox innovation", 3, None, None, fake_get)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(requested_urls[0]).query)
        self.assertEqual(query["limit"], ["3"])
        self.assertEqual(query["stats"], ["false"])

    def test_core_normalizes_string_fields_and_empty_download(self):
        payload = {"results": [{
            "id": 124, "title": "Metadata Only", "authors": [], "yearPublished": 2024,
            "downloadUrl": "", "sourceFulltextUrls": "", "fieldOfStudy": "Economics; Innovation",
            "links": {"type": "display", "url": "https://core.ac.uk/works/124"}
        }]}
        records, _ = search_core("innovation", 5, None, None, lambda _u, _t: json.dumps(payload).encode())
        self.assertIsNone(records[0]["open_access_pdf_url"])
        self.assertEqual(records[0]["fields_of_study"], ["Economics", "Innovation"])

    def test_openalex_parser_and_abstract_reconstruction(self):
        payload = {"results": [{
            "id": "https://openalex.org/W123", "doi": "https://doi.org/10.4/example",
            "title": "Sandbox Innovation", "publication_year": 2025,
            "authorships": [{"author": {"display_name": "Ada Smith"}}],
            "primary_location": {"landing_page_url": "https://doi.org/10.4/example", "source": {"display_name": "Economics Journal"}},
            "best_oa_location": {"pdf_url": "https://example.org/paper.pdf"},
            "open_access": {"is_oa": True, "oa_status": "gold"},
            "abstract_inverted_index": {"Innovation": [1], "Sandbox": [0]},
            "cited_by_count": 7, "referenced_works_count": 12, "type": "article",
            "topics": [{"display_name": "Financial Regulation"}], "ids": {"openalex": "https://openalex.org/W123"}
        }]}
        records, safe_url = search_openalex("sandbox innovation", 5, 2015, 2026, lambda _u, _t: json.dumps(payload).encode())
        self.assertEqual(records[0]["abstract"], "Sandbox Innovation")
        self.assertEqual(records[0]["doi"], "10.4/example")
        self.assertNotIn("api_key", safe_url)

    def test_arxiv_parser(self):
        atom = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:arxiv="http://arxiv.org/schemas/atom"><entry><id>https://arxiv.org/abs/2501.00001</id>
          <updated>2025-01-02T00:00:00Z</updated><published>2025-01-01T00:00:00Z</published>
          <title>Regulation and Innovation</title><summary>Evidence.</summary><author><name>A. Author</name></author>
          <category term="econ.GN"/><link href="https://arxiv.org/pdf/2501.00001" type="application/pdf"/></entry></feed>'''
        records, _ = search_arxiv("regulation innovation", 5, 2015, 2026, lambda _u, _t: atom)
        self.assertEqual(records[0]["source_record_ids"]["arxiv"], "2501.00001")
        self.assertTrue(records[0]["is_open_access"])

    def test_nber_parser(self):
        fixtures = {
            "ref.tsv": "paper\tauthor\ttitle\tissue_date\tdoi\nw12345\tA Author\tRegulatory Sandbox Innovation\t2025-01-01\t10.3386/w12345\n",
            "abs.tsv": "paper\tabstract\nw12345\tInnovation evidence from a sandbox.\n",
            "auths.tsv": "paper\tname\nw12345\tA Author\n",
            "date.tsv": "paper\tissue_date\nw12345\t2025-01-01\n",
            "jel.tsv": "paper\tjel\nw12345\tG28\n",
        }
        def fetch(url, _timeout):
            return fixtures[url.rsplit("/", 1)[-1]].encode()
        with tempfile.TemporaryDirectory() as directory:
            records, _ = search_nber("regulatory sandbox innovation", 5, 2015, 2026, fetch, cache_dir=Path(directory))
        self.assertEqual(records[0]["jel_codes"], ["G28"])
        self.assertEqual(records[0]["doi"], "10.3386/w12345")

    def test_nber_tolerates_missing_titles_and_null_dois(self):
        fixtures = {
            "ref.tsv": "paper\tauthor\ttitle\tissue_date\tdoi\nw1\tA Author\t\t2025-01-01\tNULL\nw2\tB Author\tInnovation\t2024-01-01\tNULL\n",
            "abs.tsv": "paper\tabstract\nw1\tNo title.\nw2\tEvidence on innovation.\n",
            "auths.tsv": "paper\tname\nw1\tA Author\nw2\tB Author\n",
            "date.tsv": "paper\tissue_date\nw1\t2025-01-01\nw2\t2024-01-01\n",
            "jel.tsv": "paper\tjel\nw2\tO31\n",
        }
        def fetch(url, _timeout):
            return fixtures[url.rsplit("/", 1)[-1]].encode()
        with tempfile.TemporaryDirectory() as directory:
            records, _ = search_nber("innovation", 5, None, None, fetch, cache_dir=Path(directory))
        self.assertEqual(records[0]["doi"], "10.3386/w2")

    def test_dedupes_same_title_when_only_one_record_has_doi(self):
        first = search_crossref("innovation", 5, None, None, lambda _u, _t: json.dumps({"message": {"items": [{
            "DOI": "10.1/example", "title": ["Same Paper"], "published": {"date-parts": [[2025]]}
        }]}}).encode())[0][0]
        second = dict(first)
        second["record_id"] = "other"
        second["doi"] = None
        second["source_record_ids"] = {"nber": "w1"}
        second["retrieval_sources"] = ["nber"]
        merged = _merge_records([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["retrieval_sources"], ["crossref", "nber"])

    def test_search_plan_requires_no_provider_specific_fields(self):
        plan = {
            "research_question": "监管沙盒与创新的关系",
            "scope": {"time_range": "2015-2026"},
            "concept_blocks": [
                {"concept": "policy", "terms": ["regulatory sandbox"]},
                {"concept": "outcome", "terms": ["innovation"]},
            ],
            "sources": ["unsupported-source"],
            "source_policy": {"max_records_per_source": 2},
        }
        # Empty source functions avoid network while testing plan-to-runtime translation.
        import literature_search.runtime as runtime
        original = runtime.SOURCE_FUNCTIONS.copy()
        runtime.SOURCE_FUNCTIONS = {source: (lambda *_args, **_kwargs: ([], "test://source")) for source in runtime.AVAILABLE_SOURCES}
        try:
            output = search_plan(plan)
        finally:
            runtime.SOURCE_FUNCTIONS = original
        self.assertEqual(output["input_summary"], plan["research_question"])
        self.assertIn("Working query: regulatory sandbox innovation", output["handoff"]["notes"])

    def test_manual_sources_generate_traceable_search_logs(self):
        output = search_literature("监管沙盒 创新", ["cnki", "wanfang", "google-scholar"], limit=2)
        self.assertEqual(len(output["records"]), 0)
        self.assertTrue(all(log["execution_status"] == "manual-check-needed" for log in output["search_logs"]))
        self.assertIn("%E7%9B%91%E7%AE%A1", output["search_logs"][0]["query_parameters"]["search_url"])

    def test_manual_search_url_uses_source_specific_parameter(self):
        self.assertIn("txtKey_Words=regulatory+sandbox", manual_search_url("ssrn", "regulatory sandbox"))


if __name__ == "__main__":
    unittest.main()
