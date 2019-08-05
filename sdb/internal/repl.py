# -*- coding: utf-8 -*-
import readline

from sdb.command import SDBCommand


class REPL:
    """
    The class that provides the REPL for sdb. It is essentially a wrapper
    on top of readline and is the place where current and future
    enhancements in the interactivity of sdb should be placed (e.g.
    autocompletion, history, etc...).
    """

    @staticmethod
    def __make_completer(vocabulary):
        """
        Attribution:
        The following completer code came from Eli Berdensky's blog
        released under the public domain.
        """

        def custom_complete(text, state):
            # None is returned for the end of the completion session.
            results = [x for x in vocabulary if x.startswith(text)] + [None]
            # A space is added to the completion since the Python readline
            # doesn't do this on its own. When a word is fully completed we
            # want to mimic the default readline library behavior of adding
            # a space after it.
            return results[state] + " "

        return custom_complete

    def __init__(self, target, vocabulary, prompt="> ", closing=""):
        self.prompt = prompt
        self.closing = closing
        self.vocabulary = vocabulary
        self.target = target
        readline.parse_and_bind("tab: complete")
        readline.set_completer(REPL.__make_completer(vocabulary))

    def run(self):
        """
        Starts a REPL session.
        """
        while True:
            try:
                s = input(self.prompt).strip()
                if not s:
                    continue
                SDBCommand.invoke(self.target, s)
            except (EOFError, KeyboardInterrupt):
                print(self.closing)
                break
