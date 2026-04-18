import json

from openai import OpenAI
from schema import SchemaError

from crawler.pipeline.types import OperatorInfo, ParseResult, ClassifyResult

client = OpenAI()


def classify(
    parsed: ParseResult,
    operator: OperatorInfo,
    prompt_context: str,
    expected_shape,
) -> ClassifyResult:
    prompt = (
        prompt_context
        + "\nSpecified operator: "
        + operator.name
        + "\nSpecified operator location: "
        + (operator.city + (", " if operator.city else "") + operator.country)
        + "\n\nYou are crawling "
        + operator.url
        + "\n\nHyperlink key:\n"
        + (parsed.hyperlink_key_text or "")
        + "\n\nParsed webpage HTML:\n"
        + (parsed.parsed_text or "")
    )

    try:
        res = client.responses.create(
            model="gpt-5-mini",
            service_tier="flex",
            input=prompt,
            # text={"verbosity": "low"},
            # reasoning={"effort": "low"},
            prompt_cache_key="AOIOUSJD98231u89hKAJSHf1982u3JKAHSDAKSHJD1982zxkhfkl",
        )
    except Exception:
        return ClassifyResult(ok=False, message="ChatGPT API error")

    result_meta = {
        "input_tokens": res.usage.input_tokens
        - res.usage.input_tokens_details.cached_tokens,
        "cached_input_tokens": res.usage.input_tokens_details.cached_tokens,
        "output_tokens": res.usage.output_tokens,
    }

    try:
        parsed_output = json.loads(res.output_text)
    except json.JSONDecodeError:
        return ClassifyResult(
            ok=False,
            message="ChatGPT provided invalid JSON",
            **result_meta,
        )

    try:
        expected_shape.validate(parsed_output)
    except SchemaError:
        return ClassifyResult(
            ok=False,
            message="ChatGPT provided invalid JSON schema",
            **result_meta,
        )

    if "ok" in parsed_output and not parsed_output["ok"]:
        return ClassifyResult(
            ok=False,
            message="LLM identified webpage error",
            **result_meta,
        )

    if "belongs_to_specified_operator" in parsed_output and not parsed_output["belongs_to_specified_operator"]:
        return ClassifyResult(
            ok=False,
            message="Webpage is not about the operator",
            **result_meta,
        )

    if "is_experience" in parsed_output and not parsed_output["is_experience"]:
        return ClassifyResult(
            ok=False,
            message="Webpage is not an experience",
            **result_meta,
        )

    result_values = dict(parsed_output)
    result_values.pop("ok", None)
    classification = result_values.pop("classification", None)
    if classification is not None:
        result_values.update(classification)

    return ClassifyResult(ok=True, **result_values, **result_meta)
