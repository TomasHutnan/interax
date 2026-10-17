"""Capture the README screenshots from a running InteraX instance.

Plays one realistic session: a patient (phone) scans a medication box, dictates more
medications, picks a regimen and gets a PIN; a doctor (desktop) logs in, opens the form
with that PIN and reviews the interactions. Nothing is sent to the FHIR repository and
the PIN is revoked at the end.

    pip install playwright && playwright install chromium
    INTERAX_DOCTOR_USER=... INTERAX_DOCTOR_PASSWORD=... \
        python docs/screenshots/capture.py [--url https://interax.hutnan.dev]

Needs macOS `say` (Czech voice "Zuzana") for the dictation audio.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

HERE = Path(__file__).resolve().parent
BOX_IMAGE = HERE / "assets" / "dithiaden.jpg"
DICTATION = (
    "Prestarium deset miligramů, jednu ráno. "
    "Warfarin tři miligramy, jednu večer. A Godasal sto, jednu ráno."
)
REGIMEN_QUERY = "FOLFOX"
REGIMEN = "FOLFOX4"
MODEL_TIMEOUT = 180_000  # OCR / transcription / interactions go through remote models
HIDE_TOASTS = "[data-slot=toast-viewport] { visibility: hidden !important; }"


def shot(
    page: Page,
    name: str,
    toasts: bool = False,
    around: str | None = None,
    region: list[str] | None = None,
    **kwargs,
) -> None:
    """Screenshot. `around` crops to an element plus a wide margin (for sparse pages);
    `region` crops the full page to the union of several elements."""
    path = HERE / f"{name}.png"
    style = None if toasts else page.add_style_tag(content=HIDE_TOASTS)
    if around:
        box = page.locator(around).first.bounding_box()
        kwargs["clip"] = {
            "x": box["x"] - 160,
            "y": box["y"] - 70,
            "width": box["width"] + 320,
            "height": box["height"] + 140,
        }
    if region:
        scroll_y = page.evaluate("window.scrollY")
        boxes = [page.locator(s).first.bounding_box() for s in region]
        top = min(b["y"] for b in boxes) + scroll_y - 16
        bottom = max(b["y"] + b["height"] for b in boxes) + scroll_y + 16
        width = page.viewport_size["width"]
        kwargs.update(full_page=True, clip={"x": 0, "y": top, "width": width, "height": bottom - top})
    page.screenshot(path=path, animations="disabled", **kwargs)
    if style:
        style.evaluate("el => el.remove()")
    print(f"  saved {path.relative_to(HERE.parent.parent)}")


def wait_toast(page: Page, text: str) -> None:
    page.get_by_text(text).first.wait_for(timeout=MODEL_TIMEOUT)


def make_dictation(tmp: Path) -> tuple[Path, float]:
    wav = tmp / "dictation.wav"
    subprocess.run(
        ["say", "-v", "Zuzana", "-o", str(wav), "--data-format=LEI16@48000", DICTATION],
        check=True,
    )
    with wave.open(str(wav)) as w:
        return wav, w.getnframes() / w.getframerate()


def patient_flow(page: Page, url: str, audio_seconds: float) -> str:
    print("patient: new form")
    page.goto(f"{url}/patient/view?id={int(time.time() * 1000)}")
    page.get_by_role("button", name="Scan").wait_for()

    print("patient: scan the box photo")
    page.locator("input[type=file]").set_input_files(BOX_IMAGE)
    wait_toast(page, "Medications updated from photo.")
    shot(page, "patient-scan", toasts=True)

    print("patient: dictate")
    hold = page.get_by_role("button", name="Hold to speak")
    hold.scroll_into_view_if_needed()
    box = hold.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.get_by_role("button", name="Recording...").wait_for()
    time.sleep(1.2)
    shot(page, "patient-recording")
    time.sleep(max(audio_seconds - 1.2, 0) + 0.6)
    page.mouse.up()
    wait_toast(page, "Medications updated from dictation.")
    time.sleep(0.5)
    shot(page, "patient-dictation", full_page=True)

    print("patient: regimen")
    regimen = page.get_by_role("textbox").last
    regimen.scroll_into_view_if_needed()
    regimen.fill(REGIMEN_QUERY)
    page.get_by_role("listbox").wait_for()
    time.sleep(0.3)
    shot(page, "patient-regimen", region=["section >> nth=-1", "[role=listbox]"])
    page.get_by_role("option", name=REGIMEN, exact=True).click()

    print("patient: save and get a code")
    page.get_by_role("button", name="Save").click()
    page.get_by_role("button", name="Get code").click()
    pin_text = page.get_by_text(re.compile(r"PIN: \d{6}"))
    pin_text.wait_for(timeout=30_000)
    time.sleep(0.5)
    shot(page, "patient-pin")
    return re.search(r"\d{6}", pin_text.inner_text()).group()


def doctor_flow(page: Page, url: str, user: str, password: str, pin: str) -> None:
    print("doctor: landing + login")
    page.goto(url)
    page.get_by_role("link", name="Doctor").wait_for()
    shot(page, "landing", around="h1 >> xpath=../..")

    page.goto(f"{url}/doctor")
    page.get_by_placeholder("Username").fill(user)
    page.get_by_placeholder("Password").fill(password)
    shot(page, "doctor-login", around="form")
    page.get_by_role("button", name="Login").click()

    print("doctor: enter PIN")
    page.get_by_text("Input patient PIN code to continue:").wait_for(timeout=30_000)
    page.locator("input[data-input-otp]").click()
    page.keyboard.type(pin, delay=60)
    time.sleep(0.3)
    shot(page, "doctor-pin", around="form")
    page.get_by_role("button", name="Continue").click()

    print("doctor: review")
    page.get_by_role("button", name="See interactions").wait_for(timeout=30_000)
    page.get_by_role("button", name="Apply components").click()
    expect(page.get_by_role("button", name="Delete substance").first).to_be_visible(
        timeout=30_000
    )
    shot(page, "doctor-review")

    print("doctor: interactions")
    page.get_by_role("button", name="See interactions").click()
    checking = page.get_by_text("Checking interactions...")
    try:
        checking.wait_for(timeout=5_000)
    except Exception:
        pass
    checking.wait_for(state="hidden", timeout=MODEL_TIMEOUT)
    # Hide the "unknown" noise, then hover the most severe hit to highlight its rows.
    slider = page.locator("input[type=range]")
    slider.focus()
    for _ in range(2):  # unknown -> minor -> moderate
        slider.press("ArrowRight")
    for severity in ("Contraindicated", "Major", "Moderate"):
        hit = page.locator("div.px-2.py-2").filter(has_text=severity)
        if hit.count():
            hit.first.hover()
            break
    time.sleep(0.3)
    shot(page, "doctor-interactions", full_page=True)

    print("doctor: finish dialog")
    page.mouse.move(0, 0)
    page.get_by_role("button", name="Finish viewing").click()
    page.get_by_text("Send to repository?").wait_for()
    page.get_by_text("Checking interactions...").wait_for(state="hidden", timeout=MODEL_TIMEOUT)
    time.sleep(0.5)
    shot(page, "doctor-finish")
    page.get_by_role("button", name="Finish without sending").click()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://interax.hutnan.dev")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    url = args.url.rstrip("/")

    user = os.environ.get("INTERAX_DOCTOR_USER")
    password = os.environ.get("INTERAX_DOCTOR_PASSWORD")
    if not user or not password:
        sys.exit("set INTERAX_DOCTOR_USER and INTERAX_DOCTOR_PASSWORD")

    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        audio, seconds = make_dictation(Path(tmp))
        browser = pw.chromium.launch(
            headless=not args.headed,
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                f"--use-file-for-fake-audio-capture={audio}",
            ],
        )
        common = {"locale": "en-GB", "timezone_id": "Europe/Prague", "color_scheme": "light"}

        phone = browser.new_context(
            **common,
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=False,  # mouse events, so the hold-to-speak button can be held
            permissions=["microphone"],
        )
        patient = phone.new_page()
        pin = patient_flow(patient, url, seconds)
        print(f"  PIN {pin}")

        desktop = browser.new_context(
            **common, viewport={"width": 1440, "height": 900}, device_scale_factor=2
        )
        doctor_flow(desktop.new_page(), url, user, password, pin)

        print("patient: revoke the code")
        patient.get_by_role("button", name="Revoke code").click()
        wait_toast(patient, "Code revoked.")
        browser.close()


if __name__ == "__main__":
    main()
