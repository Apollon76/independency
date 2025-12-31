from typing import Any, Callable, Dict, Set

from .common import (
    ObjType,
    Registration,
    build_container,
    builder_register,
    create_overridden_container,
    create_test_container_copy,
    finalize_resolve,
    prepare_resolve,
)


class Container:  # pylint: disable=R0903
    __slots__ = ["_registry", "_localns", "_resolved"]

    def __init__(self, registry: Dict[ObjType[Any], Registration], localns: Dict[str, Any]):
        self._registry = registry
        self._localns = localns
        self._resolved: Dict[ObjType[Any], Any] = {}

    def get_registered_deps(self) -> Set[ObjType[Any]]:
        return set(self._registry.keys())

    def resolve(self, cls: ObjType[Any]) -> Any:
        cls, current, args, deps_to_resolve = prepare_resolve(cls, self._registry, self._resolved, self._localns)
        if current is None:
            return self._resolved[cls]

        for key, d in deps_to_resolve.items():
            args[key] = self.resolve(d)
        result = current.factory(**args)
        return finalize_resolve(current, result, self._resolved)

    def create_test_container(self) -> 'TestContainer':
        return create_test_container_copy(self._registry, self._localns, Container, TestContainer)


class TestContainer(Container):
    def with_overridden(
        self, cls: ObjType[Any], factory: Callable[..., Any], is_singleton: bool, **kwargs: Any
    ) -> 'TestContainer':
        return create_overridden_container(
            self._registry, self._localns, cls, factory, is_singleton, Container, TestContainer, **kwargs
        )

    def with_overridden_singleton(
        self, cls: ObjType[Any], factory: Callable[..., Any], **kwargs: Any
    ) -> 'TestContainer':
        return self.with_overridden(cls, factory, is_singleton=True, **kwargs)


class ContainerBuilder:
    __slots__ = ["_registry", "_localns"]

    def __init__(self) -> None:
        self._registry: Dict[ObjType[Any], Registration] = {}
        self._localns: Dict[str, Any] = {}

    def build(self) -> Container:
        return build_container(self._registry, self._localns, Container, Container)

    def singleton(self, cls: ObjType[Any], factory: Callable[..., Any], **kwargs: Any) -> None:
        self.register(cls=cls, factory=factory, is_singleton=True, **kwargs)

    def register(self, cls: ObjType[Any], factory: Callable[..., Any], is_singleton: bool, **kwargs: Any) -> None:
        builder_register(self._registry, self._localns, cls, factory, is_singleton, **kwargs)
