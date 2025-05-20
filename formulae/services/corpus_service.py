import re
def custom_par_sort_key(par: str) -> tuple[int, int]:
    """
    Extracts a sortable key from a folio identifier string containing embedded HTML.

    The input `par` is expected to look like:
        '0106<span class="verso-recto">v</span>-107<span class="verso-recto">r</span>'

    The function:
    - Extracts the first folio number and its suffix (e.g., 'r', 'v', 'bisr', 'bisv')
    - Strips leading zeros from the number
    - Maps the suffix to a defined order
    - Returns a tuple (number: int, suffix_rank: int) for use in sorting

    More information on how folio are sorted: https://de.wikipedia.org/wiki/Folium
    The 'bis' exception is novel in Sens

    :param par: The HTML-formatted folio identifier
    :return: A tuple used for custom sorting
    """
    SUFFIX_ORDER = {'r': 0, 'v': 1, 'bisr': 2, 'bisv': 3}

    # Find all number–suffix pairs like: 0106<span class="verso-recto">v</span>
    matches = re.findall(r'(\d+)<span class="verso-recto">(.*?)</span>', par)

    if matches:
        number_str, suffix = matches[0]
        number = int(number_str.lstrip('0') or '0')  # Normalize e.g. '0106' → 106
        suffix_rank = SUFFIX_ORDER.get(suffix, 99)   # Default to 99 for unknown suffixes
        return (number, suffix_rank)

    # Fallback: non-matching strings are sorted last
    return (9999, 99)