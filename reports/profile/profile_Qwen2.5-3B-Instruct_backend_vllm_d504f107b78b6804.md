# Runtime profile: Qwen/Qwen2.5-3B-Instruct / vllm / none / {'platform': 'Linux-6.6.122+-x86_64-with-glibc2.35', 'system': 'Linux', 'machine': 'x86_64', 'processor': 'x86_64', 'python': '3.13.15', 'gpu': 'Tesla T4', 'cuda': True}

Overall: n=800, acc=0.6675, tok/s mean=n/a

## By task

| task | n | acc | tok/s mean | e2e ms mean | ttft ms mean | new tok mean |
|---|---|---|---|---|---|---|
| arc_easy | 200 | 0.965 | None | None | None | 2.43 |
| gsm8k | 200 | 0.415 | None | None | None | 241.665 |
| hellaswag | 200 | 0.775 | None | None | None | 3.31 |
| mgsm | 200 | 0.515 | None | None | None | 234.685 |

## By language

| language | n | acc | tok/s mean |
|---|---|---|---|
| de | 67 | 0.522388 | None |
| en | 667 | 0.697151 | None |
| fr | 66 | 0.515152 | None |

Timing fields absent from an item are excluded from that statistic (counts in the JSON under n=0 entries); nothing is zero-filled. tok/s reflects the full stack, not the model alone.

_Provenance: DERIVED from measured per-item timing records_
