import dataclasses
from typing import Any, Callable, Dict, ForwardRef, Type, TypeVar, Union, cast, get_args, get_origin, get_type_hints

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


class Container:  # pylint: disable=R0903
    def __init__(self, registry: Dict[ObjType[Any], Registration], localns: Dict[str, Any]):
        self._registry = registry
        self._localns = localns
        self._resolved: Dict[ObjType[Any], Any] = {}

    def resolve(self, cls: ObjType[Any]) -> Any:
        if cls in self._resolved:
            return self._resolved[cls]

        cls = self._get_from_localns(cls)
        try:
            current = self._registry[cls]
        except KeyError as e:
            raise ContainerError(f'No dependency of type {cls}') from e

        deps_to_resolve = {
            name: value
            for name, value in get_signature(current.factory, self._localns).items()
            if name not in current.kwargs
        }
        args = self._resolve_kwargs(current.kwargs)
        for key, d in deps_to_resolve.items():
            args[key] = self.resolve(d)
        result = current.factory(**args)
        if current.is_singleton:
            self._resolved[current.cls] = result
        return result  # noqa: R504

    def _get_from_localns(self, cls: ObjType[Any]) -> Any:
        if isinstance(cls, type):
            return self._localns.get(cls.__name__, cls)
        if isinstance(cls, ForwardRef):
            return self._localns.get(cls.__forward_arg__, cls)
        return self._localns.get(cls, cls)

    def _resolve_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for key, value in kwargs.items():
            if not isinstance(value, Dependency):
                result[key] = value
                continue
            result[key] = self.resolve(value.cls)
        return result


class ContainerBuilder:
    def __init__(self) -> None:
        self._registry: Dict[ObjType[Any], Registration] = {}
        self._localns: Dict[str, Any] = {}

    def build(self) -> Container:
        self._check_resolvable()
        return Container(self._registry.copy(), self._localns.copy())

    def singleton(self, cls: ObjType[Any], factory: Callable[..., Any], **kwargs: Any) -> None:
        self.register(cls=cls, factory=factory, is_singleton=True, **kwargs)

    def register(self, cls: ObjType[Any], factory: Callable[..., Any], is_singleton: bool, **kwargs: Any) -> None:
        if generic_params := getattr(cls, '__parameters__', None):
            raise ValueError(f'Specify generic parameters for {cls=}: {generic_params}')
        if cls in self._registry:
            raise ContainerError(f'Type {cls} is already registered')
        try:
            signature = get_signature(factory, self._localns)
        except NameError as exc:
            raise ContainerError(*exc.args) from exc
        for name in kwargs:
            if name not in signature:
                raise ValueError(f'No argument {name} for factory for type {cls}')
        self._registry[cls] = Registration(cls=cls, factory=factory, kwargs=kwargs, is_singleton=is_singleton)
        self._update_localns(cls)

    def _check_resolvable(self) -> None:  # pylint: disable=R0201
        ...

    def _update_localns(self, cls: ObjType[Any]) -> None:
        if isinstance(cls, type):
            self._localns[cls.__name__] = cls
        else:
            self._localns[cls] = cls
