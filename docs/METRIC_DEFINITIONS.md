# Metric Definitions

All metrics are computed from simulator events and packet outcomes. They are not measurements from physical routers.

| Metric | Definition | Interpretation |
|---|---|---|
| Generated packets | Number of packet-generation events | Experiment denominator |
| Network-delivered packets | Packets that reached the destination node | Includes packets later rejected by security validation |
| Packet delivery ratio (PDR) | Network-delivered / generated | End-to-end network delivery fraction |
| Packet loss ratio | (Generated - network-delivered) / generated | Network delivery failure fraction; security rejection is not network loss |
| Throughput (Mbps) | Network-delivered payload bits / measurement window in seconds / 1,000,000 | Excludes protocol/control overhead |
| Mean latency | Arithmetic mean of destination-arrival time minus generation time | Includes packets that fail authentication after arriving |
| Median latency | Median of the same destination-arrival latency samples | Robust center statistic |
| 95th-percentile latency | Nearest-rank 95th percentile of destination-arrival latencies | Upper-tail latency summary |
| Queue overflow | Packets rejected because their directed-link queue occupancy reached its configured capacity | Capacity counts queued and currently serialized packets |
| Hop attempts | Number of packet transmissions started on a directed output link | Includes a packet's final edge attempt when that packet is subsequently lost on the link |
| Bytes serialized | Sum of payload bytes whose link serialization completed | Includes packets that are later lost during propagation; this is not destination-delivered payload throughput |
| Lost-on-edge location | Link endpoints recorded by `packet_lost_on_link` | Identifies where an in-flight per-packet fault or configured link loss occurred |
| TTL expiry | Packets whose hop count reached TTL before another forwarding step | Classified separately from link loss/failure |
| Route recalculations | Per-packet route calculation after a topology version change or forced retry | Not a count of control-plane routing messages |
| Route recovery time | First successful destination delivery of a packet whose route changed after the first scheduled failure, minus that failure time | A packet-level outcome, not control-plane convergence |
| Signing time | Wall-clock duration of an Ed25519 signing operation | Environment/runtime dependent |
| Verification time | Wall-clock duration of an Ed25519 verification operation | Includes repeated/duplicate verification attempts where applicable |
| Verification success rate | Authenticated packets / network-delivered packets when security is enabled | `null`/N/A when security is disabled or no packet reached destination |
| Security rejection count | Network-delivered packets rejected by signature, digest, expiry or replay checks | Kept separate from network packet loss |
| Replay rejected duplicates | Duplicate/replay injection attempts rejected by the run-local nonce cache | Additional verification attempts, not additional original packets |
| Edges explored | Adjacency entries examined by path-search operations | Counts directed adjacency examinations, not unique physical edges |

## Measurement window

The measurement window is at least the configured traffic-generation duration and extends to the latest packet terminal time if in-flight packets finish later.

## Confidence intervals

For `n >= 2`, the mean's two-sided 95% confidence interval is:

`mean ± t(0.975, n−1) × sample_sd / sqrt(n)`

The Student-t critical value is calculated numerically. No confidence interval is produced for `n=1`.

## Paired differences

For matching repetition and seed, the paired difference is:

`candidate metric − reference metric`

The 95% interval is computed on the set of paired differences. Positive values do not always indicate improvement; interpretation depends on the metric (for example, higher PDR is generally better, lower latency is generally better).
