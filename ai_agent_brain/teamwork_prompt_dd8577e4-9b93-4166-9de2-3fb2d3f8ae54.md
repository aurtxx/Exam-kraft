The orchestrator must establish the following specialized agents and coordinate their work: Agent 0 (Chief Architect and Team Manager), Agent 1 (Browser Exploration Specialist), Agent 2 (UI/UX Reconstruction Engineer), Agent 3 (System Architecture Analyst), Agent 4 (Database Architect), Agent 5 (Backend Engineering Specialist), Agent 6 (Examination Engine Specialist), Agent 7 (Frontend Engineering Specialist), Agent 8 (Quality Assurance and Security Engineer), and Agent 9 (DevOps and Deployment Engineer). Systematically investigate the authorized, user-visible functionality of the EZExam examination web application currently authenticated in the browser at https://ezexamqwertyuiop.ezexam.in/staff, and independently reconstruct a fully functional, self-hosted full-stack examination platform with equivalent workflows, interface structure, feature coverage, and user experience.

Working directory: ~/teamwork_projects/ezexam_reconstruction
Integrity mode: development

## Reference Material
- Authenticated reference web application in active browser session at https://ezexamqwertyuiop.ezexam.in/staff

## Requirements

### R1. Application Discovery and Research Documentation
Systematically explore all authorized and accessible pages of the reference application at https://ezexamqwertyuiop.ezexam.in/staff using the active browser session, without modifying live reference data, accessing unauthorized roles, or copying proprietary code. Establish and maintain the required research and management documentation across `research/` and `management/`, including route inventories, feature matrices, observable API contracts, database designs, and workflow analyses.

### R2. Full-Stack System Architecture and Data Isolation
Reconstruct the application as an independent modular monolith using React, TypeScript, Vite, and Tailwind CSS for the frontend, Django and Django REST Framework (with Channels and Celery where justified) for the backend, PostgreSQL for persistence, and Docker Compose with Nginx. Implement independent authentication, session management, and organization-level data isolation without using mock APIs or relying on reference application servers.

### R3. Administrative and Examination Management
Implement complete administrative management for organizations, faculty, students, groups, batches, examination centers, roles and permissions, notices, and settings. Implement end-to-end examination management including question banks, section management, marking schemes, scheduling, candidate assignments, and publication.

### R4. Student Examination Engine and Automated Evaluation
Reconstruct a student examination engine supporting server-authoritative timers, section and question navigation, MCQs (single/multiple-correct), numerical questions, question palette status tracking, automatic answer persistence, recovery across browser refreshes and temporary disconnections, and idempotent submission. Implement automated scoring, ranking, percentile calculations, answer review, and student performance reports.

### R5. Reliability, Testing, and Deployment
Ensure the application supports at least 100 simultaneous candidates, low-bandwidth/LAN operation, server-authoritative deadlines, and duplicate attempt prevention. Provide synthetic demonstration datasets, demo accounts for each role, Docker container configurations, health-check endpoints, automated test suites (Pytest, Playwright, Vitest), and installation/deployment documentation for local, LAN, and WAN environments.

## Acceptance Criteria

### Research Documentation and Exploration Parity
- [ ] Research documentation in `research/` and `management/` is populated covering all authorized routes, UI components, observable API contracts, and user workflows.
- [ ] No proprietary source code, private records, credentials, or protected assets are copied from the reference application.

### Administrative and Examination Lifecycle
- [ ] Administrative platform allows managing students, faculty, batches, and examination centers with role-based access control and persistent database storage.
- [ ] Examinations can be authored, configured with question banks/sections/marking schemes, scheduled, assigned, and published.
- [ ] Candidates can start attempts, navigate questions/sections, save responses, and submit manually or via automatic server-authoritative timer expiry.
- [ ] Student examination attempts restore correctly upon browser refresh or temporary network disconnection without response loss.
- [ ] Automated evaluation computes scores, rankings, and percentiles according to configured marking schemes.

### Architecture, Testing, and Deployment
- [ ] Frontend (React/TypeScript/Tailwind) and Backend (Django/DRF/PostgreSQL) run independently without mock APIs or external reference server dependencies.
- [ ] Multi-container deployment runs via Docker Compose with health checks, database migrations, and synthetic demonstration seed data.
- [ ] Automated test suite passes covering unit, integration, and end-to-end examination attempt lifecycles.
- [ ] Deployment and installation documentation is complete and verified for local and LAN/WAN self-hosted operation.