# Runtime profile: Qwen/Qwen2.5-3B-Instruct / hf / none / {'platform': 'Linux-6.6.122+-x86_64-with-glibc2.35', 'system': 'Linux', 'machine': 'x86_64', 'processor': 'x86_64', 'python': '3.12.13', 'gpu': 'Tesla T4', 'cuda': True}

Overall: n=800, acc=0.64375, tok/s mean=10.8097 (med 17.8095, n=800)

## By task

| task | n | acc | tok/s mean | e2e ms mean | ttft ms mean | new tok mean |
|---|---|---|---|---|---|---|
| arc_easy | 200 | 0.96 | 2.9669 | 414.1107 | 337.8143 | 1.435 |
| gsm8k | 200 | 0.425 | 19.1102 | 12678.0639 | 343.5182 | 242.375 |
| hellaswag | 200 | 0.77 | 1.9615 | 791.7925 | 650.706 | 2.735 |
| mgsm | 200 | 0.42 | 19.2001 | 12237.0294 | 375.2439 | 235.03 |

## By language

| language | n | acc | tok/s mean |
|---|---|---|---|
| de | 67 | 0.38806 | 19.224 |
| en | 667 | 0.694153 | 9.1326 |
| fr | 66 | 0.393939 | 19.2167 |

Timing fields absent from an item are excluded from that statistic (counts in the JSON under n=0 entries); nothing is zero-filled. tok/s reflects the full stack, not the model alone.

_Provenance: DERIVED from measured per-item timing records_
