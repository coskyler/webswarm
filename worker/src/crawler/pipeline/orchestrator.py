from pathlib import Path

from crawler.pipeline.fetcher import fetch
from crawler.pipeline.parser import parse
from crawler.pipeline.classifier import classify
from crawler.pipeline.searcher import search
from crawler.pipeline.prompts.expected_shapes import (
    ExpectedBooking,
    ExpectedLanding,
    ExpectedProfiles,
)
from crawler.pipeline.types import (
    OperatorInfo,
    FetchResult,
    ParseResult,
    ClassifyResult,
    SearchResult,
)
from schema import Schema
from crawler.pipeline.trace import Trace


_PROMPT_DIR = Path(__file__).with_name("prompts")
_LANDING_PROMPT = (_PROMPT_DIR / "landing.txt").read_text(encoding="utf-8")
_BOOKING_PROMPT = (_PROMPT_DIR / "booking.txt").read_text(encoding="utf-8")
_PROFILES_PROMPT = (_PROMPT_DIR / "profiles.txt").read_text(encoding="utf-8")


def _classify_pipeline(url: str, operator: OperatorInfo, prompt: str, model_output_shape: Schema, trace: Trace) -> tuple[ClassifyResult, str | None]:
    fetched: FetchResult = fetch(url, trace=trace)
    if not fetched.ok:
        return ClassifyResult(ok=False, message=fetched.message, final_url=fetched.url, used_stealth=fetched.used_stealth), "fetch"

    parsed: ParseResult = parse(fetched, trace=trace)
    if not parsed.ok:
        return ClassifyResult(ok=False, message=parsed.message, final_url=fetched.url, used_stealth=fetched.used_stealth), "parse"
    
    classification: ClassifyResult = classify(parsed, operator, prompt, model_output_shape, trace=trace)
    if not classification.ok:
        return ClassifyResult(ok=False, message=classification.message, final_url=fetched.url, used_stealth=fetched.used_stealth), "classification"
    
    classification.final_url = fetched.url
    classification.used_stealth = fetched.used_stealth
    return classification, None


def run(operator: OperatorInfo, trace: Trace) -> ClassifyResult:
    classification, landing_err = _classify_pipeline(operator.url, operator, _LANDING_PROMPT, ExpectedLanding, trace)

    # if the pipeline fails, retry once with a serped URL
    if landing_err and not (landing_err == "classification" and classification.message != "Webpage is not about the operator"):
        searched: SearchResult = search(operator, trace=trace)
        classification.searched = True

        if searched.ok:
            searched_classification, searched_err = _classify_pipeline(searched.url, operator, _LANDING_PROMPT, ExpectedLanding, trace)
            classification.merge(searched_classification)

            if searched_err:
                return classification
        else:
            classification.merge(ClassifyResult(ok=False, message=searched.message))
            return classification
            
    if classification.follow_booking:
        booking_classification, booking_err = _classify_pipeline(classification.follow_booking, operator, _BOOKING_PROMPT, ExpectedBooking, trace)
        classification.merge(booking_classification)

    if classification.follow_contact:
        profiles_classification, profiles_err = _classify_pipeline(classification.follow_contact, operator, _PROFILES_PROMPT, ExpectedProfiles, trace)
        classification.merge(profiles_classification)
    
    return classification
