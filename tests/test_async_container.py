import abc
from functools import lru_cache
from typing import Any, Dict, Final, Generic, TypeVar

import pytest

from independency._common import ContainerError, Dependency as Dep
from independency._common import get_generic_mapping, get_signature
from independency.async_container import AsyncContainer, AsyncContainerBuilder


@pytest.mark.asyncio
async def test_container():
    class A:
        def __init__(self, x: int, y: str):
            self.x = x
            self.y = y

    builder = AsyncContainerBuilder()
    builder.singleton(int, lambda: 1)
    builder.singleton('y', lambda: 'abacaba')
    builder.singleton(A, A, y=Dep('y'))
    container = builder.build()
    inst = await container.resolve(A)
    assert isinstance(inst, A)
    assert inst.x == 1
    assert inst.y == 'abacaba'


@pytest.mark.asyncio
async def test_container_with_async_factory():
    class A:
        def __init__(self, x: int, y: str):
            self.x = x
            self.y = y

    async def async_int_factory():
        return 42

    async def async_str_factory():
        return 'async_value'

    builder = AsyncContainerBuilder()
    builder.singleton(int, async_int_factory)
    builder.singleton('y', async_str_factory)
    builder.singleton(A, A, y=Dep('y'))
    container = builder.build()
    inst = await container.resolve(A)
    assert isinstance(inst, A)
    assert inst.x == 42
    assert inst.y == 'async_value'


@pytest.mark.asyncio
async def test_mixed_sync_async_factories():
    class A:
        def __init__(self, x: int, y: str):
            self.x = x
            self.y = y

    async def async_int_factory():
        return 100

    builder = AsyncContainerBuilder()
    builder.singleton(int, async_int_factory)  # async factory
    builder.singleton('y', lambda: 'sync_value')  # sync factory
    builder.singleton(A, A, y=Dep('y'))  # sync factory
    container = builder.build()
    inst = await container.resolve(A)
    assert isinstance(inst, A)
    assert inst.x == 100
    assert inst.y == 'sync_value'


@pytest.mark.asyncio
async def test_generics():  # noqa: C901
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

    builder = AsyncContainerBuilder()
    builder.singleton(Interface[int], A, x=1)
    builder.singleton(Interface[str], B[str], value='abacaba')
    builder.singleton(Interface[Interface[str]], C[str])
    builder.singleton(D[str], D[str])
    container = builder.build()
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


@pytest.mark.asyncio
async def test_get_all_registered_types():  # noqa: C901
    T = TypeVar('T')  # noqa: N806
    StringDepsName: Final[str] = 'kek'

    class Interface(abc.ABC, Generic[T]):
        pass

    class A(Interface[int]):
        def __init__(self):
            pass

    class B(Interface[T], Generic[T]):
        def __init__(self):
            pass

    class C(Interface[Interface[T]]):
        def __init__(self):
            pass

    builder = AsyncContainerBuilder()
    builder.singleton(Interface[int], A)
    builder.singleton(Interface[str], B[str])
    builder.singleton(Interface[Interface[str]], C[str])
    builder.singleton(StringDepsName, C[str])
    container = builder.build()
    types = container.get_registered_deps()

    assert len(types) == 5

    assert StringDepsName in types
    assert Interface[int] in types
    assert Interface[str] in types
    assert Interface[Interface[str]] in types
    assert AsyncContainer in types


def test_missing_dependencies_raise_exception():
    class A:
        pass

    class B:
        def __init__(self, a: A):
            self._a = a

    builder = AsyncContainerBuilder()
    builder.singleton(B, B)

    with pytest.raises(ContainerError):
        builder.build()


@pytest.mark.asyncio
async def test_resolves_instances():
    class A:
        pass

    class B:
        pass

    builder = AsyncContainerBuilder()
    builder.register(A, A, is_singleton=False)
    builder.singleton(B, B)
    container = builder.build()

    assert (await container.resolve(A)) != (await container.resolve(A))
    assert (await container.resolve(B)) is (await container.resolve(B))


def test_registering_an_instance_as_factory_is_exception():
    class A:
        pass

    builder = AsyncContainerBuilder()
    a = A()

    with pytest.raises(ContainerError):
        builder.register(A, a, is_singleton=True)  # type: ignore


@pytest.mark.asyncio
async def test_can_use_a_string_key():
    builder = AsyncContainerBuilder()
    builder.register("foo", lambda: 1, is_singleton=True)

    container = builder.build()
    assert (await container.resolve("foo")) == 1


@pytest.mark.asyncio
async def test_resolution():
    T = TypeVar('T')  # noqa: N806

    class A(Generic[T]):
        def __init__(self, value: T):
            self.value = value

    class B(Generic[T]):
        def __init__(self, value: T):
            self.value = value

    class C(Generic[T]):
        def __init__(self, value: A[B[T]]):
            self.value = value

    builder = AsyncContainerBuilder()
    builder.singleton(B[int], B[int], value=1)
    builder.singleton(A[B[int]], A[B[int]])
    builder.singleton(C[int], C[int])

    inst = await builder.build().resolve(C[int])
    assert isinstance(inst, C)
    assert inst.value.value.value == 1


@pytest.mark.asyncio
async def test_resolution_by_function():
    T = TypeVar('T')  # noqa: N806

    class A(Generic[T]):
        def __init__(self, x: int, y: T):
            self.x = x
            self.y = y

    class B(Generic[T]):
        def __init__(self, value: A[T]):
            self.value = value

    def create_b(value: A[int]) -> B[str]:
        return B[str](A[str](x=value.x, y=str(value.y)))

    builder = AsyncContainerBuilder()
    builder.singleton(A[int], A[int], x=1, y=2)
    builder.singleton(B[str], create_b)

    inst = await builder.build().resolve(B[str])
    assert inst.value.x == 1
    assert inst.value.y == '2'


@pytest.mark.asyncio
async def test_resolution_by_async_function():
    T = TypeVar('T')  # noqa: N806

    class A(Generic[T]):
        def __init__(self, x: int, y: T):
            self.x = x
            self.y = y

    class B(Generic[T]):
        def __init__(self, value: A[T]):
            self.value = value

    async def create_b(value: A[int]) -> B[str]:
        return B[str](A[str](x=value.x, y=str(value.y)))

    builder = AsyncContainerBuilder()
    builder.singleton(A[int], A[int], x=1, y=2)
    builder.singleton(B[str], create_b)

    inst = await builder.build().resolve(B[str])
    assert inst.value.x == 1
    assert inst.value.y == '2'


def test_resolution_with_error():
    T = TypeVar('T')  # noqa: N806

    class B(Generic[T]):
        def __init__(self, value: T):
            self.value = value

    class A(Generic[T]):
        def __init__(self, value: B[T]):
            self.value = value

    builder = AsyncContainerBuilder()
    builder.singleton(B[str], B[str], value='some value')
    builder.singleton(A[int], A[int])

    with pytest.raises(ContainerError):
        builder.build()


@pytest.mark.asyncio
async def test_different_generics_resolution():
    T = TypeVar('T')  # noqa: N806

    class B(Generic[T]):
        def __init__(self, value: T):
            self.value = value

    class A(Generic[T]):
        def __init__(self, value: B[T]):
            self.value = value

    builder = AsyncContainerBuilder()
    builder.singleton(B[int], B[int], value=1)
    builder.singleton(A[int], A[int])
    builder.singleton(B[str], B[str], value='str')
    builder.singleton(A[str], A[str])

    container = builder.build()
    inst_int = await container.resolve(A[int])
    inst_str = await container.resolve(A[str])
    assert inst_int.value.value == 1
    assert inst_str.value.value == 'str'


def test_register_generic_type_without_params():
    T = TypeVar('T')  # noqa: N806

    class B(Generic[T]):
        def __init__(self, value: T):
            self.value = value

    builder = AsyncContainerBuilder()

    with pytest.raises(ValueError):
        builder.singleton(B, B[int])


@pytest.mark.asyncio
async def test_can_resolve_objects_with_forward_references():
    class Kek:
        def __init__(self, kek: 'Lol'):
            self.kek = kek

    class Lol:
        def __init__(self, x: int):
            self.x = x

    builder = AsyncContainerBuilder()

    builder.singleton(Lol, lambda: Lol(1))
    builder.singleton(Kek, Kek)

    container = builder.build()
    instance = await container.resolve(Kek)
    assert instance.kek.x == 1


@pytest.mark.asyncio
async def test_forward_references_can_be_registered_as_strings():
    class Kek:
        def __init__(self, kek: 'Lol'):
            self.kek = kek

    class Lol:
        def __init__(self, x: int):
            self.x = x

    builder = AsyncContainerBuilder()

    builder.singleton("Lol", lambda: Lol(1))
    builder.singleton(Kek, Kek)

    container = builder.build()
    instance = await container.resolve(Kek)
    assert instance.kek.x == 1


@pytest.mark.asyncio
async def test_can_use_dependency_with_forward_ref():
    class Kek:
        def __init__(self, kek: 'Lol'):
            self.kek = kek

    class Lol:
        def __init__(self, x: int):
            self.x = x

    builder = AsyncContainerBuilder()

    builder.singleton("Lol", lambda: Lol(1))
    builder.singleton(Kek, Kek, kek=Dep("Lol"))

    container = builder.build()
    instance = await container.resolve(Kek)
    assert instance.kek.x == 1


@pytest.mark.asyncio
async def test_can_use_dependency_with_forward_ref_as_class():
    class Kek:
        def __init__(self, kek: 'Lol'):
            self.kek = kek

    class Lol:
        def __init__(self, x: int):
            self.x = x

    builder = AsyncContainerBuilder()

    builder.singleton("Lol", lambda: Lol(1))
    builder.singleton(Kek, Kek, kek=Dep(Lol))

    container = builder.build()
    instance = await container.resolve(Kek)
    assert instance.kek.x == 1


@pytest.mark.asyncio
async def test_register_after_building_does_not_affect_on_container():
    class A:
        pass

    class B:
        pass

    builder = AsyncContainerBuilder()
    builder.singleton(A, A)
    container = builder.build()

    with pytest.raises(ContainerError):
        await container.resolve(B)

    builder.singleton(B, B)
    with pytest.raises(ContainerError):
        await container.resolve(B)


def test_cyclic_dependencies():
    class A:
        def __init__(self, b: 'B'):
            self.b = b

    class B:
        def __init__(self, a: A):
            self.a = a

    builder = AsyncContainerBuilder()
    builder.register(A, A, is_singleton=False)
    builder.register(B, B, is_singleton=False)
    with pytest.raises(ContainerError):
        builder.build()


@pytest.mark.asyncio
async def test_overridden():
    class A:
        def __init__(self, x: int, y: str):
            self.x = x
            self.y = y

    builder = AsyncContainerBuilder()
    builder.singleton(int, lambda: 1)
    builder.singleton('y', lambda: 'abacaba')
    builder.singleton(A, A, y=Dep('y'))
    container = builder.build()
    container_copy = container.create_test_container().with_overridden_singleton(int, lambda: 2)

    inst = await container.resolve(A)
    assert isinstance(inst, A)
    assert inst.x == 1
    assert inst.y == 'abacaba'

    copy_inst = await container_copy.resolve(A)
    assert inst is not copy_inst
    assert isinstance(copy_inst, A)
    assert copy_inst.x == 2
    assert copy_inst.y == 'abacaba'


def test_raise_when_override_missing_dependency():
    builder = AsyncContainerBuilder()
    container = builder.build()

    with pytest.raises(ContainerError):
        container.create_test_container().with_overridden_singleton(int, lambda: 1)


def test_invalid_argument():
    builder = AsyncContainerBuilder()

    class A:
        def __init__(self, x: int):
            pass

    with pytest.raises(ValueError):
        builder.singleton(A, A, x=1, y=1)


def test_raise_when_register_already_existing_dependency():
    builder = AsyncContainerBuilder()
    builder.singleton(int, lambda: 1)
    with pytest.raises(ContainerError):
        builder.singleton(int, lambda: 2)


def test_get_generic_mapping():
    T1 = TypeVar('T1')  # noqa: N806
    T2 = TypeVar('T2')  # noqa: N806
    T3 = TypeVar('T3')  # noqa: N806

    class A(Generic[T1, T2, T3]):
        pass

    class B:
        pass

    assert get_generic_mapping(A[int, float, str]) == {T1: int, T2: float, T3: str}
    assert get_generic_mapping(B) == {}
    assert get_generic_mapping(int) == {}


def test_get_signature():
    T1 = TypeVar('T1')  # noqa: N806

    def f(x: int, y: T1) -> None:
        pass

    def g(x: str, y: float) -> None:
        pass

    class A:
        def __init__(self, x: int, y: str):
            pass

    class B(Generic[T1]):
        def __init__(self, x: T1, y: int):
            pass

    assert get_signature(f, {}) == {'x': int, 'y': T1}
    assert get_signature(g, {}) == {'x': str, 'y': float}
    assert get_signature(A, {}) == {'x': int, 'y': str}
    assert get_signature(B, {}) == {'x': T1, 'y': int}
    with pytest.raises(ContainerError):
        get_signature(1, {})  # type: ignore


@pytest.mark.asyncio
async def test_get_container_as_dependency():
    class A:
        def __init__(self, x: Any):
            self.x = x

    class Settings:
        def __init__(self, mapping: Dict[str, Any]):
            self.mapping = mapping

    async def make_a(container: AsyncContainer, settings: Settings) -> A:
        return A(await container.resolve(settings.mapping['key']))

    builder = AsyncContainerBuilder()
    builder.singleton(int, lambda: 1)
    builder.singleton(Settings, lambda: Settings(mapping={'key': int}))
    builder.singleton(A, make_a)

    container = builder.build()
    a = await container.resolve(A)
    assert a.x == 1


@pytest.mark.asyncio
async def test_container_as_dependency_in_test_container():
    class A:
        def __init__(self, x: int):
            self.x = x

    async def make_a(container: AsyncContainer) -> A:
        return A(await container.resolve(int))

    builder = AsyncContainerBuilder()
    builder.singleton(int, lambda: 1)
    builder.singleton(A, make_a)

    container = builder.build()
    test_container = container.create_test_container().with_overridden_singleton(int, lambda: 2)

    assert (await container.resolve(A)).x == 1
    assert (await test_container.resolve(A)).x == 2


def test_show_parent_for_missing():
    class A:
        def __init__(self, x: int):
            self.x = x

    class B:
        def __init__(self, value: A):
            self.value = value

    builder = AsyncContainerBuilder()
    builder.singleton(B, B)
    with pytest.raises(
        ContainerError,
        match="No dependency of type <class 'tests.test_async_container.test_show_parent_for_missing.<locals>.A'> "
        "needed by <class 'tests.test_async_container.test_show_parent_for_missing.<locals>.B'>",
    ):
        builder.build()


def test_unsupported_callable_raise_exception():
    @lru_cache(maxsize=None)
    def fake_factory():
        return ...

    builder = AsyncContainerBuilder()
    with pytest.raises(ContainerError):
        builder.singleton('a', fake_factory)


@pytest.mark.asyncio
async def test_async_singleton_caching():
    """Test that async singletons are properly cached"""
    call_count = 0

    async def create_service():
        nonlocal call_count
        call_count += 1
        return {"count": call_count}

    builder = AsyncContainerBuilder()
    builder.singleton("service", create_service)
    container = builder.build()

    # Resolve twice
    first = await container.resolve("service")
    second = await container.resolve("service")

    # Should be the same instance
    assert first is second
    assert call_count == 1


@pytest.mark.asyncio
async def test_async_transient_instances():
    """Test that async transient dependencies create new instances"""
    call_count = 0

    async def create_service():
        nonlocal call_count
        call_count += 1
        return {"count": call_count}

    builder = AsyncContainerBuilder()
    builder.register("service", create_service, is_singleton=False)
    container = builder.build()

    # Resolve twice
    first = await container.resolve("service")
    second = await container.resolve("service")

    # Should be different instances
    assert first is not second
    assert call_count == 2
    assert first["count"] == 1
    assert second["count"] == 2
