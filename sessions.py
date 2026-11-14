#!/usr/bin/env python3
"""sessions.py — 按设备把读数流切成会话并聚合输出。

用法: python3 sessions.py [readings.jsonl] [outdir]
默认:  /workspace/readings.jsonl -> /workspace/out/

边界口径(全部写进输出, 可复算):
  * 切断: 同设备相邻两点 gap = ts - last_ts, gap > 1800s 才切断;
    gap == 1800s(恰好30分钟)的那一拍仍属同一会话。cut_rule 列记 "gap>1800"。
  * 处理顺序: 严格按文件行序(到达顺序), 不做全局 ts 排序。
  * 时钟回拨: ts < 活动会话 last_ts 的点, 若命中某已关闭会话窗口 [start,end]
    -> 重开该会话合并(sid 沿用, 每批迟到点 reopen+1);
    否则记 clock_rollback 进 anomalies.csv, 不进任何聚合。
  * 缺测(无 val 字段): 点计入 cnt, 但 min/max/avg 只对有效值聚合;
    含缺测的会话四要素不全 -> 判无效入 invalid.csv。
  * 流结束时仍未切断的会话 state=open, 其余 closed。
"""
import csv
import json
import sys
from datetime import datetime, timezone

CUT_SECONDS = 1800
CUT_RULE = "gap>1800"  # 静默超过30分钟切断; 恰满30分钟不切断


def iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_session(dev, seq, ts, val):
    return {
        "sid": f"{dev}-S{seq:03d}",  # {dev}-S{创建序号, 三位补零}
        "dev": dev,
        "start": ts,
        "end": ts,          # 会话内最后一拍的 ts (last_ts)
        "cnt": 1,           # 全部点数(含缺测)
        "missing": 0 if val is not None else 1,
        "nval": 0,          # 有效读数点数
        "sum": 0.0,
        "min": None,
        "max": None,
        "reopen": 0,        # 重开批次数
        "state": None,
        "cut_gap": None,    # 触发切断的 gap 秒数(open 会话为空)
    }


def add_point(s, ts, val):
    """把一拍并入会话 s (不改动 start/end 的调用方负责边界)。"""
    s["cnt"] += 1
    if val is None:
        s["missing"] += 1
    else:
        s["nval"] += 1
        s["sum"] += val
        s["min"] = val if s["min"] is None else min(s["min"], val)
        s["max"] = val if s["max"] is None else max(s["max"], val)


def run(input_path):
    devs = {}       # dev -> {active, closed, seq}
    anomalies = []  # clock_rollback / malformed 行
    reopens = []    # 重开合并且被吸收的迟到点
    malformed = 0

    with open(input_path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):  # 行号自一起计
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                dev, ts = rec["dev"], rec["ts"]
            except (ValueError, KeyError, TypeError):
                malformed += 1
                anomalies.append([line_no, "", "", line[:80], "malformed",
                                  "", "", "unparseable record; skipped"])
                continue
            val = rec.get("val")  # 缺测: 无 val 字段
            st = devs.setdefault(dev, {"active": None, "closed": [], "seq": 0,
                                       "last_reopen_sid": None})
            a = st["active"]

            if a is None:
                st["seq"] += 1
                a = new_session(dev, st["seq"], ts, val)
                if val is not None:
                    a["nval"], a["sum"], a["min"], a["max"] = 1, float(val), val, val
                st["active"] = a
                continue

            if ts < a["end"]:
                # 回拨形态: 先查是否命中某个已关闭会话的窗口 -> 重开合并
                cand = [s for s in st["closed"] if s["start"] <= ts <= s["end"]]
                if cand:
                    s = min(cand, key=lambda s: abs(ts - s["end"]))
                    add_point(s, ts, val)
                    if st["last_reopen_sid"] != s["sid"]:  # 每批迟到点 reopen+1
                        s["reopen"] += 1
                    st["last_reopen_sid"] = s["sid"]
                    reopens.append([line_no, dev, s["sid"], ts,
                                    val if val is not None else "",
                                    s["reopen"], s["reopen"]])
                else:
                    anomalies.append([line_no, dev, ts,
                                      val if val is not None else "",
                                      "clock_rollback", a["end"], ts - a["end"],
                                      "ts earlier than active session last_ts; "
                                      "no closed-session window match"])
                continue

            st["last_reopen_sid"] = None
            gap = ts - a["end"]
            if gap > CUT_SECONDS:  # 切断口径: 严格大于; ==1800 仍同一会话
                a["state"], a["cut_gap"] = "closed", gap
                st["closed"].append(a)
                st["seq"] += 1
                a = new_session(dev, st["seq"], ts, val)
                if val is not None:
                    a["nval"], a["sum"], a["min"], a["max"] = 1, float(val), val, val
                st["active"] = a
            else:
                a["end"] = ts
                add_point(a, ts, val)

    # 收尾: 流结束时仍活动的会话记 open
    sessions, invalid = [], []
    for dev in sorted(devs):
        st = devs[dev]
        if st["active"] is not None:
            st["active"]["state"] = "open"
            all_s = st["closed"] + [st["active"]]
        else:
            all_s = st["closed"]
        for s in sorted(all_s, key=lambda s: s["start"]):
            s["avg"] = round(s["sum"] / s["nval"], 6) if s["nval"] else None
            # 四要素: 起止时刻 / 点数 / 极值(含avg) / 状态, 缺一即无效
            if s["missing"] > 0 or s["nval"] == 0:
                s["reason"] = "missing_extremes"
                invalid.append(s)
            else:
                sessions.append(s)
    return sessions, invalid, anomalies, reopens, malformed


def sess_row(s):
    return [s["sid"], s["dev"], s["start"], s["end"], s["cnt"],
            s["min"], s["max"], s["avg"], s["state"], s["reopen"],
            s["nval"], s["sum"],
            s["cut_gap"] if s["cut_gap"] is not None else "",
            CUT_RULE, iso(s["start"]), iso(s["end"])]


def main():
    input_path = sys.argv[1] if len(sys.argv) > 1 else "/workspace/readings.jsonl"
    outdir = sys.argv[2] if len(sys.argv) > 2 else "/workspace/out"
    import os
    os.makedirs(outdir, exist_ok=True)

    sessions, invalid, anomalies, reopens, malformed = run(input_path)

    with open(f"{outdir}/session.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sid", "dev", "start", "end", "cnt", "min", "max", "avg",
                    "state", "reopen", "nval", "sum", "cut_gap_s", "cut_rule",
                    "start_iso", "end_iso"])
        for s in sessions:
            w.writerow(sess_row(s))

    with open(f"{outdir}/invalid.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sid", "dev", "start", "end", "cnt", "missing", "reason",
                    "min", "max", "avg", "state", "reopen", "nval", "sum",
                    "cut_gap_s", "cut_rule", "start_iso", "end_iso"])
        for s in invalid:
            w.writerow([s["sid"], s["dev"], s["start"], s["end"], s["cnt"],
                        s["missing"], s["reason"], s["min"], s["max"], s["avg"],
                        s["state"], s["reopen"], s["nval"], s["sum"],
                        s["cut_gap"] if s["cut_gap"] is not None else "",
                        CUT_RULE, iso(s["start"]), iso(s["end"])])

    with open(f"{outdir}/anomalies.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["line", "dev", "ts", "val", "reason", "ref_ts",
                    "delta_s", "detail"])
        w.writerows(anomalies)

    with open(f"{outdir}/reopens.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["line", "dev", "sid", "ts", "val",
                    "reopen_seq", "session_reopen_total"])
        w.writerows(reopens)

    rules = {
        "input": input_path,
        "cut_seconds": CUT_SECONDS,
        "cut_convention": "gt",
        "cut_rule": CUT_RULE,
        "boundary_note": "gap == cut_seconds 的那一拍延续(恰满30分钟仍同一会话); "
                         "仅 gap 更大才切断",
        "processing_order": "文件行序(到达顺序), 不做全局 ts 排序",
        "rollback_rule": "ts < 活动会话 last_ts 且不命中任何已关闭会话窗口 "
                         "-> clock_rollback, 不进聚合",
        "reopen_rule": "回拨形态点的 ts 命中某已关闭会话 [start,end] -> 重开该会话, "
                       "sid 沿用, 每批迟到点 reopen+1",
        "missing_val_rule": "缺值点计入 cnt, 但 min/max/avg 只对有效值聚合 -> "
                            "会话四要素不全, 判无效",
        "avg_decimals": 6,
        "sid_rule": "{dev}-S{该设备会话创建序号, 从1起, 三位补零}",
        "state_values": ["open (流结束时仍活动)", "closed (已被静默切断)"],
        "validity_elements": ["start/end", "cnt", "min/max/avg", "state"],
        "counts": {
            "input_lines": sum(1 for _ in open(input_path)),
            "valid_sessions": len(sessions),
            "invalid_sessions": len(invalid),
            "anomaly_rows": len(anomalies),
            "clock_rollback": sum(1 for r in anomalies if r[4] == "clock_rollback"),
            "malformed_records": malformed,
            "reopen_events": len(reopens),
            "reopened_sessions": sum(1 for s in sessions + invalid if s["reopen"]),
        },
    }
    with open(f"{outdir}/rules.json", "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    print(f"valid={len(sessions)} invalid={len(invalid)} "
          f"anomalies={len(anomalies)} reopens={len(reopens)} -> {outdir}/")


if __name__ == "__main__":
    main()
