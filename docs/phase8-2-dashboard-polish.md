# Phase 8.2 — comparison dashboard polish

Phase 8.2 improves the readability of multi-provider experiments without changing provider
execution behaviour.

## Improvements

- comparison cards use two columns instead of squeezing every provider into one row
- configured provider labels replace raw provider identifiers
- success and failure badges make partial comparison results easier to scan
- a compact summary table keeps status, latency, token usage, and estimated cost together
- numeric values use separators and retain their complete units and precision
- two-column cards collapse naturally on narrow Streamlit layouts

Provider failures remain isolated to their own cards, and every successful result keeps its full
model output.
