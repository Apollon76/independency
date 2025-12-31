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
_ContainerT = TypeVar('_ContainerT')
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
    try:
        return inspect.getfullargspec(f).args
    except TypeError as e:
        raise ContainerError(f'Unsupported callable {type(f)}') from e


def get_from_localns(cls: ObjType[Any], localns: Dict[str, Any]) -> Any:
    if isinstance(cls, type):
        return localns.get(cls.__name__, cls)
    if isinstance(cls, ForwardRef):  # type: ignore[unreachable]
        return localns.get(cls.__forward_arg__, cls)  # type: ignore[unreachable]
    return localns.get(cls, cls)


def get_deps(reg: Registration, localns: Dict[str, Any]) -> Dict[str, ObjType[Any]]:
    result: Dict[str, ObjType[Any]] = {
        name: value for name, value in get_signature(reg.factory, localns).items() if name not in reg.kwargs
    }
    for key, value in reg.kwargs.items():
        if isinstance(value, Dependency):
            result[key] = value.cls
    return result


def resolve_constants(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    result = {}
    for key, value in kwargs.items():
        if not isinstance(value, Dependency):
            result[key] = value
    return result


def validate_registration(cls: ObjType[Any], factory: Callable[..., Any], kwargs: Dict[str, Any]) -> None:
    if generic_params := getattr(cls, '__parameters__', None):
        raise ValueError(f'Specify generic parameters for {cls=}: {generic_params}')
    signature = get_arg_names(factory)
    for name in kwargs:
        if name not in signature:
            raise ValueError(f'No argument {name} for factory for type {cls}')


def update_localns(cls: ObjType[Any], localns: Dict[str, Any]) -> None:
    if isinstance(cls, type):
        localns[cls.__name__] = cls
    else:
        localns[cls] = cls


def builder_register(
    registry: Dict[ObjType[Any], Registration],
    localns: Dict[str, Any],
    cls: ObjType[Any],
    factory: Callable[..., Any],
    is_singleton: bool,
    **kwargs: Any,
) -> None:
    if cls in registry:
        raise ContainerError(f'Type {cls} is already registered')
    validate_registration(cls, factory, kwargs)
    registry[cls] = Registration(cls=cls, factory=factory, kwargs=kwargs, is_singleton=is_singleton)
    update_localns(cls, localns)


def check_resolution(  # noqa: C901
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
        check_resolution(value, resolved=resolved, resolving=resolving, registry=registry, localns=localns, parent=cls)
    resolving.remove(cls)
    resolved.add(cls)


def check_resolvable(registry: Dict[ObjType[Any], Registration], localns: Dict[str, Any]) -> None:
    resolved: Set[ObjType[Any]] = set()
    for cls in registry:
        check_resolution(cls, resolved, set(), registry=registry, localns=localns, parent=None)


PrepareResolveResult = tuple[Any, Optional[Registration], Dict[str, Any], Dict[str, ObjType[Any]]]


def prepare_resolve(
    cls: ObjType[Any],
    registry: Dict[ObjType[Any], Registration],
    resolved: Dict[ObjType[Any], Any],
    localns: Dict[str, Any],
) -> PrepareResolveResult:
    """Prepare arguments for resolving a dependency."""
    cls = get_from_localns(cls, localns)
    if cls in resolved:
        return cls, None, {}, {}

    try:
        current = registry[cls]
    except KeyError as e:
        raise ContainerError(f'No dependency of type {cls}') from e

    args = resolve_constants(current.kwargs)
    deps_to_resolve = get_deps(current, localns)
    return cls, current, args, deps_to_resolve


def finalize_resolve(current: Registration, result: Any, resolved: Dict[ObjType[Any], Any]) -> Any:  # noqa: C901
    """Finalize dependency resolution by caching if singleton."""
    if current.is_singleton:
        resolved[current.cls] = result
    return result


def create_overridden_container(
    original_registry: Dict[ObjType[Any], Registration],
    original_localns: Dict[str, Any],
    cls: ObjType[Any],
    factory: Callable[..., Any],
    is_singleton: bool,
    container_class: Type[Any],
    test_container_factory: Callable[[Dict[ObjType[Any], Registration], Dict[str, Any]], _ContainerT],
    **kwargs: Any,
) -> _ContainerT:
    if cls not in original_registry:
        raise ContainerError("Can not override class without any registration")
    validate_registration(cls, factory, kwargs)
    registry = copy.deepcopy(original_registry)
    localns = copy.deepcopy(original_localns)
    update_localns(cls, localns)
    registry[cls] = Registration(cls=cls, factory=factory, kwargs=kwargs, is_singleton=is_singleton)
    container = test_container_factory(registry, localns)
    registry[container_class] = Registration(container_class, factory=lambda: container, is_singleton=True, kwargs={})
    update_localns(container_class, localns)
    return container
