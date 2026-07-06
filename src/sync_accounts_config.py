"""Append missing TikTok accounts to config/accounts.yaml from BitBrowser.

This script is intentionally conservative:
  - It reads BitBrowser windows by exact name, e.g. tiktok_21.
  - It appends only missing account blocks to config/accounts.yaml.
  - It does not rewrite the existing YAML, comments, or formatting.
  - It validates all required windows before writing anything.

Default layout for 50 accounts:
  - tiktok_21..35: morning shift [[9, 12]], ip_group 11..25
  - tiktok_36..50: evening shift [[19, 23]], ip_group 11..25

Example:
    python sync_accounts_config.py
    python sync_accounts_config.py --dry-run
    python sync_accounts_config.py --api-url http://127.0.0.1:54345
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config" / "accounts.yaml"


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def account_numbers(start, end):
    if start > end:
        raise ValueError("--start 不能大于 --end")
    return list(range(start, end + 1))


def exact_profile_map(profiles, prefix):
    """Return {name: id}; fail on duplicate exact names."""
    by_name = {}
    duplicates = []

    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        name = str(profile.get("name") or "").strip()
        if not name.startswith(f"{prefix}_"):
            continue

        profile_id = profile.get("id") or profile.get("browserId")
        if not profile_id:
            continue

        if name in by_name:
            duplicates.append(name)
        by_name[name] = str(profile_id)

    if duplicates:
        names = ", ".join(sorted(set(duplicates)))
        raise RuntimeError(f"BitBrowser 存在重复窗口名: {names}")
    return by_name


def shift_for_number(number, morning_start, morning_end, evening_start,
                     evening_end):
    if morning_start <= number <= morning_end:
        return "上午", [[9, 12]]
    if evening_start <= number <= evening_end:
        return "晚上", [[19, 23]]
    raise ValueError(
        f"编号 {number} 不在上午段 {morning_start}-{morning_end} "
        f"或晚上段 {evening_start}-{evening_end} 内"
    )


def ip_group_for_number(number, morning_start, morning_end, evening_start,
                        evening_end, first_ip_group):
    morning_count = morning_end - morning_start + 1
    evening_count = evening_end - evening_start + 1
    if morning_count != evening_count:
        raise ValueError("上午段和晚上段数量必须一致，才能一一复用 ip_group")

    if morning_start <= number <= morning_end:
        return first_ip_group + (number - morning_start)
    if evening_start <= number <= evening_end:
        return first_ip_group + (number - evening_start)
    raise ValueError(f"编号 {number} 无法计算 ip_group")


def build_account_block(number, prefix, profile_id, morning_start, morning_end,
                        evening_start, evening_end, first_ip_group):
    shift_name, hours = shift_for_number(
        number, morning_start, morning_end, evening_start, evening_end
    )
    ip_group = ip_group_for_number(
        number, morning_start, morning_end, evening_start, evening_end,
        first_ip_group
    )
    if shift_name == "晚上":
        pair_number = morning_start + (number - evening_start)
        note = f"IP-{ip_group} 晚上（与 {prefix}_{pair_number} 共享 IP）"
    else:
        note = f"IP-{ip_group} 上午"

    return (
        f"  - id: {prefix}_{number}\n"
        f"    enabled: true\n"
        f"    ip_group: {ip_group}\n"
        f"    active_hours: {hours}\n"
        f"    bitbrowser_profile_id: \"{profile_id}\"\n"
        f"    notes: \"{note}\"\n"
    )


def _windows_overlap(a, b):
    for s1, e1 in a:
        for s2, e2 in b:
            if s1 < e2 and s2 < e1:
                return True
    return False


def validate_candidate_config(candidate_text):
    cfg = yaml.safe_load(candidate_text)
    accounts = cfg.get("accounts") or []

    ids = [a.get("id") for a in accounts]
    duplicated_ids = sorted(k for k, v in Counter(ids).items() if k and v > 1)
    if duplicated_ids:
        raise RuntimeError(f"accounts.yaml 将出现重复账号 id: {duplicated_ids}")

    profile_ids = [
        a.get("bitbrowser_profile_id") for a in accounts
        if a.get("bitbrowser_profile_id")
    ]
    duplicated_profiles = sorted(
        k for k, v in Counter(profile_ids).items() if k and v > 1
    )
    if duplicated_profiles:
        raise RuntimeError(
            f"accounts.yaml 将出现重复 bitbrowser_profile_id: {duplicated_profiles}"
        )

    defaults = cfg.get("defaults") or {}
    default_hours = defaults.get("active_hours") or [[9, 12], [19, 23]]
    by_group = {}
    for account in accounts:
        if not account.get("enabled", True):
            continue
        group = account.get("ip_group")
        if group is not None:
            by_group.setdefault(group, []).append(account)

    conflicts = []
    for group, members in by_group.items():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                left = members[i]
                right = members[j]
                left_hours = left.get("active_hours") or default_hours
                right_hours = right.get("active_hours") or default_hours
                if _windows_overlap(left_hours, right_hours):
                    conflicts.append(
                        f"ip_group {group}: {left.get('id')} / {right.get('id')}"
                    )

    if conflicts:
        raise RuntimeError(
            "accounts.yaml 将出现同 ip_group 班次重叠:\n" +
            "\n".join(conflicts)
        )


def append_missing_accounts(config_path, profile_map, args):
    original = config_path.read_text(encoding="utf-8")
    cfg = yaml.safe_load(original)
    existing_ids = {
        str(account.get("id") or "").strip()
        for account in (cfg.get("accounts") or [])
    }

    missing_numbers = [
        number for number in account_numbers(args.start, args.end)
        if f"{args.prefix}_{number}" not in existing_ids
    ]
    if not missing_numbers:
        print("accounts.yaml 已包含目标范围内的所有账号，无需补充")
        return 0

    required_names = [f"{args.prefix}_{number}" for number in missing_numbers]
    missing_profiles = [name for name in required_names if name not in profile_map]
    if missing_profiles:
        raise RuntimeError(
            "BitBrowser 未找到以下窗口，未写入 accounts.yaml:\n  " +
            "\n  ".join(missing_profiles)
        )

    blocks = []
    current_shift = None
    for number in missing_numbers:
        shift_name, _ = shift_for_number(
            number, args.morning_start, args.morning_end,
            args.evening_start, args.evening_end
        )
        if shift_name != current_shift:
            current_shift = shift_name
            if shift_name == "上午":
                blocks.append(
                    f"\n  # ========== 上午班 [[9, 12]] —— IP "
                    f"{args.first_ip_group}~"
                    f"{args.first_ip_group + args.morning_end - args.morning_start} "
                    f"各一个号 ==========\n"
                )
            else:
                blocks.append(
                    f"\n  # ========== 晚上班 [[19, 23]] —— 与上午班共享 "
                    f"IP {args.first_ip_group}~"
                    f"{args.first_ip_group + args.morning_end - args.morning_start} "
                    f"==========\n"
                )

        name = f"{args.prefix}_{number}"
        blocks.append(
            build_account_block(
                number=number,
                prefix=args.prefix,
                profile_id=profile_map[name],
                morning_start=args.morning_start,
                morning_end=args.morning_end,
                evening_start=args.evening_start,
                evening_end=args.evening_end,
                first_ip_group=args.first_ip_group,
            )
        )

    addition = "".join(blocks)
    candidate = original.rstrip() + "\n" + addition
    validate_candidate_config(candidate)

    print(f"待补充账号数: {len(missing_numbers)}")
    print(f"范围: {args.prefix}_{missing_numbers[0]}~{args.prefix}_{missing_numbers[-1]}")
    if args.dry_run:
        print("\n--- dry-run: 将追加以下内容，不写入文件 ---")
        print(addition.rstrip())
        return 0

    config_path.write_text(candidate + "\n", encoding="utf-8")
    print(f"已补充: {config_path}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="从 BitBrowser 窗口列表补充 config/accounts.yaml 账号配置",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="accounts.yaml 路径，默认 ../config/accounts.yaml",
    )
    parser.add_argument(
        "--api-url",
        help="比特浏览器 Local API 地址；默认读取 accounts.yaml 的 bitbrowser.api_url",
    )
    parser.add_argument("--prefix", default="tiktok", help="窗口名前缀")
    parser.add_argument("--start", type=int, default=21, help="补充起始编号")
    parser.add_argument("--end", type=int, default=50, help="补充结束编号")
    parser.add_argument("--morning-start", type=int, default=21)
    parser.add_argument("--morning-end", type=int, default=35)
    parser.add_argument("--evening-start", type=int, default=36)
    parser.add_argument("--evening-end", type=int, default=50)
    parser.add_argument(
        "--first-ip-group",
        type=int,
        default=11,
        help="新增上午第一号对应的 ip_group，默认 11",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将追加的配置，不写入 accounts.yaml",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_file():
        parser.error(f"配置文件不存在: {config_path}")

    try:
        import requests
        from bitbrowser import BitBrowserClient
    except ModuleNotFoundError as exc:
        print(f"[error] 缺少依赖: {exc.name}，请先安装 requirements.txt", file=sys.stderr)
        return 1

    try:
        cfg = load_config(config_path)
        api_url = args.api_url or cfg["bitbrowser"]["api_url"]
        numbers = account_numbers(args.start, args.end)
        profiles = BitBrowserClient(api_url).list_browsers(name=f"{args.prefix}_")
        profile_map = exact_profile_map(profiles, args.prefix)
        expected = [f"{args.prefix}_{number}" for number in numbers]
        found = sum(1 for name in expected if name in profile_map)
        print(f"BitBrowser 目标窗口: 找到 {found}/{len(expected)}")
        return append_missing_accounts(config_path, profile_map, args)
    except (requests.RequestException, RuntimeError, ValueError, KeyError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
