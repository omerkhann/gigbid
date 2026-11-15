# scholarforge

## Overview
`scholarforge` is a maintenance repository for a legacy WordPress membership platform serving ~4,000 education users. The codebase contains custom theme assets, Elementor page templates, and a set of scripts that automate routine upgrade tasks, database migrations, and CSS refactoring. The primary goal is to keep the site stable across major WordPress core releases while preserving member data and custom styling.

## Architecture
- **Theme Layer**: A child theme built on Elementor that overrides core templates. All CSS lives in `assets/css/` and is compiled from modular SCSS files using `sassc`. 
- **Upgrade Scripts**: Bash scripts in `scripts/` orchestrate the sequence of steps required for a WordPress core upgrade: backup, version switch, dependency update, and cache flush. They rely on WP-CLI commands for database export/import and option sanitisation.
- **Configuration**: Environment‑specific settings are stored in `config/*.env` files and loaded via `dotenv`. Sensitive credentials are never committed.
- **CI/CD**: A GitHub Actions workflow (`.github/workflows/deploy.yml`) runs the upgrade scripts on a staging environment, runs a suite of Selenium‑based UI smoke tests, and, upon success, pushes the changes to production.

## Getting Started
1. Clone the repo:
   ```bash
   git clone https://github.com/yourusername/scholarforge.git
   cd scholarforge
   ```
2. Install dependencies:
   ```bash
   npm install -g sassc
   composer install   # only for WP‑CLI packages
   ```
3. Set up environment variables:
   ```bash
   cp config/example.env config/local.env
   # edit local.env with DB credentials and site URLs
   ```
4. Run a local build of the CSS:
   ```bash
   ./scripts/build-css.sh
   ```
5. Execute a test upgrade on a local Docker WordPress instance:
   ```bash
   ./scripts/upgrade.sh --dry-run
   ```

## Maintenance
- **CSS updates**: Add or modify SCSS modules under `assets/css/modules/` and re‑run `build-css.sh`.
- **Core upgrades**: Update the `WP_VERSION` variable in `scripts/upgrade.sh` and run the script on staging before production.
- **Monitoring**: Logs from the upgrade process are written to `logs/upgrade.log` and are shipped to the central log aggregator.

---
*This repository is intended for engineers maintaining legacy WordPress installations; it abstracts repetitive upgrade steps into reproducible, version‑controlled scripts.*
