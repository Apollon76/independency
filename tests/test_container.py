from di.container import ContainerBuilder


def test_container():
    class A:
        def __init__(self, x: int, y: str):
            self.x = x
            self.y = y

    builder = ContainerBuilder()
    builder.singleton(int, lambda: 1)
    builder.singleton(str, lambda: 'abacaba')
    builder.singleton(A, A)
    container = builder.build()
    inst = container.resolve(A)
    print(inst.x)
    print(inst.y)
