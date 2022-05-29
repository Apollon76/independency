import copy
import dataclasses
import inspect
from typing import (
    Any,
    Callable,
    Dict,
    ForwardRef,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

_T = TypeVar('_T')
ObjType = Union[str, Type[_T]]


class ContainerError(Exception):
    pass


@dataclasses.dataclass
class Registration:
    cls: ObjType[Any]
    factory: Callable[..., Any]
    is_singleton: bool
    kwargs: Dict[str, Any]


@dataclasses.dataclass
class Dependency:
    cls: ObjType[Any]


def get_generic_mapping(cls: Any) -> Dict[TypeVar, Type[_T]]:
    origin = get_origin(cls)
    if origin is None:
        return {}
    return dict(zip(origin.__parameters__, get_args(cls)))


def resolve(t: Type[_T], mapping: Dict[Any, Type[Any]]) -> Type[_T]:
    if t in mapping:
        return cast(Type[_T], mapping[t])
    if get_origin(t) is None:
        return t
    resolved_args = [resolve(arg, mapping) for arg in get_args(t)]
    return get_origin(t)[tuple(resolved_args)]  # type: ignore


def get_signature(f: Callable[..., Any], localns: Dict[str, Any]) -> Dict[str, Type[Any]]:
    if get_origin(f) is not None:
        cls = get_origin(f)
        signature = get_signature(cls.__init__, localns=localns)  # type: ignore
        mapping = get_generic_mapping(f)  # type: ignore
        for key, value in signature.items():
            signature[key] = resolve(value, mapping)
        return signature
    if isinstance(f, type):
        return get_signature(f.__init__, localns)  # type: ignore
    if not callable(f):
        raise ContainerError(f'Can not use non-callable instance of  type {type(f)} as a factory')
    return {name: annotation for name, annotation in get_type_hints(f, localns=localns).items() if name != 'return'}


def get_arg_names(f: Callable[..., Any]) -> List[str]:
    if get_origin(f) is not None:
        cls = get_origin(f)
        return get_arg_names(cls.__init__)  # type: ignore
    if isinstance(f, type):
        return get_arg_names(f.__init__)  # type: ignore
    if not callable(f):
        raise ContainerError(f'Can not use non-callable instance of  type {type(f)} as a factory')
    return inspect.getfullargspec(f).args


def get_from_localns(cls: ObjType[Any], localns: Dict[str, Any]) -> Any:
    if isinstance(cls, type):
        return localns.get(cls.__name__, cls)
    if isinstance(cls, ForwardRef):
        return localns.get(cls.__forward_arg__, cls)
    return localns.get(cls, cls)


def get_deps(reg: Registration, localns: Dict[str, Any]) -> Dict[str, ObjType[Any]]:
    result: Dict[str, ObjType[Any]] = {
        name: value for name, value in get_signature(reg.factory, localns).items() if name not in reg.kwargs
    }
    for key, value in reg.kwargs.items():
        if isinstance(value, Dependency):
            result[key] = value.cls
    return result


def _resolve_constants(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    result = {}
    for key, value in kwargs.items():
        if not isinstance(value, Dependency):
            result[key] = value
    return result


def _validate_registration(cls: ObjType[Any], factory: Callable[..., Any], kwargs: Dict[str, Any]) -> None:
    if generic_params := getattr(cls, '__parameters__', None):
        raise ValueError(f'Specify generic parameters for {cls=}: {generic_params}')
    signature = get_arg_names(factory)
    for name in kwargs:
        if name not in signature:
            raise ValueError(f'No argument {name} for factory for type {cls}')


def _update_localns(cls: ObjType[Any], localns: Dict[str, Any]) -> None:
    if isinstance(cls, type):
        localns[cls.__name__] = cls
    else:
        localns[cls] = cls


class Container:  # pylint: disable=R0903
    __slots__ = ["_registry", "_localns", "_resolved"]

    def __init__(self, registry: Dict[ObjType[Any], Registration], localns: Dict[str, Any]):
        self._registry = registry
        self._localns = localns
        self._resolved: Dict[ObjType[Any], Any] = {}

    def resolve(self, cls: ObjType[Any]) -> Any:
        cls = get_from_localns(cls, self._localns)
        if cls in self._resolved:
            return self._resolved[cls]

        try:
            current = self._registry[cls]
        except KeyError as e:
            raise ContainerError(f'No dependency of type {cls}') from e

        args = _resolve_constants(current.kwargs)
        deps_to_resolve = get_deps(current, self._localns)
        for key, d in deps_to_resolve.items():
            args[key] = self.resolve(d)
        result = current.factory(**args)
        if current.is_singleton:
            self._resolved[current.cls] = result
        return result  # noqa: R504

    def create_test_container(self) -> 'TestContainer':
        registry = copy.deepcopy(self._registry)
        localns = copy.deepcopy(self._localns)
        test_container = TestContainer(registry=registry, localns=localns)
        registry[Container] = Registration(Container, factory=lambda: test_container, is_singleton=True, kwargs={})
        _update_localns(Container, localns)
        return test_container


class TestContainer(Container):
    def with_overridden(
        self, cls: ObjType[Any], factory: Callable[..., Any], is_singleton: bool, **kwargs: Any
    ) -> 'TestContainer':
        if cls not in self._registry:
            raise ContainerError("Can not override class without any registration")
        _validate_registration(cls, factory, kwargs)
        registry = copy.deepcopy(self._registry)
        localns = copy.deepcopy(self._localns)
        _update_localns(cls, localns)
        registry[cls] = Registration(cls=cls, factory=factory, kwargs=kwargs, is_singleton=is_singleton)
        container = TestContainer(registry, localns)
        registry[Container] = Registration(Container, factory=lambda: container, is_singleton=True, kwargs={})
        _update_localns(Container, localns)
        return container

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
        registry = self._registry.copy()
        localns = self._localns.copy()
        container = Container(registry=registry, localns=localns)
        registry[Container] = Registration(cls=Container, factory=lambda: container, kwargs={}, is_singleton=True)
        _update_localns(Container, localns)
        self._check_resolvable(registry, localns)
        return container

    def singleton(self, cls: ObjType[Any], factory: Callable[..., Any], **kwargs: Any) -> None:
        self.register(cls=cls, factory=factory, is_singleton=True, **kwargs)

    def register(self, cls: ObjType[Any], factory: Callable[..., Any], is_singleton: bool, **kwargs: Any) -> None:
        if cls in self._registry:
            raise ContainerError(f'Type {cls} is already registered')
        _validate_registration(cls, factory, kwargs)
        self._registry[cls] = Registration(cls=cls, factory=factory, kwargs=kwargs, is_singleton=is_singleton)
        _update_localns(cls, self._localns)

    def _check_resolvable(self, registry: Dict[ObjType[Any], Registration], localns: Dict[str, Any]) -> None:
        resolved: Set[ObjType[Any]] = set()
        for cls in registry:
            self._check_resolution(cls, resolved, set(), registry=registry, localns=localns, parent=None)

    def _check_resolution(
        self,
        cls: ObjType[Any],
        resolved: Set[ObjType[Any]],
        resolving: Set[ObjType[Any]],
        registry: Dict[ObjType[Any], Registration],
        localns: Dict[str, Any],
        parent: Optional[ObjType[Any]],
    ) -> None:
        cls = get_from_localns(cls, localns)
        if cls in resolved:
            return
        if cls in resolving:
            raise ContainerError(f'Cycle dependencies for type {cls}')
        resolving.add(cls)

        try:
            current = registry[cls]
        except KeyError as e:
            raise ContainerError(f'No dependency of type {cls} needed by {parent}') from e

        deps_to_resolve = get_deps(current, localns=localns)
        for value in deps_to_resolve.values():
            self._check_resolution(
                value, resolved=resolved, resolving=resolving, registry=registry, localns=localns, parent=cls
            )
        resolving.remove(cls)
        resolved.add(cls)
