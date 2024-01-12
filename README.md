<img width="1400" alt="Screenshot 2024-01-11 at 10 37 23 PM" src="https://github.com/descope/descope-firebase-migration/assets/32936811/2b5e6106-198d-4be5-b90d-a997fdce8be5">

# Descope Firebase User Migration Tool

This repository includes a Python utility for migrating your Firebase users to Descope.

## Setup 💿

1. Clone the Repo:

```
git clone git@github.com:descope/descope-firebase-migration.git
```

2. Create a Virtual Environment

```
python3 -m venv venv
source venv/bin/activate
```

3. Install the Necessary Python libraries

```
pip3 install -r requirements.txt
```

4. Download Firebase Credential Private Key

You'll need to download your Firebase Credential and put it in the `/creds` folder in order to give the Firebase Admin SDK access to your user table.

a. First, you'll need to open Settings > [Service Accounts](https://console.firebase.google.com/project/_/settings/serviceaccounts/adminsdk), in the Firebase Console.

b. Click `Generate New Private Key`, then confirm by clicking `Generate Key`.

<img width="931" alt="Monosnap test - Project settings - Firebase console 2024-01-11 22-34-33" src="https://github.com/descope/descope-firebase-migration/assets/32936811/e4dd6cdf-2b8d-47e6-90a4-25be429b6ad8">

c. Securely store the JSON file containing the key, in the `/creds` folder, in the root of this repository.

> **Note**: You can read more about the setup process on the Firebase [docs page](https://firebase.google.com/docs/admin/setup).

5. Setup Your Environment Variables

You can change the name of the `.env.example` file to `.env` to use as a template.

```
DESCOPE_PROJECT_ID=<Descope Project ID>
DESCOPE_MANAGEMENT_KEY=<Descope Management Key>
FIREBASE_DB_URL=<Firebase Realtime DB URL> (Optional)
```

a. To get your Descope Project ID, go [here](https://app.descope.com/settings/project), then copy the token to your
`.env` file.

b. To create a Descope Management Key, go [here](https://app.descope.com/settings/company/managementkeys), then copy
the token to your `.env` file.

c. The `FIREBASE_DB_URL` is the endpoint URL of your Firebase Realtime Database. This URL is required for the application to interact with your Firebase Database, enabling it to read and write data.

To find your Firebase Realtime Database URL:

1. Go to the [Firebase Console](https://console.firebase.google.com/).
2. Select your project.
3. Navigate to `Realtime Database` in the `Develop` section.
4. Your database URL will be displayed at the top of the Database screen. It typically follows the format `https://<your-project-id>.firebaseio.com/`.

<img width="1356" alt="Monosnap test - Realtime Database - Firebase console 2024-01-11 22-35-59" src="https://github.com/descope/descope-firebase-migration/assets/32936811/ce6b66a0-04b5-4824-829a-4e10e2754fe9">

> **Note**: Ensure that your Firebase Database rules allow the necessary read/write operations for your application.

6. The tool depends on a few custom user attributes you need to create within Descope to assist you with the migration. The below outlines the machine names of the attributes to create within the [user's custom attributes](https://app.descope.com/users/attributes) section of the Descope console.

- `freshlyMigrated` (type: Boolean): This custom attribute will be set to true during the migration. This allows for you
  to later check this via a conditional during Descope flow execution.

If you're going to migrate any other custom attributes, via the Realtime Database, you'll need to create those as well in the Descope Console before you run this script.

Once you've set all of that up, you're ready to run the script.

## Running the Migration Script 🚀

### Dry run the migration script

You can dry run the migration script which will allow you to see the number of users, tenants, roles, etc which will be migrated
from Firebase to Descope.

```
python3 src/main.py --dry-run
```

The output would appear similar to the following:

```
Would migrate 112 users from Firebase to Descope
```

### Live run the migration Script

To migrate your Firebase users, simply run the following command:

```
python3 src/main.py
```

The output will include the responses of the created users, organizations, roles, and permissions as well as the mapping between the various objects within Descope:

The output will include the responses of the created users, organizations, roles, and permissions as well as the mapping between the various objects within Descope. A log file will also be generated in the format of `migration_log_%d_%m_%Y_%H:%M:%S.log`. Any items which failed to be migrated will also be listed with the error that occurred during the migration.

```
Starting migration of 112 users found via Firebase Admin SDK
Still working, migrated 10 users.
...
Still working, migrated 110 users.
=================== User Migration =============================
Firebase Users found via Admin SDK 112
Successfully migrated 112 users
Successfully merged 0 users
Created users within Descope 112
```

### Post Migration Verification

Once the migration tool has ran successfully, you can check the [users](https://app.descope.com/users) for the migrated users from Firebase. You can verify the created users based on the output of the migration tool.

## Testing 🧪

Unit testing can be performed by running the following command:

```
python3 -m unittest tests.test_migration
```

## Issue Reporting ⚠️

For any issues or suggestions, feel free to open an issue in the GitHub repository.

## License 📜

This project is licensed under the MIT License - see the LICENSE file for details.
