"""Claude Code statusLine girdisini kota uygulamasının okuyacağı dosyaya yazar."""

from datetime import datetime
import json
import os
from pathlib import Path
import sys


def main() -> int:
    try:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        ham = sys.stdin.buffer.read()
        veri = json.loads(ham.decode("utf-8", errors="replace"))
        if not isinstance(veri, dict) or not isinstance(veri.get("rate_limits"), dict):
            print("")
            return 0
        rate_limits = veri["rate_limits"]
        if not any(isinstance(rate_limits.get(a), dict) for a in ("five_hour", "seven_day")):
            print("")
            return 0
        yol = Path(os.environ.get("KOTA_CLAUDE_DURUM") or (Path.home() / ".kota" / "claude_durum.json"))
        yol.parent.mkdir(parents=True, exist_ok=True)
        yazilacak = {
            "kaynak": "statusline",
            "yazildi": datetime.now().astimezone().replace(microsecond=0).isoformat(),
            "rate_limits": rate_limits,
        }
        tmp = yol.with_name(yol.name + ".tmp")
        tmp.write_text(json.dumps(yazilacak, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, yol)
        parcalar = []
        for alan, etiket in (("five_hour", "5s"), ("seven_day", "hafta")):
            pencere = rate_limits.get(alan)
            if isinstance(pencere, dict) and isinstance(pencere.get("used_percentage"), (int, float)):
                parcalar.append(f"{etiket} %{round(pencere['used_percentage'])}")
        print("Claude " + " · ".join(parcalar))
    except Exception:
        try:
            print("")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
