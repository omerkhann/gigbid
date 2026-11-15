# fitpulse

## Overview
`fitpulse` is a cross‑platform mobile client that enables members of a fitness studio to view class schedules, book sessions, and receive push notifications for upcoming bookings. The app communicates with a Firebase backend for authentication, real‑time data sync, and cloud messaging, and integrates with the studio's RESTful API for class catalog and booking operations.

## Architecture
- **Frontend**: JavaScript codebase structured with a modular component hierarchy. State management is handled via Redux, with side‑effects managed by Redux‑Saga. Navigation is powered by React Navigation.
- **Backend Services**:
  - **Firebase Auth** for secure email/password and social logins.
  - **Firestore** stores user profiles, booking records, and class metadata with real‑time listeners for UI updates.
  - **Firebase Cloud Messaging** delivers push notifications for booking reminders.
- **External API**: A custom REST API (hosted by the studio) provides the master schedule, class details, and booking endpoints. All API calls are wrapped in a thin service layer using Axios with automatic token refresh.
- **Build System**: Metro bundler with Babel transpilation. CI/CD pipelines use GitHub Actions to run linting, unit tests (Jest), and generate release builds.

## Getting Started
1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/fitpulse.git
   cd fitpulse
   ```
2. **Install dependencies**
   ```bash
   npm ci
   ```
3. **Configure Firebase**
   - Create a Firebase project and enable Auth, Firestore, and Cloud Messaging.
   - Download `google-services.json` (Android) and `GoogleService-Info.plist` (iOS) and place them in the respective platform directories.
   - Add the generated config to `.env` (see `.env.example`).
4. **Run the app**
   - Android: `npm run android`
   - iOS: `npm run ios`
5. **Testing**
   ```bash
   npm test   # runs Jest unit tests
   ```

## Deployment
Release builds are generated via `npm run build:android` and `npm run build:ios`. The CI workflow automatically uploads artifacts to the respective app stores after successful lint, test, and version bump stages.

---
*© 2023 fitpulse – Open source under the MIT License.*
