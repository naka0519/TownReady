#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import unittest
from pathlib import Path


class KPIIngestorTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault('GCP_PROJECT', 'test-project')
        os.environ.setdefault('REGION', 'asia-northeast1')
        os.environ.setdefault('FIRESTORE_DB', 'test-db')

    def tearDown(self) -> None:
        for key in ['GCP_PROJECT', 'REGION', 'FIRESTORE_DB']:
            os.environ.pop(key, None)

    def test_ingest_skips_when_clients_unavailable(self):
        try:
            from GCP_AI_Agent_hackathon.services.kpi_ingest import KPIIngestor  # type: ignore
        except Exception:
            import sys
            sys.path.append(str(Path(__file__).resolve().parents[1]))
            from services.kpi_ingest import KPIIngestor  # type: ignore

        ingestor = KPIIngestor()
        result = ingestor.ingest({"metric": "attendance", "value": 0.82})
        fs_status = result.get('firestore', '')
        bq_status = result.get('bigquery', '')
        self.assertTrue(fs_status.startswith(('skipped', 'error')))
        self.assertTrue(bq_status.startswith(('skipped', 'error')))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
