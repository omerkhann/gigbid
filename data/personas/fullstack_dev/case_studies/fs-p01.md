<!-- project_id: fs-p01 | synthetic -->
# Scalable Booking System for Physiotherapy Clinics

## Context
Sara Malik was approached by a growing chain of physiotherapy clinics looking to modernize their appointment scheduling. The existing process relied on phone calls and manual entry, leading to double‑bookings, missed appointments, and an inability to capture online payments. The client needed a web‑based platform that could handle high traffic, provide a smooth user experience for patients booking sessions, integrate secure payment processing, and send automated reminders to reduce no‑shows. The solution also had to store patient data safely and support future expansion across multiple locations.

## What I built
I designed and delivered a full‑stack web application using a modern JavaScript framework for the front end, paired with a robust server‑side environment. The interface was built with a component‑based library, enabling fast page loads and responsive design across devices. Type safety was introduced throughout the codebase to catch errors early and improve maintainability.

On the back end, I implemented a relational database to store appointment slots, patient records, and transaction details. All data interactions were handled through a typed query layer, ensuring consistency and security. For payments, I integrated a widely used online payment service, allowing patients to pay for sessions at the time of booking while complying with industry standards for data protection.

User authentication was set up with secure token handling, giving patients a personalized dashboard to view, reschedule, or cancel appointments. To keep the system performant under heavy load, I employed an in‑memory data store that cached frequently accessed information such as available time slots and session tokens, dramatically reducing database round‑trips and latency.

Automated email and SMS reminders were scheduled to trigger before each appointment, helping patients remember their bookings and giving the clinic an easy way to confirm attendance. The architecture was containerized, making deployment straightforward and allowing the platform to scale horizontally as the clinic network grew.

## Results
Within the first six months after launch, the platform recorded **18,000 bookings**, a clear indicator of increased patient engagement and streamlined operations. The automated reminder system contributed to a **27% reduction in no‑show rates**, translating into higher revenue and better resource utilization for the clinics. The solution’s scalability and maintainable codebase positioned the client for future growth, with additional locations ready to be onboarded without major re‑engineering.
