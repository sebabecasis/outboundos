import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from outboundos.providers import OpenAIEncoder, extract_passages, scrape, digest


class ProviderTests(unittest.TestCase):
    def test_embeddings_normalise_and_cache_without_second_request(self):
        calls = []
        def transport(url, payload, **kw):
            calls.append(payload)
            return {"data": [{"embedding": [3, 4]}]}
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
            encoder = OpenAIEncoder(dimensions=2, cache=directory, transport=transport)
            self.assertEqual([0.6, 0.8], encoder.encode("source"))
            self.assertEqual([0.6, 0.8], OpenAIEncoder(dimensions=2, cache=directory, transport=transport).encode("source"))
            self.assertEqual(1, len(calls))
            self.assertEqual([0, 0], encoder.encode(" "))

    def test_bad_embedding_is_rejected(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
            for vector in ([1], [0, 0], [float("nan"), 1]):
                with self.assertRaises(ValueError):
                    OpenAIEncoder(dimensions=2, transport=lambda *a, **kw: {"data": [{"embedding": vector}]}).encode("source")

    def test_extraction_requires_verbatim_evidence(self):
        def response(text):
            return lambda *a, **kw: {"choices": [{"message": {"content": json.dumps({"passages": [text]})}}]}
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"}):
            self.assertEqual(["source"], extract_passages("a source quote", "goal", model="model", transport=response("source")))
            with self.assertRaises(ValueError):
                extract_passages("a source quote", "goal", model="model", transport=response("invented"))

    def test_scrape_requires_content_and_safe_url(self):
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "test"}):
            with self.assertRaises(ValueError):
                scrape("file:///etc/passwd")
            with self.assertRaises(ValueError):
                scrape("https://example.test", transport=lambda *a, **kw: {"success": False})
            page = scrape("https://example.test", transport=lambda *a, **kw: {"success": True, "data": {"markdown": "evidence"}})
            self.assertEqual("evidence", page["text"])

    def test_digest_ignores_object_key_order_not_content(self):
        self.assertEqual(digest({"a": 1, "b": 2}), digest({"b": 2, "a": 1}))
        self.assertNotEqual(digest({"a": 1}), digest({"a": 2}))
