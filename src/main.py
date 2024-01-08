from migration_utils import fetch_auth0_users, process_users, fetch_auth0_roles, process_roles, fetch_auth0_organizations, process_auth0_organizations
import sys
import argparse


def main():
    """
    Main function to process Auth0 users, roles, permissions, and organizations, creating and mapping them together within your Descope project.
    """
    parser = argparse.ArgumentParser(description='This is a program to assist you in the migration of your users, roles, permissions, and organizations to Descope.')
    parser.add_argument('--dry-run', action='store_true', help='Enable dry run mode')
    args = parser.parse_args()
    dry_run = False

    if args.dry_run:
        dry_run=True

    # Fetch and Create Users
    auth0_users = fetch_auth0_users()
    failed_users, successful_migrated_users, merged_users, disabled_users_mismatch = process_users(auth0_users, dry_run)

    # Fetch, create, and associate users with roles and permissions
    auth0_roles = fetch_auth0_roles()
    failed_roles, successful_migrated_roles, failed_permissions, successful_migrated_permissions, roles_and_users, failed_roles_and_users = process_roles(auth0_roles, dry_run)

    # Fetch, create, and associate users with Organizations
    auth0_organizations = fetch_auth0_organizations()
    successful_tenant_creation, failed_tenant_creation, failed_users_added_tenants, tenant_users = process_auth0_organizations(auth0_organizations, dry_run)
    if dry_run == False:
        print("=================== User Migration =============================")
        print(f"Auth0 Users found via API {len(auth0_users)}")
        print(f"Successfully migrated {successful_migrated_users} users")
        print(f"Successfully merged {merged_users} users")
        if len(disabled_users_mismatch) !=0:
            print(f"Users migrated, but disabled due to one of the merged accounts being disabled {len(disabled_users_mismatch)}")
            print(f"Users disabled due to one of the merged accounts being disabled {disabled_users_mismatch}")
        if len(failed_users) !=0:
            print(f"Failed to migrate {len(failed_users)}")
            print(f"Users which failed to migrate:")
            for failed_user in failed_users:
                print(failed_user)
        print(f"Created users within Descope {successful_migrated_users - merged_users}")

        print("=================== Role Migration =============================")
        print(f"Auth0 Roles found via API {len(auth0_roles)}")
        print(f"Successfully migrated {successful_migrated_roles} roles")
        if len(failed_roles) !=0:
            print(f"Failed to migrate {len(failed_roles)}")
            print(f"Roles which failed to migrate:")
            for failed_role in failed_roles:
                print(failed_role)
        print(f"Created roles within Descope {successful_migrated_roles}")

        print("=================== Permission Migration =======================")
        print(f"Auth0 Permissions found via API {len(failed_permissions)+successful_migrated_permissions}")
        print(f"Successfully migrated {successful_migrated_permissions} permissions")
        if len(failed_permissions) !=0:
            print(f"Failed to migrate {len(failed_permissions)}")
            print(f"Permissions which failed to migrate:")
            for failed_permission in failed_permissions:
                print(failed_permission)
        print(f"Created permissions within Descope {successful_migrated_permissions}")

        print("=================== User/Role Mapping ==========================")
        print(f"Successfully role and user mapping")
        for success_role_user in roles_and_users:
            print(success_role_user)
        if len(failed_roles_and_users) !=0:
            print(f"Failed role and user mapping")
            for failed_role_user in failed_roles_and_users:
                print(failed_role_user)

        print("=================== Tenant Migration ===========================")
        print(f"Auth0 Tenants found via API {len(auth0_organizations)}")
        print(f"Successfully migrated {successful_tenant_creation} tenants")
        if len(failed_tenant_creation) !=0:
            print(f"Failed to migrate {len(failed_tenant_creation)}")
            print(f"Tenants which failed to migrate:")
            for failed_tenant in failed_tenant_creation:
                print(failed_tenant)

        print("=================== User/Tenant Mapping ========================")
        print(f"Successfully tenant and user mapping")
        for tenant_user in tenant_users:
            print(tenant_user)
        if len(failed_users_added_tenants) !=0:
            print(f"Failed tenant and user mapping")
            for failed_users_added_tenant in failed_users_added_tenants:
                print(failed_users_added_tenant)

if __name__ == "__main__":
    main()
