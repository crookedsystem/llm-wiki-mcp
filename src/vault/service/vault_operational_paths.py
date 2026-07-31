import re

LOG_NOTE_PATH = "log.md"
INDEX_NOTE_PATH = "index.md"
ROOT_OPERATIONAL_FILES = frozenset({"SCHEMA.md", INDEX_NOTE_PATH, LOG_NOTE_PATH})
LOG_ARCHIVE_PATTERN = re.compile(r"^log-(\d{4})\.md$")


def log_archive_path(year: str) -> str:
    """지난 연도 changelog를 담는 archive note의 vault 상대 경로를 만듭니다."""
    return f"log-{year}.md"


def log_archive_year(relative_path: str) -> str | None:
    """log archive note면 그 연도를, 아니면 None을 돌려줍니다."""
    matched = LOG_ARCHIVE_PATTERN.match(relative_path)
    return matched.group(1) if matched else None


def is_operational_note(relative_path: str) -> bool:
    """도구가 자동으로 유지하는 note인지 판단합니다.

    root 운영 파일 세 개와 연도별 log archive가 여기에 해당하며, 사용자 note와 달리
    changelog/index 유지 대상에서 제외되고 삭제 정리 후보로도 제시되지 않습니다.
    """
    return relative_path in ROOT_OPERATIONAL_FILES or log_archive_year(relative_path) is not None
