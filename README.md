# Escrow API

A small peer-to-peer (P2P) escrow API built with Django REST Framework.

I'm building this to learn how payment systems keep money safe: locking funds,
recording every movement, and stopping double payments. It uses fake balances
only. No real crypto or payments are involved.

## Status

Work in progress. I'm building it step by step, and this README will grow with the code.

## How a trade works

1. A seller posts an offer to sell coins at a set price.
2. A buyer starts a trade, and the seller's coins are locked in escrow.
3. The buyer pays the seller outside the platform, then marks the trade as paid.
4. The seller confirms the money arrived and releases the coins to the buyer.

A trade can also be **cancelled** (the coins go back to the seller) or
**disputed** (the coins stay locked until the dispute is settled).

## Done so far

- Wallets with separate available and locked balances
- A ledger that records every coin movement, with reconciliation checks
- Database rules that block negative balances and invalid trades
- Row locks (`select_for_update`) so two requests can't spend the same coins
- Ordered locking across two wallets to avoid deadlocks
- A trade state machine: only allowed moves, only by allowed people
- An audit log of every trade move and who made it
- 20 tests, including double release and "coins are never created or destroyed"

## Next

- REST API with login
- Idempotency keys, so a repeated request never pays twice
- A test that fires two requests at the same moment
- Database indexes, with notes on why each one exists
- Docker setup for the whole app, and GitHub Actions

## Tech

Python, Django, Django REST Framework, PostgreSQL, Docker

## Running it locally
