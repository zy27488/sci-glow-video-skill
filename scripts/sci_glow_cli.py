#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""CLI helper for sci-glow-video-skill: preflight, scaffolding, BGM climax analysis,
lines validation, and quantitative QA auditing with blind-review prompt generation.

All subcommands write deterministic UTF-8 (no-BOM) JSON to --output and print
only a concise status line to stdout.
"""

from __future__ import annotations

import argparse
from array import array
import contextlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from urllib import error as urllib_error
from urllib import request as urllib_request

try:
    import msvcrt  # type: ignore
except ImportError:  # pragma: no cover
    msvcrt = None  # type: ignore

try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


SIZES: dict[str, tuple[int, int]] = {
    '3x4': (1080, 1440),
    '9x16': (1080, 1920),
    '16x9': (1920, 1080),
    '1x1': (1440, 1440),
    '4x5': (1080, 1350),
}

PLEX_WEIGHTS: list[tuple[str, int]] = [
    ('IBMPlexSansSC-Thin.otf', 100),
    ('IBMPlexSansSC-ExtraLight.otf', 200),
    ('IBMPlexSansSC-Light.otf', 300),
    ('IBMPlexSansSC-Regular.otf', 400),
    ('IBMPlexSansSC-Text.otf', 450),
    ('IBMPlexSansSC-Medium.otf', 500),
    ('IBMPlexSansSC-SemiBold.otf', 600),
    ('IBMPlexSansSC-Bold.otf', 700),
]

JSDELIVR_PLEX_BASE = (
    'https://cdn.jsdelivr.net/gh/IBM/plex@%40ibm/plex-sans-sc%401.1.0/'
    'packages/plex-sans-sc/fonts/complete/otf/unhinted'
)
GITHUB_RAW_PLEX_BASE = (
    'https://raw.githubusercontent.com/IBM/plex/%40ibm/plex-sans-sc%401.1.0/'
    'packages/plex-sans-sc/fonts/complete/otf/unhinted'
)

TRAIL_PUNCT = set('。．.，,、；;：:！!？?…—–-~～·')
CLOSE_BRACKETS = set('”’」』》〉）)】]')


class RateLimitError(Exception):
    """Raised when the remote CDN rate limit (HTTP 429) is exceeded."""


@contextlib.contextmanager
def _cross_process_lock(lock_path: Path):
    """Acquire an advisory OS file lock so concurrent subagents share rate limits."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, 'a+b') as fh:
        if msvcrt is not None:
            fh.seek(0)
            while True:
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
            try:
                yield fh
            finally:
                fh.seek(0)
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
        elif fcntl is not None:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield fh
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        else:  # pragma: no cover
            yield fh


class CDNFontFetcher:
    """Rate-limited HTTP client for fetching missing IBM Plex Sans SC OTF fonts.

    Enforces <= 1 request/second using time.monotonic() and a cross-process file
    lock, exponential backoff on 5xx/network errors, and dedicated RateLimitError
    handling on HTTP 429.
    """

    REQUESTS_PER_SECOND = 1.0
    LOCK_PATH = Path(tempfile.gettempdir()) / 'sci_glow_cdn_font_ratelimit.lock'

    def __init__(self) -> None:
        self.delay = 1.0 / self.REQUESTS_PER_SECOND
        self.last_request_time = 0.0

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def _download_url(self, url: str, dest: Path, retries: int = 3) -> None:
        tmp_path = dest.with_suffix(dest.suffix + '.part')
        for attempt in range(retries):
            with _cross_process_lock(self.LOCK_PATH):
                self._wait_for_rate_limit()
                try:
                    req = urllib_request.Request(
                        url,
                        headers={'User-Agent': 'sci-glow-video-skill/1.0'},
                    )
                    with urllib_request.urlopen(req, timeout=60) as resp:
                        self.last_request_time = time.monotonic()
                        with open(tmp_path, 'wb') as out_fh:
                            shutil.copyfileobj(resp, out_fh, 1 << 18)
                    header = tmp_path.read_bytes()[:4]
                    if header not in (b'OTTO', b'\x00\x01\x00\x00', b'true'):
                        raise ValueError(
                            f'Downloaded file from {url} is not a valid SFNT/OTF font.'
                        )
                    os.replace(tmp_path, dest)
                    return
                except urllib_error.HTTPError as exc:
                    self.last_request_time = time.monotonic()
                    if tmp_path.exists():
                        tmp_path.unlink(missing_ok=True)
                    if exc.code == 429:
                        wait = 2**attempt
                        print(
                            f'Rate limited (429) on {url}, retrying in {wait}s '
                            f'(attempt {attempt + 1}/{retries})...',
                            file=sys.stderr,
                        )
                        if attempt == retries - 1:
                            raise RateLimitError(
                                f'HTTP 429 Too Many Requests from {url}. '
                                f'CDN rate limit ({self.REQUESTS_PER_SECOND} req/s) '
                                f'exceeded after {retries} retries.'
                            ) from exc
                        time.sleep(wait)
                        continue
                    if exc.code >= 500:
                        wait = 2**attempt
                        print(
                            f'Server error {exc.code} from {url}, retrying in {wait}s '
                            f'(attempt {attempt + 1}/{retries})...',
                            file=sys.stderr,
                        )
                        if attempt == retries - 1:
                            raise RuntimeError(
                                f'HTTP {exc.code} from {url} '
                                f'(rate limit {self.REQUESTS_PER_SECOND} req/s) '
                                f'after {retries} retries.'
                            ) from exc
                        time.sleep(wait)
                        continue
                    try:
                        body = exc.read().decode('utf-8', errors='replace')[:1000]
                    except OSError:
                        body = str(exc.reason)
                    raise RuntimeError(
                        f'HTTP {exc.code} from {url} '
                        f'(rate limit {self.REQUESTS_PER_SECOND} req/s): {body}'
                    ) from exc
                except (urllib_error.URLError, OSError, ValueError) as exc:
                    self.last_request_time = time.monotonic()
                    if tmp_path.exists():
                        tmp_path.unlink(missing_ok=True)
                    if attempt == retries - 1:
                        raise RuntimeError(
                            f'Failed to download {url} after {retries} attempts '
                            f'(rate limit {self.REQUESTS_PER_SECOND} req/s): {exc}'
                        ) from exc
                    wait = 2**attempt
                    print(
                        f'Transient error on {url}: {exc}; retrying in {wait}s '
                        f'(attempt {attempt + 1}/{retries})...',
                        file=sys.stderr,
                    )
                    time.sleep(wait)

    def fetch_font(self, filename: str, dest_dir: Path, custom_url: str | None = None) -> str:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filename
        candidates = [f'{JSDELIVR_PLEX_BASE}/{filename}']
        if custom_url:
            candidates.append(custom_url)
        else:
            candidates.append(f'{GITHUB_RAW_PLEX_BASE}/{filename}')
        last_err: Exception | None = None
        for url in candidates:
            try:
                self._download_url(url, dest)
                return url
            except RateLimitError:
                raise
            except Exception as exc:
                last_err = exc
                print(
                    f'Fallback triggered after failure on {url}: {exc}',
                    file=sys.stderr,
                )
        raise RuntimeError(f'All mirrors failed for {filename}: {last_err}')


def write_output(data: dict | list, output_file: str) -> None:
    """Writes data to a UTF-8 (no-BOM) JSON file and prints a short status."""
    out_path = Path(output_file)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write('\n')
        print(f'Success! Data written to: {out_path}')
    except (OSError, TypeError) as exc:
        print(f'Error writing output JSON to {out_path}: {exc}', file=sys.stderr)
        sys.exit(1)


def find_skill_dir(name: str, explicit: str | None = None) -> Path | None:
    """Locate an upstream skill directory across common agent skill roots."""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        return p if p.is_dir() else None

    here = Path(__file__).resolve()
    skill_root = here.parents[1]
    candidates = [
        skill_root.parent / name,
        Path.cwd() / '.agents' / 'skills' / name,
        Path.cwd() / '.claude' / 'skills' / name,
        Path.home() / '.gemini' / 'antigravity' / 'skills' / name,
        Path.home() / '.gemini' / 'config' / 'skills' / name,
        Path.home() / '.claude' / 'skills' / name,
        Path.home() / '.agents' / 'skills' / name,
    ]
    for cand in candidates:
        if cand.is_dir() and (cand / 'SKILL.md').is_file():
            return cand.resolve()
    return None


def find_chrome() -> str | None:
    """Locate local Chromium or Google Chrome binary."""
    env_chrome = os.environ.get('CHROME_PATH') or os.environ.get('CHROMIUM_PATH')
    if env_chrome and Path(env_chrome).is_file():
        return env_chrome
    candidates = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/usr/bin/google-chrome',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
    ]
    for c in candidates:
        if Path(c).is_file():
            return c
    for cmd in ('google-chrome', 'chromium', 'chrome'):
        found = shutil.which(cmd)
        if found:
            return found
    return None


def find_playwright(upstream_dir: Path | None) -> str | None:
    """Detect installed playwright package in workspace or global npm."""
    search_roots = [
        Path.cwd(),
        Path.cwd() / '.code',
        upstream_dir / 'scripts' if upstream_dir else None,
    ]
    for root in search_roots:
        if not root:
            continue
        for sub in (root / 'node_modules' / 'playwright', root.parent / 'node_modules' / 'playwright'):
            if sub.is_dir():
                return str(sub)
    node_bin = shutil.which('node')
    npm_bin = shutil.which('npm')
    if node_bin and npm_bin:
        res = subprocess.run(
            [npm_bin, 'root', '-g'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
        )
        g_root = res.stdout.strip()
        if g_root and (Path(g_root) / 'playwright').is_dir():
            return str(Path(g_root) / 'playwright')
    return None


def find_system_python_with_numpy() -> str | None:
    """Find a system Python executable that has numpy installed for upstream scripts."""
    candidates: list[str] = []
    for cmd in ('python', 'python3', 'py'):
        p = shutil.which(cmd)
        if p:
            candidates.append(p)
    for static in (r'D:\python\python.exe', sys.executable):
        if static and Path(static).is_file() and static not in candidates:
            candidates.append(static)

    seen: set[str] = set()
    for py in candidates:
        norm = str(Path(py).resolve()).lower()
        if norm in seen:
            continue
        seen.add(norm)
        probe = subprocess.run(
            [py, '-c', 'import numpy, scipy; print("OK")'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
        )
        if probe.returncode == 0 and 'OK' in probe.stdout:
            return py
    return None


def cmd_preflight(args: argparse.Namespace) -> None:
    upstream_anim = find_skill_dir('lead-knowledge-animation', args.upstream_dir)
    upstream_script = find_skill_dir('lead-media-script')

    node_bin = shutil.which('node')
    node_ver = None
    node_ok = False
    if node_bin:
        res = subprocess.run([node_bin, '-v'], capture_output=True, text=True, encoding='utf-8')
        node_ver = res.stdout.strip()
        m = re.match(r'^v?(\d+)', node_ver)
        node_ok = bool(m and int(m.group(1)) >= 18)

    ffmpeg_bin = shutil.which('ffmpeg')
    ffprobe_bin = shutil.which('ffprobe')
    chrome_bin = find_chrome()
    pw_path = find_playwright(upstream_anim)
    sys_py = find_system_python_with_numpy()

    font_dir = (upstream_anim / 'assets' / 'fonts') if upstream_anim else None
    manifest_urls: dict[str, str] = {}
    if font_dir and (font_dir / 'fonts.json').is_file():
        mf = json.loads((font_dir / 'fonts.json').read_text(encoding='utf-8'))
        for item in mf.get('fonts', []):
            manifest_urls[item['file']] = item.get('url', '')

    font_dirs_to_check: list[Path] = []
    if os.environ.get('LEAD_FONT_DIR'):
        font_dirs_to_check.append(Path(os.environ['LEAD_FONT_DIR']))
    if font_dir:
        font_dirs_to_check.append(font_dir)

    missing_fonts: list[str] = []
    found_fonts: dict[str, str] = {}
    for fname, _weight in PLEX_WEIGHTS:
        hit = None
        for fd in font_dirs_to_check:
            cand = fd / fname
            if cand.is_file() and cand.stat().st_size > 10_000:
                hit = str(cand)
                break
        if hit:
            found_fonts[fname] = hit
        else:
            missing_fonts.append(fname)

    downloaded_fonts: list[dict[str, str]] = []
    if args.auto_fix_fonts and missing_fonts:
        if not font_dir:
            print('Error: Cannot auto-fix fonts because lead-knowledge-animation dir was not found.', file=sys.stderr)
            sys.exit(1)
        fetcher = CDNFontFetcher()
        for fname in list(missing_fonts):
            used_url = fetcher.fetch_font(fname, font_dir, manifest_urls.get(fname))
            downloaded_fonts.append({'file': fname, 'url': used_url, 'dest': str(font_dir / fname)})
            found_fonts[fname] = str(font_dir / fname)
            missing_fonts.remove(fname)

    remediations: list[str] = []
    if not upstream_anim:
        remediations.append('Install upstream engine skill: AzenYes/leaderai-media-toolkit (lead-knowledge-animation).')
    if not upstream_script:
        remediations.append('Install upstream scriptwriter skill: AzenYes/leaderai-media-toolkit (lead-media-script).')
    if not node_ok:
        remediations.append('Install Node.js 18+ and ensure `node` is on PATH.')
    if not ffmpeg_bin or not ffprobe_bin:
        remediations.append('Install FFmpeg + FFprobe and ensure both are on PATH.')
    if not chrome_bin:
        remediations.append('Install Google Chrome or set CHROME_PATH environment variable.')
    if not pw_path:
        remediations.append(
            'Install playwright without re-downloading Chromium: '
            '$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD="1"; npm i playwright --registry https://registry.npmmirror.com'
        )
    if not sys_py:
        remediations.append('Install numpy and scipy in system Python: pip install numpy scipy fonttools')
    if missing_fonts:
        remediations.append('Re-run `preflight --auto-fix-fonts` to download missing IBM Plex Sans SC OTF weights.')

    ok = all([
        bool(upstream_anim),
        bool(upstream_script),
        node_ok,
        bool(ffmpeg_bin),
        bool(ffprobe_bin),
        bool(chrome_bin),
        bool(pw_path),
        bool(sys_py),
        len(missing_fonts) == 0,
    ])

    write_output(
        {
            'ok': ok,
            'checks': {
                'node': {'ok': node_ok, 'version': node_ver, 'path': node_bin},
                'ffmpeg': {'ok': bool(ffmpeg_bin), 'path': ffmpeg_bin},
                'ffprobe': {'ok': bool(ffprobe_bin), 'path': ffprobe_bin},
                'chrome': {'ok': bool(chrome_bin), 'path': chrome_bin},
                'playwright': {'ok': bool(pw_path), 'path': pw_path},
                'python_numpy_scipy': {'ok': bool(sys_py), 'path': sys_py},
                'upstream_knowledge_animation': {'ok': bool(upstream_anim), 'path': str(upstream_anim) if upstream_anim else None},
                'upstream_media_script': {'ok': bool(upstream_script), 'path': str(upstream_script) if upstream_script else None},
                'ibm_plex_sans_sc_fonts': {
                    'ok': len(missing_fonts) == 0,
                    'found_count': len(found_fonts),
                    'expected_count': len(PLEX_WEIGHTS),
                },
            },
            'found_fonts': found_fonts,
            'missing_fonts': missing_fonts,
            'downloaded_fonts': downloaded_fonts,
            'remediations': remediations,
        },
        args.output,
    )


def cmd_scaffold_project(args: argparse.Namespace) -> None:
    upstream_anim = find_skill_dir('lead-knowledge-animation', args.upstream_dir)
    if not upstream_anim:
        print('Error: Cannot find upstream lead-knowledge-animation skill directory.', file=sys.stderr)
        sys.exit(1)

    workspace = Path(args.workspace).expanduser().resolve()
    script_dir = workspace / '口播文案输出' / f'{args.date} {args.topic}科普'
    anim_dir = workspace / '.code' / f'{args.date} {args.topic}科普动画'
    script_dir.mkdir(parents=True, exist_ok=True)
    anim_dir.mkdir(parents=True, exist_ok=True)

    ratio_for_new = '9x16' if args.ratio == '3x4' else args.ratio
    new_film_mjs = upstream_anim / 'scripts' / 'new_film.mjs'
    proc = subprocess.run(
        ['node', str(new_film_mjs), str(anim_dir), '--ratio', ratio_for_new, '--fonts', 'sans'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    if proc.returncode != 0:
        print(f'Error running new_film.mjs:\n{proc.stderr or proc.stdout}', file=sys.stderr)
        sys.exit(1)

    index_html = anim_dir / 'film' / 'index.html'
    html = index_html.read_text(encoding='utf-8')

    if args.ratio == '3x4':
        html = html.replace("get('ratio') || '9x16'", "get('ratio') || '3x4'")
        if "'3x4':" not in html:
            html = html.replace(
                "const SIZES = {",
                "const SIZES = { '3x4': [1080, 1440],",
            )
    if 'bloom:' not in html:
        html = html.replace(
            'vignette: .6,',
            'vignette: 0.60, bloom: 0.26,',
        )
    index_html.write_text(html, encoding='utf-8', newline='\n')

    cues_path = anim_dir / 'work' / 'cues.json'
    if not cues_path.exists():
        cues_path.write_text('{\n  "cues": []\n}\n', encoding='utf-8', newline='\n')

    film_md = anim_dir / 'work' / 'film.md'
    if not film_md.exists():
        film_md.write_text(
            f'# {args.topic} —— 分镜脚本与事实出处 ({args.date})\n\n'
            '## 核心视觉识别系统（Carbon 策划填写）\n'
            '- 主色相：\n'
            '- 强调色：\n'
            '- 贯穿物（冷开场与结尾呼应）：\n\n'
            '## 逐句分镜表\n\n'
            '| 句ID | 时间 | 观众要看懂什么 | 主体动作与核心隐喻 | 画面文字 | 细节与光效 | 转场 |\n'
            '| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n\n'
            '## 权威文献出处\n- \n',
            encoding='utf-8',
            newline='\n',
        )

    write_output(
        {
            'ok': True,
            'workspace': str(workspace),
            'script_dir': str(script_dir),
            'animation_dir': str(anim_dir),
            'film_dir': str(anim_dir / 'film'),
            'work_dir': str(anim_dir / 'work'),
            'out_dir': str(anim_dir / 'out'),
            'ratio': args.ratio,
            'dimensions': list(SIZES[args.ratio]),
            'files_initialized': [
                str(index_html),
                str(cues_path),
                str(film_md),
                str(anim_dir / 'work' / 'lines.json'),
            ],
        },
        args.output,
    )


def _decode_audio_frames(bgm_path: Path, hop_sec: float = 0.1) -> tuple[float, list[float], list[float], list[float]]:
    """Decode audio with FFmpeg into 8kHz mono PCM and extract per-hop RMS & <180Hz envelopes."""
    sr = 8000
    hop_samples = int(round(sr * hop_sec))
    proc = subprocess.run(
        ['ffmpeg', '-v', 'error', '-i', str(bgm_path), '-vn', '-ac', '1', '-ar', str(sr), '-f', 's16le', '-'],
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        err = proc.stderr.decode('utf-8', errors='replace')
        raise RuntimeError(f'FFmpeg failed to decode {bgm_path}: {err}')

    pcm = array('h')
    pcm.frombytes(proc.stdout[: len(proc.stdout) - (len(proc.stdout) % 2)])
    total_samples = len(pcm)
    duration = total_samples / sr

    dt = 1.0 / sr
    rc = 1.0 / (2.0 * math.pi * 180.0)
    alpha = dt / (rc + dt)
    lp_state = 0.0

    rms_env: list[float] = []
    low_env: list[float] = []
    inv_scale = 1.0 / 32768.0

    for offset in range(0, total_samples - hop_samples + 1, hop_samples):
        sum_sq = 0.0
        low_sq = 0.0
        chunk = pcm[offset : offset + hop_samples]
        for s in chunk:
            v = s * inv_scale
            sum_sq += v * v
            lp_state += alpha * (v - lp_state)
            low_sq += lp_state * lp_state
        rms_env.append(math.sqrt(sum_sq / hop_samples))
        low_env.append(math.sqrt(low_sq / hop_samples))

    flux_env = [0.0]
    for i in range(1, len(rms_env)):
        d_low = max(0.0, low_env[i] - low_env[i - 1])
        d_rms = max(0.0, rms_env[i] - rms_env[i - 1])
        flux_env.append(d_low + 0.5 * d_rms)

    return duration, rms_env, low_env, flux_env


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 1.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round((len(s) - 1) * q))))
    return max(s[idx], 1e-6)


def cmd_analyze_bgm(args: argparse.Namespace) -> None:
    bgm_path = Path(args.bgm).expanduser().resolve()
    if not bgm_path.is_file():
        print(f'Error: BGM file not found: {bgm_path}', file=sys.stderr)
        sys.exit(1)
    if args.top_k < 1:
        print('Error: --top-k must be >= 1.', file=sys.stderr)
        sys.exit(1)

    hop_sec = 0.1
    try:
        track_dur, rms_raw, low_raw, flux_raw = _decode_audio_frames(bgm_path, hop_sec=hop_sec)
    except RuntimeError as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)

    if track_dur < args.target_duration:
        print(
            f'Error: Audio duration ({track_dur:.2f}s) is shorter than target ({args.target_duration:.2f}s).',
            file=sys.stderr,
        )
        sys.exit(1)

    p95_rms = _percentile(rms_raw, 0.95)
    p95_low = _percentile(low_raw, 0.95)
    p95_flux = _percentile(flux_raw, 0.95)
    rms = [v / p95_rms for v in rms_raw]
    low = [v / p95_low for v in low_raw]
    flux = [v / p95_flux for v in flux_raw]

    win_frames = int(round(args.target_duration / hop_sec))
    step_frames = max(1, int(round(args.step / hop_sec)))
    max_start_idx = len(rms) - win_frames
    candidates: list[dict] = []

    d1_lo = max(20, int(round(4.5 / hop_sec)))
    d1_hi = min(win_frames - 20, int(round(9.5 / hop_sec)))
    bd_lo = int(round(args.target_duration * 0.52 / hop_sec))
    bd_hi = int(round(args.target_duration * 0.78 / hop_sec))
    cl_hi = min(win_frames - 25, int(round(args.target_duration * 0.88 / hop_sec)))

    for s_idx in range(0, max_start_idx + 1, step_frames):
        w_r = rms[s_idx : s_idx + win_frames]
        w_l = low[s_idx : s_idx + win_frames]
        w_f = flux[s_idx : s_idx + win_frames]

        best_d1_idx = d1_lo
        best_d1_score = -1e9
        for k in range(d1_lo, max(d1_lo + 1, d1_hi)):
            pre = sum(w_r[max(0, k - 15) : k]) / max(1, min(k, 15))
            post = sum(w_l[k : k + 15]) / 15.0 + sum(w_r[k : k + 15]) / 15.0
            burst = max(w_f[max(0, k - 2) : k + 3])
            sc = (post * 0.55 - pre * 0.65) + 0.9 * burst
            if sc > best_d1_score:
                best_d1_score = sc
                best_d1_idx = k

        best_bd_idx = bd_lo
        best_bd_val = 1e9
        for k in range(max(d1_hi + 20, bd_lo), max(bd_lo + 1, bd_hi)):
            val = sum(w_r[k - 12 : k + 12]) / 24.0
            if val < best_bd_val:
                best_bd_val = val
                best_bd_idx = k

        cl_lo = max(best_bd_idx + 12, int(round(args.target_duration * 0.68 / hop_sec)))
        best_cl_idx = cl_lo
        best_cl_score = -1e9
        for k in range(cl_lo, max(cl_lo + 1, cl_hi)):
            pre = sum(w_r[max(0, k - 15) : k]) / 15.0
            post = 0.6 * (sum(w_l[k : k + 30]) / 30.0) + 0.4 * (sum(w_r[k : k + 30]) / 30.0)
            burst = max(w_f[max(0, k - 2) : k + 3])
            sc = (post - pre) * 1.4 + 1.0 * burst + 0.5 * post
            if sc > best_cl_score:
                best_cl_score = sc
                best_cl_idx = k

        intro_e = sum(w_r[:30]) / max(1, min(30, len(w_r)))
        outro_e = sum(w_r[-20:]) / 20.0
        climax_post = sum(w_r[best_cl_idx : best_cl_idx + 30]) / 30.0
        contrast = climax_post - best_bd_val

        total_score = best_d1_score + 1.3 * best_cl_score + 1.1 * contrast
        if intro_e < 0.12:
            total_score -= 1.0
        if outro_e < 0.18:
            total_score -= 1.2

        drop1_sec = round(best_d1_idx * hop_sec, 2)
        break_sec = round(best_bd_idx * hop_sec, 2)
        climax_sec = round(best_cl_idx * hop_sec, 2)
        m_start = round(s_idx * hop_sec, 2)
        dips = (
            f'{max(0.4, drop1_sec - 0.35):.2f}-{drop1_sec:.2f}:-14,'
            f'{max(0.4, climax_sec - 0.38):.2f}-{climax_sec:.2f}:-14'
        )
        candidates.append(
            {
                'music_start_sec': m_start,
                'score': round(total_score, 4),
                'drop1_video_sec': drop1_sec,
                'breakdown_video_sec': break_sec,
                'climax_drop_video_sec': climax_sec,
                'metrics': {
                    'intro_energy_norm': round(intro_e, 3),
                    'breakdown_energy_norm': round(best_bd_val, 3),
                    'climax_post_energy_norm': round(climax_post, 3),
                    'outro_energy_norm': round(outro_e, 3),
                },
                'mix_py_dips': dips,
                'suggested_timeline_anchors': {
                    'hook_start': 0.3,
                    'title_card_at': drop1_sec,
                    'breakdown_at': break_sec,
                    'climax_at': climax_sec,
                    'callback_window': [round(args.target_duration - 3.0, 2), args.target_duration],
                },
            }
        )

    candidates.sort(key=lambda item: item['score'], reverse=True)
    picked: list[dict] = []
    for cand in candidates:
        if all(abs(cand['music_start_sec'] - prev['music_start_sec']) >= 2.0 for prev in picked):
            picked.append(cand)
        if len(picked) >= args.top_k:
            break

    write_output(
        {
            'ok': bool(picked),
            'bgm_file': str(bgm_path),
            'track_duration_sec': round(track_dur, 3),
            'target_duration_sec': args.target_duration,
            'top_k': args.top_k,
            'candidates': picked,
        },
        args.output,
    )


def _strip_end_punct(text: str) -> str:
    s = text.rstrip()
    while True:
        j = len(s)
        while j > 0 and (s[j - 1] in CLOSE_BRACKETS or s[j - 1].isspace()):
            j -= 1
        k = j
        while k > 0 and s[k - 1] in TRAIL_PUNCT:
            k -= 1
        if k == j:
            return s
        s = (s[:k] + s[j:]).rstrip()


def _clean_char_count(text: str) -> int:
    clean = re.sub(r'#(?:[0-9a-fA-F]{6})', '', text)
    return len(re.sub(r'[\s\[\]{}<>|，。、：；！？,.!?“”"「」『』（）()—…·\-]', '', clean))


def _est_pixel_width(text: str, font_size: float) -> float:
    cleaned = re.sub(r'[\[\]{}<>|]|#[0-9a-fA-F]{6}', '', text)
    w = 0.0
    for ch in cleaned:
        w += font_size * (1.0 if unicodedata.east_asian_width(ch) in ('W', 'F') else 0.58) + font_size * 0.05
    return w


def cmd_validate_lines(args: argparse.Namespace) -> None:
    lines_path = Path(args.lines).expanduser().resolve()
    if not lines_path.is_file():
        print(f'Error: lines.json not found: {lines_path}', file=sys.stderr)
        sys.exit(1)

    raw_bytes = lines_path.read_bytes()
    has_bom = raw_bytes.startswith(b'\xef\xbb\xbf')
    text_str = raw_bytes.decode('utf-8-sig')
    spec = json.loads(text_str)

    width_px = SIZES[args.ratio][0]
    is_narrow = width_px <= 1080
    max_hook_chars = 12 if is_narrow else 16
    max_cap_chars = 15 if is_narrow else 20

    cps = float(spec.get('cps', 6.0))
    base = float(spec.get('base', 0.9))
    gap = float(spec.get('gap', 0.3))
    t = float(spec.get('start', 0.3))
    prev_end = -1.0

    beats: list[float] = []
    if args.beats:
        bp = Path(args.beats).expanduser().resolve()
        if bp.is_file():
            bdata = json.loads(bp.read_text(encoding='utf-8-sig'))
            beats = [x - args.music_start for x in bdata.get('beats', []) if x >= args.music_start]

    def snap(val: float) -> float:
        if not beats:
            return val
        near = min(beats, key=lambda x: abs(x - val))
        return near if abs(near - val) <= 0.18 else val

    violations: list[dict[str, str | float | int]] = []
    warnings: list[dict[str, str | float | int]] = []
    timeline_preview: list[dict] = []

    if has_bom and not args.fix_bom:
        violations.append({'id': '__file__', 'type': 'utf8_bom', 'message': 'File has UTF-8 BOM; pass --fix-bom to strip.'})

    for ln in spec.get('lines', []):
        lid = str(ln.get('id', ''))
        txt = str(ln.get('text', ''))
        card = bool(ln.get('card'))
        hook = bool(ln.get('hook'))

        if txt.count('[') != txt.count(']'):
            violations.append({'id': lid, 'type': 'unbalanced_brackets', 'message': f'Unbalanced [] in: {txt}'})
        if not card and _strip_end_punct(txt) != txt:
            violations.append({'id': lid, 'type': 'trailing_punctuation', 'message': f'Remove trailing punctuation in: {txt}'})

        n = _clean_char_count(txt)
        if not card:
            if hook and n > max_hook_chars:
                violations.append({'id': lid, 'type': 'hook_too_long', 'message': f'{n} chars > {max_hook_chars} max for {args.ratio} hook'})
            if not hook and n > max_cap_chars:
                violations.append({'id': lid, 'type': 'caption_too_long', 'message': f'{n} chars > {max_cap_chars} max for {args.ratio} caption'})

            est_size = (76.0 if is_narrow else 104.0) if hook else 52.0
            lim_px = width_px * (0.90 if hook else 0.86)
            pw = _est_pixel_width(txt, est_size)
            if pw > lim_px:
                item = {
                    'id': lid,
                    'type': 'line_pixel_overflow',
                    'message': (
                        f'Estimated width {pw:.0f}px > {lim_px:.0f}px limit on '
                        f'{width_px}px canvas (kit.js will auto-shrink {est_size:.0f}px to ~{est_size * lim_px / pw:.0f}px)'
                    ),
                }
                if hook and n <= max_hook_chars:
                    warnings.append(item)
                else:
                    violations.append(item)

        hold = float(ln['hold']) if 'hold' in ln else (
            2.5 if card else max(1.5, 0.5 + n / 8.0) if hook else max(1.6, base + n / cps)
        )
        if ln.get('at') is not None:
            t = max(t, float(ln['at']))
        ts = snap(t)
        if ts >= prev_end + gap * 0.5:
            t = ts

        end_t = t + hold
        timeline_preview.append({'id': lid, 'start': round(t, 3), 'end': round(end_t, 3), 'chars': n, 'hook': hook, 'card': card})
        prev_end = end_t
        t = end_t + gap + float(ln.get('pause', 0.0))

    hooks = [x for x in timeline_preview if x['hook']]
    if not hooks:
        violations.append({'id': '__hooks__', 'type': 'missing_hook', 'message': 'At least one opening line must set "hook": true.'})
    else:
        if hooks[0]['start'] > 1.0:
            violations.append({'id': hooks[0]['id'], 'type': 'slow_hook_start', 'message': f'First hook starts at {hooks[0]["start"]}s (> 1.0s).'})
        hook_finish = hooks[-1]['start'] + hooks[-1]['chars'] / 22.0 + 0.5
        if hook_finish > 5.0:
            violations.append({'id': hooks[-1]['id'], 'type': 'slow_hook_finish', 'message': f'Hooks finish around {hook_finish:.2f}s (> 5.0s).'})

    last_end = timeline_preview[-1]['end'] if timeline_preview else 0.0
    recommended_tail = round(args.target_duration - last_end, 3)
    current_tail = float(spec.get('tail', 3.0))
    predicted_total = round(last_end + current_tail, 3)
    delta_sec = round(predicted_total - args.target_duration, 3)

    rewritten = False
    if args.apply_tail:
        if recommended_tail < 0:
            violations.append({
                'id': '__duration__',
                'type': 'negative_tail',
                'message': f'Last line ends at {last_end:.3f}s, exceeding target {args.target_duration:.3f}s.',
            })
        else:
            spec['tail'] = recommended_tail
            current_tail = recommended_tail
            predicted_total = round(last_end + current_tail, 3)
            delta_sec = round(predicted_total - args.target_duration, 3)
            lines_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
            rewritten = True
            has_bom = False
    elif args.fix_bom and has_bom:
        lines_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        rewritten = True
        has_bom = False

    if abs(delta_sec) > 0.05:
        violations.append({
            'id': '__duration__',
            'type': 'duration_mismatch',
            'message': f'Predicted total {predicted_total:.3f}s differs from target {args.target_duration:.3f}s (recommended tail={recommended_tail:.3f}s).',
        })
    if 0 <= recommended_tail < 1.2 or recommended_tail > 5.0:
        warnings.append({'id': '__tail__', 'type': 'tail_balance', 'message': f'Recommended tail {recommended_tail:.3f}s outside typical [1.2, 5.0]s window.'})

    write_output(
        {
            'passed': len(violations) == 0,
            'lines_file': str(lines_path),
            'ratio': args.ratio,
            'canvas_width_px': width_px,
            'had_utf8_bom': has_bom,
            'rewritten_no_bom': rewritten,
            'line_count': len(timeline_preview),
            'last_line_end_sec': round(last_end, 3),
            'current_tail_sec': current_tail,
            'recommended_tail_sec': recommended_tail,
            'predicted_total_sec': predicted_total,
            'target_duration_sec': args.target_duration,
            'duration_delta_sec': delta_sec,
            'violations': violations,
            'warnings': warnings,
            'timeline_preview': timeline_preview,
        },
        args.output,
    )


def _parse_qa_output(raw: str) -> dict:
    parsed: dict = {}
    m_meta = re.search(
        r'(\d+)×(\d+)\s*·\s*([\d.]+)fps\s*·\s*([\d.]+)s\s*·\s*帧数\s*(\d+)\s*·\s*(\S+)\s*·\s*音轨\s*(有|无)',
        raw,
    )
    if m_meta:
        parsed['width'] = int(m_meta.group(1))
        parsed['height'] = int(m_meta.group(2))
        parsed['fps'] = float(m_meta.group(3))
        parsed['duration_sec'] = float(m_meta.group(4))
        parsed['frames'] = int(m_meta.group(5))
        parsed['pix_fmt'] = m_meta.group(6)
        parsed['has_audio'] = m_meta.group(7) == '有'

    m_dead = re.search(r'死区（[^）]*）：([^\n]+)', raw)
    if m_dead:
        val = m_dead.group(1).strip()
        parsed['dead_zones'] = [] if val == '无' else [x.strip() for x in val.split(',') if x.strip()]

    m_sp = re.search(r'单帧跳变（[^）]*）：([^\n]+)', raw)
    if m_sp:
        val = m_sp.group(1).strip()
        parsed['single_frame_spikes'] = [] if val == '无' else [x.strip() for x in val.split(',') if x.strip()]

    m_fl = re.search(r'黑/白闪帧：([^\n]+)', raw)
    if m_fl:
        val = m_fl.group(1).strip()
        parsed['flash_frames'] = [] if val == '无' else [x.strip() for x in val.split(',') if x.strip()]

    m_mv = re.search(r'有明显运动的时间占比\s*(\d+)%', raw)
    if m_mv:
        parsed['moving_pct'] = int(m_mv.group(1))

    m_luma = re.search(
        r'p99=(\d+)[^·]*·\s*高亮像素\s*([\d.]+)%[^·]*·\s*画面均值\s*(\d+)[^·]*·\s*近黑帧\s*(\d+)%',
        raw,
    )
    if m_luma:
        parsed['luma_fingerprint'] = {
            'p99': int(m_luma.group(1)),
            'bright_pct': float(m_luma.group(2)),
            'mean': int(m_luma.group(3)),
            'near_black_pct': int(m_luma.group(4)),
        }

    m_aud = re.search(r'响度\s*([-\d.?]+)\s*LUFS\s*·\s*真峰值\s*([-\d.?]+)\s*dBFS', raw)
    if m_aud:
        try:
            parsed['audio'] = {
                'lufs': float(m_aud.group(1)),
                'true_peak_dbfs': float(m_aud.group(2)),
            }
        except ValueError:
            parsed['audio'] = {'lufs': m_aud.group(1), 'true_peak_dbfs': m_aud.group(2)}

    return parsed


def cmd_audit_qa(args: argparse.Namespace) -> None:
    video_path = Path(args.video).expanduser().resolve()
    film_dir = Path(args.film_dir).expanduser().resolve()
    if not video_path.is_file():
        print(f'Error: Video file not found: {video_path}', file=sys.stderr)
        sys.exit(1)
    if not film_dir.is_dir():
        print(f'Error: Film directory not found: {film_dir}', file=sys.stderr)
        sys.exit(1)

    upstream_anim = find_skill_dir('lead-knowledge-animation', args.upstream_dir)
    if not upstream_anim:
        print('Error: Cannot locate upstream lead-knowledge-animation dir.', file=sys.stderr)
        sys.exit(1)
    sys_py = find_system_python_with_numpy()
    if not sys_py:
        print('Error: No Python with numpy/scipy found to execute upstream qa_video.py.', file=sys.stderr)
        sys.exit(1)

    qa_py = upstream_anim / 'scripts' / 'qa_video.py'
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    proc = subprocess.run(
        [sys_py, str(qa_py), str(video_path), '--film', str(film_dir)],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=env,
    )
    if proc.returncode != 0:
        print(f'Error executing qa_video.py:\n{proc.stderr or proc.stdout}', file=sys.stderr)
        sys.exit(1)

    metrics = _parse_qa_output(proc.stdout)
    luma = metrics.get('luma_fingerprint', {})
    p99 = luma.get('p99', 0)
    bright = luma.get('bright_pct', 0.0)
    mean_v = luma.get('mean', 0)
    near_black = luma.get('near_black_pct', 0)
    dead_zones = metrics.get('dead_zones', [])
    flashes = metrics.get('flash_frames', [])
    fps = metrics.get('fps', 0.0)

    failures: list[str] = []
    prescriptions: list[str] = []
    if p99 < 130:
        failures.append(f'p99={p99} < 130 (subject peak not bright enough)')
        prescriptions.append('Strengthen K.core bright core or increase main subject stroke contrast.')
    elif fps < 50 and p99 < 133:
        prescriptions.append(f'Draft 30fps p99={p99} is near 130 floor; push >=133 so 60fps --blur 2 stays >=130.')

    if bright > 3.5:
        failures.append(f'bright_pct={bright}% > 3.5% (over-bloomed highlight saturation)')
        prescriptions.append('Lower Kit({ bloom }) to 0.20-0.28, reduce K.fog to 0.024-0.028, lower K.amb haze to 0.04-0.10.')
    elif bright < 1.5:
        failures.append(f'bright_pct={bright}% < 1.5% (insufficient glowing mass)')
        prescriptions.append('Enlarge luminous hero elements or add K.core / K.glowLine detail layers.')

    if mean_v > 24:
        failures.append(f'mean={mean_v} > 24 (background haze too bright)')
        prescriptions.append('Keep mean in golden zone [17, 20]: increase vignette to 0.56-0.62 and darken haze/grid.')
    elif mean_v < 14:
        failures.append(f'mean={mean_v} < 14 (too dark overall)')
        prescriptions.append('Keep mean in golden zone [17, 20]: gently raise K.amb dust/stars and ambient fog to 0.025.')

    if dead_zones:
        failures.append(f'dead_zones detected: {dead_zones}')
        prescriptions.append('Add beat-synchronized camera drift, flowing particles, or secondary pulse inside listed intervals.')
    if flashes:
        failures.append(f'flash_frames detected: {flashes}')
        prescriptions.append('Check K.flash peak/timing near listed timestamps to eliminate jarring white/black single frames.')
    if near_black > 40:
        failures.append(f'near_black_pct={near_black}% > 40%')
        prescriptions.append('Ensure ambient background dust/nebula stays visible outside intentional blackout transitions.')

    proj_dir = film_dir.parent
    review_dir = proj_dir / 'out' / f'review_r{args.round}'
    blind_prompt = (
        f'你是未参与制作、极度挑剔的资深科普动画盲审导演。严禁读取 `{film_dir}` 下的源码。'
        f'请仅查看审片包目录 `{review_dir}` 中的 `review.md`、`1_对照联系表.png`、`2_关键帧.png`、`motion/` 与 `transitions/`：'
        '按 9 项维度（故事清晰/开头5秒/丰富度/设计秩序/变化频率/运动质感/转场/完成度/目标风格贴合度）诚实打分（1-10），'
        '并逐一核查文字防撞（HUD 右上角禁用、callout 不进主体、片名卡不撞副标题、过渡无高斯糊影）。'
        '列出影响最大的 P0/P1 问题（精确到秒）与修改建议；若存在任何 P0/P1 或均分 < 8.5，必须明确判定 REJECT。'
    )

    write_output(
        {
            'passed': len(failures) == 0,
            'round': args.round,
            'video': str(video_path),
            'metrics': metrics,
            'failures': failures,
            'prescriptions': prescriptions,
            'review_dir_expected': str(review_dir),
            'blind_reviewer_prompt': blind_prompt,
            'raw_qa_report': proc.stdout.strip(),
        },
        args.output,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Sci-Glow Popular Science Video Production CLI Helper'
    )
    sub = parser.add_subparsers(dest='command', required=True)

    p_pre = sub.add_parser('preflight', help='Verify local toolchain and IBM Plex Sans SC OTF fonts')
    p_pre.add_argument('--upstream-dir', help='Optional explicit path to lead-knowledge-animation')
    p_pre.add_argument('--auto-fix-fonts', action='store_true', help='Download missing OTF weights via rate-limited CDN client')
    p_pre.add_argument('--output', required=True, help='Output JSON file path')

    p_scaf = sub.add_parser('scaffold-project', help='Initialize dual script and deterministic animation directories')
    p_scaf.add_argument('--workspace', required=True, help='Project root workspace directory')
    p_scaf.add_argument('--date', required=True, help='YYYYMMDD stamp, e.g. 20261118')
    p_scaf.add_argument('--topic', required=True, help='Short Chinese topic name, e.g. 光遗传学')
    p_scaf.add_argument('--ratio', required=True, choices=list(SIZES.keys()), help='Target canvas aspect ratio')
    p_scaf.add_argument('--upstream-dir', help='Optional explicit path to lead-knowledge-animation')
    p_scaf.add_argument('--output', required=True, help='Output JSON file path')

    p_bgm = sub.add_parser('analyze-bgm', help='Analyze MP3 spectral energy to locate drops, breakdowns, and climax cuts')
    p_bgm.add_argument('--bgm', required=True, help='Path to user MP3/WAV background music')
    p_bgm.add_argument('--target-duration', type=float, required=True, help='Target film duration in seconds (e.g. 60)')
    p_bgm.add_argument('--top-k', type=int, required=True, help='Number of ranked candidate windows to output')
    p_bgm.add_argument('--step', type=float, default=0.5, help='Sliding search step in seconds (default 0.5)')
    p_bgm.add_argument('--output', required=True, help='Output JSON file path')

    p_val = sub.add_parser('validate-lines', help='Check BOM, char length, pixel width, hooks, and lock exact tail duration')
    p_val.add_argument('--lines', required=True, help='Path to work/lines.json')
    p_val.add_argument('--target-duration', type=float, required=True, help='Exact target film duration in seconds (e.g. 60)')
    p_val.add_argument('--ratio', required=True, choices=list(SIZES.keys()), help='Canvas aspect ratio for pixel-width check')
    p_val.add_argument('--beats', help='Optional work/beats.json for exact beat-snapped total simulation')
    p_val.add_argument('--music-start', type=float, default=0.0, help='BGM start offset in seconds matching timeline.py')
    p_val.add_argument('--fix-bom', action='store_true', help='Strip UTF-8 BOM and rewrite lines.json cleanly')
    p_val.add_argument('--apply-tail', action='store_true', help='Write exact recommended tail back to lines.json (no BOM)')
    p_val.add_argument('--output', required=True, help='Output JSON file path')

    p_qa = sub.add_parser('audit-qa', help='Run upstream qa_video.py, judge brightness gates, and emit blind-review prompt')
    p_qa.add_argument('--video', required=True, help='Path to draft or master MP4')
    p_qa.add_argument('--film-dir', required=True, help='Path to film/ directory containing timing.js')
    p_qa.add_argument('--round', type=int, required=True, help='Review round number (1, 2, ...)')
    p_qa.add_argument('--upstream-dir', help='Optional explicit path to lead-knowledge-animation')
    p_qa.add_argument('--output', required=True, help='Output JSON file path')

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {
        'preflight': cmd_preflight,
        'scaffold-project': cmd_scaffold_project,
        'analyze-bgm': cmd_analyze_bgm,
        'validate-lines': cmd_validate_lines,
        'audit-qa': cmd_audit_qa,
    }
    try:
        dispatch[args.command](args)
    except RateLimitError as exc:
        print(f'RateLimitError: {exc}', file=sys.stderr)
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as exc:
        print(f'Error in {args.command}: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
