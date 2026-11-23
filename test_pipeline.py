import json
import unittest
from datetime import date
from unittest import mock

import requests

import pipeline

DAY = date(2026, 11, 19)
BODY = {"hourly": {"time": ["2026-11-19T00:00"], "temperature_2m": [1.0]}}


def make_response(status, body=None):
    """Build a real requests.Response without touching the network."""
    response = requests.Response()
    response.status_code = status
    response.url = "https://example.test"
    response._content = json.dumps(body or {}).encode()
    return response


@mock.patch("time.sleep")  # never actually wait during tests
class TestExtractRetries(unittest.TestCase):

    @mock.patch("requests.get", return_value=make_response(503))
    def test_503_every_time_gives_up_after_max_attempts(self, mock_get, mock_sleep):
        with self.assertRaises(pipeline.ExtractError):
            pipeline.extract(59.91, 10.75, DAY, DAY)
        self.assertEqual(mock_get.call_count, pipeline.MAX_ATTEMPTS)

    @mock.patch("requests.get")
    def test_fails_twice_then_succeeds(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            make_response(503),
            requests.Timeout("too slow"),   # exceptions in the list are raised
            make_response(200, BODY),
        ]
        with self.assertLogs("pipeline", level="WARNING") as logs:
            result = pipeline.extract(59.91, 10.75, DAY, DAY)

        self.assertEqual(result, BODY)
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(len(logs.records), 2)  # one warning per failed attempt

    @mock.patch("requests.get", return_value=make_response(404))
    def test_404_is_not_retried(self, mock_get, mock_sleep):
        with self.assertRaises(pipeline.ExtractError):
            pipeline.extract(59.91, 10.75, DAY, DAY)
        self.assertEqual(mock_get.call_count, 1)


if __name__ == "__main__":
    unittest.main()