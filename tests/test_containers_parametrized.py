"""Parametrized tests that work for both sync and async containers."""
import abc
import inspect
from functools import lru_cache
from typing import Any, Dict, Final, Generic, TypeVar

import pytest

from independency import ContainerError, Dependency as Dep


def _run_test(builder, container_type, is_async, test_func):
    """Helper to run test function for both sync and async containers."""
    container = builder.build()
    result = test_func(container)
    if is_async and inspect.iscoroutine(result):
        import asyncio
        return asyncio.run(result)
    return result


@pytest.mark.parametrize('container_builder_fixture', ['sync', 'async'], indirect=True, ids=['Container', 'AsyncContainer'])
def test_basic_container(container_builder_fixture):
    """Test basic container functionality with dependencies."""
    builder, container_type, is_async = container_builder_fixture

    class A:
        def __init__(self, x: int, y: str):
            self.x = x
            self.y = y

    builder.singleton(int, lambda: 1)
    builder.singleton('y', lambda: 'abacaba')
    builder.singleton(A, A, y=Dep('y'))

    container = builder.build()

    async def async_check():
        inst = await container.resolve(A)
        assert isinstance(inst, A)
        assert inst.x == 1
        assert inst.y == 'abacaba'

    def sync_check():
        inst = container.resolve(A)
        assert isinstance(inst, A)
        assert inst.x == 1
        assert inst.y == 'abacaba'

    if is_async:
        import asyncio
        asyncio.run(async_check())
    else:
        sync_check()


@pytest.mark.parametrize('container_builder_fixture', ['sync', 'async'], indirect=True, ids=['Container', 'AsyncContainer'])
def test_generics(container_builder_fixture):  # noqa: C901
    """Test generic types resolution."""
    builder, container_type, is_async = container_builder_fixture
    T = TypeVar('T')  # noqa: N806

    class Interface(abc.ABC, Generic[T]):
        @abc.abstractmethod
        def f(self) -> T:
            pass

    class A(Interface[int]):
        def __init__(self, x: int):
            self.x = x

        def f(self) -> int:
            return self.x

    class B(Interface[T], Generic[T]):
        def __init__(self, value: T):
            self.value = value

        def f(self) -> T:
            return self.value

    class C(Interface[Interface[T]]):
        def __init__(self, value: Interface[T]):
            self.value = value

        def f(self) -> Interface[T]:
            return self.value

    class D(Generic[T]):
        def __init__(self, value: Interface[T]):
            self.value = value

    builder.singleton(Interface[int], A, x=1)
    builder.singleton(Interface[str], B[str], value='abacaba')
    builder.singleton(Interface[Interface[str]], C[str])
    builder.singleton(D[str], D[str])

    container = builder.build()

    async def async_check():
        a = await container.resolve(Interface[int])
        assert isinstance(a, A)
        assert a.x == 1
        b = await container.resolve(Interface[str])
        assert isinstance(b, B)
        assert b.value == 'abacaba'
        c = await container.resolve(Interface[Interface[str]])
        assert isinstance(c, C)
        assert c.value.f() == 'abacaba'
        d = await container.resolve(D[str])
        assert isinstance(d, D)
        assert d.value.f() == 'abacaba'

    def sync_check():
        a = container.resolve(Interface[int])
        assert isinstance(a, A)
        assert a.x == 1
        b = container.resolve(Interface[str])
        assert isinstance(b, B)
        assert b.value == 'abacaba'
        c = container.resolve(Interface[Interface[str]])
        assert isinstance(c, C)
        assert c.value.f() == 'abacaba'
        d = container.resolve(D[str])
        assert isinstance(d, D)
        assert d.value.f() == 'abacaba'

    if is_async:
        import asyncio
        asyncio.run(async_check())
    else:
        sync_check()


@pytest.mark.parametrize('container_builder_fixture', ['sync', 'async'], indirect=True, ids=['Container', 'AsyncContainer'])
def test_string_key(container_builder_fixture):
    """Test using string keys for dependencies."""
    builder, container_type, is_async = container_builder_fixture

    builder.singleton('test', lambda: 42)
    container = builder.build()

    async def async_check():
        result = await container.resolve('test')
        assert result == 42

    def sync_check():
        result = container.resolve('test')
        assert result == 42

    if is_async:
        import asyncio
        asyncio.run(async_check())
    else:
        sync_check()


@pytest.mark.parametrize('container_builder_fixture', ['sync', 'async'], indirect=True, ids=['Container', 'AsyncContainer'])
def test_nested_resolution(container_builder_fixture):
    """Test resolution with nested dependencies."""
    builder, container_type, is_async = container_builder_fixture

    class A:
        def __init__(self, b: 'B', c: 'C'):
            self.b = b
            self.c = c

    class B:
        def __init__(self, c: 'C'):
            self.c = c

    class C:
        def __init__(self):
            pass

    builder.singleton(C, C)
    builder.singleton(B, B)
    builder.singleton(A, A)

    container = builder.build()

    async def async_check():
        result = await container.resolve(A)
        assert isinstance(result, A)
        assert isinstance(result.b, B)
        assert isinstance(result.c, C)
        assert result.b.c is result.c

    def sync_check():
        result = container.resolve(A)
        assert isinstance(result, A)
        assert isinstance(result.b, B)
        assert isinstance(result.c, C)
        assert result.b.c is result.c

    if is_async:
        import asyncio
        asyncio.run(async_check())
    else:
        sync_check()


@pytest.mark.parametrize('container_builder_fixture', ['sync', 'async'], indirect=True, ids=['Container', 'AsyncContainer'])
def test_resolution_by_function(container_builder_fixture):
    """Test resolution using factory functions."""
    builder, container_type, is_async = container_builder_fixture

    class A:
        def __init__(self, value: int):
            self.value = value

    def factory(value: int) -> A:
        return A(value)

    builder.singleton(int, lambda: 42)
    builder.singleton(A, factory)

    container = builder.build()

    async def async_check():
        result = await container.resolve(A)
        assert isinstance(result, A)
        assert result.value == 42

    def sync_check():
        result = container.resolve(A)
        assert isinstance(result, A)
        assert result.value == 42

    if is_async:
        import asyncio
        asyncio.run(async_check())
    else:
        sync_check()


@pytest.mark.parametrize('container_builder_fixture', ['sync', 'async'], indirect=True, ids=['Container', 'AsyncContainer'])
def test_different_generics_resolution(container_builder_fixture):
    """Test resolution of different generic types."""
    builder, container_type, is_async = container_builder_fixture
    T = TypeVar('T')  # noqa: N806

    class A(Generic[T]):
        def __init__(self, value: T):
            self.value = value

    builder.singleton(A[int], A[int], value=1)
    builder.singleton(A[str], A[str], value='abacaba')

    container = builder.build()

    async def async_check():
        a_int = await container.resolve(A[int])
        a_str = await container.resolve(A[str])
        assert isinstance(a_int, A)
        assert a_int.value == 1
        assert isinstance(a_str, A)
        assert a_str.value == 'abacaba'

    def sync_check():
        a_int = container.resolve(A[int])
        a_str = container.resolve(A[str])
        assert isinstance(a_int, A)
        assert a_int.value == 1
        assert isinstance(a_str, A)
        assert a_str.value == 'abacaba'

    if is_async:
        import asyncio
        asyncio.run(async_check())
    else:
        sync_check()


@pytest.mark.parametrize('container_builder_fixture', ['sync', 'async'], indirect=True, ids=['Container', 'AsyncContainer'])
def test_forward_references(container_builder_fixture):
    """Test resolution with forward references."""
    builder, container_type, is_async = container_builder_fixture

    class Kek:
        def __init__(self, kek: 'Lol'):
            self.kek = kek

    class Lol:
        def __init__(self, x: int):
            self.x = x

    builder.singleton(Lol, lambda: Lol(1))
    builder.singleton(Kek, Kek)

    container = builder.build()

    async def async_check():
        instance = await container.resolve(Kek)
        assert instance.kek.x == 1

    def sync_check():
        instance = container.resolve(Kek)
        assert instance.kek.x == 1

    if is_async:
        import asyncio
        asyncio.run(async_check())
    else:
        sync_check()


@pytest.mark.parametrize('container_builder_fixture', ['sync', 'async'], indirect=True, ids=['Container', 'AsyncContainer'])
def test_forward_references_as_strings(container_builder_fixture):
    """Test registration of forward references as strings."""
    builder, container_type, is_async = container_builder_fixture

    class Kek:
        def __init__(self, kek: 'Lol'):
            self.kek = kek

    class Lol:
        def __init__(self, x: int):
            self.x = x

    builder.singleton("Lol", lambda: Lol(1))
    builder.singleton(Kek, Kek)

    container = builder.build()

    async def async_check():
        instance = await container.resolve(Kek)
        assert instance.kek.x == 1

    def sync_check():
        instance = container.resolve(Kek)
        assert instance.kek.x == 1

    if is_async:
        import asyncio
        asyncio.run(async_check())
    else:
        sync_check()


@pytest.mark.parametrize('container_builder_fixture', ['sync', 'async'], indirect=True, ids=['Container', 'AsyncContainer'])
def test_dependency_with_forward_ref(container_builder_fixture):
    """Test using Dependency with forward references."""
    builder, container_type, is_async = container_builder_fixture

    class Kek:
        def __init__(self, kek: 'Lol'):
            self.kek = kek

    class Lol:
        def __init__(self, x: int):
            self.x = x

    builder.singleton("Lol", lambda: Lol(1))
    builder.singleton(Kek, Kek, kek=Dep("Lol"))

    container = builder.build()

    async def async_check():
        instance = await container.resolve(Kek)
        assert instance.kek.x == 1

    def sync_check():
        instance = container.resolve(Kek)
        assert instance.kek.x == 1

    if is_async:
        import asyncio
        asyncio.run(async_check())
    else:
        sync_check()


@pytest.mark.parametrize('container_builder_fixture', ['sync', 'async'], indirect=True, ids=['Container', 'AsyncContainer'])
def test_dependency_with_forward_ref_as_class(container_builder_fixture):
    """Test using Dependency with forward reference as class."""
    builder, container_type, is_async = container_builder_fixture

    class Kek:
        def __init__(self, kek: 'Lol'):
            self.kek = kek

    class Lol:
        def __init__(self, x: int):
            self.x = x

    builder.singleton("Lol", lambda: Lol(1))
    builder.singleton(Kek, Kek, kek=Dep(Lol))

    container = builder.build()

    async def async_check():
        instance = await container.resolve(Kek)
        assert instance.kek.x == 1

    def sync_check():
        instance = container.resolve(Kek)
        assert instance.kek.x == 1

    if is_async:
        import asyncio
        asyncio.run(async_check())
    else:
        sync_check()


@pytest.mark.parametrize('container_builder_fixture', ['sync', 'async'], indirect=True, ids=['Container', 'AsyncContainer'])
def test_container_as_dependency(container_builder_fixture):
    """Test using container as a dependency."""
    builder, container_type, is_async = container_builder_fixture

    class A:
        def __init__(self, x: Any):
            self.x = x

    class Settings:
        def __init__(self, mapping: Dict[str, Any]):
            self.mapping = mapping

    async def make_a_async(container: container_type, settings: Settings) -> A:
        return A(await container.resolve(settings.mapping['key']))

    def make_a_sync(container: container_type, settings: Settings) -> A:
        return A(container.resolve(settings.mapping['key']))

    builder.singleton(int, lambda: 1)
    builder.singleton(Settings, lambda: Settings(mapping={'key': int}))
    builder.singleton(A, make_a_async if is_async else make_a_sync)

    container = builder.build()

    async def async_check():
        a = await container.resolve(A)
        assert a.x == 1

    def sync_check():
        a = container.resolve(A)
        assert a.x == 1

    if is_async:
        import asyncio
        asyncio.run(async_check())
    else:
        sync_check()


@pytest.mark.parametrize('container_builder_fixture', ['sync', 'async'], indirect=True, ids=['Container', 'AsyncContainer'])
def test_container_as_dependency_in_test_container(container_builder_fixture):
    """Test using container as dependency in test container with overrides."""
    builder, container_type, is_async = container_builder_fixture

    class A:
        def __init__(self, x: int):
            self.x = x

    async def make_a_async(container: container_type) -> A:
        return A(await container.resolve(int))

    def make_a_sync(container: container_type) -> A:
        return A(container.resolve(int))

    builder.singleton(int, lambda: 1)
    builder.singleton(A, make_a_async if is_async else make_a_sync)

    container = builder.build()
    test_container = container.create_test_container().with_overridden_singleton(int, lambda: 2)

    async def async_check():
        assert (await container.resolve(A)).x == 1
        assert (await test_container.resolve(A)).x == 2

    def sync_check():
        assert container.resolve(A).x == 1
        assert test_container.resolve(A).x == 2

    if is_async:
        import asyncio
        asyncio.run(async_check())
    else:
        sync_check()
