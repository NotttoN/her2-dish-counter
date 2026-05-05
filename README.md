from her2dish.core.constants import BORDERLINE_RATIO_WARNING, GROUP_ADDITIONAL_EVALUATION_WARNING
from her2dish.core.models import NucleusCount
from her2dish.core.scoring import calculate_score, classify_ish_group


def nuclei(count, her2, cep17):
    return [NucleusCount(nucleus_id=i + 1, x=0, y=0, her2_black=her2, cep17_red=cep17) for i in range(count)]


def test_group_1():
    result = calculate_score(nuclei(20, her2=4, cep17=1))
    assert result.ish_group == "Group 1"
    assert result.total_her2 == 80
    assert result.total_cep17 == 20
    assert result.her2_cep17_ratio == 4.0
    assert result.average_her2_copy_number == 4.0


def test_group_2():
    result = calculate_score(nuclei(20, her2=3, cep17=1))
    assert result.ish_group == "Group 2"
    assert GROUP_ADDITIONAL_EVALUATION_WARNING in result.warnings


def test_group_3():
    result = calculate_score(nuclei(20, her2=6, cep17=4))
    assert result.ish_group == "Group 3"
    assert GROUP_ADDITIONAL_EVALUATION_WARNING in result.warnings


def test_group_4():
    result = calculate_score(nuclei(20, her2=5, cep17=3))
    assert result.ish_group == "Group 4"
    assert GROUP_ADDITIONAL_EVALUATION_WARNING in result.warnings


def test_group_5():
    result = calculate_score(nuclei(20, her2=3, cep17=3))
    assert result.ish_group == "Group 5"


def test_excluded_nuclei_are_not_counted():
    data = nuclei(20, her2=3, cep17=3)
    data.append(NucleusCount(nucleus_id=21, x=0, y=0, her2_black=100, cep17_red=1, included=False))
    result = calculate_score(data)
    assert result.total_her2 == 60
    assert result.total_cep17 == 60
    assert result.ish_group == "Group 5"


def test_cluster_value_added_to_her2():
    data = [NucleusCount(nucleus_id=i + 1, x=0, y=0, her2_black=1, cep17_red=1, cluster_value=3) for i in range(20)]
    result = calculate_score(data)
    assert result.total_her2 == 80
    assert result.average_her2_copy_number == 4
    assert result.ish_group == "Group 1"


def test_zero_cep17_is_not_evaluable():
    result = calculate_score(nuclei(20, her2=4, cep17=0))
    assert result.ish_group == "Not evaluable"
    assert result.her2_cep17_ratio is None
    assert result.average_her2_copy_number is None


def test_borderline_ratio_warning():
    # ratio = 40/20 = 2.0, average HER2 = 2.0, Group 2 and borderline ratio
    result = calculate_score(nuclei(20, her2=2, cep17=1))
    assert result.ish_group == "Group 2"
    assert BORDERLINE_RATIO_WARNING in result.warnings


def test_classify_none_values():
    assert classify_ish_group(None, 5.0) == "Not evaluable"
    assert classify_ish_group(2.0, None) == "Not evaluable"
