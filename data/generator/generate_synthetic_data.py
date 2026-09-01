"""
generate_synthetic_data.py — PredicTrace synthetic dataset generator.

WHY THIS EXISTS
----------------
Real NCRP/1930 cybercrime complaint data is access-restricted. We do not pretend
otherwise (see Execution Blueprint, Section 14 — REAL vs SIMULATED). Instead we
generate a rule-based dataset that contains genuine, learnable structure:
fraud rings with shared mule accounts, layered transaction chains, ring-specific
geographic cash-out clustering, and ring-specific cash-out timing profiles —
plus enough background noise that the problem isn't trivially solvable, and a
held-out "unseen pattern" set to genuinely test generalization.

IMPORTANT — NO DATA LEAKAGE:
`fraud_rings.csv` (and the `ring_id` column on withdrawal_events) is GENERATOR-SIDE
ground truth for evaluation only. It must NEVER be fed into the ML pipeline as an
input feature — that would be leaking the answer. The graph pipeline is expected
to *discover* ring-like structure itself (via Louvain community detection on the
transaction graph); that discovered `community_id` is a different, legitimate,
unsupervised signal and is fine to use as a feature.

OUTPUT (CSV files in --outdir, default ../output/):
    victims.csv, accounts.csv, complaints.csv, transactions.csv,
    withdrawal_points.csv, withdrawal_events.csv, fraud_rings.csv (ground truth only)

Run:
    python3 generate_synthetic_data.py
    python3 generate_synthetic_data.py --config rings_config.yaml --outdir ../output --seed 42
"""

import argparse
import random
import string
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml

# ----------------------------------------------------------------------------
# Name generation (no external Faker dependency — keeps this script dependency-light)
# ----------------------------------------------------------------------------
FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Krishna",
    "Ishaan", "Rohan", "Ananya", "Diya", "Saanvi", "Aadhya", "Kiara", "Myra",
    "Pari", "Anika", "Navya", "Riya", "Rahul", "Amit", "Suresh", "Rajesh",
    "Priya", "Neha", "Pooja", "Kavita", "Sunita", "Deepak", "Manoj", "Vikram",
    "Ravi", "Sanjay", "Anil", "Sunil", "Meena", "Geeta", "Lakshmi", "Divya",
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Reddy", "Rao", "Iyer", "Nair", "Menon",
    "Patel", "Shah", "Mehta", "Joshi", "Kulkarni", "Desai", "Naidu", "Pillai",
    "Singh", "Kumar", "Yadav", "Chauhan", "Malhotra", "Kapoor", "Bhatt", "Pandey",
]


def random_name(rng):
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def random_phone(rng):
    return "9" + "".join(rng.choice(string.digits) for _ in range(9))


def random_account_number(rng):
    return "".join(rng.choice(string.digits) for _ in range(12))


def random_ifsc(rng, bank_code):
    branch = "".join(rng.choice(string.digits) for _ in range(4))
    return f"{bank_code}0{branch}"


NARRATIVE_TEMPLATES = [
    "I received a call claiming to be from {bank} customer support and was asked "
    "to share an OTP. Rs {amount} was debited from my account without my consent. "
    "The transaction reference mentions IFSC {ifsc}.",
    "I was tricked into installing a remote-access app after a fake {bank} KYC "
    "update message. Rs {amount} was transferred out immediately. Bank IFSC on the "
    "receiving account appears to be {ifsc}.",
    "An unknown person posing as a {bank} official convinced me to make a "
    "'verification transfer' of Rs {amount}. I later found the beneficiary IFSC "
    "was {ifsc} and the number is no longer reachable.",
    "My {bank} debit card details were compromised after a phishing SMS. "
    "Rs {amount} was withdrawn/transferred without authorization. Reference "
    "IFSC noted on the statement: {ifsc}.",
]


# ----------------------------------------------------------------------------
# Core generator
# ----------------------------------------------------------------------------
class Generator:
    def __init__(self, config: dict, seed: int):
        self.cfg = config
        self.rng = random.Random(seed)
        self.window_start = datetime.fromisoformat(config["window"]["start_date"])
        self.window_days = config["window"]["days"]
        self.window_end = self.window_start + timedelta(days=self.window_days)
        self.test_period_start = self.window_start + timedelta(days=self.window_days * 0.8)

        self.cities = config["cities"]
        self.banks = config["banks"]

        # accumulators -> lists of dict rows
        self.victims = []
        self.accounts = []
        self.complaints = []
        self.transactions = []
        self.withdrawal_points = []
        self.withdrawal_events = []
        self.fraud_rings = []

        self._id_counters = {"victim": 0, "account": 0, "complaint": 0,
                              "transaction": 0, "withdrawal_point": 0,
                              "withdrawal_event": 0, "ring": 0}

    def _next_id(self, kind):
        self._id_counters[kind] += 1
        return self._id_counters[kind]

    def _random_timestamp(self, start=None, end=None):
        start = start or self.window_start
        end = end or self.window_end
        delta_seconds = int((end - start).total_seconds())
        if delta_seconds <= 0:
            return start
        return start + timedelta(seconds=self.rng.randint(0, delta_seconds))

    # --------------------------------------------------------------------
    # Step 1: seed withdrawal points (ATMs/branches) per city
    # --------------------------------------------------------------------
    def generate_withdrawal_points(self, per_city=40):
        area_names = ["MG Road", "Station Road", "Market Yard", "Ring Road",
                      "Civil Lines", "Old Town", "Tech Park", "Junction",
                      "Sector 12", "Bus Stand", "Fort Area", "Lake View",
                      "Airport Road", "Industrial Estate", "Central Plaza"]
        for city in self.cities:
            for i in range(per_city):
                bank = self.rng.choice(self.banks)
                kind = self.rng.choice(["ATM", "ATM", "ATM", "Branch"])  # ATMs more common
                area = self.rng.choice(area_names)
                # jitter lat/lon within roughly a 15km radius of city center
                # (some cities override this range in rings_config.yaml to
                # stay clear of the coastline -- see lat_jitter/lon_jitter)
                lat_min, lat_max = city.get("lat_jitter", [-0.12, 0.12])
                lon_min, lon_max = city.get("lon_jitter", [-0.12, 0.12])
                lat = city["lat"] + self.rng.uniform(lat_min, lat_max)
                lon = city["lon"] + self.rng.uniform(lon_min, lon_max)
                self.withdrawal_points.append({
                    "id": self._next_id("withdrawal_point"),
                    "name": f"{bank['name']} {kind}, {area}, {city['name']}",
                    "type": kind,
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "city": city["name"],
                    "bank_name": bank["name"],
                })

    def _withdrawal_points_in_city(self, city_name):
        return [w for w in self.withdrawal_points if w["city"] == city_name]

    # --------------------------------------------------------------------
    # Step 2: seed a pool of "normal" (non-fraud) accounts for background noise
    # --------------------------------------------------------------------
    def generate_normal_accounts(self):
        n = self.cfg["noise"]["normal_account_pool_size"]
        for _ in range(n):
            bank = self.rng.choice(self.banks)
            self.accounts.append({
                "id": self._next_id("account"),
                "account_number_fake": random_account_number(self.rng),
                "holder_name_fake": random_name(self.rng),
                "bank_name": bank["name"],
                "account_type": "normal",
                "ifsc_code": random_ifsc(self.rng, bank["code"]),
                "opened_at": self._random_timestamp(
                    self.window_start - timedelta(days=365), self.window_start
                ).date().isoformat(),
            })

    def _normal_account_pool(self):
        return [a for a in self.accounts if a["account_type"] == "normal"]

    # --------------------------------------------------------------------
    # Step 3: generate fraud rings (mule accounts + preferred cash-out points
    #          + hop count + delay profile)
    # --------------------------------------------------------------------
    def generate_rings(self):
        rcfg = self.cfg["rings"]
        for _ in range(rcfg["count"]):
            ring_id = self._next_id("ring")
            city = self.rng.choice(self.cities)
            n_mules = self.rng.randint(rcfg["mule_accounts_per_ring_min"],
                                        rcfg["mule_accounts_per_ring_max"])
            n_wpoints = self.rng.randint(rcfg["withdrawal_points_per_ring_min"],
                                          rcfg["withdrawal_points_per_ring_max"])
            hop_count = self.rng.randint(rcfg["hop_count_min"], rcfg["hop_count_max"])
            is_fast = self.rng.random() < rcfg["fast_ring_fraction"]
            if is_fast:
                delay_min, delay_max = rcfg["fast_delay_hours_min"], rcfg["fast_delay_hours_max"]
            else:
                delay_min, delay_max = rcfg["slow_delay_hours_min"], rcfg["slow_delay_hours_max"]

            mule_account_ids = []
            for _ in range(n_mules):
                bank = self.rng.choice(self.banks)
                acc_id = self._next_id("account")
                self.accounts.append({
                    "id": acc_id,
                    "account_number_fake": random_account_number(self.rng),
                    "holder_name_fake": random_name(self.rng),
                    "bank_name": bank["name"],
                    "account_type": "mule",
                    "ifsc_code": random_ifsc(self.rng, bank["code"]),
                    "opened_at": self._random_timestamp(
                        self.window_start - timedelta(days=200), self.window_start
                    ).date().isoformat(),
                })
                mule_account_ids.append(acc_id)

            city_points = self._withdrawal_points_in_city(city["name"])
            wpoint_ids = [w["id"] for w in self.rng.sample(
                city_points, min(n_wpoints, len(city_points)))]
            # a "hot" subset (2-3 points) the ring disproportionately favours —
            # this is what makes geospatial concentration genuinely learnable
            hot_wpoints = wpoint_ids[: min(3, len(wpoint_ids))]

            self.fraud_rings.append({
                "id": ring_id,
                "name": f"Ring-{ring_id:03d}",
                "city_cluster": city["name"],
                "typical_hops": hop_count,
                "typical_delay_hours_min": delay_min,
                "typical_delay_hours_max": delay_max,
                "mule_account_ids": ",".join(map(str, mule_account_ids)),
                "withdrawal_point_ids": ",".join(map(str, wpoint_ids)),
                "hot_withdrawal_point_ids": ",".join(map(str, hot_wpoints)),
            })

    # --------------------------------------------------------------------
    # Step 4: generate cases (victim + complaint + transaction chain +
    #          withdrawal event) for each ring
    # --------------------------------------------------------------------
    def _pick_withdrawal_point(self, ring_row):
        hot = [int(x) for x in ring_row["hot_withdrawal_point_ids"].split(",") if x]
        all_pts = [int(x) for x in ring_row["withdrawal_point_ids"].split(",") if x]
        if hot and self.rng.random() < 0.7:
            return self.rng.choice(hot)
        return self.rng.choice(all_pts)

    def generate_ring_cases(self):
        ccfg = self.cfg["cases"]
        acfg = self.cfg["amount"]
        for ring_row in self.fraud_rings:
            mule_ids = [int(x) for x in ring_row["mule_account_ids"].split(",") if x]
            n_cases = self.rng.randint(ccfg["per_ring_min"], ccfg["per_ring_max"])
            hop_count = ring_row["typical_hops"]

            for _ in range(n_cases):
                # --- victim + victim account ---
                victim_id = self._next_id("victim")
                self.victims.append({
                    "id": victim_id,
                    "name_fake": random_name(self.rng),
                    "city": ring_row["city_cluster"],
                    "state": next(c["state"] for c in self.cities
                                  if c["name"] == ring_row["city_cluster"]),
                    "phone_fake": random_phone(self.rng),
                })
                victim_bank = self.rng.choice(self.banks)
                victim_acc_id = self._next_id("account")
                self.accounts.append({
                    "id": victim_acc_id,
                    "account_number_fake": random_account_number(self.rng),
                    "holder_name_fake": self.victims[-1]["name_fake"],
                    "bank_name": victim_bank["name"],
                    "account_type": "victim",
                    "ifsc_code": random_ifsc(self.rng, victim_bank["code"]),
                    "opened_at": self._random_timestamp(
                        self.window_start - timedelta(days=800), self.window_start
                    ).date().isoformat(),
                })

                # --- timing: T0 (theft start) -> hops -> T_withdraw ---
                t0 = self._random_timestamp(self.window_start, self.window_end)
                amount = round(self.rng.uniform(acfg["victim_loss_min"], acfg["victim_loss_max"]), 2)

                complaint_id = self._next_id("complaint")

                hop_accounts = [victim_acc_id] + list(
                    self.rng.sample(mule_ids, min(hop_count, len(mule_ids)))
                )
                cur_time = t0
                cur_amount = amount
                for hop_idx in range(len(hop_accounts) - 1):
                    cur_time = cur_time + timedelta(minutes=self.rng.randint(10, 120))
                    fee_frac = self.rng.uniform(0.02, 0.08)
                    extra_loss = self.rng.uniform(0.0, acfg["split_jitter"])
                    next_amount = max(100.0, cur_amount * (1 - fee_frac - extra_loss))
                    self.transactions.append({
                        "id": self._next_id("transaction"),
                        "from_account_id": hop_accounts[hop_idx],
                        "to_account_id": hop_accounts[hop_idx + 1],
                        "amount": round(next_amount, 2),
                        "timestamp": cur_time.isoformat(timespec='seconds'),
                        "complaint_id": complaint_id,
                        "hop_index": hop_idx,
                    })
                    cur_amount = next_amount

                ring_delay = timedelta(hours=self.rng.uniform(
                    ring_row["typical_delay_hours_min"], ring_row["typical_delay_hours_max"]))
                t_withdraw = cur_time + ring_delay
                wpoint_id = self._pick_withdrawal_point(ring_row)
                final_account = hop_accounts[-1]

                self.withdrawal_events.append({
                    "id": self._next_id("withdrawal_event"),
                    "account_id": final_account,
                    "withdrawal_point_id": wpoint_id,
                    "amount": round(cur_amount, 2),
                    "timestamp": t_withdraw.isoformat(timespec='seconds'),
                    "ring_id": ring_row["id"],  # GROUND TRUTH ONLY — never a model feature
                    "complaint_id": complaint_id,
                })

                # --- filed_at: actionable (before withdrawal) vs too-late (after) ---
                is_actionable = self.rng.random() < ccfg["actionable_fraction"]
                if is_actionable:
                    lead = timedelta(hours=self.rng.uniform(
                        ccfg["actionable_lead_hours_min"], ccfg["actionable_lead_hours_max"]))
                    filed_at = max(t0, t_withdraw - lead)
                else:
                    lag = timedelta(hours=self.rng.uniform(
                        ccfg["too_late_lag_hours_min"], ccfg["too_late_lag_hours_max"]))
                    filed_at = t_withdraw + lag

                bank = self.rng.choice(self.banks)
                narrative = self.rng.choice(NARRATIVE_TEMPLATES).format(
                    bank=bank["name"], amount=int(amount),
                    ifsc=random_ifsc(self.rng, bank["code"]),
                )
                self.complaints.append({
                    "id": complaint_id,
                    "victim_id": victim_id,
                    "filed_at": filed_at.isoformat(timespec='seconds'),
                    "amount_lost": amount,
                    "narrative_text": narrative,
                    "bank_name": bank["name"],
                    "status": "open",
                })

    # --------------------------------------------------------------------
    # Step 5: background noise transactions (unrelated to any ring/complaint)
    # --------------------------------------------------------------------
    def generate_background_noise(self):
        pool = self._normal_account_pool()
        n_ring_tx = len(self.transactions)
        n_noise = int(n_ring_tx * self.cfg["noise"]["background_transaction_fraction"])
        for _ in range(n_noise):
            a, b = self.rng.sample(pool, 2)
            self.transactions.append({
                "id": self._next_id("transaction"),
                "from_account_id": a["id"],
                "to_account_id": b["id"],
                "amount": round(self.rng.uniform(200, 20000), 2),
                "timestamp": self._random_timestamp().isoformat(timespec='seconds'),
                "complaint_id": None,
                "hop_index": None,
            })

    # --------------------------------------------------------------------
    # Step 6: unseen test-only patterns — single-hop, brand-new mule
    #          accounts, placed only in the final 20% (test) period, to
    #          test generalization rather than memorized ring identity.
    # --------------------------------------------------------------------
    def generate_unseen_test_patterns(self):
        ucfg = self.cfg["unseen_test_patterns"]
        rcfg = self.cfg["rings"]
        acfg = self.cfg["amount"]
        for _ in range(ucfg["count"]):
            city = self.rng.choice(self.cities)
            victim_id = self._next_id("victim")
            self.victims.append({
                "id": victim_id, "name_fake": random_name(self.rng),
                "city": city["name"],
                "state": city["state"], "phone_fake": random_phone(self.rng),
            })
            victim_bank = self.rng.choice(self.banks)
            victim_acc_id = self._next_id("account")
            self.accounts.append({
                "id": victim_acc_id, "account_number_fake": random_account_number(self.rng),
                "holder_name_fake": self.victims[-1]["name_fake"],
                "bank_name": victim_bank["name"], "account_type": "victim",
                "ifsc_code": random_ifsc(self.rng, victim_bank["code"]),
                "opened_at": self._random_timestamp(
                    self.window_start - timedelta(days=800), self.window_start).date().isoformat(),
            })
            # brand-new, never-reused mule account
            mule_bank = self.rng.choice(self.banks)
            mule_acc_id = self._next_id("account")
            self.accounts.append({
                "id": mule_acc_id, "account_number_fake": random_account_number(self.rng),
                "holder_name_fake": random_name(self.rng),
                "bank_name": mule_bank["name"], "account_type": "mule",
                "ifsc_code": random_ifsc(self.rng, mule_bank["code"]),
                "opened_at": self._random_timestamp(
                    self.test_period_start - timedelta(days=30), self.test_period_start).date().isoformat(),
            })

            t0 = self._random_timestamp(self.test_period_start, self.window_end)
            amount = round(self.rng.uniform(acfg["victim_loss_min"], acfg["victim_loss_max"]), 2)
            complaint_id = self._next_id("complaint")
            tx_time = t0 + timedelta(minutes=self.rng.randint(10, 120))
            self.transactions.append({
                "id": self._next_id("transaction"), "from_account_id": victim_acc_id,
                "to_account_id": mule_acc_id, "amount": amount,
                "timestamp": tx_time.isoformat(timespec='seconds'), "complaint_id": complaint_id, "hop_index": 0,
            })
            is_fast = self.rng.random() < rcfg["fast_ring_fraction"]
            delay = timedelta(hours=self.rng.uniform(
                rcfg["fast_delay_hours_min"], rcfg["fast_delay_hours_max"]) if is_fast
                else self.rng.uniform(rcfg["slow_delay_hours_min"], rcfg["slow_delay_hours_max"]))
            t_withdraw = tx_time + delay
            city_points = self._withdrawal_points_in_city(city["name"])
            wpoint = self.rng.choice(city_points)
            self.withdrawal_events.append({
                "id": self._next_id("withdrawal_event"), "account_id": mule_acc_id,
                "withdrawal_point_id": wpoint["id"], "amount": round(amount * 0.95, 2),
                "timestamp": t_withdraw.isoformat(timespec='seconds'), "ring_id": None,  # not part of any ring
                "complaint_id": complaint_id,
            })
            lead = timedelta(hours=self.rng.uniform(0.5, 8))
            filed_at = max(t0, t_withdraw - lead)
            bank = self.rng.choice(self.banks)
            narrative = self.rng.choice(NARRATIVE_TEMPLATES).format(
                bank=bank["name"], amount=int(amount), ifsc=random_ifsc(self.rng, bank["code"]))
            self.complaints.append({
                "id": complaint_id, "victim_id": victim_id, "filed_at": filed_at.isoformat(timespec='seconds'),
                "amount_lost": amount, "narrative_text": narrative,
                "bank_name": bank["name"], "status": "open",
            })

    # --------------------------------------------------------------------
    def run(self):
        self.generate_withdrawal_points()
        self.generate_normal_accounts()
        self.generate_rings()
        self.generate_ring_cases()
        self.generate_background_noise()
        self.generate_unseen_test_patterns()

    def to_dataframes(self):
        return {
            "victims": pd.DataFrame(self.victims),
            "accounts": pd.DataFrame(self.accounts),
            "complaints": pd.DataFrame(self.complaints),
            "transactions": pd.DataFrame(self.transactions),
            "withdrawal_points": pd.DataFrame(self.withdrawal_points),
            "withdrawal_events": pd.DataFrame(self.withdrawal_events),
            "fraud_rings": pd.DataFrame(self.fraud_rings),
        }


def main():
    parser = argparse.ArgumentParser(description="Generate PredicTrace synthetic dataset")
    parser.add_argument("--config", default=str(Path(__file__).parent / "rings_config.yaml"))
    parser.add_argument("--outdir", default=str(Path(__file__).parent.parent / "output"))
    parser.add_argument("--seed", type=int, default=None, help="override rings_config.yaml seed")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)
    seed = args.seed if args.seed is not None else config["random_seed"]

    gen = Generator(config, seed)
    gen.run()
    frames = gen.to_dataframes()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for name, df in frames.items():
        df.to_csv(outdir / f"{name}.csv", index=False)

    print("=== Generation summary ===")
    for name, df in frames.items():
        print(f"  {name:20s} {len(df):6d} rows")
    n_actionable = sum(1 for c in gen.complaints
                       if pd.Timestamp(c["filed_at"]) < pd.Timestamp(
                           next(w["timestamp"] for w in gen.withdrawal_events
                                if w["complaint_id"] == c["id"])))
    print(f"  actionable (filed before withdrawal): {n_actionable}/{len(gen.complaints)} "
          f"({100*n_actionable/len(gen.complaints):.1f}%)")
    print(f"  test-period boundary: {gen.test_period_start.isoformat(timespec='seconds')}")
    print(f"  output directory: {outdir.resolve()}")


if __name__ == "__main__":
    main()
