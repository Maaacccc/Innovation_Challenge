# Manual UI Test Plan

This checklist is for testing the browser UI by logging in as different human roles and verifying that each role lands in its own workspace. Agent roles do not log in. They run behind the backend orchestration layer.

## 1. Start the system

### Backend
```bash
cd /Users/shengjiajun/Desktop/IC
bash backend/scripts/start_backend.sh
```

### Prepare representative dashboard data
Run this once after the backend database is available. It resets the demo database and prepares a multi-patient dataset with approved proposals, escalation artifacts, regenerated proposal lineage, and an open human-review item.

```bash
cd /Users/shengjiajun/Desktop/IC
bash backend/scripts/prepare_manual_ui_data.sh
```

### Frontend
```bash
cd /Users/shengjiajun/Desktop/IC/frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## 2. Multi-patient demo identities

All demo users share the password `demo1234`.

Patient-care team grouping:
- patient A + caregiver 1 + reviewer W
- patient B + caregiver 1 + reviewer M
- patient C + caregiver 2 + reviewer W

Human demo accounts shown in the login page:
- `reviewer.w@example.com`
- `reviewer.m@example.com`
- `caregiver.1@example.com`
- `caregiver.2@example.com`
- `patient.a@example.com`
- `patient.b@example.com`
- `patient.c@example.com`

Internal accounts still exist in the backend for API and test coverage, but they are intentionally not part of the main browser flow.

## 3. Login page checks

### Valid login
1. Open the UI.
2. Log in with `reviewer.w@example.com`.
3. Expected result:
   - login succeeds
   - the page title is `Reviewer operations console`
   - the signed-in role shows `reviewer`
   - the first screen emphasizes action-required work rather than generic history

### Invalid login
1. Log out.
2. Try a wrong password for any seeded account.
3. Expected result:
   - login fails
   - error text appears on the login form
   - no workspace is shown

## 4. Reviewer workspace checks

### Reviewer W scope
Use `reviewer.w@example.com`.

Expected patient scope:
- patient switcher only shows patient A and patient C
- patient B should not appear for reviewer W

Expected workspace modules:
- `Action center`
- `Decision workspace`
- `Proposal history by recipient role`
- `Selected role responsibilities`
- `Active escalations`
- `Safety metrics`

Expected interaction flow:
1. Open a case in `Action center`.
2. Expected result:
   - the case loads into `Decision workspace`
   - linked proposal context is shown when available
   - reviewer must choose one explicit action:
     - `Approve for release`
     - `Reject and keep blocked`
     - `Escalate to urgent handling`
   - reviewer can add notes before saving

Expected history flow:
1. Switch `Proposal history by recipient role` between:
   - `All recipient roles`
   - `Patient-facing`
   - `Caregiver-facing`
   - `Clinician-facing`
   - `Nurse-facing`
   - `Internal queue`
2. Expected result:
   - the history list updates for the selected role
   - `Selected role responsibilities` updates at the same time
   - this clearly explains what that role should receive

Lineage check:
1. Switch to patient A.
2. In history, find `Daily routine support`.
3. Expected result:
   - the visible approved proposal shows `RewriteOrRegenerationAgent`
   - version is `v2`
   - this confirms reject-and-regenerate worked

Escalation check:
1. Switch to patient C.
2. Expected result:
   - at least one escalation is visible
   - severity and status are visible

### Reviewer M scope
Use `reviewer.m@example.com`.

Expected patient scope:
- patient switcher only shows patient B
- patient A and C should not appear

Expected value:
- reviewer M should still see open work and patient B history
- the reviewer scope is no longer global

## 5. Patient workspace checks

### Patient A
Use `patient.a@example.com`.

Expected result:
- login succeeds
- page title should be `Patient care companion`
- only approved patient-facing items are visible
- a `Basic health overview` section is visible
- it includes baseline health context like sleep, steps, blood pressure, and the next appointment
- reviewer metrics and internal queues are not visible

Consent interaction test:
1. Toggle one of the caregiver-sharing options.
2. Expected result:
   - a success message appears
   - the preference persists after reload
   - caregiver visibility is explicitly controlled by the patient

Key toggles to verify:
- caregiver task cards
- caregiver basic overview
- broader caregiver updates
- medication-related caregiver support

### Patient B or C
Optional but recommended:
1. Log in as `patient.b@example.com` or `patient.c@example.com`.
2. Expected result:
   - the same patient-only pattern holds
   - approved care items stay patient-safe
   - caregiver-sharing controls are available per patient

## 6. Caregiver workspace checks

### Caregiver 1
Use `caregiver.1@example.com`.

Expected patient scope:
- patient switcher shows patient A and patient B

Expected result:
- page title should be `Caregiver task workspace`
- the workspace contains both:
  - `Patient basic overview`
  - `Caregiver task cards`
- the caregiver can now see useful baseline data like sleep and blood pressure when the patient allows it
- a caregiver observation form is visible

Observation flow:
1. Choose patient B.
2. Submit a short observation.
3. Expected result:
   - success message appears
   - the backend processes follow-up items
   - the caregiver workspace refreshes

### Caregiver 2
Use `caregiver.2@example.com`.

Expected patient scope:
- patient switcher only shows patient C

Expected result:
- patient C basic overview is visible
- at least one caregiver task card is present in the prepared demo data

## 7. What counts as pass

The UI manual test passes if:
- valid login works
- invalid login is blocked
- reviewer W only sees patients A and C
- reviewer M only sees patient B
- reviewer homepage starts with action-required work
- reviewer decision flow is explicit and understandable
- reviewer proposal history can be filtered by recipient role
- selected role responsibilities change with the role filter
- patient sees only approved patient-facing content
- patient can control caregiver visibility preferences
- caregiver sees both useful basic context and task cards
- caregiver can submit observations that trigger follow-up processing
- regenerated proposal lineage is visible through `source_agent` and version number
- escalation cases appear in the reviewer view
