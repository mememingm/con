"""本地 TAC 数据源加载与查询。

运行时只读取 CSV 一次，查询使用内存索引；XLSX 不参与服务请求。
"""

import csv
import hashlib
from collections import Counter
from pathlib import Path


class TacCatalog:
    def __init__(self, *, source, data_version, data_updated_at, coverage_through, by_tac, stats):
        self.source = source
        self.data_version = data_version
        self.data_updated_at = data_updated_at
        self.coverage_through = coverage_through
        self.by_tac = by_tac
        self.stats = stats

    @classmethod
    def from_csv(cls, path, *, source=None, data_updated_at=None, coverage_through=None):
        path = Path(path)
        raw = path.read_bytes()
        by_tac = {}
        stats = Counter()
        with path.open('r', encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            fields = {str(field or '').strip().lower(): field for field in (reader.fieldnames or [])}
            missing = {'brand', 'tac', 'specs'} - set(fields)
            if missing:
                raise ValueError(f'TAC CSV 缺少字段: {", ".join(sorted(missing))}')
            for row_number, row in enumerate(reader, 2):
                stats['rows'] += 1
                tac = str(row.get(fields['tac']) or '').strip()
                brand = str(row.get(fields['brand']) or '').strip()
                specs = str(row.get(fields['specs']) or '').strip()
                if len(tac) != 8 or not tac.isascii() or not tac.isdigit():
                    stats['invalid_rows'] += 1
                    stats[f'invalid_{len(tac) or "empty"}'] += 1
                    continue
                stats['valid_rows'] += 1
                candidate = {
                    'brand': brand,
                    'specs': specs,
                    'source_row': row_number,
                }
                candidates = by_tac.setdefault(tac, [])
                identity = (brand.casefold(), specs)
                if not any((item['brand'].casefold(), item['specs']) == identity for item in candidates):
                    candidates.append(candidate)
                else:
                    stats['duplicate_rows'] += 1
        stats['unique_tac'] = len(by_tac)
        stats['ambiguous_tac'] = sum(1 for candidates in by_tac.values() if len(candidates) > 1)
        return cls(
            source=source or path.name,
            data_version='sha256:' + hashlib.sha256(raw).hexdigest(),
            data_updated_at=data_updated_at,
            coverage_through=coverage_through,
            by_tac=by_tac,
            stats=dict(stats),
        )

    def lookup(self, tac):
        tac = str(tac or '').strip()
        candidates = [dict(item) for item in self.by_tac.get(tac, [])]
        status = 'matched' if len(candidates) == 1 else 'ambiguous' if candidates else 'unknown'
        return {
            'model_status': status,
            'tac': tac if len(tac) == 8 and tac.isascii() and tac.isdigit() else '',
            'candidates': candidates,
            'source': self.source,
            'data_version': self.data_version,
            'data_updated_at': self.data_updated_at,
            'coverage_through': self.coverage_through,
        }
