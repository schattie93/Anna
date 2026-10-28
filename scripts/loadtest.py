#!/usr/bin/env python3
"""Einfacher Lasttest gegen einen laufenden PhysioFlow-Server.

  python scripts/loadtest.py --url https://physioflow.local --user demo --password ... --users 8 --seconds 30 [--write] [--insecure]

Jeder virtuelle Benutzer meldet sich an und führt in einer Schleife typische Abläufe aus (Übersicht, Patientensuche,
Akte öffnen, Kalender). Mit --write werden zusätzlich Befunde an einem eigenen Testpatienten angelegt (ändert Daten!).
Ausgabe: Anzahl, Fehler und Antwortzeiten (Median, 95 %, 99 %) je Endpunkt. Benötigt: pip install httpx
"""

import argparse
import random
import statistics
import threading
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

import httpx

lock = threading.Lock()
timings: dict[str, list[float]] = defaultdict(list)
errors: dict[str, int] = defaultdict(int)


def record(name: str, seconds: float, ok: bool) -> None:
    with lock:
        timings[name].append(seconds)
        if not ok:
            errors[name] += 1


def call(client: httpx.Client, name: str, method: str, path: str, **kw) -> httpx.Response | None:
    start = time.perf_counter()
    try:
        r = client.request(method, path, **kw)
        record(name, time.perf_counter() - start, r.status_code < 400)
        return r
    except httpx.HTTPError:
        record(name, time.perf_counter() - start, False)
        return None


def worker(args, stop: float, test_patient: int | None) -> None:
    with httpx.Client(base_url=args.url.rstrip("/"), headers={"X-PhysioFlow": "1"}, verify=not args.insecure, timeout=30) as c:
        r = call(c, "login", "POST", "/api/auth/login", json={"username": args.user, "password": args.password})
        if not r or r.status_code != 200:
            print("Anmeldung fehlgeschlagen – Abbruch dieses Benutzers")
            return
        patients = (call(c, "patient search", "GET", "/api/patients", params={"q": ""}) or r).json() or []
        ids = [p["id"] for p in patients if isinstance(p, dict)] or [1]
        while time.time() < stop:
            call(c, "dashboard", "GET", "/api/dashboard")
            call(c, "patient search", "GET", "/api/patients", params={"q": random.choice(["m", "b", "p", "e"])})
            pid = random.choice(ids)
            for part in ("", "/anamneses", "/diagnoses", "/treatments", "/findings", "/prescriptions"):
                call(c, f"akte{part or ''}", "GET", f"/api/patients/{pid}{part}")
            now = datetime.now().astimezone()
            call(c, "kalender (Woche)", "GET", "/api/appointments", params={"start": now.isoformat(), "end": (now + timedelta(days=7)).isoformat()})
            if args.write and test_patient:
                call(c, "befund anlegen", "POST", f"/api/patients/{test_patient}/findings",
                     json={"recorded_on": date.today().isoformat(), "category": "rom", "name": "Lasttest", "value_num": random.randint(20, 160), "unit": "°"})
            time.sleep(random.uniform(0.2, 1.0))  # Denkzeit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--users", type=int, default=5)
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--write", action="store_true", help="legt Daten an einem Testpatienten an")
    ap.add_argument("--insecure", action="store_true", help="Zertifikat nicht prüfen (selbst signiertes Zertifikat)")
    args = ap.parse_args()

    test_patient = None
    if args.write:
        with httpx.Client(base_url=args.url.rstrip("/"), headers={"X-PhysioFlow": "1"}, verify=not args.insecure) as c:
            c.post("/api/auth/login", json={"username": args.user, "password": args.password}).raise_for_status()
            test_patient = c.post("/api/patients", json={"first_name": "Lasttest", "last_name": "Fiktiv", "birth_date": "1990-01-01"}).json()["id"]
    stop = time.time() + args.seconds
    threads = [threading.Thread(target=worker, args=(args, stop, test_patient)) for _ in range(args.users)]
    started = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - started

    total = sum(len(v) for v in timings.values())
    print(f"\n{args.users} Benutzer, {elapsed:.0f} s, {total} Anfragen ({total / elapsed:.1f}/s), {sum(errors.values())} Fehler\n")
    print(f"{'Endpunkt':28} {'Anzahl':>7} {'Median':>9} {'95 %':>9} {'99 %':>9} {'Fehler':>7}")
    for name, values in sorted(timings.items()):
        values.sort()
        q = lambda p: values[min(len(values) - 1, int(len(values) * p))] * 1000  # noqa: E731
        print(f"{name:28} {len(values):7d} {statistics.median(values) * 1000:7.0f}ms {q(0.95):7.0f}ms {q(0.99):7.0f}ms {errors[name]:7d}")


if __name__ == "__main__":
    main()
