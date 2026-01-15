import unittest
from unittest.mock import MagicMock, patch

from chaosdb.probes.postgres.postgres_query_saturation_status import \
    probe_query_saturation_status


class TestPostgresProbe(unittest.TestCase):
    @patch("chaosdb.probes.postgres.postgres_query_saturation_status.psycopg2")
    @patch("chaosdb.probes.postgres.postgres_query_saturation_status.get_tracer")
    @patch("chaosdb.probes.postgres.postgres_query_saturation_status.get_logger")
    def test_probe_query_saturation_status_success(
        self, mock_logger, mock_tracer, mock_psycopg2
    ):
        # Mock DB connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock query results
        # 1. active_queries -> 5
        # 2. total_connections -> 10
        # 3. max_connections -> 100
        # 4. Latency loop (10 times) -> None (fetchone result doesn't matter for latency, just timing)
        mock_cursor.fetchone.side_effect = [
            [5],  # active_queries
            [10],  # total_connections
            [100],  # max_connections
            [1],
            [1],
            [1],
            [1],
            [1],
            [1],
            [1],
            [1],
            [1],
            [1],  # latency loop fetchone
        ]

        # Run probe
        result = probe_query_saturation_status(
            host="localhost",
            port=5432,
            database="testdb",
            user="user",
            password="password",
        )

        # Verify results
        self.assertTrue(result["success"])
        self.assertEqual(result["active_queries"], 5)
        self.assertEqual(result["total_connections"], 10)
        self.assertEqual(result["max_connections"], 100)
        self.assertEqual(result["connection_utilization_percent"], 10.0)
        self.assertIn("latency_median", result)
        self.assertIn("latency_p95", result)

        # Verify calls
        mock_psycopg2.connect.assert_called_once()
        self.assertEqual(
            mock_cursor.execute.call_count, 13
        )  # 3 status queries + 10 latency queries

    @patch("chaosdb.probes.postgres.postgres_query_saturation_status.psycopg2")
    @patch("chaosdb.probes.postgres.postgres_query_saturation_status.get_tracer")
    @patch("chaosdb.probes.postgres.postgres_query_saturation_status.get_logger")
    def test_probe_query_saturation_status_failure(
        self, mock_logger, mock_tracer, mock_psycopg2
    ):
        # Mock connection failure
        mock_psycopg2.connect.side_effect = Exception("Connection failed")

        # Run probe
        result = probe_query_saturation_status(
            host="localhost",
            port=5432,
            database="testdb",
            user="user",
            password="password",
        )

        # Verify failure
        self.assertFalse(result["success"])
        self.assertIn("Connection failed", result["error"])


if __name__ == "__main__":
    unittest.main()
