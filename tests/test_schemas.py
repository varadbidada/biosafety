import pytest
from pydantic import ValidationError
from api.schemas import (
    PredictionInput,
    PredictionResponse,
    ClimateData,
    HotspotData,
    HotspotsResponse,
    DistrictOverview,
    HealthResponse,
)


class TestPredictionInput:
    def test_valid_input(self):
        data = PredictionInput(features=[1.0] * 17)
        assert len(data.features) == 17

    def test_invalid_length_short(self):
        with pytest.raises(ValidationError):
            PredictionInput(features=[1.0] * 5)

    def test_invalid_length_long(self):
        with pytest.raises(ValidationError):
            PredictionInput(features=[1.0] * 30)

    def test_non_float_values(self):
        with pytest.raises(ValidationError):
            PredictionInput(features=["a"] * 17)


class TestClimateData:
    def test_valid_climate(self):
        c = ClimateData(rainfall=100.0, temperature=28.5, ndvi=0.6, cases=15.0, monsoon=1)
        assert c.rainfall == 100.0
        assert c.monsoon == 1


class TestHotspotData:
    def test_valid_hotspot(self):
        h = HotspotData(
            id=1,
            name="Test Zone",
            district_ref="Adilabad",
            offset_lat=0.01,
            offset_lon=0.02,
            type="cases",
            avg_cases=10,
            max_cases=20,
            std_cases=2.5,
            intensity=0.5,
        )
        assert h.type == "cases"
        assert h.avg_cases == 10


class TestHealthResponse:
    def test_healthy(self):
        h = HealthResponse(status="ok", version="0.1.0", models_loaded=True)
        assert h.status == "ok"

    def test_degraded(self):
        h = HealthResponse(status="degraded", version="0.1.0", models_loaded=False)
        assert h.models_loaded is False


class TestDistrictOverview:
    def test_valid(self):
        d = DistrictOverview(
            district="Adilabad",
            avg_cases=15.0,
            max_cases=30.0,
            min_cases=5.0,
            risk_level="medium",
            intensity=0.3,
        )
        assert d.risk_level == "medium"
        assert d.intensity == 0.3
