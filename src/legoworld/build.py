"""Small annotations for otherwise ordinary BrickAgent build scripts."""


def expose_port(component, name: str, connector):
    """Name a connector in this definition, so replacement can preserve external joins."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("A port needs a non-empty name")
    connector = component.connector(connector)  # Checks ownership using BrickAgent.
    ports = getattr(component, "_legoworld_ports", None)
    if ports is None:
        ports = component._legoworld_ports = {}
    if name in ports:
        raise ValueError(f"Duplicate port {name!r}")
    ports[name] = connector
    return connector


def require_contact(component, a, b):
    """Persist a required second support/loop closure, rather than only detecting proximity."""
    from legoworld.backend import add_required_contact
    add_required_contact(component, component.connector(a), component.connector(b))


def get_port(component, name):
    """Get a previously exposed definition-local connector for native Assembly.attach."""
    return component._legoworld_ports[name]
