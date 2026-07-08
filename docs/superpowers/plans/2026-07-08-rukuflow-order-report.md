# RukuFlow Order Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static, local-first inbound order reporting system with a mobile form matching the provided screenshot and an admin order-detail view.

**Architecture:** The app is plain HTML, CSS, and JavaScript. `storage.js` owns validation, persistence, and formatting; `app.js` owns the customer form; `admin.js` owns the admin list/detail screen.

**Tech Stack:** HTML, CSS, vanilla JavaScript, browser `localStorage`, Node built-in test runner.

---

### Task 1: Data Model And Storage

**Files:**
- Create: `src/storage.js`
- Test: `tests/storage.test.mjs`

- [ ] Write failing tests for creating, validating, listing, and reading orders.
- [ ] Run `node --test tests/storage.test.mjs` and confirm missing module failure.
- [ ] Implement `createOrderStore`, `validateOrder`, and formatting helpers in `src/storage.js`.
- [ ] Re-run `node --test tests/storage.test.mjs` and confirm pass.

### Task 2: Customer Report Page

**Files:**
- Create: `index.html`
- Create: `src/app.js`
- Create: `src/styles.css`

- [ ] Build the screenshot-inspired mobile form with fields for WeChat name, delivery method, tracking numbers, total boxes, inbound details, total cans, phone, and remarks.
- [ ] Add dynamic detail rows with add, delete, collapse, and expand behavior.
- [ ] Submit valid orders into the shared store and show a success sheet.

### Task 3: Admin Page

**Files:**
- Create: `admin.html`
- Create: `src/admin.js`

- [ ] Show order list with submitter, logistics info, total boxes, total cans, status, and creation time.
- [ ] Show selected order detail including every inbound item.
- [ ] Add status update and clear-demo-data controls.

### Task 4: Verification And Usage

**Files:**
- Create: `README.md`

- [ ] Run `node --test`.
- [ ] Run a static local server.
- [ ] Verify the user form and admin page in a browser.
- [ ] Document how to use the system.
