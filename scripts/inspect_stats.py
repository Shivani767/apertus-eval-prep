"""Print a readable summary of paper/analysis/statistics.json (debug aid)."""
import json
import sys

d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "paper/analysis/statistics.json"))

print("=== CONTROL ===")
for m, c in d["control"].items():
    print(f"{m:14s} acc={c['accuracy']:.4f} CI={c['ci95']} correct={c['correct']}/{c['n']}")

print("\n=== CONTRASTS ===")
for c in d["contrasts"]:
    print(f"{c['model']:14s} {c['factor']:13s} {c['level']:12s} "
          f"d={c['delta_pp']:+7.2f}pp h={c['cohens_h']:+.3f} "
          f"p={c['mcnemar']['p_value']:<9} holm={c['p_holm']:<9} bh={c['p_bh']} "
          f"A-B={c['mcnemar']['a_correct_b_wrong']}/B-A={c['mcnemar']['a_wrong_b_correct']}")

print("\n=== TAU VS CONTROL ===")
for t in d["ranking"]["tau_vs_control"]:
    print(t["config"], "tau=", t["tau_b"], "rev=", t["reversals"], "ranks=", t.get("ranks"))

print("\nWIN RATES:", d["ranking"]["pairwise_win_rates"])
print("BOOTSTRAP:", d["ranking"]["bootstrap"])
print("RANK DISTRIBUTIONS:", json.dumps(d["ranking"]["rank_distributions"], indent=1))
print("ERS:", d["ers"]["matrix_8_configs"])
print("SEED-ERS:", d["ers"]["with_seed_component"])

print("\n=== H2H Phi vs Qwen-3B ===")
for h in d["ranking"]["phi_vs_qwen_head_to_head"]:
    print(f"{h['config']:22s} Phi {h['phi_acc']:.4f} Qwen {h['qwen_acc']:.4f} "
          f"diff {h['phi_minus_qwen_pp']:+6.2f}pp disjoint={h['ci_disjoint']} winner={h['winner']}")

print("\n=== FACTOR SENSITIVITY ===")
print(json.dumps(d["factor_sensitivity"], indent=1))

print("\n=== SAMPLING ===")
print(json.dumps(d["sampling"], indent=1))

print("\n=== LATENCY (HF control, measured) ===")
for k, v in d["latency"].items():
    print(k, v["status"], "ttft=", v["ttft_ms_mean"], "e2e=", v["e2e_ms_mean"], "tok/s=", v["tokens_per_sec_mean"])

print("\n=== FAILURE TAXONOMY (nonzero categories only) ===")
for k, v in d["failures"].items():
    nz = {c: n for c, n in v["counts"].items() if n}
    print(f"{k:28s} {nz}")

print("\n=== PROVENANCE ===")
p = d["provenance"]
print("cells:", p["n_registry_ok"], "/", p["n_planned_t4_cells"],
      " missing:", p["n_missing_cells"])
print("UTC window:", p["utc_first"], "..", p["utc_last"])
print("n git commits:", len(p["git_commits"]))
print("revisions recorded:", p["model_revisions_recorded"])
print("corrections:", p["corrections_in_registry"])
