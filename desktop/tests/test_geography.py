import pytest
from qrescate_desktop.geography import in_satipo, validate_coverage, BOUNDARY
from qrescate_desktop.models import Scenario,Point,Zone

def test_boundary_is_satipo_junin():
    properties=BOUNDARY['features'][0]['properties']
    assert properties['IDPROV']=='1206' and properties['PROVINCIA']=='SATIPO' and properties['DEPARTAMEN']=='JUNIN'

@pytest.mark.parametrize('lat,lng,expected',[(-11.253,-74.638,True),(-11.5,-74.5,True),(-12.046,-77.043,False),(-11,-74,False),(0,0,False)])
def test_provincial_polygon_not_bounding_box(lat,lng,expected):
    assert in_satipo(lat,lng) is expected

def test_rejects_scenario_with_outside_points_or_zone_centers():
    validate_coverage(Scenario(base=Point('h','Base',-11.253,-74.638)))
    with pytest.raises(ValueError):validate_coverage(Scenario(base=Point('h','Lima',-12.046,-77.043)))
    with pytest.raises(ValueError):validate_coverage(Scenario(zones=[Zone('z','Fuera',0,0,100,'exclusion')]))
