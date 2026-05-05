from __future__ import annotations
from dataclasses import dataclass, field
from .constants import BORDERLINE_RATIO_WARNING, GROUP_ADDITIONAL_EVALUATION_WARNING, MINIMUM_INITIAL_NUCLEI
from .models import NucleusCount

@dataclass(frozen=True)
class ScoreResult:
    included_cell_count: int
    total_her2: int
    total_cep17: int
    her2_cep17_ratio: float | None
    average_her2_copy_number: float | None
    ish_group: str
    warnings: list[str] = field(default_factory=list)

def classify_ish_group(ratio: float | None, average_her2: float | None) -> str:
    if ratio is None or average_her2 is None:
        return "Not evaluable"
    if ratio >= 2.0 and average_her2 >= 4.0: return "Group 1"
    if ratio >= 2.0 and average_her2 < 4.0: return "Group 2"
    if ratio < 2.0 and average_her2 >= 6.0: return "Group 3"
    if ratio < 2.0 and 4.0 <= average_her2 < 6.0: return "Group 4"
    return "Group 5"

def calculate_score(nuclei: list[NucleusCount]) -> ScoreResult:
    included = [n for n in nuclei if n.included]
    cc = len(included)
    total_h = sum(n.effective_her2 for n in included)
    total_c = sum(int(n.cep17_red) for n in included)
    warnings = []
    if cc < MINIMUM_INITIAL_NUCLEI:
        warnings.append(f"Fewer than {MINIMUM_INITIAL_NUCLEI} included nuclei. Initial HER2-DISH counting generally requires at least 20 nuclei.")
    if cc == 0 or total_c == 0:
        return ScoreResult(cc, total_h, total_c, None, None, "Not evaluable", warnings)
    ratio = total_h / total_c
    avg = total_h / cc
    group = classify_ish_group(ratio, avg)
    if 1.8 <= ratio <= 2.2:
        warnings.append(BORDERLINE_RATIO_WARNING)
    if group in {"Group 2", "Group 3", "Group 4"}:
        warnings.append(GROUP_ADDITIONAL_EVALUATION_WARNING)
    return ScoreResult(cc, total_h, total_c, ratio, avg, group, warnings)
