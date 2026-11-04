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

## What I'm building toward

- A ledger that records every money movement
- Database rules that block negative balances
- Row locks, so two trades can't spend the same coins
- Idempotency keys, so a repeated request never pays twice
- Tests that prove each of these works

## Tech

Python, Django, Django REST Framework, PostgreSQL, Docker

## Running it locally
