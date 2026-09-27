"""제출 ZIP의 구조 검사·압축 해제·생성. 실행 코드는 검사 과정에서 가져오지 않는다."""

import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

EXTENSIONS = {'python': {'.py'}, 'cpp': {'.cpp', '.h', '.hh', '.hpp'}}
ENTRIES = {'python': 'main.py', 'cpp': 'main.cpp'}


def inspect_zip(path):
    """허용 파일과 경로를 확인하고 오류 목록 및 언어를 반환한다."""
    issues = []
    language = None
    try:
        with zipfile.ZipFile(path) as archive:
            files, names = set(), set()
            for item in archive.infolist():
                name = item.filename
                parts = name.rstrip('/').split('/')
                mode = item.external_attr >> 16
                if ('\\' in name or ':' in name or name.startswith('/') or
                        any(p in ('', '.', '..') for p in parts)):
                    issues.append(f'허용되지 않는 경로: {name}')
                if name in names:
                    issues.append(f'중복 경로: {name}')
                names.add(name)
                if stat.S_ISLNK(mode):
                    issues.append(f'심볼릭링크 금지: {name}')
                elif stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                    issues.append(f'일반 파일이 아닌 항목: {name}')
                if item.flag_bits & 1:
                    issues.append(f'암호화 ZIP은 지원하지 않음: {name}')
                if not item.is_dir():
                    files.add(name)
            if 'submission.json' not in files:
                issues.append('ZIP 루트에 submission.json이 필요합니다')
            else:
                def unique(pairs):
                    data = {}
                    for key, value in pairs:
                        if key in data:
                            raise ValueError('중복된 메타데이터 키')
                        data[key] = value
                    return data
                data = json.loads(archive.read('submission.json'), object_pairs_hook=unique)
                if not isinstance(data, dict) or type(data.get('schemaVersion')) is not int or data['schemaVersion'] != 1:
                    issues.append('schemaVersion은 정수 1이어야 합니다')
                language = data.get('language') if isinstance(data, dict) else None
                if not isinstance(language, str) or language not in ENTRIES:
                    issues.append('language는 python 또는 cpp여야 합니다')
                    language = None
            if language:
                if ENTRIES[language] not in files:
                    issues.append(f'ZIP 루트에 {ENTRIES[language]}가 필요합니다')
                for name in sorted(files):
                    if name != 'submission.json' and PurePosixPath(name).suffix not in EXTENSIONS[language]:
                        issues.append(f'허용되지 않는 파일 확장자: {name}')
            for name in names:
                for parent in PurePosixPath(name).parents:
                    if str(parent) in files:
                        issues.append(f'파일과 디렉터리가 충돌하는 경로: {name}')
    except (OSError, ValueError, KeyError, RuntimeError, zipfile.BadZipFile) as exc:
        issues.append(f'ZIP 또는 메타데이터 해석 실패: {exc}')
    return {'ok': not issues, 'language': language, 'issues': issues}


def extract_zip(path, destination):
    """검증된 ZIP만 빈 폴더에 푼다. 심볼릭링크를 생성하지 않는다."""
    result = inspect_zip(path)
    if not result['ok']:
        raise ValueError('\n'.join(result['issues']))
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise ValueError('압축 해제 대상은 빈 폴더여야 합니다')
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            target = destination / item.filename
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, target.open('wb') as output:
                    import shutil
                    shutil.copyfileobj(source, output)
    return result['language']


def build_zip(source, output, entry=None):
    """언어별 폴더의 보조 파일과 선택한 진입 소스를 루트 진입 이름으로 묶는다."""
    source, output = Path(source), Path(output)
    metadata = json.loads((source / 'submission.json').read_text())
    language = metadata.get('language')
    if language not in ENTRIES:
        raise ValueError('language는 python 또는 cpp여야 합니다')
    entry = Path(entry or ENTRIES[language])
    if entry.is_absolute() or '..' in entry.parts or not (source / entry).is_file():
        raise ValueError('진입 파일은 소스 폴더 내부의 파일이어야 합니다')
    if entry.suffix != Path(ENTRIES[language]).suffix:
        raise ValueError('진입 파일 확장자가 언어와 다릅니다')
    paths = {}
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'심볼릭링크는 제출할 수 없습니다: {path}')
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        rel = path.relative_to(source)
        if rel.as_posix() == 'submission.json':
            paths['submission.json'] = path
        elif path.suffix in EXTENSIONS[language]:
            # 여러 예제의 main 함수가 함께 링크되지 않게 선택 소스와 헤더만 포함한다.
            if language == 'cpp' and rel.as_posix() in {'main.cpp', 'example_lv1.cpp', 'example_lv2.cpp'} and rel != entry:
                continue
            if rel == entry:
                paths[ENTRIES[language]] = path
            elif rel.as_posix() != ENTRIES[language]:
                paths[rel.as_posix()] = path
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, path in paths.items():
            archive.write(path, name)
    result = inspect_zip(output)
    if not result['ok']:
        raise ValueError('\n'.join(result['issues']))
    return output
