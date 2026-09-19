"""Create ixBrowser TikTok profiles with an optional fixed proxy."""

import argparse
import getpass
import sys

from create_browser import load_proxy_file, next_browser_number, parse_proxy
from ixbrowser import DEFAULT_API_URL, IXBrowserClient


PROXY_TYPES = ("http", "https", "socks5")


def _create(client, name, proxy, args):
    if proxy is None:
        print(f"创建 ixBrowser 窗口 {name!r}（不设置代理）...")
        profile_id = client.create_browser(name=name, group_id=args.group_id)
        print(f"成功: {name} -> {profile_id}")
        return profile_id

    host, port, username, password = proxy
    print(f"创建 ixBrowser 窗口 {name!r}（{args.type} {host}:{port}）...")
    profile_id = client.create_browser(
        name=name,
        proxy_type=args.type,
        host=host,
        port=port,
        username=username,
        password=password,
        group_id=args.group_id,
    )
    print(f"成功: {name} -> {profile_id}")
    return profile_id


def main(argv=None):
    parser = argparse.ArgumentParser(description="创建 ixBrowser TikTok 窗口")
    parser.add_argument("--name", help="单个模式窗口名称，例如 tiktok_26")
    parser.add_argument("--proxy", help="host:port:用户名:密码")
    parser.add_argument("--no-proxy", action="store_true", help="不为窗口设置代理")
    parser.add_argument("--file", help="批量代理文件，每行 host:port:用户名:密码")
    parser.add_argument("--prefix", default="tiktok", help="批量窗口名前缀")
    parser.add_argument("--type", choices=PROXY_TYPES, default="socks5")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--group-id", help="可选的 ixBrowser 分组 ID")
    args = parser.parse_args(argv)

    if args.file and args.proxy:
        parser.error("--file 和 --proxy 不能同时使用")
    if args.no_proxy and (args.file or args.proxy):
        parser.error("--no-proxy 不能与 --file 或 --proxy 同时使用")
    if args.file and args.name:
        parser.error("批量模式由脚本生成名称，请勿传 --name")
    if not args.file and not args.name:
        parser.error("单个模式必须传 --name；批量模式请传 --file")

    try:
        client = IXBrowserClient(args.api_url)
        if args.file:
            proxies = load_proxy_file(args.file)
            profiles = client.list_browsers(name=f"{args.prefix}_")
            number = next_browser_number(profiles, args.prefix)
            failed = []
            for position, (line_number, proxy) in enumerate(proxies, start=1):
                name = f"{args.prefix}_{number}"
                print(f"[{position}/{len(proxies)}] 代理文件第 {line_number} 行")
                try:
                    _create(client, name, proxy, args)
                    number += 1
                except (RuntimeError, ValueError) as exc:
                    failed.append((line_number, str(exc)))
                    print(f"失败: {exc}", file=sys.stderr)
            print(f"批量完成：成功={len(proxies) - len(failed)} 失败={len(failed)}")
            return 1 if failed else 0

        if args.no_proxy:
            proxy = None
        else:
            proxy_value = args.proxy
            if proxy_value is None:
                proxy_value = getpass.getpass(
                    "代理信息（host:port:用户名:密码，直接回车表示不设置）: "
                )
            proxy = parse_proxy(proxy_value) if proxy_value.strip() else None
        profile_id = _create(client, args.name, proxy, args)
        print("\n将该 ID 与窗口名称保存到 ixBrowser 账号配置中：")
        print(f"profile_id: {profile_id}")
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
