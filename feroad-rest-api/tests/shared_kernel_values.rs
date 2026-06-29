use feroad_rest_api::shared_kernel::value_objects::GeoPoint;

#[test]
fn geo_point_distance_meters_within_700m() {
    let a = GeoPoint::new(37.5665, 126.9780).unwrap();
    let b = GeoPoint::new(37.5670, 126.9785).unwrap();
    assert!(a.distance_meters(&b) < 700.0);
}