"""E2: восстановить наблюдаемый процесс по журналу.

Запуск из папки практики:

    python E2/analyze.py

Пишет variants.csv, student_transitions.csv и таблицы в E2/data/.
Исходный students.csv не меняет.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SRC = ROOT / "students.csv"


def load():
    df = pd.read_csv(SRC)
    df["ts"] = pd.to_datetime(df["Timestamp"], utc=True).dt.tz_convert("Europe/Moscow")
    return df.sort_values(["ProcessInstanceId", "EventIndex", "ts"]).reset_index(drop=True)


def routes_and_edges(df):
    routes = {}
    edges = []
    examples = {}
    for pid, g in df.groupby("ProcessInstanceId", sort=False):
        g = g.sort_values("EventIndex")
        names = g.ActivityName.tolist()
        route = " > ".join(names)
        routes[pid] = route
        examples.setdefault(route, pid)
        for a, b in zip(names, names[1:]):
            edges.append((a, b, pid))
    return routes, edges, examples


def result_follows(df):
    """Следующая активность после каждого человеческих результата. Для проверки развилок."""
    rows = []
    for pid, g in df.groupby("ProcessInstanceId", sort=False):
        g = g.sort_values("EventIndex")
        names = g.ActivityName.tolist()
        results = g.Result.fillna("").tolist()
        types = g.EventType.tolist()
        for i in range(len(names) - 1):
            if types[i] != "task_completed":
                continue
            rows.append(
                {
                    "ActivityName": names[i],
                    "Result": results[i],
                    "Next": names[i + 1],
                }
            )
    return pd.DataFrame(rows)


def amount_gate(df):
    meta = (
        df.sort_values("EventIndex")
        .groupby("ProcessInstanceId", sort=False)
        .agg(Amount=("Amount", "first"), AmountN=("Amount", "nunique"))
    )
    reached = set(df.loc[df.ActivityName == "Проверка бюджета", "ProcessInstanceId"])
    extra = set(df.loc[df.ActivityName == "Дополнительное согласование", "ProcessInstanceId"])
    sub = meta.loc[list(reached)].copy()
    sub["Extra"] = sub.index.isin(extra)
    without = sub.loc[~sub.Extra, "Amount"]
    with_extra = sub.loc[sub.Extra, "Amount"]
    return {
        "amount_changes_inside_process": int((meta.AmountN > 1).sum()),
        "reached_budget": int(len(reached)),
        "with_extra": int(sub.Extra.sum()),
        "without_extra": int((~sub.Extra).sum()),
        "max_without_extra": float(without.max()) if len(without) else None,
        "min_with_extra": float(with_extra.min()) if len(with_extra) else None,
        "exact_150000": int((sub.Amount == 150000).sum()),
        "below_or_eq_150000_but_extra": int(((sub.Amount <= 150000) & sub.Extra).sum()),
        "above_150000_without_extra": int(((sub.Amount > 150000) & ~sub.Extra).sum()),
    }


def rework_stats(df):
    counts = (
        df[df.ActivityName == "Доработка заявки"]
        .groupby("ProcessInstanceId")
        .size()
    )
    return {str(k): int(v) for k, v in counts.value_counts().sort_index().items()}


def quality(df):
    sizes = df.groupby("ProcessInstanceId").size()
    ends = df[df.EventType == "process_completed"].groupby("ProcessInstanceId").size()
    starts = df[df.EventIndex == 1]
    human = df[df.EventType == "task_completed"]
    off = [
        (t.weekday() >= 5) or (t.hour < 9) or (t.hour >= 18)
        for t in human.ts
    ]
    return {
        "n_events": int(len(df)),
        "n_processes": int(df.ProcessInstanceId.nunique()),
        "events_per_process_min": int(sizes.min()),
        "events_per_process_max": int(sizes.max()),
        "all_have_one_end": bool((ends == 1).all() and ends.shape[0] == df.ProcessInstanceId.nunique()),
        "start_activity": starts.ActivityName.value_counts().to_dict(),
        "start_role": starts.Role.value_counts().to_dict(),
        "end_activity": df.loc[df.EventType == "process_completed", "ActivityName"].value_counts().to_dict(),
        "end_result": df.loc[df.EventType == "process_completed", "Result"].value_counts().to_dict(),
        "activities": df.ActivityName.value_counts().to_dict(),
        "activity_ids": df.groupby("ActivityName").ActivityId.nunique().to_dict(),
        "roles_by_activity": {
            name: g.Role.fillna("(empty)").value_counts().to_dict()
            for name, g in df.groupby("ActivityName")
        },
        "results_by_activity": {
            name: g.Result.fillna("(empty)").value_counts().to_dict()
            for name, g in df.groupby("ActivityName")
        },
        "index_gaps": int((df.groupby("ProcessInstanceId").EventIndex.diff().dropna() != 1).sum()),
        "time_reversals": int(
            (df.groupby("ProcessInstanceId").ts.diff().dt.total_seconds().dropna() < 0).sum()
        ),
        "human_off_hours": int(sum(off)),
        "template_versions": [int(x) for x in sorted(df.TemplateVersion.unique())],
        "ts_min": df.ts.min().isoformat(),
        "ts_max": df.ts.max().isoformat(),
    }


def follows_summary(follows):
    out = {}
    for (act, result), g in follows.groupby(["ActivityName", "Result"]):
        nxt = g.Next.value_counts().to_dict()
        out[f"{act} | {result}"] = nxt
    return out


def main():
    df = load()
    routes, edges, examples = routes_and_edges(df)
    route_s = pd.Series(routes, name="Route")
    counts = route_s.value_counts()
    n = len(route_s)
    variants = counts.rename_axis("Route").reset_index(name="NumberOfCases")
    variants.insert(0, "Variant", [f"V{i}" for i in range(1, len(variants) + 1)])
    variants["Share"] = (variants.NumberOfCases / n).round(4)
    # Доли после округления могут не дать 1. Храним точную долю отдельно и в csv
    # отдаём число от 0 до 1 с 4 знаками, последнюю строку не подгоняем:
    # сумма 0.567+0.188+0.117+0.045+0.026+0.021+0.018+0.018 = 1.000.
    assert int(variants.NumberOfCases.sum()) == n

    edge_df = pd.DataFrame(edges, columns=["SourceActivity", "TargetActivity", "ProcessInstanceId"])
    edge_counts = (
        edge_df.groupby(["SourceActivity", "TargetActivity"], sort=False)
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
    )
    transitions = edge_counts[["SourceActivity", "TargetActivity"]].drop_duplicates()

    follows = result_follows(df)
    gate = amount_gate(df)
    stats = {
        "quality": quality(df),
        "n_variants": int(len(variants)),
        "variants_cover_all": bool(variants.NumberOfCases.sum() == n),
        "share_sum": float(variants.Share.sum()),
        "examples": {route: examples[route] for route in counts.index},
        "rework_task_counts": rework_stats(df),
        "amount_gate": gate,
        "result_to_next": follows_summary(follows),
        "edge_counts": [
            {"source": r.SourceActivity, "target": r.TargetActivity, "count": int(r.Count)}
            for r in edge_counts.itertuples(index=False)
        ],
    }

    DATA.mkdir(exist_ok=True)
    variants.to_csv(ROOT / "variants.csv", index=False, encoding="utf-8")
    transitions.to_csv(ROOT / "student_transitions.csv", index=False, encoding="utf-8")
    edge_counts.to_csv(DATA / "transition_counts.csv", index=False, encoding="utf-8-sig")
    route_s.rename_axis("ProcessInstanceId").reset_index().to_csv(
        DATA / "process_routes.csv", index=False, encoding="utf-8-sig"
    )
    (DATA / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    from draw_scheme import draw

    draw()
    print("processes", n, "variants", len(variants), "edges", len(transitions))
    print(variants.to_string(index=False))
    print("amount", json.dumps(gate, ensure_ascii=False))
    print("rework", stats["rework_task_counts"])
    print("share sum", stats["share_sum"])


if __name__ == "__main__":
    main()
