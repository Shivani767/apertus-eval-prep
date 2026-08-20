# Wilson CI width vs n

Not the paper matrix. Prefix Wilson intervals on already-scored items.
The n=4 T4 smoke is supposed to have a huge interval; n=28 is still wide.

## Width at the end of each run

| run | n | accuracy | 95% Wilson CI | width |
|---|---:|---:|---|---:|
| T4 smoke n=4 | 4 | 0.25 | [0.0456, 0.6994] | 0.6538 |
| Mac canary n=28 | 28 | 0.7143 | [0.5294, 0.8475] | 0.3181 |

## Prefix curve (selected n)

### T4 smoke n=4

| n | correct | acc | lo | hi | width |
|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 0.0 | 0.0 | 0.7935 | 0.7935 |
| 2 | 1 | 0.5 | 0.0945 | 0.9055 | 0.8109 |
| 4 | 1 | 0.25 | 0.0456 | 0.6994 | 0.6538 |

### Mac canary n=28

| n | correct | acc | lo | hi | width |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 1.0 | 0.2065 | 1.0 | 0.7935 |
| 2 | 2 | 1.0 | 0.3424 | 1.0 | 0.6576 |
| 4 | 4 | 1.0 | 0.5101 | 1.0 | 0.4899 |
| 8 | 8 | 1.0 | 0.6756 | 1.0 | 0.3244 |
| 16 | 10 | 0.625 | 0.3864 | 0.8152 | 0.4288 |
| 28 | 20 | 0.7143 | 0.5294 | 0.8475 | 0.3181 |

A rank reversal inside overlapping CIs is not evidence. That is the demo.
