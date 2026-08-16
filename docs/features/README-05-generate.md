# Feature 05 — Generator

> Backend: `generate/generator.py`
> CLI: `upf-insight generate`

## What it does

Scaffolds a structurally valid power-intent skeleton from a domain list,
always-on signals, and retention domains.

## Example

```bash
upf-insight generate --domains core,io --always-on clk,rst --retention core
```

Emits:

```upf
upf_version 3.0
set_design_top top

create_power_domain core -elements {}
create_power_domain io -elements {}

create_supply_port vdd -direction in
create_supply_port vss -direction in
create_supply_net vdd -resolve port
...
create_supply_set primary -function {power vdd} -function {ground vss}
set_domain_supply_net core -primary_power_net vdd -primary_ground_net vss
...

add_port_state vdd -state {ON 1.0} -state {OFF 0.0}
create_pst pst_top -supplies {vdd vss}
add_pst_state PS_0 -pst pst_top -state {vdd ON vss ON}
...

set_retention core_ret -domain core -retention_supply retention \
    -save_signal save -restore_signal restore

set_port_attributes clk, rst -attribute {always_on true}
```

## Trust boundary

Generated output is a **starting point**, not a complete verified power
intent. Run `upf-insight check` on the result.

## Determinism

Same flags → byte-identical output.