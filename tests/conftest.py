"""Pytest configuration and fixtures for container tests."""
import pytest


@pytest.fixture(params=['sync', 'async'], ids=['Container', 'AsyncContainer'])
def container_builder_fixture(request):
    """Fixture that provides both sync and async container builders."""
    if request.param == 'sync':
        from independency.container import Container, ContainerBuilder
        return ContainerBuilder(), Container, False
    else:
        from independency.async_container import AsyncContainer, AsyncContainerBuilder
        return AsyncContainerBuilder(), AsyncContainer, True
