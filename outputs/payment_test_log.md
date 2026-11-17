# Payment Test Log — MOCKED

> Evidence mode: REPLAY of evidence_snapshots/strong_scenario.json (captured 2026-11-17T15:52:54+00:00); no evidence was collected in this run
> LLM mode: LLM_DISABLED (no LLM was called in this run)
> Scoring version: v1 (relevance: any idea keyword + category vocabulary)

> All transactions below are simulations. No real money was moved.
> No payment processor SDK is installed. HMAC secret is a local mock.

## Checkout
- Order ID: `ord_663fe24b5ce3`
- Status: `paid`

## Idempotency (replay test)
- Replayed webhook status: `duplicate_replay`
- IDEMPOTENCY: PASS

## Refund
- Order: `ord_663fe24b5ce3`
- Token revoked: `True`
- REVOCATION: PASS

## Reconciliation
- Orders checked: 1
- Mismatches: []
- RECONCILIATION: PASS

## Summary
- IDEMPOTENCY: PASS
- REVOCATION: PASS
- RECONCILIATION: PASS