<!-- project_id: fs-p11 | synthetic -->
# REST API and Partner Integrations for a Travel Agency

## Context
Sara Malik was engaged by a travel agency looking to modernize its booking workflow. The agency relied on manual data entry and phone calls to retrieve quotes from multiple suppliers, resulting in a quote turnaround time of about two days. The client needed a scalable solution that could aggregate supplier data, automate quote generation, and reduce response times dramatically. The project scope included building a robust REST API, integrating five external supplier services, and ensuring data persistence with PostgreSQL.

## What I built
Using Django as the backend framework, I designed a clean, modular architecture that exposed a set of RESTful endpoints for internal and external consumption. Each endpoint handled authentication, request validation, and error handling consistently. The core of the solution was a set of integration services that communicated with the five supplier APIs. I employed Django's async capabilities to parallelize calls, minimizing latency when gathering pricing and availability data.

Key technical components:
- **API Development**: Implemented CRUD operations for travel itineraries, quotes, and supplier configurations using Django REST Framework.
- **Supplier Integrations**: Built adapter modules for each supplier, handling differing authentication schemes (API keys, OAuth) and data formats (JSON, XML). Unified the responses into a common schema for downstream processing.
- **Database Layer**: Modeled the domain with PostgreSQL, leveraging relational integrity for bookings, customer profiles, and historical quote data. Added indexing strategies to accelerate lookup of supplier rates.
- **Performance Optimizations**: Utilized async views and connection pooling, reducing the average API response time from minutes to seconds.
- **Documentation & Testing**: Produced OpenAPI specifications and comprehensive unit/integration tests, ensuring reliability across all integration points.

## Results
The new system connected all five supplier APIs seamlessly, automating the quote generation process. Quote turnaround time dropped from two days to approximately ten minutes—a 96% reduction. The agency reported increased conversion rates as customers received faster responses, and operational overhead for staff decreased significantly. The scalable architecture also positioned the agency to onboard additional suppliers with minimal effort, supporting future growth.
