import os
import sys
from migration_utils import (
    fetch_firebase_users,
    process_users,
    set_custom_attribute_source,
)
import argparse


def main():
    """
    Main function to process Firebase users, roles, permissions, and organizations, creating and mapping them together within your Descope project.
    """

    dry_run = False

    parser = argparse.ArgumentParser(
        description="This is a program to assist you in the migration of your users, roles, permissions, and organizations to Descope."
    )
    parser.add_argument("--dry-run", action="store_true", help="Enable dry run mode")

    args = parser.parse_args()

    hash_params_file_path = "creds/password-hash.txt"

    # Check if the password-hash.txt file exists
    if not os.path.isfile(hash_params_file_path):
        print(
            f"Required file '{hash_params_file_path}' not found. Please ensure it is placed in the correct location."
        )
        sys.exit(1)

    # If the file exists, proceed to parse the hash parameters
    hash_params = parse_hash_params(hash_params_file_path)

    # Ask the user if they want to import custom attributes
    import_custom_attributes = (
        input("Do you want to import custom user attributes? (y/n): ").strip().lower()
    )
    attribute_source = None

    if import_custom_attributes == "y":
        while attribute_source not in ["firestore", "realtime"]:
            attribute_source = (
                input("Enter the source of custom attributes (firestore or realtime): ")
                .strip()
                .lower()
            )
        set_custom_attribute_source(attribute_source)

    if args.dry_run:
        dry_run = True

    # Fetch and Create Users
    firebase_users = fetch_firebase_users()
    print(firebase_users)
    (
        failed_users,
        successful_migrated_users,
        merged_users,
        disabled_users_mismatch,
    ) = process_users(firebase_users, hash_params, dry_run)

    if dry_run == False:
        print("=================== User Migration =============================")
        print(f"Firebase Users found via Admin SDK {len(firebase_users)}")
        print(f"Successfully migrated {successful_migrated_users} users")
        print(f"Successfully merged {merged_users} users")
        if len(disabled_users_mismatch) != 0:
            print(
                f"Users migrated, but disabled due to one of the merged accounts being disabled {len(disabled_users_mismatch)}"
            )
            print(
                f"Users disabled due to one of the merged accounts being disabled {disabled_users_mismatch}"
            )
        if len(failed_users) != 0:
            print(f"Failed to migrate {len(failed_users)}")
            print(f"Users which failed to migrate:")
            for failed_user in failed_users:
                print(failed_user)
        print(
            f"Created users within Descope {successful_migrated_users - merged_users}"
        )


def parse_hash_params(hash_params_file_path):
    """
    Parse the hash parameters from the given password-hash.txt file.
    """
    hash_params = {}
    try:
        with open(hash_params_file_path, "r") as file:
            for line in file:
                line = line.strip()
                if line.startswith("algorithm:"):
                    hash_params["algorithm"] = line.split(":", 1)[1].strip()
                elif line.startswith("base64_signer_key:"):
                    hash_params["signer_key"] = line.split(":", 1)[1].strip()
                elif line.startswith("base64_salt_separator:"):
                    hash_params["salt_separator"] = line.split(":", 1)[1].strip()
                elif line.startswith("rounds:"):
                    # Added strip(',') to remove any trailing commas
                    hash_params["rounds"] = int(
                        line.split(":", 1)[1].strip().strip(",")
                    )
                elif line.startswith("mem_cost:"):
                    # Added strip(',') to remove any trailing commas
                    hash_params["mem_cost"] = int(
                        line.split(":", 1)[1].strip().strip(",")
                    )
    except FileNotFoundError:
        print(f"File not found: {hash_params_file_path}")
        exit(1)
    except ValueError as e:
        print(f"Error parsing hash parameters: {e}")
        exit(1)
    return hash_params


if __name__ == "__main__":
    main()
