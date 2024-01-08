import unittest
from unittest.mock import patch, Mock
from src.migration_utils import fetch_auth0_users


class TestMigration(unittest.TestCase):
    @patch("src.migration_utils.requests.get")
    def test_fetch_auth0_users_success(self, mock_get):
        # Mock a successful API response
        mock_get.return_value = Mock(status_code=200)
        mock_get.return_value.json.return_value = [{"id": "user1"}, {"id": "user2"}]

        # Call the function
        users = fetch_auth0_users()

        # Assert the results
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0]["id"], "user1")
        self.assertEqual(users[1]["id"], "user2")

    @patch("src.migration_utils.requests.get")
    def test_fetch_auth0_users_failure(self, mock_get):
        mock_get.return_value = Mock(status_code=500)
        users = fetch_auth0_users()
        self.assertEqual(len(users), 0)


if __name__ == "__main__":
    unittest.main()
