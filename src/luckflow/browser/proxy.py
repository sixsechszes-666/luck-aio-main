"""Proxy file formatting helpers.

Ported from ``func/proxy_formatter.py``. Reads ``proxy.txt`` and converts each
``username:password@ip:port`` line into a Playwright proxy dict.
"""

from __future__ import annotations

from luckflow.core import logging as log

ProxyConfig = dict[str, str]


def format_proxies(path: str = "proxy.txt") -> list[ProxyConfig]:
    """Read proxies from ``path`` and return Playwright-ready proxy dicts.

    Each line is expected in ``username:password@ip:port`` form. Lines that do
    not match are skipped (logged as warnings) instead of aborting the run.
    """
    try:
        with open(path) as file:
            proxies = [line.strip() for line in file if line.strip()]

        log.info("Proxies found in file", str(len(proxies)))

        formatted_proxies: list[ProxyConfig] = []
        for proxy in proxies:
            try:
                if "@" in proxy:  # username:password@ip:port
                    auth, address = proxy.split("@")
                    username, password = auth.split(":")
                    ip, port = address.split(":")
                    proxy_dict: ProxyConfig = {
                        "server": f"http://{ip}:{port}",
                        "username": username,
                        "password": password,
                    }
                    formatted_proxies.append(proxy_dict)
                    log.success("Proxy parsed", proxy)
            except Exception:
                log.warning("Failed to parse proxy", proxy)

        log.info("Total formatted proxies", str(len(formatted_proxies)))
        return formatted_proxies

    except Exception as exc:
        log.error("Critical error reading proxies", str(exc))
        return []
