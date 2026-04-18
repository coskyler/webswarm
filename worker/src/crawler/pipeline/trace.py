import time

class Trace:
    def __init__(self):
        self.start_time = time.time()
        self.steps = []

    def add(self, step, **data):
        self.steps.append({
            "t": time.time(),
            "step": step,
            **data
        })

    def to_string(self):
        base = self.start_time
        lines = []

        for e in self.steps:
            dt = e["t"] - base
            step = e["step"]
            parts = []
            for k, v in e.items():
                if k in {"t", "step"}:
                    continue
                if k == "attempts":
                    for attempt in v:
                        n = attempt.get("attempt")
                        info = ", ".join(
                            f"{ak}={av}" for ak, av in attempt.items() if ak != "attempt"
                        )
                        parts.append(f"attempt-{n}=({info})")
                else:
                    parts.append(f"{k}={v}")
            meta = " ".join(parts)
            line = f"[{dt:.2f}s] {step:<16} {meta}".rstrip()
            lines.append(line)

        return "\n".join(lines)
