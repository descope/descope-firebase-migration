import json
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
    AssociatedTenant,
    RoleMapping,
    AttributeMapping,
)

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
AUTH0_TOKEN = os.getenv("AUTH0_TOKEN")
AUTH0_TENANT_ID = os.getenv("AUTH0_TENANT_ID")
DESCOPE_PROJECT_ID = os.getenv("DESCOPE_PROJECT_ID")
DESCOPE_MANAGEMENT_KEY = os.getenv("DESCOPE_MANAGEMENT_KEY")

try:
    descope_client = DescopeClient(
        project_id=DESCOPE_PROJECT_ID, management_key=DESCOPE_MANAGEMENT_KEY
    )
except AuthException as error:
    logging.error(f"Failed to initialize Descope Client: {error}")
    sys.exit()


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


### Begin Auth0 Actions


def fetch_auth0_users():
    """
    Fetch and parse Auth0 users from the provided endpoint.

    Returns:
    - all_users (Dict): A list of parsed Auth0 users if successful, empty list otherwise.
    """
    headers = {"Authorization": f"Bearer {AUTH0_TOKEN}"}
    page = 0
    per_page = 20
    all_users = []
    while True:
        response = api_request_with_retry(
            "get",
            f"https://{AUTH0_TENANT_ID}.us.auth0.com/api/v2/users?page={page}&per_page={per_page}",
            headers=headers,
        )
        if response.status_code != 200:
            logging.error(
                f"Error fetching Auth0 users. Status code: {response.status_code}"
            )
            return all_users
        users = response.json()
        if not users:
            break
        all_users.extend(users)
        page += 1
    return all_users


def fetch_auth0_roles():
    """
    Fetch and parse Auth0 roles from the provided endpoint.

    Returns:
    - all_roles (Dict): A list of parsed Auth0 roles if successful, empty list otherwise.
    """
    headers = {"Authorization": f"Bearer {AUTH0_TOKEN}"}
    page = 0
    per_page = 20
    all_roles = []
    while True:
        response = api_request_with_retry(
            "get",
            f"https://{AUTH0_TENANT_ID}.us.auth0.com/api/v2/roles?page={page}&per_page={per_page}",
            headers=headers,
        )
        if response.status_code != 200:
            logging.error(
                f"Error fetching Auth0 roles. Status code: {response.status_code}"
            )
            return all_roles
        roles = response.json()
        if not roles:
            break
        all_roles.extend(roles)
        page += 1
    return all_roles


def get_users_in_role(role):
    """
    Get and parse Auth0 users associated with the provided role.

    Returns:
    - role (string): The role ID to get the associated members
    """
    headers = {"Authorization": f"Bearer {AUTH0_TOKEN}"}
    page = 0
    per_page = 20
    all_users = []

    while True:
        response = api_request_with_retry(
            "get",
            f"https://{AUTH0_TENANT_ID}.us.auth0.com/api/v2/roles/{role}/users?page={page}&per_page={per_page}",
            headers=headers,
        )
        if response.status_code != 200:
            logging.error(
                f"Error fetching Auth0 users in roles. Status code: {response.status_code}"
            )
            return all_users
        users = response.json()
        if not users:
            break
        all_users.extend(users)
        page += 1
    return all_users


def get_permissions_for_role(role):
    """
    Get and parse Auth0 permissions for a role

    Args:
    - role (string): The id of the role to query for permissions
    Returns:
    - all_permissions (string): Dictionary of all permissions associated to the role.
    """
    headers = {"Authorization": f"Bearer {AUTH0_TOKEN}"}
    page = 0
    per_page = 20
    all_permissions = []

    while True:
        response = api_request_with_retry(
            "get",
            f"https://{AUTH0_TENANT_ID}.us.auth0.com/api/v2/roles/{role}/permissions?per_page={per_page}&page={page}",
            headers=headers,
        )
        if response.status_code != 200:
            logging.error(
                f"Error fetching Auth0 permissions in roles. Status code: {response.status_code}"
            )
            return all_permissions
        permissions = response.json()
        if not permissions:
            break
        all_permissions.extend(permissions)
        page += 1
    return all_permissions


def fetch_auth0_organizations():
    """
    Fetch and parse Auth0 organization members from the provided endpoint.

    Returns:
    - all_organizations (string): Dictionary of all organizations within the Auth0 tenant.
    """
    headers = {"Authorization": f"Bearer {AUTH0_TOKEN}"}
    page = 0
    per_page = 20
    all_organizations = []

    while True:
        response = api_request_with_retry(
            "get",
            f"https://{AUTH0_TENANT_ID}.us.auth0.com/api/v2/organizations?per_page={per_page}&page={page}",
            headers=headers,
        )
        if response.status_code != 200:
            logging.error(
                f"Error fetching Auth0 organizations. Status code: {response.status_code}"
            )
            return all_organizations
        organizations = response.json()
        if not organizations:
            break
        all_organizations.extend(organizations)
        page += 1
    return all_organizations


def fetch_auth0_organization_members(organization):
    """
    Fetch and parse Auth0 organization members from the provided endpoint.

    Args:
    - organization (string): Auth0 organization ID to fetch the members
    Returns:
    - all_members (dict): Dictionary of all members within the organization.
    """
    headers = {"Authorization": f"Bearer {AUTH0_TOKEN}"}
    page = 0
    per_page = 20
    all_members = []

    while True:
        response = api_request_with_retry(
            "get",
            f"https://{AUTH0_TENANT_ID}.us.auth0.com/api/v2/organizations/{organization}/members?per_page={per_page}&page={page}",
            headers=headers,
        )
        if response.status_code != 200:
            logging.error(
                f"Error fetching Auth0 organization members. Status code: {response.status_code}"
            )
            return all_members
        members = response.json()
        if not members:
            break
        all_members.extend(members)
        page += 1
    return all_members


### End Auth0 Actions

### Begin Descope Actions


def create_descope_role_and_permissions(role, permissions):
    """
    Create a Descope role and its associated permissions using the Descope Python SDK.

    Args:
    - role (dict): A dictionary containing role details from Auth0.
    - permissions (dict): A dictionary containing permissions details from Auth0.
    """
    permissionNames = []
    success_permissions = 0
    failed_permissions = []
    for permission in permissions:
        name = permission["permission_name"]
        description = permission.get("description", "")
        try:
            descope_client.mgmt.permission.create(name=name, description=description)
            permissionNames.append(name)
            success_permissions += 1
        except AuthException as error:
            failed_permissions.append(f"{name}, Reason: {error.error_message}")
            logging.error(f"Unable to create permission: {name}.")
            logging.error(f"Status Code: {error.status_code}")
            logging.error(f"Error: {error.error_message}")

    role_name = role["name"]
    role_description = role.get("description", "")
    try:
        descope_client.mgmt.role.create(
            name=role_name,
            description=role_description,
            permission_names=permissionNames,
        )
        return True, success_permissions, failed_permissions, ""
    except AuthException as error:
        logging.error(f"Unable to create role: {role_name}.")
        logging.error(f"Status Code: {error.status_code}")
        logging.error(f"Error: {error.error_message}")
        return (
            False,
            success_permissions,
            failed_permissions,
            f"{role_name}  Reason: {error.error_message}",
        )


def create_descope_user(user):
    """
    Create a Descope user based on matched Auth0 user data using Descope Python SDK.

    Args:
    - user (dict): A dictionary containing user details fetched from Auth0 API.
    """
    try:
        login_ids = []
        connections = []
        for identity in user.get("identities", []):
            if "Username" in identity["connection"]:
                login_ids.append(user.get("email"))
                connections.append(identity["connection"])
            elif "sms" in identity["connection"]:
                login_ids.append(user.get("phone_number"))
                connections.append(identity["connection"])
            elif "-" in identity["connection"]:
                login_ids.append(
                    identity["connection"].split("-")[0] + "-" + identity["user_id"]
                )
                connections.append(identity["connection"])
            else:
                login_ids.append(identity["connection"] + "-" + identity["user_id"])
                connections.append(identity["connection"])

        emails = [user.get("email")]

        users = []
        try:
            resp = descope_client.mgmt.user.search_all(emails=emails)
            users = resp["users"]
        except AuthException as error:
            pass

        if len(users) == 0:
            login_id = login_ids[0]
            email = user.get("email")
            phone = (
                user.get("phone_number") if identity.get("provider") == "sms" else None
            )
            display_name = user.get("name")
            given_name = user.get("given_name")
            family_name = user.get("family_name")
            picture = user.get("picture")
            verified_email = user.get("email_verified", False)
            verified_phone = user.get("phone_verified", False) if phone else False
            custom_attributes = {
                "connection": ",".join(map(str, connections)),
                "freshlyMigrated": True,
            }
            additional_login_ids = login_ids[1 : len(login_ids)]

            # Create the user
            resp = descope_client.mgmt.user.create(
                login_id=login_id,
                email=email,
                display_name=display_name,
                given_name=given_name,
                family_name=family_name,
                phone=phone,
                picture=picture,
                custom_attributes=custom_attributes,
                verified_email=verified_email,
                verified_phone=verified_phone,
                additional_login_ids=additional_login_ids,
            )

            # Update user status if necessary
            status = "disabled" if user.get("blocked", False) else "enabled"
            if status == "disabled":
                try:
                    resp = descope_client.mgmt.user.deactivate(login_id=login_id)
                except AuthException as error:
                    logging.error(f"Unable to deactivate user.")
                    logging.error(f"Status Code: {error.status_code}")
                    logging.error(f"Error: {error.error_message}")
            elif status == "enabled":
                try:
                    resp = descope_client.mgmt.user.activate(login_id=login_id)
                except AuthException as error:
                    logging.error(f"Unable to activate user.")
                    logging.error(f"Status Code: {error.status_code}")
                    logging.error(f"Error: {error.error_message}")
            return True, False, False, ""
        else:
            user_to_update = users[0]
            if user.get("picture"):
                picture = user.get("picture")
            else:
                picture = user_to_update["picture"]

            if user.get("given_name"):
                given_name = user.get("given_name")
            else:
                given_name = user_to_update["givenName"]

            if user.get("family_name"):
                family_name = user.get("family_name")
            else:
                family_name = user_to_update["familyName"]

            custom_attributes = user_to_update["customAttributes"]
            additional_connections = ",".join(map(str, connections))
            custom_attributes["connection"] += "," + additional_connections

            try:
                login_ids.pop(login_ids.index(user_to_update["loginIds"][0]))
            except Exception as e:
                pass
            login_id = user_to_update["loginIds"][0]
            resp = descope_client.mgmt.user.update(
                login_id=login_id,
                email=user_to_update["email"],
                display_name=user_to_update["name"],
                given_name=given_name,
                family_name=family_name,
                phone=user_to_update["phone"],
                picture=picture,
                custom_attributes=custom_attributes,
                verified_email=user_to_update["verifiedEmail"],
                verified_phone=user_to_update["verifiedPhone"],
                additional_login_ids=login_ids,
            )
            # TODO: Handle user statuses? Yea, that's my thinking, if either are disabled, merge them, disable the merged one, print the disabled accounts that hit this scenario in the completion?
            status = "disabled" if user.get("blocked", False) else "enabled"
            if status == "disabled" or user_to_update["status"] == "disabled":
                try:
                    resp = descope_client.mgmt.user.deactivate(login_id=login_id)

                except AuthException as error:
                    logging.error(f"Unable to deactivate user.")
                    logging.error(f"Status Code: {error.status_code}")
                    logging.error(f"Error: {error.error_message}")
                return True, True, True, user.get("user_id")
            return True, True, False, ""
    except AuthException as error:
        logging.error(f"Unable to create user. {user}")
        logging.error(f"Error: {error.error_message}")
        return (
            False,
            False,
            False,
            user.get("user_id") + " Reason: " + error.error_message,
        )


def add_user_to_descope_role(user, role):
    """
    Add a Descope user based on matched Auth0 user data.

    Args:
    - user (str): Login ID of the user you wish to add to role
    - role (str): The name of the role which you want to add the user to
    """
    role_names = [role]

    try:
        resp = descope_client.mgmt.user.add_roles(login_id=user, role_names=role_names)
        logging.info("User role successfully added")
        return True, ""
    except AuthException as error:
        logging.error(
            f"Unable to add role to user.  Status code: {error.error_message}"
        )
        return False, f"{user} Reason: {error.error_message}"


def create_descope_tenant(organization):
    """
    Create a Descope create_descope_tenant based on matched Auth0 organization data.

    Args:
    - organization (dict): A dictionary containing organization details fetched from Auth0 API.
    """
    name = organization["display_name"]
    tenant_id = organization["id"]

    try:
        resp = descope_client.mgmt.tenant.create(name=name, id=tenant_id)
        return True, ""
    except AuthException as error:
        logging.error("Unable to create tenant.")
        logging.error(f"Error:, {error.error_message}")
        return False, f"Tenant {name} failed to create Reason: {error.error_message}"


def add_descope_user_to_tenant(tenant, loginId):
    """
    Map a descope user to a tenant based on Auth0 data using Descope SDK.

    Args:
    - tenant (string): The tenant ID of the tenant to associate the user.
    - loginId (string): the loginId of the user to associate to the tenant.
    """
    try:
        resp = descope_client.mgmt.user.add_tenant(login_id=loginId, tenant_id=tenant)
        return True, ""
    except AuthException as error:
        logging.error("Unable to add user to tenant.")
        logging.error(f"Error:, {error.error_message}")
        return False, error.error_message


### End Descope Actions:

### Begin Process Functions


def process_users(api_response_users, dry_run):
    """
    Process the list of users from Auth0 by mapping and creating them in Descope.

    Args:
    - api_response_users (list): A list of users fetched from Auth0 API.
    """
    failed_users = []
    successful_migrated_users = 0
    merged_users = 0
    disabled_users_mismatch = []
    if dry_run:
        print(f"Would migrate {len(api_response_users)} users from Auth0 to Descope")
    else:
        print(
            f"Starting migration of {len(api_response_users)} users found via Auth0 API"
        )
        for user in api_response_users:
            success, merged, disabled_mismatch, user_id_error = create_descope_user(
                user
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


def process_roles(auth0_roles, dry_run):
    """
    Process the Auth0 organizations - creating roles, permissions, and associating users

    Args:
    - auth0_roles (dict): Dictionary of roles fetched from Auth0
    """
    failed_roles = []
    successful_migrated_roles = 0
    total_failed_permissions = []
    successful_migrated_permissions = 0
    roles_and_users = []
    failed_roles_and_users = []
    if dry_run:
        print(f"Would migrate {len(auth0_roles)} roles from Auth0 to Descope")
        for role in auth0_roles:
            permissions = get_permissions_for_role(role["id"])
            print(
                f"Would migrate {role['name']} with {len(permissions)} associated permissions."
            )
    else:
        print(f"Starting migration of {len(auth0_roles)} roles found via Auth0 API")
        for role in auth0_roles:
            permissions = get_permissions_for_role(role["id"])
            print(
                f"Starting migration of {role['name']} with {len(permissions)} associated permissions."
            )
            (
                success,
                success_permissions,
                failed_permissions,
                error,
            ) = create_descope_role_and_permissions(role, permissions)
            if success:
                successful_migrated_roles += 1
                successful_migrated_permissions += success_permissions
            else:
                failed_roles.append(error)
                successful_migrated_permissions += success_permissions
            if len(failed_permissions) != 0:
                for item in failed_permissions:
                    total_failed_permissions.append(item)
            users = get_users_in_role(role["id"])

            users_added = 0
            for user in users:
                success, error = add_user_to_descope_role(user["email"], role["name"])
                if success:
                    users_added += 1
                else:
                    failed_roles_and_users.append(
                        f"{user['user_id']} failed to be added to {role['name']} Reason: {error}"
                    )
            roles_and_users.append(f"Mapped {users_added} user to {role['name']}")

    return (
        failed_roles,
        successful_migrated_roles,
        total_failed_permissions,
        successful_migrated_permissions,
        roles_and_users,
        failed_roles_and_users,
    )


def process_auth0_organizations(auth0_organizations, dry_run):
    """
    Process the Auth0 organizations - creating tenants and associating users

    Args:
    - auth0_organizations (dict): Dictionary of organizations fetched from Auth0
    """
    successful_tenant_creation = 0
    failed_tenant_creation = []
    failed_users_added_tenants = []
    tenant_users = []
    if dry_run:
        print(
            f"Would migrate {len(auth0_organizations)} organizations from Auth0 to Descope"
        )
        for organization in auth0_organizations:
            org_members = fetch_auth0_organization_members(organization["id"])
            print(
                f"Would migrate {organization['display_name']} with {len(org_members)} associated users."
            )
    else:
        for organization in auth0_organizations:
            success, error = create_descope_tenant(organization)
            if success:
                successful_tenant_creation += 1
            else:
                failed_tenant_creation.append(error)

            org_members = fetch_auth0_organization_members(organization["id"])
            users_added = 0
            for user in org_members:
                success, error = add_descope_user_to_tenant(
                    organization["id"], user["email"]
                )
                if success:
                    users_added += 1
                else:
                    failed_users_added_tenants.append(
                        f"User {loginId} failed to be added to tenant {organization['display_name']} Reason: {error}"
                    )
            tenant_users.append(
                f"Associated {users_added} users with tenant: {organization['display_name']} "
            )
    return (
        successful_tenant_creation,
        failed_tenant_creation,
        failed_users_added_tenants,
        tenant_users,
    )


### End Process Functions
