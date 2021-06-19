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
