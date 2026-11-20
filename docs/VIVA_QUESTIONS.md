# IRSD Research Edition — Demonstration and Viva Topics

1. Why is the graph edge's `weight` kept separate from `propagation_delay_ms`?
2. Why is BFS an appropriate minimum-hop baseline only for an unweighted interpretation?
3. How does Static Dijkstra differ from Dynamic Dijkstra in the simulator?
4. What does it mean to freeze one destination-specific forwarding entry per router at simulation time zero?
5. How does a link failure affect a packet during serialization versus after propagation has begun?
6. How is serialization delay calculated from packet size and link capacity?
7. Why does the simulator use separate FIFO queues for each direction of an undirected link?
8. What is the difference between packet delivery ratio and authentication success rate?
9. What does Ed25519 provide? What does SHA-256 bind into the packet envelope?
10. Why does Ed25519 authentication not provide confidentiality?
11. How do nonce and replay-cache checks reject a duplicate packet?
12. Why must algorithms share a topology snapshot, traffic schedule and matched random seed in a paired comparison?
13. What does a 95% confidence interval describe, and why is no interval shown for one repetition?
14. What is the limitation of measuring signing/verification time using local wall-clock timers?
15. Which simulation features are not modelled, and how do those limitations affect research claims?
