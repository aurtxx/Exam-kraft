# Student Examination Screen UI/UX Specification (R4 Parity Architecture)

## 1. Executive Summary & Philosophy

This specification provides the comprehensive, pixel-precise frontend blueprint for the **Student Examination Screen** of the reconstructed EZExam platform.

The examination interface adheres to the standardized **NTA (National Testing Agency) / JEE Advanced / Computer Based Testing (CBT)** paradigm, delivering:
1. A distraction-free, full-viewport assessment canvas (`100vw x 100vh`).
2. Server-authoritative countdown timing with progressive visual warnings.
3. Multi-section navigation with real-time progress indicators.
4. Flexible question interaction supporting Single-Correct MCQs, Multi-Correct MCQs (with partial scoring), Numerical Answers (with an on-screen virtual numpad), and Subjective/Code questions.
5. The canonical **5-state question palette** with instantaneous status transitions.
6. Robust anti-cheating, window switch monitoring, and zero-data-loss recovery across browser refreshes and network drops.

---

## 2. Examination Canvas Layout Architecture

The overall viewport is organized into a full-height grid/flex layout:

```
+---------------------------------------------------------------------------------------------------------+
| TOP BAR: [Brand Logo]       [Exam Title & Info]        [Candidate Name & Photo]        [Timer: 59:45]   |
+---------------------------------------------------------------------------------------------------------+
| SECTION TABS: [Mathematics (5)]  [Physics (5)]  [Chemistry (5)]           [Progress Hover Tooltip]      |
+-------------------------------------------------------------------+-------------------------------------+
| QUESTION PANE (Left ~68-72% Width)                                | QUESTION PALETTE (Right ~28-32%)    |
| +---------------------------------------------------------------+ | +---------------------------------+ |
| | Section Header: Section Chemistry (5 Questions, Max: 20)      | | | Chemistry - Questions Overview  | |
| | Q.No. 11        [Instruction]           Marking: +4, -1, 0    | | | [Legend Modal Trigger (?)]      | |
| +---------------------------------------------------------------+ | +---------------------------------+ |
| | Question Text & Formulae / Diagrams (#qimg / #qtext)          | | | Palette Button Grid:            | |
| |                                                               | | | [ 1] [ 2] [ 3] [ 4] [ 5]        | |
| | Options List:                                                 | | | [ 6] [ 7] [ 8] [ 9] [10]        | |
| |  (A) Option Text or Image                                     | | | [11] [12] [13] [14] [15]        | |
| |  (B) Option Text or Image                                     | | +---------------------------------+ |
| |  (C) Option Text or Image                                     | | | Quick Actions:                  | |
| |  (D) Option Text or Image                                     | | | [Question Paper] [Instructions] | |
| |                                                               | | +---------------------------------+ |
| | [OR: Virtual Numpad for Numerical Questions]                  | | | [Submit Exam Button (Red)]      | |
| +---------------------------------------------------------------+ | +---------------------------------+ |
| BOTTOM ACTION BAR:                                              |                                       |
| [Clear Response]  [Previous]       [Mark for Review & Next]  [Save & Next]                              |
+-------------------------------------------------------------------+-------------------------------------+
```

---

## 3. Top Bar Specifications (`<header id="header">`)

- **Dimensions**: Full viewport width (`w-full`), fixed height `h-16` (64px), background `#ffffff`, border bottom `1px solid #e2e8f0`, shadow `shadow-sm`, z-index `z-30`.
- **Left Group**:
  - `Brand Logo`: Organization logo (`h-10 object-contain`) with automatic fallback to text branding.
- **Center Group**:
  - `Exam Title`: `text-base md:text-lg font-bold text-slate-800 flex items-center gap-2`.
  - `Exam Info Trigger`: Tooltip/modal icon (`info_outline`) displaying total questions, total duration, and maximum marks.
- **Right Group**:
  - `Candidate Profile`:
    - Candidate Name (`text-sm font-semibold text-slate-700 hidden sm:inline-block`).
    - Roll Number / Registration ID (`text-xs text-slate-500 hidden sm:block`).
    - Circular photo thumbnail (`w-9 h-9 rounded-full border border-slate-300 bg-slate-100 flex items-center justify-center overflow-hidden`).
    - If webcam proctoring is enabled (`cam: true`), displays a live 1 FPS mini-webcam status dot (green when camera stream is healthy, red when blocked).
  - `Server-Authoritative Countdown Timer (`#timer`)`:
    - Font: Monospace numerals, bold (`font-mono text-lg md:text-xl font-bold tracking-wider px-3 py-1 rounded-lg border`).
    - **Normal State**: Text color `#284b92` (Navy Blue), background `#f0f4fc`, border `#d0ddf7`. Time remaining > 10 minutes.
    - **Warning State**: Text color `#b45309` (Amber-700), background `#fef3c7`, border `#fde68a`. Time remaining between 5 and 10 minutes.
    - **Critical / Danger State**: Text color `#b91c1c` (Red-700), background `#fee2e2`, border `#fca5a5`, with CSS pulsing animation (`animate-pulse`). Time remaining < 5 minutes.
    - **Expired State**: Displays `"EXPIRED"`, disables all question choice inputs, immediately launches `#finish-modal` with auto-submission mode (`autoFinalSubmit(false)`).

---

## 4. Section Tabs & Section Navigation (`#secs-container`)

- **Container**: `h-14 px-4 bg-white border-b border-slate-200 flex items-center gap-2 overflow-x-auto thin-scrollx`.
- **Section Tab Element (`.btn.section`)**:
  - Styling: `px-5 py-2 rounded-xl text-xs md:text-sm font-semibold uppercase tracking-wider transition-all duration-200 shadow-sm cursor-pointer whitespace-nowrap`.
  - **Active Tab**: Background `#2d8df1` (Primary Blue), text `#ffffff`, shadow `shadow-md`, scale `scale-[1.02]`.
  - **Inactive Tab**: Background `#e2e8f0` (Slate-200), text `#475569` (Slate-600), hover `bg-slate-300 text-slate-800`.
  - **Disabled Tab (Section Timed / Non-Skippable)**: When `sec_skip: false`, tabs for future or past locked sections are disabled (`opacity-50 cursor-not-allowed pointer-events-none`).
- **Section Summary Hover Tooltip (`#hoverShow`)**:
  - Hovering over a section tab triggers a popover floating badge showing real-time question statistics for that specific section:
    * `Answered Qs`: Count styled in green `#49c98c`.
    * `Unanswered Qs`: Count styled in coral/red `#f96a69`.
    * `Not Visited Qs`: Count styled in neutral gray `#64748b`.

---

## 5. Question Pane (Left Main Content Area)

- **Container**: Flex-1 full height with independent vertical scrolling (`overflow-y-auto px-6 py-4 bg-slate-50`).

### 5.1 Question Header Bar
- **Section & Marks Meta**:
  - `Section Name`: `text-xs font-bold uppercase tracking-wider text-primary-500 bg-primary-50 px-2.5 py-1 rounded-md border border-primary-200`.
  - `Question Number`: `text-xl font-extrabold text-slate-800` (accompanied by subtle `.pulse` glow effect on question change).
  - `Instruction Label`: `text-xs md:text-sm font-medium text-slate-600 text-center flex-1 mx-4 italic`.
  - `Marking Scheme Indicator`:
    * Container: `bg-slate-100 border border-slate-200 px-3 py-1 rounded-lg text-xs font-semibold text-slate-700 flex items-center gap-2`.
    * Text for Standard: `+4 for Correct, -1 for Incorrect`.
    * Text for Multi-Correct Partial: `+4: All correct; -2: Incorrect; +1: Each correct`.
  - `Report Question Button`: Flag icon button (`text-slate-400 hover:text-danger-500 text-xs flex items-center gap-1`). Toggles to "Undo Report".

### 5.2 Question Body & Media
- **Formula / Text Display (`#qtext`)**:
  - Read-only, user-select disabled (`select-none`), copy/paste prevented (`oncopy="return false"`).
  - Support for LaTeX / KaTeX rendering for mathematical notation (`$\frac{d}{dx}$`, `$\sqrt{x}$`, etc.).
- **Question Image Container (`#qimg`)**:
  - Rendered when question is authored via image/PDF extraction.
  - Border: `border border-slate-200 rounded-xl bg-white p-4 shadow-sm max-w-full object-contain cursor-zoom-in`.
  - Clicking launches full-resolution modal preview (`#question-modal`).

### 5.3 Input Controls by Question Type

#### A. Single-Correct MCQ (`qtype: 1, 21, 31, 51, 61`)
- Options (A, B, C, D):
  - Row component: `flex items-center gap-4 p-3.5 my-2.5 rounded-xl border border-slate-200 bg-white hover:border-primary-400 hover:bg-primary-50/50 cursor-pointer transition-all`.
  - Radio Indicator: Circular button with option letter (`w-9 h-9 rounded-full font-bold text-sm flex items-center justify-center transition-colors`).
    * Unselected: `bg-slate-100 text-slate-600 border border-slate-300`.
    * Selected (`.oselected`): `bg-primary-500 text-white shadow-md border-primary-500`. Row background transitions to `#c4ecff`, row border to `#2d8df1`.
  - Clicking any unselected option automatically deselects prior choice.

#### B. Multi-Correct MCQ (`qtype: 2, 32, 52, 62`)
- Options (A, B, C, D):
  - Same visual layout as Single-Correct, but with square/rounded-lg checkbox badges.
  - Multiple options can be toggled simultaneously.
  - Deselecting an already selected option removes it from the choice set.

#### C. Numerical Questions (`qtype: 3, 30, 35, 300`)
- **Display Field (`#num-resp`)**:
  - Centered text input (`w-56 h-12 text-center font-mono text-2xl font-bold rounded-xl border-2 border-primary-500 bg-white shadow-inner focus:outline-none focus:ring-2 focus:ring-primary-400`).
  - Read-only on mobile/tablet to enforce virtual numpad use, or synchronized with physical keyboard on desktop.
- **On-Screen Virtual Numpad (`#numpad`)**:
  - Key layout in 3x4 grid:
    * Row 1: `[7] [8] [9]`
    * Row 2: `[4] [5] [6]`
    * Row 3: `[1] [2] [3]`
    * Row 4: `[0] [ . ] [ - ]` (Minus for negative numerical values)
  - Key styling: `w-14 h-14 rounded-full bg-white border border-slate-300 shadow-md font-bold text-lg text-slate-700 hover:bg-primary-50 hover:text-primary-600 hover:border-primary-400 active:scale-95 transition-all flex items-center justify-center`.
  - Actions Row:
    * `Backspace`: Wide pill button (`bg-slate-100 hover:bg-rose-50 hover:text-rose-600 border border-slate-300 text-xs font-semibold py-2 px-4 rounded-xl flex items-center justify-center gap-1`).
    * `Clear All`: Wide pill button (`bg-slate-100 hover:bg-rose-50 hover:text-rose-600 border border-slate-300 text-xs font-semibold py-2 px-4 rounded-xl flex items-center justify-center gap-1`).
  - Key input constraints: Only one decimal point allowed; minus allowed only as leading character; max 12 digits.

#### D. Subjective / Code Questions (`qtype: 71, 72`)
- Subjective Textarea: `w-full min-h-[160px] rounded-xl border border-slate-300 p-4 font-sans text-sm focus:border-primary-500` with live word counter (`Word Count: [N]`).
- Code Editor: Integrated Monaco/CodeMirror editor with language selector (Python, Java, C, C++), syntax highlighting, line numbers, and terminal output execution console.

---

## 6. Question Palette (Right Sidebar)

- **Dimensions**: Fixed width `w-80 md:w-96` on desktop, collapsible sliding sheet on mobile/tablet. Background `#ffffff`, border left `1px solid #e2e8f0`, shadow-sm.
- **Palette Header**:
  - Title: `[Section Name] - Questions Overview` (`text-sm font-bold uppercase text-slate-700`).
  - Help / Legend Modal Trigger: Question circle icon button triggering `#overview-modal`.

### 6.1 The 5 Standard Question Palette Statuses
The palette grid tracks real-time status according to the canonical 5 NTA states:

| Status Index | State Name | Hex Code | Visual Styling | Meaning / Rules |
|---|---|---|---|---|
| **1** | **Not Visited** | `#dcdcdc` | `bg-[#dcdcdc] text-slate-700 font-bold` | Question has not been navigated to yet. Default initial state. |
| **2** | **Not Answered** | `#FF614D` | `bg-[#FF614D] text-white font-bold` | Candidate viewed question, but left without answering (`.qskipped`). |
| **3** | **Answered** | `#22C969` | `bg-[#22C969] text-white font-bold` | Candidate saved response (`.qattempted`). Evaluated in final scoring. |
| **4** | **Marked for Review** | `#9967ff` | `bg-[#9967ff] text-white font-bold` | Candidate flagged for review without selecting answer (`.qreview`). NOT evaluated. |
| **5** | **Answered & Marked for Review** | `#9967ff` + Tick | `bg-[#9967ff] text-white font-bold relative` with top-right green/white checkmark badge | Candidate answered AND marked for review (`.qreview.qattempted`). **WILL be evaluated in final scoring!** |

### 6.2 Palette Grid Component
- **Grid Layout**: `grid grid-cols-5 gap-3 p-4 overflow-y-auto max-h-[calc(100vh-280px)] thin-scrolly`.
- **Button Element (`.qsq`)**:
  - Dimensions: `w-10 h-10` (40px x 40px), rounded `rounded-lg`, shadow `shadow-sm hover:shadow-md`, font `text-xs font-bold font-mono`.
  - Position: `relative flex items-center justify-center cursor-pointer transition-transform hover:scale-105 active:scale-95`.
  - **Checkmark Badge (`.top-right-tick`)**: Small circular badge (`w-3.5 h-3.5 rounded-full bg-emerald-500 text-white text-[9px] flex items-center justify-center absolute -top-1 -right-1 shadow-sm border border-white`).
- **Real-time Synchronization**:
  - Clicking any palette button immediately evaluates the current question's input:
    * If answer is selected/entered -> Marks current as Answered (`#22C969`).
    * If no answer is present -> Marks current as Not Answered (`#FF614D`).
    * Loads the clicked question into the question pane.

---

## 7. Bottom Action Bar

- **Container**: Fixed footer bar across the bottom of the Question Pane (`h-16 bg-white border-t border-slate-200 px-6 flex items-center justify-between z-20`).
- **Left Group**:
  - `Clear Response Button`: `px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:text-danger-500 hover:bg-slate-100 border border-slate-300 transition-colors`. Resets option selection or numerical input for current question.
  - `Previous Button`: `px-5 py-2 rounded-xl text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-300 flex items-center gap-1`. Navigates to question `currQ - 1` (disabled if `currQ === 1`).
- **Center / Right Group**:
  - `Mark for Review & Next (`.rev-btn`)`:
    - Styling: `px-6 py-2.5 rounded-xl text-xs md:text-sm font-semibold text-purple-700 bg-purple-50 hover:bg-purple-600 hover:text-white border border-purple-300 transition-all shadow-sm`.
    - Behavior: If answer selected, marks as *Answered & Marked for Review*; if blank, marks as *Marked for Review*. Advances to next question.
  - `Save & Next (`.nxt-btn`)`:
    - Styling: `px-7 py-2.5 rounded-xl text-xs md:text-sm font-bold text-white bg-primary-500 hover:bg-primary-600 active:bg-primary-700 transition-all shadow-md flex items-center gap-1`.
    - Behavior: If answer selected, saves response and marks *Answered*; if blank, marks *Not Answered*. Advances to next question.
    - **Dynamic Last Question Behavior**: On the final question of the examination, button label automatically transitions to **"Save & Finish"** with emerald accent.

---

## 8. Exam Submission & Finish Confirmation Modal (`#finish-modal`)

Clicking the red **"Submit Exam"** button (`bg-[#FF614D] hover:bg-[#e04f3d] text-white font-bold py-2.5 px-6 rounded-xl shadow-md`) opens the authoritative submission modal:

- **Modal Header**:
  - Title: `Finish Exam` / `Submit Answers` (`font-bold text-xl text-slate-800`).
  - Subtitle: `Please review your attempt summary before final submission.`
- **Summary Table Component**:
  - Table displaying attempt breakdown across every section:
    | Section | Total Qs | Answered | Not Answered | Marked for Review | Answered & Marked | Not Visited |
    |---|---|---|---|---|---|---|
    | **Mathematics** | 5 | 4 | 1 | 0 | 0 | 0 |
    | **Physics** | 5 | 3 | 0 | 1 | 1 | 0 |
    | **Chemistry** | 5 | 2 | 2 | 0 | 0 | 1 |
    | **Total** | **15** | **9** | **3** | **1** | **1** | **1** |
- **Warning Notice**:
  - Highlight banner: `bg-amber-50 border border-amber-200 text-amber-800 p-3 rounded-xl text-xs font-medium`.
  - Text: `"Are you sure you want to submit? You cannot return to the examination after final submission."`
- **Modal Actions**:
  - `Return to Exam`: Secondary button (`px-5 py-2 rounded-xl text-sm font-semibold text-slate-600 hover:bg-slate-100 border border-slate-300`).
  - `Submit Answers`: Primary CTA (`px-8 py-2.5 rounded-xl text-sm font-bold text-white bg-success-500 hover:bg-success-600 shadow-lg flex items-center justify-center gap-2`).
  - Submission triggers idempotent `POST /api/v1/attempts/{id}/submit/`, locks local state, clears timer, and redirects to submission acknowledgement / results view.

---

## 9. Proctoring, Resiliency & Recovery Architecture

### 9.1 Window Switch & Tab Blur Monitoring
- **Event Listeners**: Attached to `window.onblur` and `document.onvisibilitychange`.
- **Warning Threshold**:
  - Each time the candidate navigates away from the examination tab, the switch counter increments.
  - Triggers `#warning-modal` upon return:
    * Banner: `WARNING: Time spent outside Exam Tab/Window is being recorded!`
    * Switch Count: `Switched Outside Exam X times! (Allowed: 5)`
    * Button: `"I Understand"` (returns focus).
  - When switch count exceeds `num_switches` (default 5), invokes `autoFinalSubmit(true)` with message: `"Switched Exam Too Many Times! Auto-Submitting Responses now."`

### 9.2 Offline Persistence & Disconnect Recovery
- **Triple-Layer State Storage**:
  1. `React State`: In-memory reactive state for instant 60 FPS UI responsiveness.
  2. `localStorage`: Synchronous write on every option click, numpad keystroke, or navigation:
     * Key: `ezexam_${candidateId}_${examId}_responses` -> Array of responses.
     * Key: `ezexam_${candidateId}_${examId}_qTimeline` -> Traversed question history.
     * Key: `ezexam_${candidateId}_${examId}_timeline` -> Timestamp offsets.
     * Key: `ezexam_${candidateId}_${examId}_currQ` -> Current question pointer.
     * Key: `ezexam_${candidateId}_${examId}_txtboxes` -> Text/code drafts.
  3. `Server-Authoritative Sync`:
     * Background debounced HTTP sync (`POST /api/v1/attempts/{id}/save_response/`) every response change.
     * WebSocket heartbeat broadcast every 30 seconds for clock synchronization.
- **Crash / Refresh Resilience**:
  - If candidate refreshes browser, loses power, or disconnects:
    1. Page reloads and queries `localStorage`.
    2. Candidate session is restored to the exact question, saved responses, and elapsed server deadline without any lost data.

---

## 10. Features Discovered & Edge Cases

### Features Discovered
| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Examination Screen | Server Countdown Timer | Authoritative timer with visual warnings and auto-submit | Server start & duration | Formatted MM:SS display | On expiry: forces final submit | `check_qpap_47327.html` DOM |
| 2 | Examination Screen | 5-State Question Palette | Real-time tracking of Not Visited, Not Answered, Answered, Review, Answered & Review | Click events & response state | Color-coded palette buttons | Defaults to Not Visited | `check_qpap_47327.html` & CSS |
| 3 | Examination Screen | Section Tabs with Hover Tooltip | Tabbed section switcher showing question breakdown | Click tab, hover tab | Section switch, floating tooltip | Disabled if section skip off | `check_qpap_47327.html` DOM |
| 4 | Question Interaction | On-Screen Virtual Numpad | 3x4 grid for numerical answers with backspace and clear | Virtual button clicks | Formatted decimal/negative string | Disallows invalid decimals | `check_qpap_47327.html` DOM |
| 5 | Question Interaction | Dynamic "Save & Next" to "Save & Finish" | Button text transforms on last question | Question index pointer | Button label text change | None | Script #2 inspection |
| 6 | Proctoring | Window Switch Detection & Auto-Submit | Tracks window blur events with modal warning | Window blur event | Switch counter increment | On limit: autoFinalSubmit | Script #2 inspection |
| 7 | Submission | Pre-Submission Summary Table | Section-wise table of answer counts in submit modal | Click Submit Exam | Section breakdown summary | Disallows submission while submitting | `#finish-modal` inspection |
| 8 | Resilience | Triple-Layer Offline Recovery | Persists answers in LocalStorage, Cookie, and Server sync | Any response mutation | Updated LocalStorage keys | Fallback to LocalStorage on offline | Script #2 inspection |

### Edge Cases
| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | Timer Expiration | Timer reaches 00:00 while candidate typing | Disables inputs, sets title to `"Times Up!"`, immediately posts all saved responses |
| 2 | Tab Switching | Candidate switches to another tab | Warning modal opens immediately on focus return; increments `switch_count` |
| 3 | Clear Response on Numerical | Candidate clicks Clear All on numpad | Input cleared, status changes from Answered to Not Answered (`.qskipped`), `resps[currQ] = -1` |
| 4 | Rapid Double Clicking | Candidate double clicks Save & Next | Guard flag `submitting` or transition debounce prevents duplicate question advances |
| 5 | Partial Marking Multi-Correct | 2 out of 3 correct options picked, 0 incorrect | Awarded partial marks (`pmk * 2`); if 1 incorrect picked, immediately marked with negative penalty (`imk`) |
| 6 | Answered & Marked for Review | Candidate answers and clicks Review | Purple background + top-right green tick added; explicitly marked as evaluated in final score |
