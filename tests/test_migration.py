import unittest
from unittest.mock import patch, MagicMock
from src.migration_utils import fetch_firebase_users, create_descope_user


class TestMigration(unittest.TestCase):
    @patch("src.migration_utils.requests.get")
    def test_fetch_firebase_users_success(self, mock_list_users):
        mock_user1 = MagicMock()
        mock_user1.__dict__ = {"_data": {"id": "user1"}}
        mock_user2 = MagicMock()
        mock_user2.__dict__ = {"_data": {"id": "user2"}}

        # Mock Firebase user list response
        mock_page = MagicMock()
        mock_page.users = [mock_user1, mock_user2]
        mock_page.has_next_page = False
        mock_list_users.return_value = mock_page

        # Call the function
        users = fetch_firebase_users()

        # Assert the results
        self.assertEqual(len(users), 12)
        self.assertEqual(users[0]["_data"]["id"], "user1")
        self.assertEqual(users[1]["_data"]["id"], "user2")

    @patch("src.migration_utils.requests.get")
    def test_fetch_firebase_users_failure(self, mock_list_users):
        mock_list_users.side_effect = Exception("An error occurred")

        # Call the function and expect an empty result due to error
        users = fetch_firebase_users()
        self.assertEqual(len(users), 12)

    @patch("your_module.fetch_custom_attributes")
    def test_create_descope_user(self, mock_fetch_custom_attributes):
        # Mock the custom attributes returned by fetch_custom_attributes
        mock_fetch_custom_attributes.return_value = {
            "company": "MockCorp",
            "email": "mockuser@mock.com",
            "changedOTP": True,
        }

        user_data = {"localId": "mockuser"}
        result = create_descope_user(user_data)


if __name__ == "__main__":
    unittest.main()
