# Operational Gaps and Assumptions

This document records answers to the infrastructure questions raised during the management audit. It should be updated whenever assumptions change.

## Hardware & OS
- **CPU model:** Intel Xeon (AVX2 available, AVX-512 not guaranteed).
- **NVMe endurance:** Development machines have >80% lifetime remaining. WAL bursts capped at 50MB/s to avoid wear.

## Network Path
- **RPC RTT:** ~80ms to public Solana RPC with negligible packet loss.
- **Peering:** Standard Internet; no dedicated lanes.

## Disk I/O
- **SQLite IOPS:** sustained writes tested up to 500 IOPS without throttling.
- **tmpfs:** Not used; database stored on local disk.

## Swap / OOM
- Docker containers limit memory to 1GB. OOM kills the Python process first.

## Time Sync
- NTP via `pool.ntp.org` checked at startup; drift must be <1s.

## Backup & DR
- Database backed up hourly via cron to encrypted S3 (RPO 1h). Restore tested on bare metal.

## Regulatory / Audit
- Order and balance logs retained 7 years. No PII stored.

## Incident Process
- PagerDuty alert on order latency or failed bootstrap. On-call engineer responds within 15m.

## Kill-Switch Governance
- Multisig wallet controls `TRADE_ENABLED` flag in config table.

## Third-Party Quotas
- Coingecko free tier: 50 calls/minute. Cache TTL set to 30s to stay below limit.

## Test-Net vs Main-Net
- Separate database paths for each environment to avoid contamination.

## Python Version
- Python 3.11.6 currently used; wheels pinned in `constraints.txt`.

## Dependency Risk
- `sqlmodel` pinned to 0.0.8; fork maintained internally if upstream is abandoned.

## Static Analysis Gates
- CI runs `ruff` and `mypy --strict`; failures block merge.

## Observability Endpoint Auth
- `/metrics` available only on localhost; mTLS optional for remote deployments.

## Hotfix Path
- Uvicorn reloads on SIGHUP allowing hot patches without downtime.

## Clock Skew
- `time.monotonic_ns` used for latency metrics ensuring monotonic order.

## Logging
- Structured JSON logs shipped to Loki; rotated daily.

## Latency Headroom
- 99.9% tick-to-order measured at 3ms locally, leaving 2ms headroom.
