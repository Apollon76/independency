import inspect
from typing import Union, Type, Any, Callable, Dict, List

ObjType = Union[str, Type]


class ContainerError(Exception):
    pass


class Registration:
    def __init__(self, cls: ObjType, factory: Callable, is_singleton: bool, kwargs: Dict[str, Any]):
        self.cls = cls
        self.factory = factory
        self.is_singleton = is_singleton
        self.kwargs = kwargs


class Container:
    def __init__(self, registry: Dict[ObjType, Registration]):
        self._registry = registry
        self._resolved = {}

    def resolve(self, cls: ObjType) -> Any:
        if cls in self._resolved:
            return self._resolved[cls]
        try:
            current = self._registry[cls]
        except KeyError as e:
            raise ContainerError from e

        deps_to_resolve = self._get_deps(current)
        args = current.kwargs
        for key, d in deps_to_resolve.items():
            args[key] = self.resolve(d)
        result = current.factory(**args)
        if current.is_singleton:
            self._resolved[current.cls] = result
        return result

    def _get_deps(self, r: Registration) -> Dict[str, ObjType]:
        signature = inspect.signature(r.factory)
        result = {}
        for data in signature.parameters.values():
            if data.name in r.kwargs:
                continue
            result[data.name] = data.annotation
        return result


class ContainerBuilder:
    def __init__(self):
        self._registry = {}

    def build(self) -> Container:
        self._check()
        return Container(self._registry)

    def singleton(self, cls: ObjType, factory: Callable, **kwargs: Any) -> None:
        self.register(cls=cls, factory=factory, is_singleton=True, **kwargs)

    def register(self, cls: ObjType, factory: Callable, is_singleton: bool, **kwargs: Any) -> None:
        if cls in self._registry:
            raise ContainerError(f'Type {cls} is already registered')
        # TODO: check kwargs for factory
        self._registry[cls] = Registration(cls=cls, factory=factory, kwargs=kwargs, is_singleton=is_singleton)

    def _check(self) -> None:
        ...
