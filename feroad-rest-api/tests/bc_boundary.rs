#[test]
fn pot_domain_has_no_supply_dependency() {
    let pot_lib = std::fs::read_to_string("src/pot/domain/mod.rs").unwrap();
    assert!(!pot_lib.contains("crate::supply"));
}