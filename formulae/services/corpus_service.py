import re

def extract_folio_sort_key(par: str) -> tuple[int, int]:
    """
    Extracts a sortable key from a folio identifier string containing embedded HTML.

    The input `par` is expected to look like:
        '28 bis<span class="verso-recto">r</span>'
        '107<span class="verso-recto">v</span>'
        '0106<span class="verso-recto">bisr</span>'

    The function:
    - Extracts the first folio number and its suffix
    - Handles optional 'bis' between number and suffix
    - Normalizes number and assigns sort priority to suffixes
    - Returns a tuple (int, int) for sorting

    :param par: The HTML-formatted folio identifier
    :return: A tuple used for custom sorting
    """
    SUFFIX_ORDER = {'r': 0, 'v': 1, 'bisr': 2, 'bisv': 3}

    # Match: number, optional ' bis', then verso/recto span
    match = re.search(r'(\d+)(?:\s+bis)?<span class="verso-recto">(\w+)</span>', par)

    if match:
        number_str, suffix = match.groups()
        number = int(number_str.lstrip('0') or '0')
        suffix_rank = SUFFIX_ORDER.get(suffix, 99)
        return (number, suffix_rank)

    # Fallback: sort last
    return (9999, 99)
