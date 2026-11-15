// GTM Event Migration Script
// This script migrates legacy GA events to GA4 format
// Author: Data Analyst
// Date: 2023-10-12

// Mapping of legacy events to GA4 events
const eventMap = {
  "legacy_signup": "sign_up",
  "legacy_purchase": "purchase",
  "legacy_login": "login",
  "legacy_pageview": "page_view",
  "legacy_video_start": "video_start",
  "legacy_video_complete": "video_complete"
};

// Function to push event to dataLayer in GA4 format
function pushGA4Event(legacyEvent, params = {}) {
  const ga4Event = eventMap[legacyEvent];
  if (!ga4Event) {
    console.warn(`No GA4 mapping for event: ${legacyEvent}`);
    return;
  }
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push({
    event: ga4Event,
    ...params
  });
  console.log(`Pushed GA4 event: ${ga4Event}`, params);
}

// Example usage: migrating a batch of events
const legacyEvents = [
  { name: "legacy_signup", userId: "U123" },
  { name: "legacy_purchase", transactionId: "T456", value: 99.99, currency: "USD" },
  { name: "legacy_login", userId: "U123" }
];

legacyEvents.forEach(evt => {
  pushGA4Event(evt.name, { user_id: evt.userId, transaction_id: evt.transactionId, value: evt.value, currency: evt.currency });
});

// Export for testing purposes
export { pushGA4Event, eventMap };
