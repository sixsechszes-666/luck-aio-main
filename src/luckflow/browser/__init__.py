"""Browser automation layer: ixBrowser lifecycle, proxies, extensions, sessions."""

from luckflow.browser.captcha import auto_solve_captchafox
from luckflow.browser.ixbrowser import (
    cleanup_browser_resources,
    clear_pages,
    create_new_tab,
    find_websocket_endpoint,
    get_available_tabs,
    launch_ixbrowser_profile,
    stop_ixbrowser_profile,
)
from luckflow.browser.proxy import format_proxies
from luckflow.browser.session import (
    decode_qr_from_svg_path,
    find_qr_code_element,
    get_and_decode_qr_code,
    get_and_decode_qr_via_svg,
    wait_for_new_qr_code,
)

__all__ = [
    "launch_ixbrowser_profile",
    "stop_ixbrowser_profile",
    "clear_pages",
    "cleanup_browser_resources",
    "get_available_tabs",
    "create_new_tab",
    "find_websocket_endpoint",
    "format_proxies",
    "auto_solve_captchafox",
    "decode_qr_from_svg_path",
    "get_and_decode_qr_code",
    "get_and_decode_qr_via_svg",
    "find_qr_code_element",
    "wait_for_new_qr_code",
]
