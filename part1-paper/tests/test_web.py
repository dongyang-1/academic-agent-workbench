import os
import tempfile
import unittest
import re
from pathlib import Path
from unittest.mock import patch

from literature_search.web import _local_economics_translation, _translation_chunks, generate_search_protocol, import_corpus, public_config, translate_text_to_chinese, validate_search_payload


class WebPayloadTests(unittest.TestCase):
    def test_long_translation_text_is_chunked_and_reassembled(self):
        text = "First sentence about innovation. " + ("Evidence and methods are discussed. " * 20)
        chunks = _translation_chunks(text, maximum=90)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 90 for chunk in chunks))
        with patch("literature_search.web._translate_chunk_to_chinese", side_effect=lambda value: f"译文[{value}]"):
            translated = translate_text_to_chinese(text)
        self.assertEqual(translated["source"], "public-translation-service")
        self.assertEqual(translated["translation"].count("译文["), len(_translation_chunks(text)))

    def test_existing_chinese_text_is_not_sent_to_translation_service(self):
        with patch("literature_search.web._translate_chunk_to_chinese") as translator:
            translated = translate_text_to_chinese("这是一段中文摘要。")
        translator.assert_not_called()
        self.assertEqual(translated["source"], "original-chinese")

    def test_local_economics_translation(self):
        translated = _local_economics_translation("监管沙盒与创新的关系")
        self.assertIn("regulatory sandbox", translated)
        self.assertIn("innovation", translated)
        self.assertIn("relationship", translated)

    def test_local_translation_keeps_minimum_wage_treatment(self):
        translated = _local_economics_translation("最低工资政策对企业创新的影响")
        self.assertIn("minimum wage policy", translated)
        self.assertIn("firm innovation", translated)
        self.assertIn("impact", translated)

    def test_valid_payload_is_normalized(self):
        value = validate_search_payload({
            "research_question": "监管沙盒与创新的关系",
            "working_query": "regulatory sandbox innovation",
            "start_year": "2015",
            "end_year": 2026,
            "limit": "20",
            "sources": ["openalex", "core", "openalex"],
        })
        self.assertEqual(value["query"], "regulatory sandbox innovation")
        self.assertEqual(value["sources"], ["openalex", "core"])
        self.assertEqual(value["limit"], 20)
        self.assertEqual(value["ranking"], "combined")

    def test_relationship_question_generates_matching_protocol(self):
        with patch("literature_search.web.translate_research_question", return_value={
            "translation": "relationship between regulatory sandbox and innovation",
            "source": "test",
        }):
            protocol = generate_search_protocol("监管沙盒与创新的关系")
        self.assertEqual(protocol["working_query"], "relationship between regulatory sandbox and innovation")
        self.assertEqual(protocol["concept_blocks"][0]["terms"], ["监管沙盒", "regulatory sandbox"])
        self.assertEqual(protocol["concept_blocks"][1]["terms"], ["创新", "innovation"])
        self.assertEqual(protocol["requested_methods"], ["面板回归 (panel regression)"])
        self.assertFalse(protocol["protocol_confirmed"])
        self.assertIn("监管沙盒", protocol["inclusion_criteria"][0])

    def test_causal_question_refreshes_method_protocol(self):
        with patch("literature_search.web.translate_research_question", return_value={
            "translation": "impact of digital economy on firm innovation",
            "source": "test",
        }):
            protocol = generate_search_protocol("数字经济对企业创新的影响")
        self.assertEqual(protocol["concept_blocks"][0]["terms"], ["数字经济", "digital economy"])
        self.assertEqual(protocol["concept_blocks"][1]["terms"], ["企业创新", "firm innovation"])
        self.assertTrue(any("difference-in-differences" in method for method in protocol["requested_methods"]))
        self.assertTrue(any("instrumental variables" in method for method in protocol["requested_methods"]))
        self.assertTrue(all(re.search(r"[\u4e00-\u9fff]", item) for item in protocol["inclusion_criteria"] + protocol["exclusion_criteria"]))

    def test_systematic_mode_requires_confirmed_protocol(self):
        with self.assertRaisesRegex(ValueError, "系统检索"):
            validate_search_payload({"working_query": "innovation", "mode": "systematic"})

        value = validate_search_payload({
            "working_query": "innovation", "mode": "systematic", "protocol_confirmed": True,
            "inclusion_criteria": ["Directly studies innovation"],
        })
        self.assertEqual(value["mode"], "systematic")

    def test_invalid_year_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "起始年份"):
            validate_search_payload({"working_query": "innovation", "start_year": 2026, "end_year": 2015})

    def test_unknown_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "不支持的数据源"):
            validate_search_payload({"working_query": "innovation", "sources": ["unknown"]})

    def test_config_exposes_only_key_availability(self):
        with patch.dict(os.environ, {"CORE_API_KEY": "secret-core", "OPENALEX_API_KEY": "secret-openalex"}), \
             patch("literature_search.web.zotero_configuration", return_value={"configured": True, "mode": "local-connector", "version": "9.0.6"}):
            config = public_config()
            encoded = str(config)
        self.assertNotIn("secret-core", encoded)
        self.assertNotIn("secret-openalex", encoded)
        self.assertNotIn("api_key", encoded.lower())
        self.assertTrue(next(item for item in config["sources"] if item["id"] == "crossref")["configured"])
        self.assertTrue(config["zotero"]["configured"])

    def test_user_corpus_uses_shared_deduplication_and_scoring(self):
        payload = {
            "search_context": {
                "research_question": "监管沙盒与创新的关系",
                "working_query": "regulatory sandbox innovation",
                "sources": ["crossref"],
            },
            "records": [
                {"id": "a", "title": "Regulatory Sandboxes and FinTech Innovation", "author": "Ada Smith"},
                {"id": "b", "title": "Regulatory Sandbox & Fintech Innovation", "author": "Ada Smith"},
                {"id": "c"},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            latest = Path(directory) / "latest.json"
            with patch("literature_search.web.save_session", return_value="ls-test"), \
                 patch("literature_search.web.LATEST_RESULT", latest):
                result = import_corpus(payload)
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["search_metrics"]["duplicates_removed"], 1)
        self.assertIn("total_score", result["records"][0])
        self.assertEqual(len(result["verification_gaps"]), 1)


if __name__ == "__main__":
    unittest.main()
