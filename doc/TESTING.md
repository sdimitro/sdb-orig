# Testing your changes

The minimal testing that we ask from PRs until our testing infrastructure
is in place is the following:
* Ensure that no regressions are introduced on the test suite
* Try your best to not introduce more lint or checkstyle noise
* Introduce at least one test-case for new commands

The current tools that we use for the above are the following:

* [pytest](https://docs.pytest.org/en/latest/) for unit tests.
```
$ python3 -m pip install pytest
$ python3 -m pytest
```

* [yapf](https://github.com/google/yapf)
```
$ python3 -m pip install black
$ python3 -m black sdb
```

`pylint`, `mypy`, and `isort` are also used to some extend, but
are not required yet as there is still a lot of noise.
