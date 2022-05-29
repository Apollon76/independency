import abc
from typing import Any, Dict, Generic, TypeVar

import pytest

from independency.container import Container, ContainerBuilder, ContainerError
from independency.container import Dependency as Dep
from independency.container import get_generic_mapping, get_signature


def test_container():
    class A:
        def __init__(self, x: int, y: str):
            self.x = x
            self.y = y

    builder = ContainerBuilder()
    builder.singleton(int, lambda: 1)
    builder.singleton('y', lambda: 'abacaba')
    builder.singleton(A, A, y=Dep('y'))
    container = builder.build()
    inst = container.resolve(A)
    assert isinstance(inst, A)
    assert inst.x == 1
    assert inst.y == 'abacaba'


def test_generics():  # noqa: C901
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

    builder = ContainerBuilder()
    builder.singleton(Interface[int], A, x=1)
    builder.singleton(Interface[str], B[str], value='abacaba')
    builder.singleton(Interface[Interface[str]], C[str])
    builder.singleton(D[str], D[str])
    container = builder.build()
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


def test_missing_dependencies_raise_exception():
    class A:
        pass

    class B:
        def __init__(self, a: A):
            self._a = a

    builder = ContainerBuilder()
    builder.singleton(B, B)

    with pytest.raises(ContainerError):
        builder.build()


def test_resolves_instances():
    class A:
        pass

    class B:
        pass

    builder = ContainerBuilder()
    builder.register(A, A, is_singleton=False)
    builder.singleton(B, B)
    container = builder.build()

    assert container.resolve(A) != container.resolve(A)
    assert container.resolve(B) is container.resolve(B)


def test_registering_an_instance_as_factory_is_exception():
    class A:
        pass

    builder = ContainerBuilder()
    a = A()

    with pytest.raises(ContainerError):
        builder.register(A, a, is_singleton=True)  # type: ignore


def test_can_use_a_string_key():
    builder = ContainerBuilder()
    builder.register("foo", lambda: 1, is_singleton=True)

    container = builder.build()
    assert container.resolve("foo") == 1


def test_resolution():
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

    builder = ContainerBuilder()
    builder.singleton(B[int], B[int], value=1)
    builder.singleton(A[B[int]], A[B[int]])
    builder.singleton(C[int], C[int])

    inst = builder.build().resolve(C[int])
    assert isinstance(inst, C)
    assert inst.value.value.value == 1


def test_resolution_by_function():
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

    builder = ContainerBuilder()
    builder.singleton(A[int], A[int], x=1, y=2)
    builder.singleton(B[str], create_b)

    inst = builder.build().resolve(B[str])
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

    builder = ContainerBuilder()
    builder.singleton(B[str], B[str], value='some value')
    builder.singleton(A[int], A[int])

    with pytest.raises(ContainerError):
        builder.build()


def test_different_generics_resolution():
    T = TypeVar('T')  # noqa: N806

    class B(Generic[T]):
        def __init__(self, value: T):
            self.value = value

    class A(Generic[T]):
        def __init__(self, value: B[T]):
            self.value = value

    builder = ContainerBuilder()
    builder.singleton(B[int], B[int], value=1)
    builder.singleton(A[int], A[int])
    builder.singleton(B[str], B[str], value='str')
    builder.singleton(A[str], A[str])

    container = builder.build()
    inst_int = container.resolve(A[int])
    inst_str = container.resolve(A[str])
    assert inst_int.value.value == 1
    assert inst_str.value.value == 'str'


def test_register_generic_type_without_params():
    T = TypeVar('T')  # noqa: N806

    class B(Generic[T]):
        def __init__(self, value: T):
            self.value = value

    builder = ContainerBuilder()

    with pytest.raises(ValueError):
        builder.singleton(B, B[int])


def test_can_resolve_objects_with_forward_references():
    class Kek:
        def __init__(self, kek: 'Lol'):
            self.kek = kek

    class Lol:
        def __init__(self, x: int):
            self.x = x

    builder = ContainerBuilder()

    builder.singleton(Lol, lambda: Lol(1))
    builder.singleton(Kek, Kek)

    container = builder.build()
    instance = container.resolve(Kek)
    assert instance.kek.x == 1


def test_forward_references_can_be_registered_as_strings():
    class Kek:
        def __init__(self, kek: 'Lol'):
            self.kek = kek

    class Lol:
        def __init__(self, x: int):
            self.x = x

    builder = ContainerBuilder()

    builder.singleton("Lol", lambda: Lol(1))
    builder.singleton(Kek, Kek)

    container = builder.build()
    instance = container.resolve(Kek)
    assert instance.kek.x == 1


def test_can_use_dependency_with_forward_ref():
    class Kek:
        def __init__(self, kek: 'Lol'):
            self.kek = kek

    class Lol:
        def __init__(self, x: int):
            self.x = x

    builder = ContainerBuilder()

    builder.singleton("Lol", lambda: Lol(1))
    builder.singleton(Kek, Kek, kek=Dep("Lol"))

    container = builder.build()
    instance = container.resolve(Kek)
    assert instance.kek.x == 1


def test_can_use_dependency_with_forward_ref_as_class():
    class Kek:
        def __init__(self, kek: 'Lol'):
            self.kek = kek

    class Lol:
        def __init__(self, x: int):
            self.x = x

    builder = ContainerBuilder()

    builder.singleton("Lol", lambda: Lol(1))
    builder.singleton(Kek, Kek, kek=Dep(Lol))

    container = builder.build()
    instance = container.resolve(Kek)
    assert instance.kek.x == 1


def test_register_after_building_does_not_affect_on_container():
    class A:
        pass

    class B:
        pass

    builder = ContainerBuilder()
    builder.singleton(A, A)
    container = builder.build()

    with pytest.raises(ContainerError):
        container.resolve(B)

    builder.singleton(B, B)
    with pytest.raises(ContainerError):
        container.resolve(B)


def test_cyclic_dependencies():
    class A:
        def __init__(self, b: 'B'):
            self.b = b

    class B:
        def __init__(self, a: A):
            self.a = a

    builder = ContainerBuilder()
    builder.register(A, A, is_singleton=False)
    builder.register(B, B, is_singleton=False)
    with pytest.raises(ContainerError):
        builder.build()


def test_overridden():
    class A:
        def __init__(self, x: int, y: str):
            self.x = x
            self.y = y

    builder = ContainerBuilder()
    builder.singleton(int, lambda: 1)
    builder.singleton('y', lambda: 'abacaba')
    builder.singleton(A, A, y=Dep('y'))
    container = builder.build()
    container_copy = container.create_test_container().with_overridden_singleton(int, lambda: 2)

    inst = container.resolve(A)
    assert isinstance(inst, A)
    assert inst.x == 1
    assert inst.y == 'abacaba'

    copy_inst = container_copy.resolve(A)
    assert inst is not copy_inst
    assert isinstance(copy_inst, A)
    assert copy_inst.x == 2
    assert copy_inst.y == 'abacaba'


def test_raise_when_override_missing_dependency():
    builder = ContainerBuilder()
    container = builder.build()

    with pytest.raises(ContainerError):
        container.create_test_container().with_overridden_singleton(int, lambda: 1)


def test_invalid_argument():
    builder = ContainerBuilder()

    class A:
        def __init__(self, x: int):
            pass

    with pytest.raises(ValueError):
        builder.singleton(A, A, x=1, y=1)


def test_raise_when_register_already_existing_dependency():
    builder = ContainerBuilder()
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


def test_get_singature():
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


def test_get_container_as_dependency():
    class A:
        def __init__(self, x: Any):
            self.x = x

    class Settings:
        def __init__(self, mapping: Dict[str, Any]):
            self.mapping = mapping

    def make_a(container: Container, settings: Settings) -> A:
        return A(container.resolve(settings.mapping['key']))

    builder = ContainerBuilder()
    builder.singleton(int, lambda: 1)
    builder.singleton(Settings, lambda: Settings(mapping={'key': int}))
    builder.singleton(A, make_a)

    container = builder.build()
    a = container.resolve(A)
    assert a.x == 1


def test_container_as_dependency_in_test_container():
    class A:
        def __init__(self, x: int):
            self.x = x

    def make_a(container: Container) -> A:
        return A(container.resolve(int))

    builder = ContainerBuilder()
    builder.singleton(int, lambda: 1)
    builder.singleton(A, make_a)

    container = builder.build()
    test_container = container.create_test_container().with_overridden_singleton(int, lambda: 2)

    assert container.resolve(A).x == 1
    assert test_container.resolve(A).x == 2


def test_show_parent_for_missing():
    class A:
        def __init__(self, x: int):
            self.x = x

    class B:
        def __init__(self, value: A):
            self.value = value

    builder = ContainerBuilder()
    builder.singleton(B, B)
    with pytest.raises(
        ContainerError,
        match="No dependency of type <class 'tests.test_container.test_show_parent_for_missing.<locals>.A'> needed by "
        "<class 'tests.test_container.test_show_parent_for_missing.<locals>.B'>",
    ):
        builder.build()
