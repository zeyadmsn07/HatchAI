# Payment Test Log — MOCKED

> All transactions below are simulations. No real money was moved.
> No payment processor SDK is installed. HMAC secret is a local mock.

## Checkout
- Order ID: `ord_7921f62a035d`
- Status: `paid`

## Idempotency (replay test)
- Replayed webhook status: `duplicate_replay`
- IDEMPOTENCY: PASS

## Refund
- Order: `ord_7921f62a035d`
- Token revoked: `True`
- REVOCATION: PASS

## Reconciliation
- Orders checked: 9
- Mismatches: []
- RECONCILIATION: PASS

## Summary
- IDEMPOTENCY: PASS
- REVOCATION: PASS
- RECONCILIATION: PASS