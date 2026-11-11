"""Software/simulator fixture: deterministic scalar, no I/O, no third-party deps."""


def run(ctx):
    value = int(ctx["params"].get("value", 9001))
    return dict(result=dict(value=value, passed=True))
