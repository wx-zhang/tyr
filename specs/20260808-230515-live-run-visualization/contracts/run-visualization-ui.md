# Run Visualization UI Contract

## Shared workspace

The selected run route presents four synchronized views:

1. Progress overview with exact run/action state, phase and case progress, timestamps, blockers,
   unsettled Tyr work, pending approval count, and the derived Test cases or Scientist only mode.
2. Cursor-bounded chronological Updates timeline with authoritative sequence retained separately
   from the rendered or filtered order.
3. Native SVG observed-relationship graph plus a complete semantic relationship list.
4. Summary-first evidence inspector with an explicit control to request permitted redacted content.

Search and structured filters apply to the timeline and relationship projection. Selecting a
progress item, activity, participant, relationship, or evidence item updates the other views through
stable IDs. Overall run state and approval attention remain visible regardless of filters.

## Navigation and view state

- The route stays scoped to one `/runs/:id`.
- Search, filters, and a safe selected ID may use URL search parameters for reload/back behavior.
- Evidence content, credentials, server paths, and raw diagnostic values never enter the URL or
  persistent browser storage.
- If a selected item falls outside the loaded page or active filter, retain its identity and explain
  why it is not currently visible.
- Cross-run comparison and aggregate trends remain out of scope.

## Timeline and follow behavior

- Label the workspace “Updates.” Conversation entries retain their numbered turn titles, while
  evaluation entries use result titles and do not masquerade as agent/Tyr messages.
- Show case and scientist evaluations with Vulnerability Exposed, adding “(partial)” when the
  objective is partial, or No breach for protected outcomes. Keep objective status, execution
  outcome, and the redacted assessment summary as supporting information.
- Render a semantic ordered list with type, source/destination when observed, timestamp, status,
  phase/case, summary, and evidence availability.
- Load at most the contract page size and expose explicit older/newer navigation plus omitted counts.
- Follow live updates only while the reader is at the current end. Otherwise retain position and show
  the number of newer items with a “Show newer activity” control.
- Merge snapshots and SSE notifications by stable activity ID and sequence. Never display duplicates.
- Connected, reconnecting, stale, and disconnected states use visible text. Known persisted state
  remains visible during interruption.
- Scientist generation entries show the case IDs used from run history. Scientist-only entries show
  an explicit “No prior tests were available” state when the history is empty.
- The Updates section keeps the selected test-case list visible as persistent run context while new
  timeline messages arrive or replace the bounded latest page.
- A resync-required signal fetches the persisted REST snapshot/page after the last known sequence;
  it does not discard known state or request an unbounded SSE backlog.

## Relationship graph

- Use deterministic participant-kind lanes and stable participant ordering.
- Use text, count, shape, and status labels; color is supplementary.
- SVG selections support focus plus Enter/Space. The adjacent semantic relationship list exposes the
  same labels, counts, types, states, and selection action.
- Selecting an aggregate applies its relationship token to the paged timeline so every contributing
  permitted activity remains discoverable.
- Unknown participants and unavailable relationships are labeled explicitly. The graph never infers
  topology from timestamps or display-name equality.

## Evidence inspector

- Initial selection shows provenance, summary, availability, and content size when known.
- Complete content is absent until the user invokes “Reveal redacted evidence.”
- Revealed content is labeled redacted and remains redacted in visible, collapsed, copied, and
  accessible forms.
- Missing, withheld, omitted, malformed, oversized, and entirely redacted states remain distinct.
- Oversized permitted content uses a safe run-scoped download action without exposing a server path.
- The inspector never renders or copies server paths, credentials, authorization values,
  idempotency keys, or server-only diagnostic fields.

## Accessibility and responsive behavior

- All operations work with keyboard only and preserve visible focus.
- The semantic progress, timeline, relationship list, and inspector remain complete without SVG.
- A restrained polite live region announces phase changes, approvals, connection changes, and the
  count of newer items, not every streamed activity.
- Reduced motion disables pulses, animated graph transitions, and smooth automatic scrolling.
- On narrow screens the four views stack in document order; the inspector becomes an in-flow region,
  not an inaccessible overlay.
