import os
import sys
import requests
from dotenv import load_dotenv
import logging
import time
from datetime import datetime

from descope import (
    AuthException,
    DescopeClient,
    UserPassword,
    UserPasswordFirebase,
    UserObj,
)

import firebase_admin
from firebase_admin import credentials
from firebase_admin import auth
from firebase_admin import db
from firebase_admin import firestore

log_directory = "logs"
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# datetime object containing current date and time
now = datetime.now()

dt_string = now.strftime("%d_%m_%Y_%H:%M:%S")
logging_file_name = os.path.join(log_directory, f"migration_log_{dt_string}.log")
logging.basicConfig(
    filename=logging_file_name,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

"""Load and read environment variables from .env file"""
load_dotenv()
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")
DESCOPE_PROJECT_ID = os.getenv("DESCOPE_PROJECT_ID")
DESCOPE_MANAGEMENT_KEY = os.getenv("DESCOPE_MANAGEMENT_KEY")

try:
    descope_client = DescopeClient(
        project_id=DESCOPE_PROJECT_ID, management_key=DESCOPE_MANAGEMENT_KEY
    )
except AuthException as error:
    logging.error(f"Failed to initialize Descope Client: {error}")
    sys.exit()

cred = credentials.Certificate(
    os.getcwd() + "/creds/test-62789-firebase-adminsdk-ulw0l-6028923de2.json"
)

if FIREBASE_DB_URL:
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
else:
    firebase_admin.initialize_app(cred)

attribute_source = None


def api_request_with_retry(action, url, headers, data=None, max_retries=4, timeout=10):
    """
    Handles API requests with additional retry on timeout and rate limit.

    Args:
    - action (string): 'get' or 'post'
    - url (string): The URL of the path for the api request
    - headers (dict): Headers to be sent with the request
    - data (json): Optional and used only for post, but the payload to post
    - max_retries (int): The max number of retries
    - timeout (int): The timeout for the request in seconds
    Returns:
    - API Response
    - Or None
    """
    retries = 0
    while retries < max_retries:
        try:
            if action == "get":
                response = requests.get(url, headers=headers, timeout=timeout)
            else:
                response = requests.post(
                    url, headers=headers, data=data, timeout=timeout
                )

            if (
                response.status_code != 429
            ):  # Not a rate limit error, proceed with response
                return response

            # If rate limit error, prepare for retry
            retries += 1
            wait_time = 5**retries
            logging.info(f"Rate limit reached. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

        except requests.exceptions.ReadTimeout as e:
            # Handle read timeout exception
            logging.warning(f"Read timed out. (read timeout={timeout}): {e}")
            retries += 1
            wait_time = 5**retries
            logging.info(f"Retrying attempt {retries}/{max_retries}...")
            time.sleep(
                wait_time
            )  # Wait for 5 seconds before retrying or use a backoff strategy

        except requests.exceptions.RequestException as e:
            # Handle other request exceptions
            logging.error(f"A request exception occurred: {e}")
            break  # In case of other exceptions, you may want to break the loop

    logging.error("Max retries reached. Giving up.")
    return None


### Begin Firebase Actions


def fetch_firebase_users():
    """
    Fetch and parse Firebase users.

    Returns:
    - all_users (Dict): A list of parsed Firebase users if successful, empty list otherwise.
    """
    all_users = []
    page_token = None

    while True:
        try:
            page = auth.list_users(page_token=page_token)
            for user in page.users:
                user_dict = user.__dict__

                # Fetch custom attributes from Firebase Database
                # if FIREBASE_DB_URL:
                #     custom_attributes = db.reference(
                #         f"path/to/user/{user.uid}/customAttributes"
                #     ).get()
                #     user_dict["customAttributes"] = custom_attributes or {}
                all_users.append(user_dict)

            if not page.has_next_page:
                break

            page_token = page.next_page_token

        except firebase_admin.exceptions.FirebaseError as error:
            logging.error(f"Error fetching Firebase users. Error: {error}")
            break

    return all_users


def fetch_custom_attributes(user_id):
    """
    Fetch custom attributes for a given user ID from either Realtime Database or Firestore

    Args:
    - user_id (str): The user's ID in Firebase.

    Returns:
    - dict: A dictionary of custom attributes.
    """
    if attribute_source == "firestore":
        firestore_db = firestore.client()
        doc_ref = firestore_db.collection("users").document(user_id)
        return doc_ref.get() or {}
    elif attribute_source == "realtime":
        ref = db.reference(f"users/{user_id}")
        return ref.get() or {}
    return {}


def set_custom_attribute_source(source):
    global attribute_source
    attribute_source = source


### End Firebase Actions

### Begin Descope Actions


def build_user_object_with_passwords(extracted_user, hash_params):
    userPasswordToCreate = UserPassword(
        hashed=UserPasswordFirebase(
            hash=extracted_user["password_hash"],
            salt=extracted_user["salt"],
            salt_separator=hash_params["salt_separator"],
            signer_key=hash_params["signer_key"],
            memory=hash_params["mem_cost"],
            rounds=hash_params["rounds"],
        )
    )

    user_object = [
        UserObj(
            login_id=extracted_user["email"],
            email=extracted_user["email"],
            display_name=extracted_user["display_name"],
            given_name=extracted_user["given_name"],
            family_name=extracted_user["family_name"],
            phone=extracted_user["phone"],
            picture=extracted_user["picture"],
            verified_email=extracted_user["verified_email"],
            verified_phone=extracted_user["verified_phone"],
            password=userPasswordToCreate,
            custom_attributes=extracted_user["custom_attributes"],
        )
    ]
    return user_object


def invite_batch(user_object, login_id, is_disabled):
    # Create the user
    try:
        resp = descope_client.mgmt.user.invite_batch(
            users=user_object,
            invite_url="https://localhost",
            send_mail=False,
            send_sms=False,
        )

        # Update user status in Descope based on Firebase status
        if is_disabled:
            descope_client.mgmt.user.deactivate(login_id=login_id)
        else:
            descope_client.mgmt.user.activate(login_id=login_id)

        return True
    except AuthException as error:
        logging.error("Unable to create user with password.")
        logging.error(f"Error:, {error.error_message}")
        return False


def create_descope_user(user, hash_params):
    """
    Create a Descope user based on matched Firebase user data using Descope Python SDK.

    Args:
    - user (dict): A dictionary containing user details fetched from Firebase Admin SDK.
    """
    try:
        # Extracting user data from the nested '_data' structure
        user_data = user.get("_data", {})

        custom_attributes = {"freshlyMigrated": True}
        is_disabled = user_data.get("disabled", False)
        login_id = user_data.get("email")

        password_hash = user_data.get("passwordHash") or ""
        salt = user_data.get("salt") or ""

        # Default Firebase user attributes
        extracted_user = {
            "login_id": user_data.get("email"),
            "email": user_data.get("email"),
            "phone": user_data.get("phoneNumber"),
            "display_name": user_data.get("displayName"),
            "given_name": user_data.get("givenName"),
            "family_name": user_data.get("familyName"),
            "picture": user_data.get("photoUrl"),
            "verified_email": user_data.get("emailVerified", False),
            "verified_phone": user_data.get("phoneVerified", False)
            if user_data.get("phoneNumber")
            else False,
            "custom_attributes": custom_attributes,
            "is_disabled": is_disabled,
            "password_hash": password_hash,
            "salt": salt,
        }

        # Fetch custom attributes from Firebase Realtime Database, if URL is provided
        if FIREBASE_DB_URL:
            user_id = user_data.get("localId")
            if user_id:
                additional_attributes = fetch_custom_attributes(
                    user_data.get("localId")
                )
                custom_attributes.update(additional_attributes)

        # Create the Descope user
        user_object = build_user_object_with_passwords(extracted_user, hash_params)
        success = invite_batch(user_object, login_id, is_disabled)

        return success, False, False, login_id

    except AuthException as error:
        logging.error(f"Unable to create user. {user}")
        logging.error(f"Error: {error.error_message}")
        return (
            False,
            False,
            False,
            user.get("user_id") + " Reason: " + error.error_message,
        )


### End Descope Actions:

### Begin Process Functions


def process_users(api_response_users, hash_params, dry_run):
    """
    Process the list of users from Firebase by mapping and creating them in Descope.

    Args:
    - api_response_users (list): A list of users fetched from Firebase Admin SDK.
    """
    failed_users = []
    successful_migrated_users = 0
    merged_users = 0
    disabled_users_mismatch = []
    if dry_run:
        print(f"Would migrate {len(api_response_users)} users from Firebase to Descope")
    else:
        print(
            f"Starting migration of {len(api_response_users)} users found via Firebase Admin SDK"
        )
        for user in api_response_users:
            success, merged, disabled_mismatch, user_id_error = create_descope_user(
                user, hash_params
            )
            if success:
                successful_migrated_users += 1
                if merged:
                    merged_users += 1
                    if success and disabled_mismatch:
                        disabled_users_mismatch.append(user_id_error)
            else:
                failed_users.append(user_id_error)
            if successful_migrated_users % 10 == 0:
                print(f"Still working, migrated {successful_migrated_users} users.")
    return (
        failed_users,
        successful_migrated_users,
        merged_users,
        disabled_users_mismatch,
    )


### End Process Functions
