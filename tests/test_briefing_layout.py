"""Regression for overlapping delivery/target labels in a compact convoy plan."""
import pytest
from ironanvil.briefing import diagram_label_boxes


@pytest.mark.parametrize('markers',[
    [(614,471),(306,696),(693,594),(694,581),(673,549),(678,557)],
    [(650,550)]*6,
])
def test_clustered_kneeboard_labels_are_separate_inside_diagram(markers):
    sizes=[(60,20),(110,20),(50,20),(100,20),(100,20),(90,20)]
    boxes=diagram_label_boxes(markers,sizes,(45,453,955,758),protected=[(850,445,940,518)])
    assert len(boxes)==6
    for index,box in enumerate(boxes):
        assert 45<=box[0]<box[2]<=955 and 453<=box[1]<box[3]<=758
        assert not any(box[0]<other[2] and box[2]>other[0] and box[1]<other[3] and box[3]>other[1]
                       for other in boxes[:index])
        assert not any(box[0]<x+9 and box[2]>x-9 and box[1]<y+9 and box[3]>y-9 for x,y in markers)
