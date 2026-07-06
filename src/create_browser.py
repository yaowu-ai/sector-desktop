"""Create one BitBrowser TikTok profile with a fixed proxy.

Examples:
    python create_browser.py --name tiktok_2 \
        --proxy "192.0.2.10:12324:username:password"
    python create_browser.py --name tiktok_2 --type http
    python create_browser.py --file ../config/private/proxies/ip_0630

When --proxy is omitted, the proxy string is requested with hidden input so the
password is not stored in shell history.
"""
import argparse
import getpass
import re
import sys
from pathlib import Path

import requests

from bitbrowser import BitBrowserClient


PROXY_TYPES = ("http", "https", "socks5")


def parse_proxy(value):
    """Parse host:port:username:password, allowing ':' inside the password."""
    parts = value.strip().split(":", 3)
    if len(parts) != 4 or not all(parts):
        raise ValueError("代理格式必须是 host:port:用户名:密码")

    host, port_text, username, password = parts
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("代理端口必须是整数") from exc
    if not 1 <= port <= 65535:
        raise ValueError("代理端口必须在 1~65535 之间")
    return host, port, username, password


def load_proxy_file(path):
    """Load and validate proxies before any browser profile is created."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"代理文件不存在: {path}")

    proxies = []
    errors = []
    for line_number, raw in enumerate(
            path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        try:
            proxy = parse_proxy(value)
        except ValueError as exc:
            errors.append(f"第 {line_number} 行: {exc}")
            continue
        proxies.append((line_number, proxy))

    if errors:
        raise ValueError("代理文件格式错误:\n" + "\n".join(errors))
    if not proxies:
        raise ValueError(f"代理文件没有有效记录: {path}")
    return proxies


def next_browser_number(profiles, prefix="tiktok"):
    """Find max exact '<prefix>_<number>' profile name and return max + 1."""
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)$", re.IGNORECASE)
    numbers = []
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        match = pattern.fullmatch(str(profile.get("name") or "").strip())
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def proxy_is_used(check_result):
    return isinstance(check_result, dict) and bool(check_result.get("used"))


def require_client_methods(client, *method_names):
    """Fail clearly when create_browser.py and bitbrowser.py are out of sync."""
    missing = [name for name in method_names if not hasattr(client, name)]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"bitbrowser.py 版本不匹配，缺少方法: {joined}；"
            "请同时更新 src/create_browser.py 和 src/bitbrowser.py"
        )


def create_batch(client, args, parser):
    try:
        proxies = load_proxy_file(args.file)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        profiles = client.list_browsers(name=f"{args.prefix}_")
    except (requests.RequestException, RuntimeError) as exc:
        print(f"[error] 读取现有窗口失败: {exc}", file=sys.stderr)
        return 1

    next_number = next_browser_number(profiles, args.prefix)
    current_max = next_number - 1
    print(f"现有 {args.prefix}_<数字> 最大编号: {current_max}")
    print(f"代理文件有效记录: {len(proxies)} 条")
    print(f"首个新窗口名称: {args.prefix}_{next_number}\n")

    created = []
    skipped = []
    failed = []
    for position, (line_number, proxy) in enumerate(proxies, start=1):
        host, port, username, password = proxy
        name = f"{args.prefix}_{next_number}"
        label = f"[{position}/{len(proxies)}] 第 {line_number} 行 {host}:{port}"
        try:
            if not args.skip_check:
                print(f"{label} 检测代理 ...")
                check_result = client.check_proxy(
                    args.type, host, port, username, password, check_exists=True
                )
                if proxy_is_used(check_result):
                    if args.skip_used:
                        print("      跳过：该代理已被现有窗口使用")
                        skipped.append((line_number, host, port, "代理已使用"))
                        continue
                    print("      注意：该代理已被使用，将按配置继续复用")

            print(f"      创建 {name} ...")
            profile_id = client.create_browser(
                name=name,
                proxy_type=args.type,
                host=host,
                port=port,
                username=username,
                password=password,
                group_id=args.group_id,
            )
        except (requests.RequestException, RuntimeError) as exc:
            print(f"      失败: {exc}", file=sys.stderr)
            failed.append((line_number, host, port, str(exc)))
            continue

        print(f"      成功: {name} -> {profile_id}")
        created.append((name, profile_id, host, port))
        next_number += 1

    print("\n批量创建完成")
    print(f"成功={len(created)} 跳过={len(skipped)} 失败={len(failed)}")
    if created:
        print("\n新窗口:")
        for name, profile_id, host, port in created:
            print(f"  {name}: {profile_id} ({host}:{port})")
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(
        description="创建一个绑定固定代理的比特浏览器 TikTok 窗口",
    )
    parser.add_argument("--name", help="单个模式的窗口名称，例如 tiktok_26")
    parser.add_argument(
        "--proxy",
        help="host:port:用户名:密码；不传时进行隐藏输入",
    )
    parser.add_argument(
        "--file",
        help="批量模式代理文件，每行一个 host:port:用户名:密码",
    )
    parser.add_argument(
        "--prefix",
        default="tiktok",
        help="批量窗口名称前缀，默认 tiktok",
    )
    parser.add_argument(
        "--type",
        choices=PROXY_TYPES,
        default="socks5",
        help="代理协议，默认 socks5",
    )
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:54345",
        help="比特浏览器 Local API 地址",
    )
    parser.add_argument("--group-id", help="可选的比特浏览器分组 ID")
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="跳过创建前的代理连通性检测",
    )
    reuse_group = parser.add_mutually_exclusive_group()
    reuse_group.add_argument(
        "--skip-used",
        action="store_true",
        help="跳过已被其他窗口使用的代理；默认允许复用",
    )
    reuse_group.add_argument(
        "--allow-used",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    if args.file and args.proxy:
        parser.error("--file 和 --proxy 不能同时使用")

    client = BitBrowserClient(args.api_url)
    if args.file:
        if args.name:
            parser.error("批量模式由脚本生成窗口名称，请勿传 --name")
        try:
            require_client_methods(
                client, "list_browsers", "check_proxy", "create_browser"
            )
        except RuntimeError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 1
        return create_batch(client, args, parser)

    if not args.name:
        parser.error("单个模式必须传 --name；批量模式请传 --file")
    try:
        require_client_methods(client, "check_proxy", "create_browser")
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    proxy_value = args.proxy or getpass.getpass(
        "代理信息（host:port:用户名:密码）: "
    )
    try:
        host, port, username, password = parse_proxy(proxy_value)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        if not args.skip_check:
            print(f"[1/2] 检测 {args.type} 代理 {host}:{port} ...")
            check_result = client.check_proxy(
                args.type, host, port, username, password, check_exists=True
            )
            print("      代理检测通过")
            if proxy_is_used(check_result):
                print("      注意：该代理已被现有窗口使用")

        print(f"[2/2] 创建窗口 {args.name!r} ...")
        profile_id = client.create_browser(
            name=args.name,
            proxy_type=args.type,
            host=host,
            port=port,
            username=username,
            password=password,
            group_id=args.group_id,
        )
    except requests.RequestException as exc:
        print(f"[error] 无法连接比特浏览器 Local API: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print("\n创建成功")
    print(f"窗口名称: {args.name}")
    print(f"代理类型: {args.type}")
    print(f"代理地址: {host}:{port}")
    print(f"profile_id: {profile_id}")
    print("\n将 profile_id 填入 config/accounts.yaml 对应账号的 "
          "bitbrowser_profile_id。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
