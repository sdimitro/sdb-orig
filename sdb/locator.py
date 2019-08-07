#
# Copyright 2019 Delphix
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import inspect

from typing import Iterable, TypeVar, Callable

import drgn
import sdb

#
# A Locator is a command that locates objects of a given type.  Subclasses
# declare that they produce a given outputType (the type being located), and
# they provide a method for each input type that they can search for objects
# of this type.  Additionally, many locators are also PrettyPrinters, and can
# pretty print the things they find. There is some logic here to support that
# workflow.
#


class Locator(sdb.Command):
    outputType: str = ""

    def __init__(self, prog: drgn.Program, args: str = "") -> None:
        super().__init__(prog, args)
        # We unset the inputType here so that the pipeline doesn't add a
        # coerce before us and ruin our ability to dispatch based on multiple
        # input types. For pure locators, and inputType wouldn't be set, but
        # hybrid Locators and PrettyPrinters will set an inputType so that
        # PrettyPrint can dispatch to them. By unsetting the inputType in the
        # instance, after registration is complete, PrettyPrint continues to
        # work, and the pipeline logic doesn't see an inputType to coerce to.
        self.inputType = None

    # subclass may override this
    def noInput(self) -> Iterable[drgn.Object]:
        raise TypeError('command "{}" requires and input'.format(self.cmdName))

    # Dispatch to the appropriate instance function based on the type of the
    # input we receive.
    def caller(self, input: Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        out_type = self.prog.type(self.outputType)
        hasInput = False
        for i in input:
            hasInput = True

            # try subclass-specified input types first, so that they can
            # override any other behavior
            try:
                for (name, method) in inspect.getmembers(self, inspect.ismethod):
                    if not hasattr(method, "input_typename_handled"):
                        continue

                    # Cache parsed type by setting an attribute on the
                    # function that this method is bound to (same place
                    # the input_typename_handled attribute is set).
                    # Unfortunately we can't do this in the decorator
                    # because the gdb types have not been set up yet.
                    if not hasattr(method, "input_type_handled"):
                        method.__func__.input_type_handled = self.prog.type(
                            method.input_typename_handled
                        )

                    if i.type_ == method.input_type_handled:
                        yield from method(i)
                        raise StopIteration
            except StopIteration:
                continue

            # try passthrough of output type
            # note, this may also be handled by subclass-specified input types
            if i.type_ == out_type:
                yield i
                continue

            # try walkers
            try:
                for o in Walk().call([i]):
                    yield drgn.cast(out_type, o)
                continue
            except TypeError:
                pass

            # error
            raise TypeError(
                'command "{}" does not handle input of type {}'.format(
                    self.cmdName, i.type_
                )
            )
        if not hasInput:
            yield from self.noInput()

    def call(self, input: Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        # If this is a hybrid locator/pretty printer, this is where that is
        # leveraged.
        if self.islast and isinstance(self, sdb.PrettyPrinter):
            self.pretty_print(self.caller(input))
        else:
            yield from self.caller(input)


T = TypeVar("T", bound=Locator)
IH = Callable[[T, drgn.Object], Iterable[drgn.Object]]


def InputHandler(typename: str) -> Callable[[IH[T]], IH[T]]:
    def decorator(func: IH[T]) -> IH[T]:
        func.input_typename_handled = typename  # type: ignore
        return func

    return decorator
