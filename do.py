import os
import re
import sys
import json
import math
import time
import shutil
import textwrap
import argparse
import subprocess
from pathlib import Path
from collections import Counter, defaultdict

import pyttsx3
from PIL import Image, ImageDraw, ImageFont
from bs4 import BeautifulSoup
import markdown as md


# =========================================================
# 설정
# =========================================================

VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
FPS = 30
TARGET_TOTAL_SECONDS = 300  # 5분
DEFAULT_BG = (10, 14, 24)
DEFAULT_FG = (240, 244, 255)
ACCENT = (83, 163, 255)
MUTED = (170, 180, 200)

SUPPORTED_CODE_EXT = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".kt", ".go", ".rs", ".cpp", ".c",
    ".cs", ".php", ".rb", ".swift", ".sql", ".html", ".css", ".scss", ".md", ".yml",
    ".yaml", ".json", ".xml", ".sh", ".bat", ".ps1", ".vue"
}

IGNORE_DIRS = {
    ".git", "node_modules", "dist", "build", "out", ".next", ".nuxt", ".idea",
    ".vscode", "__pycache__", "coverage", ".venv", "venv", ".mypy_cache", ".pytest_cache"
}

README_CANDIDATES = ["README.md", "readme.md", "Readme.md"]

# Windows 기본 폰트 후보
FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
]


# =========================================================
# 유틸
# =========================================================

def run_cmd(cmd, check=True):
    print("[CMD]", " ".join(map(str, cmd)))
    return subprocess.run(cmd, check=check)

def ffmpeg_filter_path(path: Path) -> str:
    # FFmpeg filter args treat ":" as an option separator, so Windows drive letters
    # and a few special characters need escaping inside filter values.
    escaped = path.resolve().as_posix()
    escaped = escaped.replace("\\", r"\\")
    escaped = escaped.replace(":", r"\:")
    escaped = escaped.replace("'", r"\'")
    return escaped

def safe_mkdir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def open_file_with_default_app(path: Path):
    try:
        if os.name == "nt":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as e:
        print(f"[WARN] 생성된 파일을 자동으로 열지 못했습니다: {e}")

def load_font(size=32, bold=False):
    for fp in FONT_CANDIDATES:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size=size)
            except Exception:
                pass
    return ImageFont.load_default()

def read_text_file(path: Path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="cp949")
        except Exception:
            try:
                return path.read_text(encoding="latin-1")
            except Exception:
                return ""

def clean_text(text: str):
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def estimate_speech_seconds(text: str, chars_per_sec=10.5):
    # 한국어/영어 혼합 대략치
    sec = max(4, int(len(text) / chars_per_sec))
    return sec

def shorten(text, max_len=240):
    text = clean_text(text)
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."

def shorten_lines(text, max_lines=8, max_chars=420):
    text = clean_text(text)
    if len(text) > max_chars:
        text = shorten(text, max_chars)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    kept = lines[:max_lines]
    kept[-1] = shorten(kept[-1], max(24, len(kept[-1]) - 3))
    if not kept[-1].endswith("..."):
        kept[-1] += " ..."
    return "\n".join(kept)

def normalize_display_text(text: str) -> str:
    text = text.replace("\\", "/")
    text = re.sub(r"\s*\|\s*", " | ", text)
    text = re.sub(r"\s*-\s*", " - ", text)
    text = re.sub(r",\s*", ", ", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"([/|])", r" \1 ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()

def format_count(n):
    return f"{n:,}"

def find_readme(repo_dir: Path):
    for name in README_CANDIDATES:
        p = repo_dir / name
        if p.exists():
            return p
    for p in repo_dir.glob("README*"):
        if p.is_file():
            return p
    return None


# =========================================================
# README 분석
# =========================================================

def markdown_to_plain_text(markdown_text: str) -> str:
    html = md.markdown(markdown_text)
    soup = BeautifulSoup(html, "html.parser")
    return clean_text(soup.get_text("\n"))

def extract_readme_sections(markdown_text: str):
    lines = markdown_text.splitlines()
    sections = []
    current_title = "소개"
    current_body = []

    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)", line.strip())
        if m:
            if current_body:
                sections.append({
                    "title": current_title,
                    "body": clean_text("\n".join(current_body))
                })
            current_title = m.group(2).strip()
            current_body = []
        else:
            current_body.append(line)

    if current_body:
        sections.append({
            "title": current_title,
            "body": clean_text("\n".join(current_body))
        })

    return [s for s in sections if s["body"]]

def summarize_readme(markdown_text: str):
    plain = markdown_to_plain_text(markdown_text)
    sections = extract_readme_sections(markdown_text)

    intro = shorten(plain, 500)

    important_sections = []
    for s in sections[:8]:
        important_sections.append({
            "title": s["title"],
            "summary": shorten(s["body"], 260)
        })

    badges = re.findall(r"!\[.*?\]\((.*?)\)", markdown_text)
    links = re.findall(r"\[.*?\]\((.*?)\)", markdown_text)

    return {
        "intro": intro,
        "sections": important_sections,
        "badge_count": len(badges),
        "link_count": len(links)
    }

def resolve_readme_asset_path(readme_path: Path, raw_path: str):
    asset = (raw_path or "").strip().strip("'\"")
    if not asset or re.match(r"^[a-z]+://", asset, re.IGNORECASE):
        return None
    asset = asset.split("?", 1)[0].split("#", 1)[0]
    candidate = (readme_path.parent / asset).resolve()
    if candidate.exists() and candidate.is_file():
        return candidate
    return None

def extract_readme_images(markdown_text: str, readme_path: Path):
    images = []

    for alt, src in re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", markdown_text):
        resolved = resolve_readme_asset_path(readme_path, src)
        if resolved:
            images.append({
                "alt": clean_text(alt) or resolved.stem,
                "src": src,
                "path": resolved
            })

    for src, alt in re.findall(r"<img[^>]*src=[\"']([^\"']+)[\"'][^>]*alt=[\"']([^\"']*)[\"'][^>]*>", markdown_text, re.IGNORECASE):
        resolved = resolve_readme_asset_path(readme_path, src)
        if resolved:
            images.append({
                "alt": clean_text(alt) or resolved.stem,
                "src": src,
                "path": resolved
            })

    for alt, src in re.findall(r"<img[^>]*alt=[\"']([^\"']*)[\"'][^>]*src=[\"']([^\"']+)[\"'][^>]*>", markdown_text, re.IGNORECASE):
        resolved = resolve_readme_asset_path(readme_path, src)
        if resolved:
            images.append({
                "alt": clean_text(alt) or resolved.stem,
                "src": src,
                "path": resolved
            })

    unique = []
    seen = set()
    for image in images:
        key = str(image["path"]).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(image)
    return unique

def normalize_markdown_line(line: str) -> str:
    line = line.rstrip()
    if not line:
        return ""
    if re.match(r"^\s*```", line):
        return ""
    line = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"[image] \1", line)
    line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", line)
    line = re.sub(r"`([^`]+)`", r"\1", line)
    line = re.sub(r"^\s*>\s?", "", line)
    if re.match(r"^\s*[-*+]\s+", line):
        line = re.sub(r"^\s*[-*+]\s+", "- ", line)
    elif re.match(r"^\s*\d+[.)]\s+", line):
        line = re.sub(r"^\s*(\d+[.)])\s+", r"\1 ", line)
    elif re.match(r"^\s*#{1,6}\s+", line):
        title = re.sub(r"^\s*#{1,6}\s+", "", line).strip()
        return title
    return clean_text(line)

def paginate_readme_for_slides(markdown_text: str, readme_path: Path, page_chars=380, max_pages=12):
    sections = extract_readme_sections(markdown_text)
    pages = []
    all_images = extract_readme_images(markdown_text, readme_path)
    image_cursor = 0

    for sec in sections:
        raw_lines = [normalize_markdown_line(line) for line in sec["body"].splitlines()]
        lines = [line for line in raw_lines if line]
        if not lines and image_cursor >= len(all_images):
            continue

        current = []
        current_len = 0
        page_no = 1

        for line in lines:
            line_len = max(len(line), 12)
            extra = line_len + (1 if current else 0)
            if current and current_len + extra > page_chars:
                pages.append({
                    "title": sec["title"],
                    "body": "\n".join(current),
                    "page_no": page_no
                })
                current = [line]
                current_len = line_len
                page_no += 1
            else:
                current.append(line)
                current_len += extra

        if current:
            pages.append({
                "title": sec["title"],
                "body": "\n".join(current),
                "page_no": page_no
            })

        if image_cursor < len(all_images):
            image = all_images[image_cursor]
            pages.append({
                "title": sec["title"],
                "body": image["alt"],
                "page_no": page_no + (1 if current else 0),
                "image_path": str(image["path"]),
                "image_caption": image["alt"]
            })
            image_cursor += 1

        if len(pages) >= max_pages:
            break

    total_pages = len(pages)
    for page in pages:
        page["page_total"] = total_pages
    return pages[:max_pages]


# =========================================================
# 소스코드 분석
# =========================================================

def should_skip_dir(dir_name: str):
    return dir_name in IGNORE_DIRS or dir_name.startswith(".")

def analyze_repo(repo_dir: Path):
    ext_counter = Counter()
    file_sizes = []
    dir_counter = Counter()
    code_files = []
    total_lines = 0
    total_files = 0
    special_files = []

    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]

        rel_root = Path(root).relative_to(repo_dir)
        if str(rel_root) != ".":
            top = str(rel_root.parts[0]) if rel_root.parts else "."
            dir_counter[top] += len(files)

        for file in files:
            fp = Path(root) / file
            rel = fp.relative_to(repo_dir)

            if fp.name.startswith("."):
                continue

            ext = fp.suffix.lower()
            total_files += 1

            if ext in SUPPORTED_CODE_EXT:
                ext_counter[ext] += 1
                code_files.append(rel)

                text = read_text_file(fp)
                lines = text.count("\n") + 1 if text else 0
                total_lines += lines
                file_sizes.append((rel, lines))

            lower_name = fp.name.lower()
            if lower_name in {
                "dockerfile", "docker-compose.yml", "docker-compose.yaml",
                "package.json", "requirements.txt", "pom.xml", "build.gradle",
                "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
                "server.js", "main.py", "app.py", "manage.py"
            }:
                special_files.append(str(rel))

    largest_files = sorted(file_sizes, key=lambda x: x[1], reverse=True)[:10]

    top_dirs = dir_counter.most_common(8)
    top_exts = ext_counter.most_common(10)

    return {
        "total_files": total_files,
        "total_lines": total_lines,
        "top_extensions": top_exts,
        "top_dirs": top_dirs,
        "largest_files": [(str(p), lines) for p, lines in largest_files],
        "special_files": special_files[:20],
        "code_file_count": sum(ext_counter.values())
    }

def detect_project_type(analysis):
    exts = dict(analysis["top_extensions"])
    specials = set(map(str.lower, analysis["special_files"]))

    if "package.json" in specials:
        if ".tsx" in exts or ".jsx" in exts:
            return "Node.js 기반 프론트엔드 또는 풀스택 프로젝트"
        return "Node.js 기반 프로젝트"

    if "requirements.txt" in specials or ".py" in exts:
        return "Python 기반 프로젝트"

    if "pom.xml" in specials or "build.gradle" in specials or ".java" in exts:
        return "Java 기반 프로젝트"

    if ".go" in exts:
        return "Go 기반 프로젝트"

    if ".rs" in exts:
        return "Rust 기반 프로젝트"

    return "복합 기술 스택 프로젝트"

def build_file_tree(repo_dir: Path, max_depth=2, max_items_per_dir=8):
    result = []

    def walk(path: Path, prefix="", depth=0):
        if depth > max_depth:
            return
        try:
            items = sorted(
                [p for p in path.iterdir() if not p.name.startswith(".") and p.name not in IGNORE_DIRS],
                key=lambda x: (x.is_file(), x.name.lower())
            )
        except Exception:
            return

        for i, item in enumerate(items[:max_items_per_dir]):
            connector = "└─ " if i == len(items[:max_items_per_dir]) - 1 else "├─ "
            result.append(prefix + connector + item.name)
            if item.is_dir():
                extension = "   " if i == len(items[:max_items_per_dir]) - 1 else "│  "
                walk(item, prefix + extension, depth + 1)

        if len(items) > max_items_per_dir:
            result.append(prefix + f"└─ ... ({len(items) - max_items_per_dir} more)")

    walk(repo_dir, "", 0)
    return "\n".join(result[:120])


# =========================================================
# 내레이션 스크립트 생성
# =========================================================

def create_video_outline(repo_name, readme_summary, repo_analysis, tree_text, readme_pages=None):
    project_type = detect_project_type(repo_analysis)

    top_ext_text = ", ".join(
        [f"{ext} {cnt}개" for ext, cnt in repo_analysis["top_extensions"][:5]]
    ) or "분석 가능한 코드 파일 정보가 많지 않습니다"

    top_dir_text = ", ".join(
        [f"{name}({cnt})" for name, cnt in repo_analysis["top_dirs"][:5]]
    ) or "주요 디렉터리 정보가 제한적입니다"

    big_files_text = ", ".join(
        [f"{name}({lines} lines)" for name, lines in repo_analysis["largest_files"][:5]]
    ) or "대형 파일 정보 없음"

    special_text = ", ".join(repo_analysis["special_files"][:8]) or "특별히 눈에 띄는 설정 파일은 많지 않습니다"

    sections = []

    sections.append({
        "title": f"{repo_name} 프로젝트 개요",
        "narration": (
            f"안녕하세요. 이번 영상에서는 GitHub 저장소 {repo_name} 를 분석합니다. "
            f"이 프로젝트는 전체적으로 {project_type} 성격을 가지고 있습니다. "
            f"먼저 README 문서를 기준으로 프로젝트 목적과 기능을 살펴보고, "
            f"그 다음 실제 소스 구조와 기술 스택, 그리고 확장 포인트를 순서대로 정리하겠습니다."
        )
    })

    sections.append({
        "title": "README 핵심 요약",
        "narration": (
            f"README를 보면 프로젝트의 핵심 설명은 다음과 같습니다. "
            f"{shorten(readme_summary['intro'], 420)} "
            f"문서 안에는 배지 {readme_summary['badge_count']}개, 링크 {readme_summary['link_count']}개가 포함되어 있어 "
            f"프로젝트 소개와 외부 연계 정보가 비교적 잘 정리된 편입니다."
        )
    })

    for page in readme_pages or []:
        page_label = f"{page['page_no']}/{page['page_total']}"
        sections.append({
            "title": f"README 슬라이드 - {page['title']}",
            "narration": (
                f"지금 보이는 화면은 README의 {page['title']} 섹션 {page_label} 페이지입니다. "
                "10초 동안 화면의 내용을 중심으로 프로젝트 설명을 읽어볼 수 있도록 구성했습니다."
            ),
            "display_body": page["body"],
            "duration": 10.0,
            "footer": f"README {page_label}",
            "image_path": page.get("image_path"),
            "image_caption": page.get("image_caption")
        })

    for sec in readme_summary["sections"][:4]:
        sections.append({
            "title": f"README 섹션: {sec['title']}",
            "narration": (
                f"다음은 README의 {sec['title']} 섹션입니다. "
                f"{shorten(sec['summary'], 380)}"
            )
        })

    sections.append({
        "title": "저장소 구조 분석",
        "narration": (
            f"이 저장소에는 총 {format_count(repo_analysis['total_files'])}개의 파일이 있으며, "
            f"분석 가능한 코드 파일은 {format_count(repo_analysis['code_file_count'])}개입니다. "
            f"전체 코드 라인 수는 대략 {format_count(repo_analysis['total_lines'])}줄 수준입니다. "
            f"주요 확장자는 {top_ext_text} 순으로 나타납니다."
        )
    })

    sections.append({
        "title": "주요 디렉터리와 파일",
        "narration": (
            f"디렉터리 분포를 보면 {top_dir_text} 중심으로 구성되어 있습니다. "
            f"특히 눈에 띄는 파일은 {special_text} 입니다. "
            f"이 파일들을 보면 프로젝트의 실행 방식, 배포 방식, 의존성 관리 방식을 대략 짐작할 수 있습니다."
        )
    })

    sections.append({
        "title": "복잡도가 큰 파일",
        "narration": (
            f"라인 수 기준으로 상대적으로 큰 파일은 {big_files_text} 입니다. "
            f"대형 파일은 보통 핵심 비즈니스 로직, UI 엔트리 포인트, 혹은 설정 집약 파일일 가능성이 높습니다. "
            f"리팩토링이나 기능 확장 시 이 파일들을 우선 검토하는 것이 효율적입니다."
        )
    })

    sections.append({
        "title": "폴더 트리 개요",
        "narration": (
            "프로젝트의 폴더 구조를 간단히 보면 기능별 분리 수준과 유지보수성을 가늠할 수 있습니다. "
            "일반적으로 루트에 설정 파일, 그 아래에 애플리케이션 소스, 그리고 필요시 자산이나 문서 폴더가 배치됩니다. "
            "구조가 명확할수록 협업과 배포 자동화가 수월해집니다."
        ),
        "extra_tree": tree_text
    })

    sections.append({
        "title": "기술적 해석",
        "narration": (
            f"이 저장소를 기술적으로 보면, README와 실제 코드 구성을 통해 "
            f"{project_type}의 전형적인 패턴이 어느 정도 드러납니다. "
            f"문서화 수준, 설정 파일 존재 여부, 소스 분리 정도를 기준으로 볼 때 "
            f"학습용, 포트폴리오용, 혹은 실서비스 확장용 기반으로 활용할 수 있습니다."
        )
    })

    sections.append({
        "title": "개선 포인트",
        "narration": (
            "개선 관점에서는 첫째, README에 실행 방법과 아키텍처 설명을 더 구조화하면 좋습니다. "
            "둘째, 대형 파일이 있다면 모듈 단위 분리를 고려할 수 있습니다. "
            "셋째, 테스트 코드와 배포 파이프라인 문서가 있다면 신뢰성이 높아집니다. "
            "넷째, 주요 기능 흐름을 다이어그램으로 추가하면 신규 참여자의 이해 속도가 빨라집니다."
        )
    })

    sections.append({
        "title": "마무리",
        "narration": (
            f"정리하면 {repo_name} 저장소는 README 기준 목적이 비교적 분명하고, "
            f"소스 구조상으로도 확장 가능성이 확인되는 프로젝트입니다. "
            f"앞으로는 실행 방법, 핵심 아키텍처, 주요 시나리오를 더 명확히 정리하면 "
            f"학습 자료이면서 동시에 포트폴리오 자료로도 더욱 강해질 수 있습니다. "
            f"이상으로 저장소 분석을 마치겠습니다."
        )
    })

    return sections


def rebalance_to_target(sections, target_seconds=300):
    # 내레이션 길이가 너무 짧으면 일부 문장을 확장
    total = sum(estimate_speech_seconds(s["narration"]) for s in sections)
    if total >= int(target_seconds * 0.85):
        return sections

    pad_sentence = (
        " 이 부분은 실제 구현 세부 사항과 운영 방식까지 함께 보면 더 정확하게 해석할 수 있습니다."
    )

    i = 0
    while total < target_seconds and i < 200:
        idx = i % len(sections)
        sections[idx]["narration"] += pad_sentence
        total = sum(estimate_speech_seconds(s["narration"]) for s in sections)
        i += 1

    return sections


# =========================================================
# TTS / 자막
# =========================================================

def tts_to_file(text, out_wav: Path, rate=165, voice_keyword=None):
    engine = pyttsx3.init()
    engine.setProperty("rate", rate)

    if voice_keyword:
        voices = engine.getProperty("voices")
        for v in voices:
            name = (getattr(v, "name", "") or "").lower()
            vid = (getattr(v, "id", "") or "").lower()
            if voice_keyword.lower() in name or voice_keyword.lower() in vid:
                engine.setProperty("voice", v.id)
                break

    engine.save_to_file(text, str(out_wav))
    engine.runAndWait()

def ffprobe_duration(file_path: Path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return 0.0
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0

def write_srt(srt_path: Path, segments):
    with srt_path.open("w", encoding="utf-8") as f:
        for idx, seg in enumerate(segments, start=1):
            start = seg["start"]
            end = seg["end"]
            text = seg["text"]

            def fmt(t):
                h = int(t // 3600)
                m = int((t % 3600) // 60)
                s = int(t % 60)
                ms = int((t - int(t)) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            f.write(f"{idx}\n")
            f.write(f"{fmt(start)} --> {fmt(end)}\n")
            f.write(text.strip() + "\n\n")


# =========================================================
# 슬라이드 생성
# =========================================================

def wrap_text_lines(draw, text, font, width):
    def text_width(value: str) -> int:
        if not value:
            return 0
        bbox = draw.textbbox((0, 0), value, font=font)
        return bbox[2] - bbox[0]

    def wrap_paragraph(paragraph: str):
        if not paragraph:
            return [""]

        tokens = re.findall(r"\S+\s*|\s+", paragraph)
        if not tokens:
            tokens = list(paragraph)

        lines = []
        current = ""
        for token in tokens:
            candidate = current + token
            if current and text_width(candidate.rstrip()) > width:
                stripped = token.strip()
                if text_width(token.rstrip()) > width and stripped:
                    for ch in stripped:
                        char_candidate = current + ch
                        if current and text_width(char_candidate) > width:
                            lines.append(current.rstrip())
                            current = ch
                        else:
                            current = char_candidate
                else:
                    lines.append(current.rstrip())
                    current = token.lstrip()
            else:
                current = candidate

        if current.strip():
            lines.append(current.rstrip())
        elif not lines:
            lines.append("")
        return lines

    lines = []
    for paragraph in text.splitlines() or [""]:
        lines.extend(wrap_paragraph(paragraph))
    return lines

def fit_text_block(draw, text, box, size_range, fill, bold=False, align="left", max_lines=None, min_line_spacing=6, max_line_spacing=14):
    x, y, w, h = box
    text = normalize_display_text(text)

    for size in range(size_range[0], size_range[1] - 1, -1):
        font = load_font(size, bold=bold)
        line_spacing = max(min_line_spacing, min(max_line_spacing, int(size * 0.35)))
        lines = wrap_text_lines(draw, text, font, w)
        if max_lines and len(lines) > max_lines:
            continue

        line_heights = []
        total_height = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line or "Ag", font=font)
            line_h = bbox[3] - bbox[1]
            line_heights.append(line_h)
            total_height += line_h
        if lines:
            total_height += line_spacing * (len(lines) - 1)

        if total_height <= h:
            cur_y = y + max(0, (h - total_height) // 2)
            for idx, line in enumerate(lines):
                bbox = draw.textbbox((0, 0), line or "Ag", font=font)
                line_w = bbox[2] - bbox[0]
                if align == "center":
                    draw_x = x + max(0, (w - line_w) // 2)
                else:
                    draw_x = x
                draw.text((draw_x, cur_y), line, font=font, fill=fill)
                cur_y += line_heights[idx] + line_spacing
            return size, len(lines)

    fallback_font = load_font(size_range[1], bold=bold)
    fallback_lines = wrap_text_lines(draw, text, fallback_font, w)
    if max_lines:
        fallback_lines = fallback_lines[:max_lines]
        if fallback_lines:
            fallback_lines[-1] = shorten(fallback_lines[-1], max(16, len(fallback_lines[-1]) - 3))
    line_spacing = min_line_spacing
    cur_y = y
    for line in fallback_lines:
        bbox = draw.textbbox((0, 0), line or "Ag", font=fallback_font)
        line_h = bbox[3] - bbox[1]
        if cur_y + line_h > y + h:
            break
        draw.text((x, cur_y), line, font=fallback_font, fill=fill)
        cur_y += line_h + line_spacing
    return size_range[1], len(fallback_lines)

def paste_contained_image(base_image, image_path: Path, box):
    x, y, w, h = box
    try:
        with Image.open(image_path) as src:
            rendered = src.convert("RGB")
            rendered.thumbnail((w, h))
            offset_x = x + max(0, (w - rendered.width) // 2)
            offset_y = y + max(0, (h - rendered.height) // 2)
            base_image.paste(rendered, (offset_x, offset_y))
            return True
    except Exception:
        return False

def create_slide_image(title, body, out_path: Path, footer="", tree_text=None, image_path=None, image_caption=None):
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), DEFAULT_BG)
    draw = ImageDraw.Draw(img)

    title_font = load_font(42, bold=True)
    body_font = load_font(30)
    small_font = load_font(20)

    # 상단 라인
    draw.rectangle((0, 0, VIDEO_WIDTH, 90), fill=(18, 25, 40))
    draw.rectangle((0, 88, VIDEO_WIDTH, 94), fill=ACCENT)

    draw.text((60, 28), title, font=title_font, fill=DEFAULT_FG)

    # 본문
    draw.rounded_rectangle((40, 118, VIDEO_WIDTH - 40, VIDEO_HEIGHT - 88), radius=24, fill=(14, 20, 32))
    text_bottom = 592 if tree_text else 606

    if image_path:
        image_box = (72, 146, VIDEO_WIDTH - 144, 330)
        draw.rounded_rectangle((68, 142, VIDEO_WIDTH - 68, 510), radius=20, fill=(22, 30, 46))
        loaded = paste_contained_image(img, Path(image_path), image_box)
        caption_text = image_caption or body
        if loaded and caption_text:
            draw_multiline(draw, caption_text, (72, 538, VIDEO_WIDTH - 144, 96), body_font, DEFAULT_FG, line_spacing=10)
        elif body:
            draw_multiline(draw, body, (72, 180, VIDEO_WIDTH - 144, 430), body_font, DEFAULT_FG, line_spacing=12)
    else:
        body_box = (72, 150, VIDEO_WIDTH - 144, 470)
        draw_multiline(draw, body, body_box, body_font, DEFAULT_FG, line_spacing=12)

    # 트리 또는 추가 정보
    if tree_text:
        tree_font = load_font(20)
        draw.rounded_rectangle((60, 420, VIDEO_WIDTH - 60, 650), radius=18, fill=(16, 22, 35))
        draw.text((80, 440), "폴더 구조 미리보기", font=load_font(24, bold=True), fill=ACCENT)
        draw_multiline(
            draw,
            tree_text,
            (80, 485, VIDEO_WIDTH - 160, 140),
            tree_font,
            MUTED,
            line_spacing=5
        )

    # 하단 푸터
    if footer:
        draw.text((60, VIDEO_HEIGHT - 48), footer, font=small_font, fill=MUTED)

    img.save(out_path)

def create_slide_image_v2(title, body, out_path: Path, footer="", tree_text=None, image_path=None, image_caption=None):
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), DEFAULT_BG)
    draw = ImageDraw.Draw(img)
    small_font = load_font(20)
    text_bottom = 592 if tree_text else 606

    draw.rectangle((0, 0, VIDEO_WIDTH, 104), fill=(18, 25, 40))
    draw.rectangle((0, 100, VIDEO_WIDTH, 106), fill=ACCENT)
    fit_text_block(
        draw,
        title,
        (56, 16, VIDEO_WIDTH - 112, 74),
        (38, 24),
        DEFAULT_FG,
        bold=True,
        max_lines=2
    )

    draw.rounded_rectangle((40, 130, VIDEO_WIDTH - 40, VIDEO_HEIGHT - 82), radius=24, fill=(14, 20, 32))

    if image_path:
        image_box = (84, 156, VIDEO_WIDTH - 168, 298)
        draw.rounded_rectangle((76, 148, VIDEO_WIDTH - 76, 468), radius=20, fill=(22, 30, 46))
        loaded = paste_contained_image(img, Path(image_path), image_box)
        caption_text = shorten_lines(image_caption or body, max_lines=4, max_chars=220)
        if loaded and caption_text:
            fit_text_block(
                draw,
                caption_text,
                (84, 494, VIDEO_WIDTH - 168, 108),
                (28, 20),
                DEFAULT_FG,
                max_lines=4
            )
        elif body:
            fit_text_block(
                draw,
                shorten_lines(body, max_lines=8, max_chars=320),
                (84, 188, VIDEO_WIDTH - 168, 360),
                (28, 18),
                DEFAULT_FG,
                max_lines=8
            )
    else:
        fit_text_block(
            draw,
            shorten_lines(body, max_lines=10, max_chars=520),
            (78, 158, VIDEO_WIDTH - 156, text_bottom - 158),
            (30, 18),
            DEFAULT_FG,
            max_lines=10
        )

    if tree_text:
        draw.rounded_rectangle((56, 414, VIDEO_WIDTH - 56, 646), radius=18, fill=(16, 22, 35))
        fit_text_block(
            draw,
            "프로젝트 구조 미리보기",
            (80, 430, VIDEO_WIDTH - 160, 28),
            (24, 20),
            ACCENT,
            bold=True,
            max_lines=1
        )
        fit_text_block(
            draw,
            shorten_lines(tree_text, max_lines=9, max_chars=360),
            (80, 474, VIDEO_WIDTH - 160, 146),
            (20, 14),
            MUTED,
            max_lines=9
        )

    if footer:
        draw.text((60, VIDEO_HEIGHT - 48), footer, font=small_font, fill=MUTED)

    img.save(out_path)


# =========================================================
# 영상 조립
# =========================================================

def create_video_from_sections(sections, work_dir: Path, final_mp4: Path):
    slides_dir = work_dir / "slides"
    audio_dir = work_dir / "audio"
    clips_dir = work_dir / "clips"
    safe_mkdir(slides_dir)
    safe_mkdir(audio_dir)
    safe_mkdir(clips_dir)

    srt_segments = []
    concat_list_path = work_dir / "concat.txt"
    concat_lines = []
    elapsed = 0.0

    for i, sec in enumerate(sections, start=1):
        slide_png = slides_dir / f"slide_{i:02d}.png"
        audio_wav = audio_dir / f"audio_{i:02d}.wav"
        clip_mp4 = clips_dir / f"clip_{i:02d}.mp4"
        body_text = sec.get("display_body", sec["narration"])
        footer_text = sec.get("footer", f"Section {i:02d}")
        duration_override = sec.get("duration")

        create_slide_image_v2(
            title=sec["title"],
            body=body_text,
            out_path=slide_png,
            footer=footer_text,
            tree_text=sec.get("extra_tree"),
            image_path=sec.get("image_path"),
            image_caption=sec.get("image_caption")
        )

        tts_to_file(sec["narration"], audio_wav, rate=165, voice_keyword=None)
        duration = duration_override or ffprobe_duration(audio_wav)
        if duration <= 0:
            duration = estimate_speech_seconds(sec["narration"])

        srt_segments.append({
            "start": elapsed,
            "end": elapsed + duration,
            "text": sec.get("subtitle_text", sec["narration"])
        })
        elapsed += duration

        # 슬라이드 1장 + 오디오로 클립 생성
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(slide_png),
            "-i", str(audio_wav),
            "-c:v", "libx264",
            "-t", f"{duration:.3f}",
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},fps={FPS}",
            "-af", f"apad=pad_dur={duration:.3f}",
            "-c:a", "aac",
            str(clip_mp4)
        ]
        run_cmd(cmd)

        concat_lines.append(f"file '{clip_mp4.as_posix()}'")

    concat_list_path.write_text("\n".join(concat_lines), encoding="utf-8")

    temp_video = work_dir / "joined.mp4"
    run_cmd([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_path),
        "-c", "copy",
        str(temp_video)
    ])

    srt_path = work_dir / "subtitles.srt"
    write_srt(srt_path, srt_segments)

    # 자막 입히기
    run_cmd([
        "ffmpeg", "-y",
        "-i", str(temp_video),
        "-vf", f"subtitles='{ffmpeg_filter_path(srt_path)}'",
        "-c:a", "copy",
        str(final_mp4)
    ])

    return srt_path


# =========================================================
# 메인
# =========================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="분석할 로컬 GitHub repo 경로")
    parser.add_argument("--out", default="./repo_video_output", help="출력 폴더")
    args = parser.parse_args()

    repo_dir = Path(args.repo).resolve()
    out_dir = Path(args.out).resolve()
    safe_mkdir(out_dir)

    if not repo_dir.exists():
        print(f"[ERROR] repo 경로가 없습니다: {repo_dir}")
        sys.exit(1)

    readme_path = find_readme(repo_dir)
    if not readme_path:
        print("[ERROR] README 파일을 찾지 못했습니다.")
        sys.exit(1)

    repo_name = repo_dir.name
    readme_text = read_text_file(readme_path)
    readme_summary = summarize_readme(readme_text)
    readme_pages = paginate_readme_for_slides(readme_text, readme_path, page_chars=380, max_pages=12)
    repo_analysis = analyze_repo(repo_dir)
    tree_text = build_file_tree(repo_dir, max_depth=2, max_items_per_dir=8)

    outline = create_video_outline(repo_name, readme_summary, repo_analysis, tree_text, readme_pages=readme_pages)
    outline = rebalance_to_target(outline, target_seconds=TARGET_TOTAL_SECONDS)

    # 결과 로그 저장
    analysis_json = {
        "repo_name": repo_name,
        "readme_path": str(readme_path),
        "readme_summary": readme_summary,
        "readme_pages": readme_pages,
        "repo_analysis": repo_analysis,
        "outline": outline
    }
    (out_dir / "analysis.json").write_text(
        json.dumps(analysis_json, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    final_mp4 = out_dir / f"{repo_name}_analysis_video.mp4"
    srt_path = create_video_from_sections(outline, out_dir, final_mp4)

    print("\n=== 완료 ===")
    print("분석 JSON :", out_dir / "analysis.json")
    print("자막 파일 :", srt_path)
    print("최종 영상 :", final_mp4)
    open_file_with_default_app(final_mp4)


if __name__ == "__main__":
    main()
