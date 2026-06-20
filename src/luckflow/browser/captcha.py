"""CaptchaFox auto-solver injection.

Ported from ``auto_solve_captchafox`` in the legacy ``luck_browser.py``. The
injected script intercepts CaptchaFox challenge responses and forwards the image
to the CaptchaSonic solving API, then drags the slider to the returned
coordinates. The API key now comes from ``settings.captcha.sonic_api_key``
instead of being baked into the source.
"""

from __future__ import annotations

from luckflow.config import settings
from luckflow.core import logging as log


async def auto_solve_captchafox(page, api_key: str | None = None) -> None:
    """Inject the automated CaptchaFox solver into ``page``.

    ``api_key`` defaults to the configured CaptchaSonic key.
    """
    key = api_key or settings.captcha.sonic_api_key
    if not key:
        log.warning("CaptchaSonic API key not configured — solver disabled")
        return

    log.info("🤖 Injecting CaptchaFox auto-solver...")
    js_code = """
    (() => {
        const CAPTCHA_SONIC_API_KEY = '__LUCKFLOW_API_KEY__';
        const originalFetch = window.fetch;

        window.fetch = async function(url, options) {
            const response = await originalFetch.apply(this, arguments);
            if (typeof url === 'string' && url.includes('api.captchafox.com') && url.includes('/challenge')) {
                const clonedResponse = response.clone();
                try {
                    const data = await clonedResponse.json();
                    if (data.challenge && data.challenge.bg) {
                        const base64Only = data.challenge.bg.replace(/^data:image\\/[a-z]+;base64,/, '');
                        setTimeout(() => { solveCaptchaAutomatically(base64Only); }, 1000);
                    }
                } catch (error) { console.error(error); }
            }
            return response;
        };

        async function solveCaptchaAutomatically(base64Image) {
            try {
                const payload = {
                    "apiKey": CAPTCHA_SONIC_API_KEY, "source": "chrome", "version": "0.2.1", "appID": 0,
                    "task": { "type": "slideImage", "queries": [base64Image], "websiteURL": window.location.href }
                };
                const response = await originalFetch("https://api.captchasonic.com/createTask", {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
                });
                const result = await response.json();
                if (result.code === 200) {
                    const [x, y] = result.answers;
                    setTimeout(() => { dragSliderToCoordinates(x, y); }, 500);
                } else { console.error('CaptchaSonic error:', result); }
            } catch (error) { console.error(error); }
        }

        async function dragSliderToCoordinates(apiX, apiY) {
            const sliderButton = document.querySelector('.cf-slider__button.cf-bpxtnj');
            const sliderTrack = document.querySelector('.cf-slider.cf-bpxtnj');
            if (!sliderButton || !sliderTrack) { console.error('Slider not found'); return; }

            const buttonRect = sliderButton.getBoundingClientRect();
            const trackRect = sliderTrack.getBoundingClientRect();
            const startX = buttonRect.left + buttonRect.width / 2;
            const startY = buttonRect.top + buttonRect.height / 2;
            const targetX = trackRect.left + (trackRect.width * apiX / 600);
            const targetY = trackRect.top + (trackRect.height * apiY / 120);
            const steps = 25, delay = 40;

            sliderButton.dispatchEvent(new MouseEvent('mousedown', {
                clientX: startX, clientY: startY, button: 0, buttons: 1, bubbles: true
            }));
            for (let i = 1; i <= steps; i++) {
                const progress = i / steps;
                const x = startX + (targetX - startX) * progress;
                const y = startY + (targetY - startY) * progress;
                const wobbleX = Math.sin(progress * Math.PI * 3) * 1;
                const wobbleY = Math.cos(progress * Math.PI * 4) * 0.5;
                sliderButton.dispatchEvent(new MouseEvent('mousemove', {
                    clientX: x + wobbleX, clientY: y + wobbleY, button: 0, buttons: 1, bubbles: true
                }));
                await new Promise(resolve => setTimeout(resolve, delay));
            }
            sliderButton.dispatchEvent(new MouseEvent('mouseup', {
                clientX: targetX, clientY: targetY, button: 0, buttons: 0, bubbles: true
            }));
        }

        window.captchaFoxSolverReady = true;
    })();
    """.replace("__LUCKFLOW_API_KEY__", key)

    await page.evaluate(js_code)
    log.success("✅ CaptchaFox auto-solver injected")
