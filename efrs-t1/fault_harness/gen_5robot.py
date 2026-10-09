"""Emit 5-robot + I2 schedule JSONs (run on host, no ROS needed)."""

import json
import sys

sys.path.insert(0, "/home/gamer/RuleSync-Fleet/efrs-t1/fault_harness")
from schedules_5robot import schedule_i2, schedules_5robot

if __name__ == "__main__":
    import sys as _s

    outdir = _s.argv[1]
    n = 0
    for p in ("efrs",):
        for name, s in schedules_5robot(p).items():
            s = dict(s)
            s["protocol"] = p
            json.dump(s, open(f"{outdir}/sched-{p}-{name}.json", "w"),
                      indent=1)
            n += 1
    i2 = dict(schedule_i2("efrs"))
    i2["protocol"] = "efrs"
    json.dump(i2, open(f"{outdir}/sched-efrs-I2.json", "w"), indent=1)
    print(f"wrote {n + 1} schedules")
