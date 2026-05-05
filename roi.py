from __future__ import annotations

from dataclasses import dataclass, field

from .constants import (
    BORDERLINE_RATIO_WARNING,
    GROUP_ADDITIONAL_EVALUATION_WARNING,
    MINIMUM_INITIAL_NUCLEI,
)
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

    @property
    def is_evaluable(self) -> bool:
        return self.ish_group != "Not evaluable"


def classify_ish_group(ratio: float | None, average_her2: float | None) -> str:
    """Classify ASCO/CAP dual-probe ISH Group 1-5.

    This function returns the group only. It does not make a final diagnostic
    interpretation. Groups 2-4 require additional workflow-dependent review.
    """
    if ratio is None or average_her2 is None:
        return "Not evaluable"

    if ratio >= 2.0 and average_her2 >= 4.0:
        return "Group 1"
    if ratio >= 2.0 and average_her2 < 4.0:
        return "Group 2"
    if ratio < 2.0 and average_her2 >= 6.0:
        return "Group 3"
    if ratio < 2.0 and 4.0 <= average_her2 < 6.0:
        return "Group 4"
    if ratio < 2.0 and average_her2 < 4.0:
        return "Group 5"

    return "Unclassified"


def calculate_score(nuclei: list[NucleusCount]) -> ScoreResult:
    """Calculate HER2-DISH summary score from included nuclei."""
    included = [n for n in nuclei if n.included]
    cell_count = len(included)
    total_her2 = sum(n.effective_her2 for n in included)
    total_cep17 = sum(int(n.cep17_red) for n in included)

    if cell_count == 0 or total_cep17 == 0:
        warnings: list[str] = []
        if cell_count < MINIMUM_INITIAL_NUCLEI:
            warnings.append(
                f"Fewer than {MINIMUM_INITIAL_NUCLEI} included nuclei. "
                "Initial HER2-DISH counting generally requires at least 20 nuclei."
            )
        return ScoreResult(
            included_cell_count=cell_count,
            total_her2=total_her2,
            total_cep17=total_cep17,
            her2_cep17_ratio=None,
            average_her2_copy_number=None,
            ish_group="Not evaluable",
            warnings=warnings,
        )

    ratio = total_her2 / total_cep17
    average_her2 = total_her2 / cell_count
    group = classify_ish_group(ratio, average_her2)

    warnings = []
    if cell_count < MINIMUM_INITIAL_NUCLEI:
        warnings.append(
            f"Fewer than {MINIMUM_INITIAL_NUCLEI} included nuclei. "
            "Initial HER2-DISH counting generally requires at least 20 nuclei."
        )
    elif cell_count == MINIMUM_INITIAL_NUCLEI:
        warnings.append("20 included nuclei reached. Review whether additional counting is needed according to the laboratory workflow.")

    if 1.8 <= ratio <= 2.2:
        warnings.append(BORDERLINE_RATIO_WARNING)

    if group in {"Group 2", "Group 3", "Group 4"}:
        warnings.append(GROUP_ADDITIONAL_EVALUATION_WARNING)

    return ScoreResult(
        included_cell_count=cell_count,
        total_her2=total_her2,
        total_cep17=total_cep17,
        her2_cep17_ratio=ratio,
        average_her2_copy_number=average_her2,
        ish_group=group,
        warnings=warnings,
    )
