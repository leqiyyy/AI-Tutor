from math import ceil


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def normalize_pagination(page: int = DEFAULT_PAGE, page_size: int = DEFAULT_PAGE_SIZE) -> tuple[int, int]:
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    return safe_page, safe_page_size


def pagination_meta(total: int, page: int, page_size: int) -> dict:
    safe_page, safe_page_size = normalize_pagination(page, page_size)
    return {
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "total_pages": ceil(total / safe_page_size) if safe_page_size else 1,
    }
