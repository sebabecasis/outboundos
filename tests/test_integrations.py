import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from outboundos.integrations import Prospeo, company_database, live_research, score_company, upload_approved
from outboundos.providers import ProviderError
from outboundos.models import CampaignBrief
from outboundos.workflow import OutboundWorkflow


class IntegrationTests(unittest.TestCase):
    def test_prospeo_default_is_dry(self):
        client = Prospeo(transport=Mock(side_effect=AssertionError("network")))
        self.assertTrue(client.search("example.test")["dry_run"])
        self.assertTrue(client.enrich("person")["dry_run"])

    @patch.dict("os.environ", {"PROSPEO_API_KEY": "test"})
    def test_prospeo_search_bounds_and_verified_enrichment(self):
        transport = Mock(side_effect=[
            {"results": [{"person": {"person_id": "p"}}, {"person": {"person_id": "p"}}], "pagination": {"total_page": 2}},
            {"results": [{"person": {"person_id": "q"}}]},
            {"person": {"email": {"email": "a@example.test", "status": "VERIFIED"}}, "company": {"name": "Example"}}])
        client = Prospeo(execute=True, transport=transport)
        self.assertEqual(2, len(client.search("example.test", max_pages=2)))
        self.assertEqual("a@example.test", client.enrich("p")["email"])
        self.assertEqual(["VERIFIED"], transport.call_args_list[0].args[1]["filters"]["person_contact_details"]["email"])

    @patch.dict("os.environ", {"PROSPEO_API_KEY": "test"})
    def test_prospeo_miss_is_not_provider_failure(self):
        client = Prospeo(execute=True, transport=Mock(side_effect=ProviderError(400, "NO_RESULTS")))
        self.assertEqual([], client.search("example.test"))
        client.transport = Mock(side_effect=ProviderError(429))
        with self.assertRaises(ProviderError):
            client.search("example.test")
        client.transport = Mock(return_value={"person": {"email": {"email": "bad@example.test", "status": "CATCH_ALL"}}})
        self.assertIsNone(client.enrich("p"))

    def test_database_to_review_pipeline_and_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with sqlite3.connect(root / "companies.db") as db:
                db.execute("CREATE TABLE companies(name TEXT, domain TEXT, website TEXT)")
                db.execute("INSERT INTO companies VALUES('Example','example.test','https://example.test')")
            (root / "plan.json").write_text(json.dumps({"database": "companies.db", "scoring_model": "model"}))
            brief = CampaignBrief("b", "goal", "audience", ["signal"], str(root / "plan.json"))
            fetch = Mock(return_value={"source_url": "https://example.test", "text": "exact evidence"})
            score = Mock(return_value={"score": 0.9, "excluded": False, "reason": "fit", "evidence": ["exact evidence"]})
            client = Mock()
            client.search.return_value = [{"person_id": "p"}]
            client.enrich.return_value = {"email": "a@example.test"}
            kwargs = dict(execute=True, fetch=fetch, scorer=score, prospeo=client, cache=root / "cache")
            payload = live_research(brief, **kwargs)
            self.assertEqual(1, len(payload["candidates"]))
            self.assertEqual("a@example.test", payload["leads"][0]["email"])
            self.assertEqual(payload, live_research(brief, **kwargs))
            fetch.assert_called_once()
            client.enrich.assert_called_once()
            self.assertEqual(1, len(company_database(root / "companies.db")))
            with self.assertRaises(ValueError):
                company_database(root / "companies.db", limit=0)

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"})
    def test_ai_score_rejects_invented_quote(self):
        brief = CampaignBrief("b", "goal", "audience", ["signal"], "unused")
        transport = Mock(return_value={"choices": [{"message": {"content": json.dumps({"score": 0.9, "excluded": False, "reason": "fit", "evidence": ["invented"]})}}]})
        with self.assertRaises(ValueError):
            score_company("actual source", brief, model="test", transport=transport)

    def setup_export(self, directory):
        workflow = OutboundWorkflow(directory, researcher=lambda b: {"candidates": [], "leads": [{"email": "a@example.test"}, {"email": "a@example.test"}]})
        workflow.schedule(CampaignBrief("b", "goal", "audience", ["signal"], "unused"))
        proposal = workflow.run_due()[0]
        return workflow, proposal.id

    @patch.dict("os.environ", {"INSTANTLY_API_KEY": "test"})
    def test_upload_gate_dry_run_destination_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            workflow, pid = self.setup_export(directory)
            kwargs = dict(campaign_id="campaign", expected_org="org")
            with self.assertRaises(PermissionError):
                upload_approved(workflow, pid, **kwargs)
            workflow.review(pid, decision="approve", reviewer="operator")
            workflow.materialize(pid)
            dry = upload_approved(workflow, pid, transport=Mock(side_effect=AssertionError()), **kwargs)
            self.assertEqual(1, dry["lead_count"])
            mismatch = Mock(return_value={"items": [{"organization": "wrong"}]})
            with self.assertRaises(PermissionError):
                upload_approved(workflow, pid, execute=True, transport=mismatch, **kwargs)
            transport = Mock(side_effect=[{"items": [{"organization": "org"}]}, {"id": "campaign", "organization": "org"}, {"leads_uploaded": 1}])
            receipt = upload_approved(workflow, pid, execute=True, transport=transport, **kwargs)
            self.assertEqual("uploaded", receipt["status"])
            self.assertEqual(receipt, upload_approved(workflow, pid, execute=True, transport=Mock(side_effect=AssertionError()), **kwargs))
            self.assertTrue(transport.call_args.args[1]["skip_if_in_campaign"])

    @patch.dict("os.environ", {"INSTANTLY_API_KEY": "test"})
    def test_uncertain_upload_never_automatically_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            workflow, pid = self.setup_export(directory)
            workflow.review(pid, decision="approve", reviewer="operator")
            workflow.materialize(pid)
            transport = Mock(side_effect=[{"items": [{"organization": "org"}]}, {"id": "c", "organization": "org"}, TimeoutError()])
            with self.assertRaises(TimeoutError):
                upload_approved(workflow, pid, campaign_id="c", expected_org="org", execute=True, transport=transport)
            with self.assertRaisesRegex(RuntimeError, "uncertain"):
                upload_approved(workflow, pid, campaign_id="c", expected_org="org", execute=True, transport=Mock(side_effect=AssertionError()))
