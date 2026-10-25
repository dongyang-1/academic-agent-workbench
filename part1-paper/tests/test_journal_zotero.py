import json
import unittest

from literature_search.journal_ranking import classify_journal
from literature_search.zotero import record_to_zotero_item, save_records_to_zotero


class JournalRankingTests(unittest.TestCase):
    def test_matches_explicit_foreign_journal_by_title(self):
        result = classify_journal("American Economic Review")
        self.assertEqual(result["level"], "TOP")
        self.assertEqual(result["match_method"], "title-exact")

    def test_matches_chinese_journal_by_cn_identifier(self):
        result = classify_journal("名称存在拼写差异", ["CN 11-1081/F"])
        self.assertEqual(result["level"], "一级A")
        self.assertEqual(result["matched_title"], "经济研究")

    def test_unlisted_journal_requires_verification(self):
        result = classify_journal("A Newly Established Journal")
        self.assertEqual(result["level"], "待核验")
        self.assertEqual(result["status"], "unmatched")
        self.assertIn("动态清单", result["note"])


class ZoteroTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            "title": "Regulatory Sandboxes and Innovation", "authors": ["Ada Smith"], "year": 2025,
            "venue": "American Economic Review", "issn": ["0002-8282"], "doi": "10.1234/example",
            "url": "https://doi.org/10.1234/example", "abstract": "Evidence.",
            "publication_types": ["journal-article"], "retrieval_sources": ["crossref"],
            "journal_ranking": {"level": "TOP"}, "source_specific": {"language": "en"},
        }

    def test_maps_record_to_zotero_item(self):
        item = record_to_zotero_item(self.record, "record-1")
        self.assertEqual(item["itemType"], "journalArticle")
        self.assertEqual(item["publicationTitle"], "American Economic Review")
        self.assertEqual(item["DOI"], "10.1234/example")
        self.assertEqual(item["id"], "record-1")

    def test_maps_arxiv_record_to_preprint_with_pdf_attachment(self):
        record = {
            **self.record,
            "source": "arxiv",
            "venue": "arXiv",
            "url": "https://arxiv.org/abs/2509.05985v1",
            "open_access_pdf_url": "https://arxiv.org/pdf/2509.05985v1",
            "publication_types": ["preprint"],
            "doi": None,
        }
        item = record_to_zotero_item(record)
        self.assertEqual(item["itemType"], "preprint")
        self.assertEqual(item["repository"], "arXiv")
        self.assertEqual(item["archiveID"], "2509.05985v1")
        self.assertNotIn("DOI", item)
        self.assertNotIn("publicationTitle", item)
        self.assertEqual(item["attachments"][0]["mimeType"], "application/pdf")
        self.assertEqual(item["attachments"][0]["url"], record["open_access_pdf_url"])

    def test_normalizes_valid_doi_and_omits_malformed_value(self):
        encoded = record_to_zotero_item({**self.record, "doi": "https://doi.org/10.1234%2Fexample"})
        malformed = record_to_zotero_item({**self.record, "doi": "not-a-doi"})
        self.assertEqual(encoded["DOI"], "10.1234/example")
        self.assertNotIn("DOI", malformed)

    def test_normalizes_structured_authors_and_omits_null_placeholders(self):
        item = record_to_zotero_item({
            **self.record,
            "authors": [
                {"Author": "Appaya, Mandepanda Sharmista"},
                "{'author': 'Gradstein, Helen Luskin'}",
                "NULL",
            ],
        })
        self.assertEqual([creator["name"] for creator in item["creators"]], [
            "Appaya, Mandepanda Sharmista", "Gradstein, Helen Luskin",
        ])

    def test_posts_with_secret_only_in_header(self):
        captured = {}

        def fake_post(url, body, headers, _timeout):
            captured.update({"url": url, "body": json.loads(body), "headers": headers})
            return 201, b""

        result = save_records_to_zotero([self.record], http_post=fake_post, require_available=False)
        self.assertEqual(result["saved"], 1)
        self.assertEqual(captured["url"], "http://127.0.0.1:23119/connector/saveItems")
        self.assertEqual(captured["headers"]["X-Zotero-Connector-API-Version"], "3")
        self.assertNotIn("Zotero-API-Key", captured["headers"])
        self.assertEqual(captured["body"]["items"][0]["DOI"], "10.1234/example")
        self.assertTrue(captured["body"]["sessionID"].startswith("econlit-"))

    def test_downloads_and_uploads_pdf_as_child_attachment(self):
        calls = []
        record = {**self.record, "open_access_pdf_url": "https://example.org/paper.pdf"}

        def fake_post(url, body, headers, _timeout):
            calls.append({"url": url, "body": body, "headers": headers})
            return (201, b"") if url.endswith("/saveItems") else (200, b"")

        result = save_records_to_zotero(
            [record], http_post=fake_post, pdf_download=lambda _url, _timeout: b"%PDF-1.7 test",
            require_available=False,
        )
        self.assertEqual(result["attachments_requested"], 1)
        self.assertEqual(result["attachments_saved"], 1)
        self.assertEqual(result["attachment_failed_count"], 0)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0]["url"].endswith("/connector/saveItems"))
        self.assertNotIn("attachments", json.loads(calls[0]["body"])["items"][0])
        self.assertTrue(calls[1]["url"].endswith("/connector/saveAttachment"))
        self.assertEqual(calls[1]["headers"]["Content-Type"], "application/pdf")
        metadata = json.loads(calls[1]["headers"]["X-Metadata"])
        self.assertEqual(metadata["parentItemID"], json.loads(calls[0]["body"])["items"][0]["id"])


if __name__ == "__main__":
    unittest.main()
