import abc
from typing import TypeVar, Generic

from di.container import ContainerBuilder, Dependency as Dep


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


def test_generics():
    T = TypeVar('T')

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

    class C(Interface[B[T]]):
        def __init__(self, value: Interface[T]):
            self.value = value

        def f(self) -> Interface[T]:
            return self.value

    builder = ContainerBuilder()
    builder.singleton(Interface[int], A, x=1)
    builder.singleton(Interface[str], B[str], value='abacaba')
    builder.singleton(Interface[Interface[str]], C[str])
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
