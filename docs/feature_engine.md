# Feature Engine

This module maintains a 256\-dimension feature vector composed of the
current normalised features and two lagged slots.  Statistics are updated in
place and the returned array is backed by an internal buffer which is mutated on
every `update`.  **Consumers must use the result before calling `update`
again.** The engine is **not thread safe** and should only be accessed from a
single event loop.

`snapshot()` returns a defensive copy of the concatenated vector for archival or
asynchronous use.

## Feature Indices 0–63

| Index | Name | Category | Description |
| --- | --- | --- | --- |
| 0 | L1 | Liquidity | Signed liquidity \u0394 reserve_a+reserve_b |
| 1 | L2 | Liquidity | Log cumulative liquidity |
| 2 | O1 | OrderFlow | Cumulative signed swap size |
| 3 | O2 | OrderFlow | Cumulative absolute swap size |
| 4 | O3 | OrderFlow | Inverse inter-arrival time (ms) |
| 5 | H1 | Ownership | Total minted amount |
| 6 | L3 | Liquidity | reserved |
| 7 | L4 | Liquidity | reserved |
| 8 | L5 | Liquidity | reserved |
| 9 | L6 | Liquidity | reserved |
| 10 | L7 | Liquidity | reserved |
| 11 | L8 | Liquidity | reserved |
| 12 | L9 | Liquidity | reserved |
| 13 | L10 | Liquidity | reserved |
| 14 | L11 | Liquidity | reserved |
| 15 | L12 | Liquidity | reserved |
| 16 | L13 | Liquidity | reserved |
| 17 | L14 | Liquidity | reserved |
| 18 | L15 | Liquidity | reserved |
| 19 | L16 | Liquidity | reserved |
| 20 | L17 | Liquidity | reserved |
| 21 | L18 | Liquidity | reserved |
| 22 | L19 | Liquidity | reserved |
| 23 | L20 | Liquidity | reserved |
| 24 | O3 | OrderFlow | reserved |
| 25 | O4 | OrderFlow | reserved |
| 26 | O5 | OrderFlow | reserved |
| 27 | O6 | OrderFlow | reserved |
| 28 | O7 | OrderFlow | reserved |
| 29 | O8 | OrderFlow | reserved |
| 30 | O9 | OrderFlow | reserved |
| 31 | O10 | OrderFlow | reserved |
| 32 | O11 | OrderFlow | reserved |
| 33 | O12 | OrderFlow | reserved |
| 34 | O13 | OrderFlow | reserved |
| 35 | O14 | OrderFlow | reserved |
| 36 | O15 | OrderFlow | reserved |
| 37 | O16 | OrderFlow | reserved |
| 38 | O17 | OrderFlow | reserved |
| 39 | O18 | OrderFlow | reserved |
| 40 | H2 | Ownership | reserved |
| 41 | H3 | Ownership | reserved |
| 42 | H4 | Ownership | reserved |
| 43 | H5 | Ownership | reserved |
| 44 | H6 | Ownership | reserved |
| 45 | H7 | Ownership | reserved |
| 46 | H8 | Ownership | reserved |
| 47 | H9 | Ownership | reserved |
| 48 | M1 | Microstructure | reserved |
| 49 | M2 | Microstructure | reserved |
| 50 | M3 | Microstructure | reserved |
| 51 | M4 | Microstructure | reserved |
| 52 | M5 | Microstructure | reserved |
| 53 | M6 | Microstructure | reserved |
| 54 | M7 | Microstructure | reserved |
| 55 | M8 | Microstructure | reserved |
| 56 | M9 | Microstructure | reserved |
| 57 | M10 | Microstructure | reserved |
| 58 | M11 | Microstructure | reserved |
| 59 | M12 | Microstructure | reserved |
| 60 | M13 | Microstructure | reserved |
| 61 | M14 | Microstructure | reserved |
| 62 | M15 | Microstructure | reserved |
| 63 | M16 | Microstructure | reserved |

Indices 64–255 are presently zero and reserved for future use.

## Metrics

Two Prometheus metrics are exported:

* `feature_update_latency_us` (Summary)
* `fv_nan_count` (Gauge)

Enable `FEATURE_TRACE=1` to record the last 100 index updates for debugging.
