# Payment Test Log — MOCKED

> All transactions below are simulations. No real money was moved.
> No payment processor SDK is installed. HMAC secret is a local mock.

## Checkout
- Order ID: `ord_27176734e50b`
- Status: `paid`

## Idempotency (replay test)
- Replayed webhook status: `duplicate_replay`
- IDEMPOTENCY: PASS

## Refund
- Order: `ord_27176734e50b`
- Token revoked: `True`
- REVOCATION: PASS

## Reconciliation
- Orders checked: 7
- Mismatches: []
- RECONCILIATION: PASS

## Summary
- IDEMPOTENCY: PASS
- REVOCATION: PASS
- RECONCILIATION: PASS