"""Route parsing against the REAL response shapes returned by Amazon Location (captured 2026-10-20)."""

from navigator.location.client import LocationClient

# Car: summary on the route. Pedestrian: no route-level summary, only per-leg details.
CAR = {"Routes": [{"Legs": [{"TravelMode": "Car", "VehicleLegDetails": {"Summary": {"Overview": {"Distance": 1083, "Duration": 243}}}}], "Summary": {"Distance": 1083, "Duration": 243}}]}
WALK = {"Routes": [{"Legs": [{"TravelMode": "Pedestrian", "PedestrianLegDetails": {"Summary": {"Overview": {"Distance": 953, "Duration": 979}}}}], "MajorRoadLabels": []}]}
MULTI_LEG = {"Routes": [{"Legs": [
    {"PedestrianLegDetails": {"Summary": {"Overview": {"Distance": 800, "Duration": 600}}}},
    {"PedestrianLegDetails": {"Summary": {"Overview": {"Distance": 809, "Duration": 600}}}}]}]}


class Routes:
    def __init__(self, response):
        self.response = response

    def calculate_routes(self, **kw):
        return self.response


def route(resp, mode="Car"):
    return LocationClient("us-east-2", places=object(), routes=Routes(resp)).route((40.8, -73.95), (40.7, -73.9), mode)


def test_car_route_uses_the_route_summary():
    r = route(CAR)
    assert (r.distance_miles, r.duration_minutes, r.travel_mode) == (0.7, 4.0, "Car")


def test_pedestrian_route_without_a_route_summary_uses_leg_details():
    r = route(WALK, "Pedestrian")
    assert (r.distance_miles, r.duration_minutes) == (0.6, 16.3)


def test_multiple_legs_are_summed():
    r = route(MULTI_LEG, "Pedestrian")
    assert r.distance_miles == 1.0 and r.duration_minutes == 20.0


def test_missing_data_means_no_route_not_a_guess():
    assert route({"Routes": []}) is None
    assert route({"Routes": [{"Legs": [{"PedestrianLegDetails": {}}]}]}, "Pedestrian") is None
