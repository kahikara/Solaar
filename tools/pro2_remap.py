#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOLAAR = ROOT / "bin" / "solaar"
TMP = Path("/tmp/pro2-onboard-profiles.yaml")

sys.path.insert(0, str(ROOT / "lib"))

# Import registers YAML constructors for !OnboardProfiles, !OnboardProfile, !Button, !LEDEffectSetting
from logitech_receiver.hidpp20 import OnboardProfiles  # noqa: F401

BUTTON_ALIASES = {
    "left": 1,
    "right": 2,
    "middle": 4,
    "back": 8,
    "forward": 16,
}

def parse_value(raw: str) -> int:
    s = raw.strip().lower()
    if s in BUTTON_ALIASES:
        return BUTTON_ALIASES[s]
    return int(s, 0)


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def dump_profiles(device: str) -> None:
    with TMP.open("w", encoding="utf-8") as f:
        subprocess.run(
            [sys.executable, str(SOLAAR), "profiles", device],
            check=True,
            stdout=f,
        )


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def save_yaml(path: Path, data) -> None:
    path.write_text(yaml.dump(data, width=float("inf")), encoding="utf-8")


def show_profile_buttons(data, profile_no: int) -> None:
    profile = data.profiles[profile_no]
    print(f"Profile {profile_no}")
    for i, button in enumerate(profile.buttons, start=1):
        print(f"  button {i}: {button.__dict__}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Patch Logitech PRO 2 onboard button mapping")
    ap.add_argument("--device", default="1")
    ap.add_argument("--profile", type=int, default=1)
    ap.add_argument("--button", type=int, help="1-based button index, 1..8")
    ap.add_argument("--value", type=str, help="raw button value or alias: left,right,middle,back,forward")
    ap.add_argument("--behavior", type=int, default=8)
    ap.add_argument("--type", dest="mapping_type", type=int, default=1)
    ap.add_argument("--write", action="store_true", help="actually write back to device")
    ap.add_argument("--show", action="store_true", help="show current button mappings for the selected profile")
    ap.add_argument("--set-all-profiles", action="store_true", help="apply the same button remap to profiles 1..5")
    args = ap.parse_args()

    if not (1 <= args.profile <= 5):
        raise SystemExit("profile must be between 1 and 5")

    dump_profiles(args.device)

    backup = TMP.with_suffix(".yaml.bak")
    shutil.copy2(TMP, backup)
    print(f"backup: {backup}")

    data = load_yaml(TMP)

    if args.show:
        show_profile_buttons(data, args.profile)
        return 0

    if args.button is None or args.value is None:
        raise SystemExit("for remap you need --button and --value, or use --show")

    if not (1 <= args.button <= 8):
        raise SystemExit("button must be between 1 and 8")

    parsed_value = parse_value(args.value)

    profile_numbers = range(1, 6) if args.set_all_profiles else [args.profile]
    idx = args.button - 1

    for profile_no in profile_numbers:
        profile = data.profiles[profile_no]
        old = profile.buttons[idx]
        print(f"profile {profile_no} old:", old.__dict__)

        profile.buttons[idx].behavior = args.behavior
        profile.buttons[idx].type = args.mapping_type
        profile.buttons[idx].value = parsed_value

        for attr in ["bytes", "sector", "address", "modifiers", "data"]:
            if hasattr(profile.buttons[idx], attr):
                try:
                    delattr(profile.buttons[idx], attr)
                except Exception:
                    pass

        print(f"profile {profile_no} new:", profile.buttons[idx].__dict__)
    save_yaml(TMP, data)
    print(f"patched: {TMP}")

    if args.write:
        run([sys.executable, str(SOLAAR), "profiles", args.device, str(TMP)])
        print("write complete")
    else:
        print("dry run only, use --write to push to device")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
