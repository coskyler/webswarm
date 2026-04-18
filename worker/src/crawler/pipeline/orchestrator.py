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
from pydantic import BaseModel


PROMPT_DIR = Path(__file__).with_name("prompts")
LANDING_PROMPT = (PROMPT_DIR / "landing.txt").read_text(encoding="utf-8")
BOOKING_PROMPT = (PROMPT_DIR / "booking.txt").read_text(encoding="utf-8")
PROFILES_PROMPT = (PROMPT_DIR / "profiles.txt").read_text(encoding="utf-8")


class GetResult(BaseModel):
    ok: bool
    parsed: ParseResult | None = None
    followed_url: str | None = None
    message: str | None = None


def _get_content(url: str) -> GetResult:
    fetched: FetchResult = fetch(url)
    if not fetched.ok:
        return GetResult(ok=False, message=fetched.message)

    parsed: ParseResult = parse(fetched)
    if not parsed.ok:
        return GetResult(ok=False, message=parsed.message)

    return GetResult(ok=True, parsed=parsed, followed_url=fetched.url)


def run(operator: OperatorInfo) -> ClassifyResult:
    searched = False
    original_url = operator.url
    found_url = None

    # fetch and parse the URL
    landing_content: GetResult = _get_content(operator.url)
    if not landing_content.ok:
        # if provided URL fails, attempt to find the operator's website with google SERP
        url_search: SearchResult = search(operator)
        searched = True
        found_url = url_search.url
        if url_search.ok:
            landing_content: GetResult = _get_content(url_search.url)
            if not landing_content.ok:
                return ClassifyResult(
                    ok=False, message=landing_content.message, searched=searched, final_url=original_url
                )

        else:
            return ClassifyResult(
                ok=False,
                message=f"{landing_content.message}, {url_search.message}",
                searched=searched,
                final_url=original_url
            )

    # update operator URL to followed URL
    operator.url = landing_content.followed_url

    # classify content with LLM
    classification = classify(
        landing_content.parsed, operator, LANDING_PROMPT, ExpectedLanding
    )
    classification.searched = searched
    if not classification.ok:
        if (
            classification.message == "Webpage is not about the operator"
            and not searched
        ):
            # if provided URL fails, attempt to find the operator's website with google SERP
            url_search: SearchResult = search(operator)
            searched = True
            found_url = url_search.url
            if url_search.ok:
                landing_content: GetResult = _get_content(url_search.url)
                if landing_content.ok:
                    operator.url = landing_content.followed_url
                    new_classification = classify(
                        landing_content.parsed,
                        operator,
                        LANDING_PROMPT,
                        ExpectedLanding,
                    )
                    new_classification.searched = searched
                    new_classification.input_tokens += classification.input_tokens
                    new_classification.cached_input_tokens += classification.cached_input_tokens
                    new_classification.output_tokens += classification.output_tokens
                    if not new_classification.ok:
                        new_classification.message=f"{classification.message}, {new_classification.message}"
                        new_classification.final_url = original_url
                        return new_classification
                    classification = new_classification
                    classification.searched = searched
                else:
                    return ClassifyResult(
                        ok=False,
                        message=f"{classification.message}, {landing_content.message}",
                        searched=searched,
                        final_url=original_url
                    )
            else:
                return ClassifyResult(
                    ok=False,
                    message=f"{classification.message}, {url_search.message}",
                    searched=searched,
                    final_url=original_url
                )
        else:
            classification.final_url = original_url
            return classification
        
    classification.final_url = found_url or original_url

    # follow the booking page
    if classification.follow_booking:
        booking_content: GetResult = _get_content(classification.follow_booking)
        if booking_content.ok:
            booking_classification = classify(
                booking_content.parsed, operator, BOOKING_PROMPT, ExpectedBooking
            )
            if booking_classification.ok:
                classification.booking_method = booking_classification.booking_method
            else:
                print(booking_classification.message)

            # update total token usage
            classification.input_tokens += booking_classification.input_tokens
            classification.cached_input_tokens += (
                booking_classification.cached_input_tokens
            )
            classification.output_tokens += booking_classification.output_tokens
        else:
            print(booking_content.message)

    # follow the contacts page
    if classification.follow_contact:
        if classification.follow_contact == operator.url:
            contact_content = landing_content
        else:
            contact_content: GetResult = _get_content(classification.follow_contact)
        if contact_content.ok:
            contacts_classification = classify(
                contact_content.parsed, operator, PROFILES_PROMPT, ExpectedProfiles
            )
            if contacts_classification.ok:
                classification.profiles = contacts_classification.profiles
            else:
                print(contacts_classification.message)

            # update total token usage
            classification.input_tokens += contacts_classification.input_tokens
            classification.cached_input_tokens += (
                contacts_classification.cached_input_tokens
            )
            classification.output_tokens += contacts_classification.output_tokens
        else:
            print(contact_content.message)

    return classification
