# UI/UX Component & Design Token Specification (Staff & Shared Architecture)

## 1. Executive Summary & Design System Foundation

This document provides the definitive UI/UX component specifications and design tokens for the reconstructed **EZExam** examination platform frontend (React 18+, TypeScript, Vite, and Tailwind CSS).

The design system is extracted directly from live inspection of the reference EZExam application (`https://ezexamqwertyuiop.ezexam.in/staff`), incorporating responsive layouts, accessibility considerations, role-based workflows, and modern component architecture.

---

## 2. Design Tokens for Tailwind CSS

The platform utilizes a structured color palette, consistent spacing scale, modern typography, and elevation layers mapped into `tailwind.config.js`.

### 2.1 Color Palette
| Token Name | Hex Code | Tailwind Class / Variable | Semantic Purpose |
|---|---|---|---|
| **Primary Blue** | `#2d8df1` | `bg-primary-500`, `text-primary-500` | Main interactive color, buttons, active tabs, highlights |
| **Primary Blue Dark** | `#1474D8` | `bg-primary-600` | Button hover state, pressed states |
| **Primary Navy** | `#284b92` | `bg-navy-900`, `text-navy-900` | Header background, timer text, authoritative headers |
| **Primary Light Blue**| `#c4ecff` | `bg-primary-100` | Selected option background (`.oselected`), subtle row highlight |
| **Success Green** | `#22C969` | `bg-success-500`, `text-success-500`| Answered question palette, confirmation dialogs, positive actions |
| **Success Dark** | `#08af4f` | `bg-success-600` | Success hover state |
| **Secondary Green** | `#49c98c` | `bg-emerald-500` | Secondary green buttons, share buttons, badge tags |
| **Danger / Red** | `#FF614D` | `bg-danger-500`, `text-danger-500` | Not Answered palette state, warning dialogs, delete buttons |
| **Danger Light / Coral**| `#f96a6a` | `bg-rose-400` | Close buttons, secondary danger icons, alert indicators |
| **Warning / Amber** | `#fccc5a` | `bg-amber-400` | Warning badges, notice stars, attention banners |
| **Orange** | `#ffac59` | `bg-orange-400` | Reset attempt warning, notice highlights |
| **Review Purple** | `#9967ff` | `bg-purple-500`, `text-purple-500` | Marked for Review palette state, review hover actions |
| **Review Purple Light**| `#b58fff` | `bg-purple-300` | Review indicators, secondary purple accents |
| **Gold / Upgrade** | `#ffad17` | `bg-amber-500` | Plan & billing buttons, VIP / SuperAdmin markers |
| **Neutral Canvas** | `#f0f0f0` | `bg-slate-100` | Application main workspace background |
| **Card / Surface** | `#ffffff` | `bg-white` | Card panels, modals, dropdowns |
| **Palette Gray** | `#dcdcdc` | `bg-slate-300` | Not Visited question palette button |
| **Border Gray** | `#e2e8f0` | `border-slate-200` | Input borders, dividers, table borders |
| **Text Primary** | `#1e293b` | `text-slate-800` | Primary headings and body copy |
| **Text Muted** | `#64748b` | `text-slate-500` | Secondary captions, helper hints |

### 2.2 Typography Scale
- **Font Family**: 
  - Primary UI: `DM Sans, 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
  - Monospace (Code Questions / JSON): `'JetBrains Mono', 'Fira Code', monospace`
- **Type Scale**:
  - `Display / Modal Header`: `font-semibold text-2xl (24px) leading-8`
  - `Card Header / Section Title`: `font-medium text-lg (18px) leading-7`
  - `Body Regular`: `font-normal text-sm (14px) leading-5`
  - `Palette Number`: `font-bold text-xs (13px) leading-none`
  - `Input Label / Tooltip`: `font-medium text-xs (12px) text-slate-500`

### 2.3 Radii & Elevation (Shadows)
- **Border Radii**:
  - Buttons (`.ee-btn`): `rounded-xl` (12px) or full pill `rounded-full` (24px)
  - Card Panels: `rounded-2xl` (16px)
  - Modals: `rounded-2xl` (16px) with distinct top header container
  - Question Palette Buttons: `rounded-md` (6px) or `rounded-lg` (8px)
- **Shadows**:
  - Card elevation: `shadow-sm hover:shadow-md transition-shadow`
  - Modals / Popups: `shadow-2xl`
  - Action buttons: `shadow-md hover:shadow-lg active:shadow-sm`

---

## 3. Staff Portal Shell & Layout Architecture

```
+---------------------------------------------------------------------------------------+
| TOP HEADER: [Menu Toggle] [Logo]       [Global Search]      [Payments] [User] [Logout] |
+-----------------------+---------------------------------------------------------------+
| SIDEBAR               | MAIN CONTENT AREA                                             |
| [User Avatar & Role]  | +-----------------------------------------------------------+ |
|                       | | BREADCRUMBS & ACTION TOOLBAR                              | |
| - Exams (Active)      | +-----------------------------------------------------------+ |
| - Students            | | FILTER & SEARCH BAR                                       | |
| - Settings            | +-----------------------------------------------------------+ |
| - Payments & Plans    | | DATA GRID / CARD LIST VIEW                                | |
| - Customize Site      | | (Exams / Students / Question Papers / Centers)            | |
| - Demo Videos         | |                                                           | |
| > Management (Collap) | |                                                           | |
|   * Faculty           | |                                                           | |
|   * Centres           | +-----------------------------------------------------------+ |
|   * Notices           | | PAGINATION CONTROLS                                       | |
| - Upgrade             | +-----------------------------------------------------------+ |
+-----------------------+---------------------------------------------------------------+
```

### 3.1 Header / Top Navigation Bar (`<header id="header">`)
- **Container**: Fixed top bar (`h-16 bg-white border-b border-slate-200 px-4 flex items-center justify-between z-30`).
- **Left Group**:
  - `Menu Toggle Button`: Circular or rounded icon button (`w-10 h-10 rounded-full flex items-center justify-center hover:bg-slate-100 text-primary-500`). Toggles sidebar collapse/expand.
  - `Organization Brand / Logo`: Clickable logo wrapper with image fallback. Clicking navigates to `/staff/customize` or `/staff/exams`.
- **Center Group**:
  - `Global Search Bar`: Hidden on mobile (`hidden md:flex items-center w-80 px-3 py-1.5 rounded-lg bg-slate-100 border border-slate-200 text-sm`). Placeholder: `"Find Students"`.
- **Right Group**:
  - `Payments & Plans`: Pill button (`bg-[#ffad17] hover:bg-[#f0b453] text-white px-4 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider`).
  - `Notifications / Help`: Help icon button triggering feature onboarding modal.
  - `Logout Button`: Exit icon (`text-slate-600 hover:text-danger-500 p-2 rounded-full hover:bg-slate-100`). Triggers confirmation modal.

### 3.2 Sidebar Navigation (`<aside id="left-sidebar-nav">`)
- **Container**: `w-64 min-h-screen bg-white border-r border-slate-200 flex flex-col`.
- **User Profile Card**:
  - Cyan-blue gradient or solid background banner (`h-20 bg-gradient-to-r from-cyan-600 to-primary-600 px-4 flex items-center gap-3 text-white`).
  - Circular avatar (50x50 px, white border).
  - User details: Full Name (`font-semibold text-sm truncate`) and User Role badge (`Super Admin`, `Faculty`, `Editor`). Click opens Account Settings.
- **Navigation Menu Items**:
  - Items styled as `flex items-center gap-3 px-4 py-3 text-slate-700 hover:text-primary-500 hover:bg-primary-50 rounded-lg mx-2 transition-colors font-medium text-sm`.
  - Active state: `bg-primary-50 text-primary-500 font-semibold border-r-4 border-primary-500`.
  - Core Navigation:
    1. **Exams** (`check_circle` icon)
    2. **Students** (`face` icon)
    3. **Settings** (`settings` icon)
    4. **Payments & Plans** (`attach_money` icon)
    5. **Customize Site** (`palette` / `local_florist` icon)
    6. **Demo Videos** (`play_circle` icon)
  - Collapsible Group ("Institution Management"):
    - **Faculty** (`perm_identity` icon)
    - **Centres** (`business` icon)
    - **Notices** (`chat` icon)
  - Bottom Action: **Upgrade** (`star` icon with gold accent).

---

## 4. Data Display Components

### 4.1 Data Tables & Grid View
- **View Toggle**: Segmented button allowing staff to switch between **Exams List** (tabular row format) and **Exams Grid** (card format).
- **Table Structure**:
  - `Table Container`: `overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm`.
  - `Header Row`: `bg-slate-50 text-slate-600 text-xs uppercase font-semibold border-b border-slate-200 px-4 py-3`.
  - `Data Rows`: `hover:bg-slate-50/80 transition-colors border-b border-slate-100 text-sm text-slate-700`.
  - `Actions Column`: Contextual kebab menu or button group: "Edit Exam", "Assign Batches", "Generate Report", "Delete".
- **Status Badges**:
  - `Draft`: `bg-slate-100 text-slate-600 border border-slate-300 rounded-full px-2.5 py-0.5 text-xs font-medium`
  - `Published / Upcoming`: `bg-blue-50 text-blue-600 border border-blue-200 rounded-full px-2.5 py-0.5 text-xs font-medium`
  - `Ongoing / Live`: `bg-emerald-50 text-emerald-600 border border-emerald-200 rounded-full px-2.5 py-0.5 text-xs font-semibold animate-pulse`
  - `Closed / Completed`: `bg-slate-100 text-slate-500 border border-slate-200 rounded-full px-2.5 py-0.5 text-xs font-medium`

### 4.2 Filter Bars & Search Inputs
- **Filter Row**: Horizontal bar above data grids (`flex flex-wrap items-center justify-between gap-3 p-4 bg-white rounded-xl border border-slate-200 mb-4`).
- **Inputs**:
  - Search input with clear button (`w-64 pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-200`).
  - Branch / Batch multi-select dropdown (`VirtualSelect` replacement using headless UI / Radix / Combobox).
  - Date Range pickers (`From: [Date]` and `To: [Date]`).
  - Capacity & Attempts indicator badge (`Attempts Available: 0 / 25`, `Total Attempts: 0`).

---

## 5. Form Controls & Authoring Modals

### 5.1 Question Creation & Editor Modal (`form-addq` & `form-editq`)
- **Layout**: Two-column responsive authoring pane.
- **Top Inputs**:
  - Question Number indicator (`Q.No. [X]`).
  - File Dropzone / Dropify (`data-max-file-size="5M"`, accepts PNG, JPG, JPEG for question paper snippets or diagrams).
  - Question Textarea (`min-h-[120px] rounded-xl border border-slate-300 p-4 font-sans text-sm placeholder:text-slate-400`).
- **Question Types Dropdown (`qtype`)**:
  | Value | Type Label | Input / Answer Mode |
  |---|---|---|
  | `1` | A B C D - Single Correct | Radio buttons (A, B, C, D) |
  | `2` | A B C D - Multi Correct | Checkboxes (A, B, C, D) |
  | `3` | Numerical Answer | Numerical text field / Virtual numpad |
  | `30` | Single Digit Integer | Single digit (0-9) |
  | `21` | True or False | Two options (True, False) |
  | `31` / `32` | A B C - Single / Multi Correct | Options A, B, C |
  | `51` / `52` | A B C D E - Single / Multi Correct | Options A, B, C, D, E |
  | `61` / `62` | A B C D E F - Single / Multi Correct | Options A, B, C, D, E, F |
  | `8` | One-Word Answer | Short text input (max 100 chars) |
  | `7` | Image Upload Subjective | Candidate webcam/file upload |
  | `71` | Text-Box Subjective | Long-form textarea |
  | `721`-`724` | Code-Box (Python, Java, C, C++) | Code editor with language selector |
- **Marking Scheme Inputs (`.markings-inputs`)**:
  - `Correct Marks (cmk)`: Positive float/int (default: `1`, JEE: `4`).
  - `Incorrect Marks (imk)`: Negative float/int (default: `0`, JEE: `-1` or `-2`).
  - `Partial Marks (pmk)`: Marks for each correct option in multi-correct questions (e.g. `+1`).
- **Action Buttons**:
  - "Previous Question", "Save & Next", "Finish".

### 5.2 Exam Creation Multi-Step Modal (`new-exam-modal`)
- **Step 1 - Exam Details**:
  - Exam Name input (`minlength="5"`).
  - Duration input (minutes) with quick-select dropdown:
    * `30 mins (Half-Hour)`
    * `60 mins (1 Hour)`
    * `90 mins (1.5 Hours)`
    * `120 mins (2 Hours)`
  - "Next" navigation button.
- **Step 2 - Question Loading Strategy**:
  - Interactive grid cards:
    1. **Add Questions Bulk**: Upload 1 question/page PDF + Key Excel, or Question Paper PDF + Key Excel, or Questions in Excel.
    2. **Add Questions One-By-One**: Opens individual question editor.
    3. **Copy Questions from Previous Exam**: Select existing exam.
    4. **From Your Question Bank**: Select questions by subject/tag.

### 5.3 Online Exam Publishing & Configuration Form (`form-add-onex`)
- **Time Window Settings**:
  - Start Date (`date`) + Start Time dropdown (30-minute intervals: `12:00 am` to `11:30 pm`).
  - End Date (`date`) + End Time dropdown.
  - "All Day" checkbox toggle.
- **Visibility & Sharing Settings**:
  - "Private Exam" (restricted to assigned candidates) vs "Public Exam" (open via shareable URL `ezex.in/[slug]`).
- **Advanced Security & Proctoring Options (Accordion)**:
  - `check-switches`: Enable Window Switch Limit (Tab change detector).
  - `num-switch`: Number of allowed switches before auto-submit (Default: 5, Range: 2-10).
  - `check-shuf`: Shuffle Questions order per student attempt.
  - `check-cam`: Enable Webcam proctoring (mandatory camera permission).
  - `check-hide-res`: Hide results/score immediately post-submission.
  - `check-hide-rank`: Hide ranks in student analytics.
  - `check-hide-anal`: Hide full performance breakdown.
  - `check-pc-only`: Restrict access to PC/Desktop browsers only (blocks mobile).
  - `check-prac`: Practice Exam mode (unlimited attempts, scores unrecorded).
  - `check-sec-skip`: Allow skipping between sections before section timer finishes.
  - `check-hide-qs`: Hide question text in post-exam analytics.

---

## 6. Modals, Drawers & Special Panels

### 6.1 Student & Batch Assignment Drawer (`card-onex-stud`)
- Drawer panel sliding in from the right when "Select Students" is triggered in the exam authoring flow.
- Filter students by Tags, Batches, Branches, or Centers.
- Checkbox table with master select-all toggle.
- Display count of selected students vs available tier capacity.
- Primary CTA: **Share & Publish Exam** (`bg-emerald-500 hover:bg-emerald-600 text-white font-semibold px-6 py-2 rounded-xl`).

### 6.2 Student Submission Reset & Proctoring Drawer (`modal-subm-reset`)
- Staff diagnostic modal for an individual candidate attempt:
  - Header: Candidate Roll Number, Candidate Name, Exam Name.
  - Summary stats: Number of questions answered, total attempt time.
  - **Saved Responses Grid**: Shows question numbers, submitted option keys, and status.
  - **Question Shuffle Mapping**: Table comparing Student Q.No vs Master Q.No.
  - **Proctoring Activity Log**: Red warning banner: `Switched Outside Exam [X] times!`.
  - **Device Metadata**: Client User-Agent, OS, Browser version, Client IP address.
  - Staff Action Buttons:
    * `Mark as Not Submitted` (Allows student to resume attempt if accidental submission occurred).
    * `Re-evaluate Attempt` (Triggers score recalculation).
    * `Delete Attempt` (Purges responses with confirmation modal).

---

## 7. Features Discovered & Edge Cases

### Features Discovered
| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Staff Shell | Collapsible Sidebar Navigation | Sidenav with role badge, icons, and nested admin menus | User interaction / click | Sidebar toggles 64px to 256px | Graceful collapse | Staff HTML inspection |
| 2 | Staff Shell | Global Student Search | Quick filter in top navigation | Query text string | Filtered student list | Empty dropdown if no match | Staff HTML inspection |
| 3 | Exam Authoring | Multi-step Exam Creation | Step 1 Details -> Step 2 Strategy (bulk/one-by-one/bank) | Form inputs (name, duration) | Next modal step | Validation toast on empty name | `new-exam-modal` inspection |
| 4 | Exam Authoring | Question Type Matrix | 14+ question types including single/multi MCQ, numerical, code | Type select dropdown | Dynamically adapts options and inputs | Defaults to type 1 | `form-addq` inspection |
| 5 | Exam Authoring | 3-Tier Marking Scheme | Positive, negative, and partial marks per question | `cmk`, `imk`, `pmk` float inputs | Marking display text | Fallback to +1, 0 | `form-addq` inspection |
| 6 | Exam Authoring | Proctoring Switch Limit | Auto-submits exam when window blurred > X times | `num-switch` input (2-10) | Switch counter limit | Clamps between 2 and 10 | `form-add-onex` inspection |
| 7 | Exam Authoring | Timed Windows & Dropdown Pickers | Specific start/end datetime with 30-min interval dropdowns | Date + 30-min slots | Scheduled window | Disallows end before start | `form-add-onex` inspection |
| 8 | Batch Management | Batch / Tag Assignment Drawer | Assigns exams to batches/tags or individual candidates | Multi-select tags, checkboxes | Updated candidate roster | Capacity check warning | `card-onex-stud` inspection |
| 9 | Attempt Management| Submission Reset & Proctoring View | View student responses, shuffle order, and window switches | Candidate attempt ID | Full attempt diagnostic drawer | 404 on invalid attempt ID | `modal-subm-reset` inspection |

### Edge Cases
| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | Duration Input | User types > 999 minutes | Clamped by `maxlength="3"` in DOM input |
| 2 | Negative Marking | User enters positive value for `imk` | Code checks `.includes("-")` and prepends `-` automatically |
| 3 | Window Switch Counter | Blur event fired on window switch | Triggers warning modal; on threshold (default 5), invokes `autoFinalSubmit(true)` |
| 4 | Multi-Correct Partial Marks | Only some correct options picked, 0 incorrect | Code calculates `pmk * correct_count`; if any incorrect picked, assigns `imk` |
| 5 | Empty Question Image | No image uploaded | DOM hides `#qimg` and displays text textarea `#qtxtbox` |
