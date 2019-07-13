import readline

class REPL(object):
    """
    XXX: High-level comment
    XXX: Point out that it kinda blows that the readline library
         enforces global state.
    """

    @staticmethod
    def __make_completer(vocabulary):
        """ XXX: proper attribution """
        def custom_complete(text, state):
            # None is returned for the end of the completion session.
            results = [x for x in vocabulary if x.startswith(text)] + [None]
            # A space is added to the completion since the Python readline doesn't
            # do this on its own. When a word is fully completed we want to mimic
            # the default readline library behavior of adding a space after it.
            return results[state] + " "
        return custom_complete

    def __init__(self, vocabulary, prompt='> ', closing = ''):
        self.prompt = prompt
        self.closing = closing
        self.vocabulary = vocabulary
        readline.parse_and_bind('tab: complete')
        readline.set_completer(REPL.__make_completer(vocabulary))

    def run(self):
        while True:
            try:
                s = input(self.prompt).strip()
                self.vocabulary[s].invoke("")
            except (EOFError, KeyboardInterrupt) as e:
                print(self.closing)
                break
            except KeyError as e:
                print('sdb: cannot recongnize command: {}'.format(s))

