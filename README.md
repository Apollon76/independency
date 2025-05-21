<p align="center">
  <a href="https://github.com/ORGANIZATION/REPOSITORY/actions/workflows/linters-and-tests.yml">
    <img src="https://github.com/ORGANIZATION/REPOSITORY/actions/workflows/linters-and-tests.yml/badge.svg?branch=main" alt="GitHub Actions Workflow Status"/>
  </a>
  <a href="https://pypi.org/project/independency/">
    <img src="https://img.shields.io/pypi/v/independency.svg" alt="PyPI Version"/>
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"/>
  </a>
</p>

<p align="center">
<img src="img/logo.svg" alt="Independency" style="width: 70%; height: auto;"/>
</p>

Independency is a Python dependency injection (DI) container designed to help you manage dependencies in your applications effectively. Dependency injection is a powerful pattern for building loosely coupled, maintainable, and testable software. This library provides a clear and straightforward way to organize and inject dependencies, leading to cleaner code and improved application structure.

Key Features & Benefits:

*   **Local Scope Operation**: Unlike many DI containers that rely on global state, Independency operates within a local scope. This means you can have multiple, isolated container instances, each with its own distinct configuration. This approach avoids the pitfalls of global mutable state, enhances predictability, and is particularly useful in larger applications or microservices where different components might require different dependency setups.
*   **Inspired by punq**: If you're familiar with the [punq](https://github.com/bobthemighty/punq) library, you'll find Independency's API very similar and intuitive to use. This allows for a smooth learning curve for developers already acquainted with punq's concepts.
*   **Support for Generics and Specific Typings**: Independency fully embraces Python's type system, offering robust support for generics (e.g., `Storage[int]`) and other specific typings. This enables you to define and resolve dependencies with type safety and precision, making your dependency graph more explicit and easier to understand.
*   **Improved Code Quality**: By promoting separation of concerns and reducing hard-coded dependencies, Independency helps you write cleaner, more modular code.
*   **Enhanced Testability**: Dependency injection makes unit testing significantly easier. You can easily mock or substitute dependencies in your tests, allowing for isolated and focused testing of your components.
*   **Better Organization**: Centralizing dependency management with Independency leads to a more organized and maintainable codebase.


## Installation

```bash
pip install independency
```

## Usage
Independency avoids global state. You must explicitly create a container, typically at the entrypoint of your application:

```python3
import independency

builder = independency.ContainerBuilder()
# register application dependencies
container = builder.build()
obj: SomeRegisteredClass = container.resolve(SomeRegisteredClass)
```

### Registering Dependencies

```python3
builder.register(User, User)  # creates new object on each `resolve`
builder.singleton(User, User)  # creates object only once
builder.singleton(Storage[int], Storage[int])  # use generics
builder.singleton('special_storage', Storage[int])  # or string keys to register dependency
```

The second argument is a factory, so you can provide not only a class `__init__` function:

```python3
def create_db(config: Config) -> Database:
    return Database(config.dsn)

builder.singleton(Config, Config)
builder.singleton(Database, create_db)
```

If you need to pass some specific dependency as an argument to a factory, use `Dependency`:

```python3
from independency import Dependency as Dep

builder.singleton(SpecificConnection, SpecificConnection)
builder.singleton(Storage, conn=Dep(SpecificConnection))
```

## Examples
```python3
import requests

from independency import Container, ContainerBuilder


class Config:
    def __init__(self, url: str):
        self.url = url


class Getter:
    def __init__(self, config: Config):
        self.config = config

    def get(self):
        return requests.get(self.config.url)


def create_container() -> Container:
    builder = ContainerBuilder()
    builder.singleton(Config, Config, url='http://example.com')
    builder.singleton(Getter, Getter)
    return builder.build()


def main():
    container = create_container()
    getter: Getter = container.resolve(Getter)
    print(getter.get().status_code)


if __name__ == '__main__':
    main()
```

Suppose we need to declare multiple objects of the same type and use them correspondingly.

```python3
from independency import Container, ContainerBuilder, Dependency as Dep


class Queue:
    def __init__(self, url: str):
        self.url = url

    def pop(self):
        ...

    
class Consumer:
    def __init__(self, q: Queue):
        self.queue = q

    def consume(self):
        while True:
            message = self.queue.pop()
            # process message


def create_container() -> Container:
    builder = ContainerBuilder()
    builder.singleton('first_q', Queue, url='http://example.com')
    builder.singleton('second_q', Queue, url='http://example2.com')
    builder.singleton('c1', Consumer, q=Dep('first_q'))
    builder.singleton('c2', Consumer, q=Dep('second_q'))
    return builder.build()


def main():
    container = create_container()
    consumer: Consumer = container.resolve('c1')
    consumer.consume()


if __name__ == '__main__':
    main()
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

If you find a bug or have a feature request, please open an issue on GitHub. Pull requests are also welcome!
