"""Case categorization helpers for stratified evaluation."""


def classify_retrieval_case(case_id: str) -> str:
    """Bucket a retrieval case by what it stresses.

    Categories:
      - negative:   no relevant tickets exist (pass = nothing retrieved)
      - paraphrase: same gold as an original case, different surface form
      - english:    English query against the Norwegian corpus
      - original:   the baseline Norwegian phrasing
    """
    if case_id.startswith("negative_"):
        return "negative"
    if case_id.endswith("_paraphrase"):
        return "paraphrase"
    if case_id.endswith("_english"):
        return "english"
    return "original"
