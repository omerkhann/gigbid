# event-migrate-gtm

## Overview
`event-migrate-gtm` is a Node.js utility that automates the migration of legacy Google Analytics (Universal Analytics) events to Google Analytics 4 (GA4) using Google Tag Manager (GTM) containers. The script parses a JSON manifest of existing UA events, generates corresponding GA4 event tags, and updates the GTM workspace via the GTM REST API. It ensures a zero‑downtime transition by keeping both UA and GA4 tags active until verification is complete.

## Architecture
- **manifest.json** – declarative list of UA events (category, action, label, value) and optional mapping to GA4 parameters.
- **src/** – core modules:
  - `parser.js` reads and validates the manifest.
  - `gtmClient.js` wraps the GTM API (authentication, workspace selection, tag CRUD).
  - `converter.js` maps UA event fields to GA4 `event_name` and `event_params` using a configurable rule set.
  - `deployer.js` creates GA4 tags, attaches triggers, and optionally disables original UA tags.
- **scripts/** – CLI entry points:
  - `migrate.js` orchestrates the full migration workflow.
- **tests/** – Jest test suite covering parsing, conversion logic, and API mock interactions.

## Prerequisites
- Node.js >=18
- A Google Cloud service account with `gtm.accounts.readonly`, `gtm.containers.update` scopes.
- Access to the target GTM container ID.

## Setup & Execution
```bash
# Clone and install dependencies
git clone https://github.com/yourusername/event-migrate-gtm.git
cd event-migrate-gtm
npm ci

# Configure environment variables
export GTM_ACCOUNT_ID=1234567890
export GTM_CONTAINER_ID=987654321
export GOOGLE_APPLICATION_CREDENTIALS=./service-account.json

# Run migration (dry‑run first)
node scripts/migrate.js --manifest ./manifest.json --dry-run

# Apply changes
node scripts/migrate.js --manifest ./manifest.json
```
The dry‑run prints a diff of tags to be created/updated without contacting GTM. After verification, omit `--dry-run` to push changes.

## Testing
```bash
npm test
```
All unit tests must pass before committing.

## License
MIT – see LICENSE file.
